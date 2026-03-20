"""Gemini Live API voice channel — real-time bidirectional audio via WebSocket."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import math
import os

import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)
router = APIRouter(tags=["voice"])

LIVE_MODEL = "models/gemini-2.5-flash-native-audio-latest"

SYSTEM_PROMPT = """You are Nexus AI, an intelligent multi-agent assistant.
You can search the web, check weather, and do calculations.
Always respond in the SAME language the user speaks (Chinese → Chinese, English → English).
Keep voice responses concise and natural — 1-3 sentences unless detail is requested."""


# ── Inline tools (mirror adk_agent tools so voice has same capabilities) ─────

def search_web(query: str) -> dict:
    """Search the web for current information on any topic.

    Args:
        query: The search query string.

    Returns:
        A dict with 'results' list or 'error'.
    """
    try:
        resp = httpx.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_redirect": "1", "no_html": "1"},
            timeout=10,
        )
        data = resp.json()
        results = []
        if data.get("AbstractText"):
            results.append({"title": data.get("Heading", query), "snippet": data["AbstractText"]})
        for r in data.get("RelatedTopics", [])[:4]:
            if isinstance(r, dict) and r.get("Text"):
                results.append({"snippet": r["Text"]})
        return {"results": results} if results else {"note": "No results found."}
    except Exception as e:
        return {"error": str(e)}


def get_weather(city: str = "Taipei") -> dict:
    """Get current weather conditions for a city.

    Args:
        city: City name, e.g. 'Taipei', 'Tokyo' (default: Taipei).

    Returns:
        A dict with temperature_c, humidity_pct, and condition.
    """
    try:
        geo = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": city, "format": "json", "limit": 1},
            headers={"User-Agent": "NexusAI/1.0"},
            timeout=5,
        ).json()
        if not geo:
            return {"error": f"City not found: {city}"}
        lat, lon = geo[0]["lat"], geo[0]["lon"]
        weather = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat, "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                "timezone": "auto",
            },
            timeout=5,
        ).json()
        current = weather.get("current", {})
        wmo = {0: "晴天", 1: "大致晴朗", 2: "多雲", 3: "陰天",
               45: "起霧", 61: "小雨", 63: "雨天", 80: "陣雨", 95: "雷雨"}
        code = current.get("weather_code", 0)
        return {
            "city": city,
            "temperature_c": current.get("temperature_2m"),
            "humidity_pct": current.get("relative_humidity_2m"),
            "wind_kmh": current.get("wind_speed_10m"),
            "condition": wmo.get(code, f"Code {code}"),
        }
    except Exception as e:
        return {"error": str(e)}


def compute(expression: str) -> dict:
    """Evaluate a mathematical expression.

    Args:
        expression: A math expression e.g. '2 + 2', 'sqrt(144)', 'sin(30)'.

    Returns:
        A dict with 'result' or 'error'.
    """
    allowed = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
    allowed.update({"abs": abs, "round": round, "min": min, "max": max, "pow": pow})
    try:
        result = eval(  # noqa: S307
            compile(expression, "<expr>", "eval"),
            {"__builtins__": None},
            allowed,
        )
        return {"expression": expression, "result": result}
    except Exception as e:
        return {"error": f"Cannot evaluate '{expression}': {e}"}


TOOLS = [search_web, get_weather, compute]


# ── WebSocket endpoint ────────────────────────────────────────────────────────

@router.websocket("/ws/voice")
async def voice_websocket(ws: WebSocket):
    """Real-time voice chat via Gemini Live API."""
    await ws.accept()
    logger.info("Voice WebSocket connected")

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        await ws.send_text(json.dumps({"type": "error", "data": "No Gemini API key configured"}))
        await ws.close()
        return

    client = genai.Client(api_key=api_key)
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=SYSTEM_PROMPT,
        tools=TOOLS,
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )

    try:
        async with client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
            await ws.send_text(json.dumps({"type": "status", "data": "connected"}))
            logger.info("Gemini Live session established")

            async def recv_from_browser():
                """Forward browser audio/text → Gemini."""
                try:
                    while True:
                        raw = await ws.receive_text()
                        msg = json.loads(raw)

                        if msg["type"] == "audio":
                            audio_bytes = base64.b64decode(msg["data"])
                            await session.send_realtime_input(
                                audio=types.Blob(data=audio_bytes, mime_type="audio/pcm;rate=16000")
                            )
                        elif msg["type"] == "text":
                            await session.send_client_content(
                                turns=types.Content(
                                    role="user",
                                    parts=[types.Part(text=msg["data"])]
                                ),
                                turn_complete=True,
                            )
                        elif msg["type"] == "end_of_turn":
                            await session.send_realtime_input(audio_stream_end=True)

                except WebSocketDisconnect:
                    pass
                except Exception as e:
                    logger.error(f"recv_from_browser error: {e}")

            # Map tool name → callable for function dispatch
            _tool_map = {fn.__name__: fn for fn in TOOLS}

            async def send_to_browser():
                """Forward Gemini responses → browser, handle tool calls."""
                try:
                    async for response in session.receive():
                        # Audio chunk
                        if response.data:
                            audio_b64 = base64.b64encode(response.data).decode()
                            await ws.send_text(json.dumps({"type": "audio", "data": audio_b64}))

                        # Tool call — execute locally and return result to Gemini
                        tc = getattr(response, "tool_call", None)
                        if tc and getattr(tc, "function_calls", None):
                            fn_responses = []
                            for fc in tc.function_calls:
                                fn = _tool_map.get(fc.name)
                                if fn:
                                    try:
                                        result = fn(**dict(fc.args))
                                    except Exception as e:
                                        result = {"error": str(e)}
                                else:
                                    result = {"error": f"Unknown tool: {fc.name}"}
                                logger.info(f"Tool call: {fc.name}({dict(fc.args)}) → {result}")
                                fn_responses.append(
                                    types.FunctionResponse(id=fc.id, name=fc.name, response=result)
                                )
                            await session.send_tool_response(function_responses=fn_responses)

                        # Input audio transcription (what the user said — for display)
                        sc = getattr(response, "server_content", None)
                        if sc:
                            it = getattr(sc, "input_transcription", None)
                            if it and getattr(it, "text", None):
                                await ws.send_text(json.dumps({"type": "user_text", "data": it.text}))

                            # Output audio transcription (text of what AI said)
                            ot = getattr(sc, "output_transcription", None)
                            if ot and getattr(ot, "text", None):
                                await ws.send_text(json.dumps({"type": "text", "data": ot.text}))

                            # Turn complete signal
                            if getattr(sc, "turn_complete", False):
                                await ws.send_text(json.dumps({"type": "turn_complete"}))

                except WebSocketDisconnect:
                    pass
                except Exception as e:
                    logger.error(f"send_to_browser error: {e}")

            await asyncio.gather(recv_from_browser(), send_to_browser())

    except WebSocketDisconnect:
        logger.info("Voice WebSocket disconnected")
    except Exception as e:
        logger.error(f"Voice WebSocket fatal error: {e}")
        try:
            await ws.send_text(json.dumps({"type": "error", "data": str(e)}))
        except Exception:
            pass
    finally:
        logger.info("Voice session closed")
