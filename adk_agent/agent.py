"""Nexus AI — Google Agent Development Kit (ADK) entry point.

Run locally:
    adk web adk_agent        # opens browser UI
    adk run adk_agent        # CLI interface

Requires:
    GOOGLE_API_KEY or GEMINI_API_KEY set in environment.
"""

from __future__ import annotations

import math
import os

import httpx
from google.adk.agents import Agent

# ADK uses GOOGLE_API_KEY; alias from GEMINI_API_KEY if needed
if not os.environ.get("GOOGLE_API_KEY") and os.environ.get("GEMINI_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]


# ── Tool definitions ──────────────────────────────────────────────────────────

def search_web(query: str) -> dict:
    """Search the web for current information on any topic.

    Args:
        query: The search query string.

    Returns:
        A dict with 'results' list (each has 'title' and 'snippet') or 'error'.
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
            results.append({
                "title": data.get("Heading", query),
                "snippet": data["AbstractText"],
                "url": data.get("AbstractURL", ""),
            })
        for r in data.get("RelatedTopics", [])[:4]:
            if isinstance(r, dict) and r.get("Text"):
                results.append({
                    "title": r.get("FirstURL", "").split("/")[-1].replace("_", " "),
                    "snippet": r["Text"],
                    "url": r.get("FirstURL", ""),
                })
        return {"results": results} if results else {"results": [], "note": "No results found. Try a different query."}
    except Exception as e:
        return {"error": str(e)}


def search_medical_papers(query: str, max_results: int = 5) -> dict:
    """Search PubMed for peer-reviewed medical and physical therapy research papers.

    Args:
        query: Medical topic or clinical question (e.g. 'rotator cuff tear rehabilitation').
        max_results: Number of papers to return (default 5, max 10).

    Returns:
        A dict with 'papers' list. Each paper has title, authors, year, and pubmed_url.
    """
    max_results = min(max_results, 10)
    try:
        search_resp = httpx.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params={"db": "pubmed", "term": query, "retmax": max_results, "retmode": "json"},
            timeout=10,
        )
        ids = search_resp.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return {"papers": [], "note": "No papers found. Try broader search terms."}

        fetch_resp = httpx.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
            params={"db": "pubmed", "id": ",".join(ids), "retmode": "json"},
            timeout=10,
        )
        summaries = fetch_resp.json().get("result", {})
        papers = []
        for pmid in ids:
            s = summaries.get(pmid, {})
            if not s:
                continue
            authors = ", ".join(a.get("name", "") for a in s.get("authors", [])[:3])
            if len(s.get("authors", [])) > 3:
                authors += " et al."
            papers.append({
                "title": s.get("title", ""),
                "authors": authors,
                "year": s.get("pubdate", "")[:4],
                "journal": s.get("source", ""),
                "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            })
        return {"papers": papers, "total_found": len(papers)}
    except Exception as e:
        return {"error": str(e)}


def compute(expression: str) -> dict:
    """Evaluate a mathematical or clinical calculation expression.

    Args:
        expression: A math expression such as '2 + 2', 'sqrt(144)', 'sin(30)', '180 / 3.14'.

    Returns:
        A dict with 'result' (the computed value) or 'error'.
    """
    allowed: dict = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
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


def get_weather(city: str = "Taipei") -> dict:
    """Get current weather conditions for a city.

    Args:
        city: City name, e.g. 'Taipei', 'Tokyo', 'New York' (default: Taipei).

    Returns:
        A dict with temperature_c, humidity_pct, and condition description.
    """
    try:
        geo = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": city, "format": "json", "limit": 1},
            headers={"User-Agent": "NexusAI/1.0 (student-assistant)"},
            timeout=5,
        ).json()
        if not geo:
            return {"error": f"City not found: {city}"}
        lat, lon = geo[0]["lat"], geo[0]["lon"]

        weather = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                "timezone": "auto",
            },
            timeout=5,
        ).json()
        current = weather.get("current", {})
        wmo_codes = {
            0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
            45: "Foggy", 48: "Freezing fog", 51: "Light drizzle", 53: "Drizzle",
            61: "Light rain", 63: "Rain", 71: "Light snow", 73: "Snow",
            80: "Showers", 95: "Thunderstorm",
        }
        code = current.get("weather_code", 0)
        return {
            "city": city,
            "temperature_c": current.get("temperature_2m"),
            "humidity_pct": current.get("relative_humidity_2m"),
            "wind_kmh": current.get("wind_speed_10m"),
            "condition": wmo_codes.get(code, f"Code {code}"),
        }
    except Exception as e:
        return {"error": str(e)}


# ── Root agent ────────────────────────────────────────────────────────────────

root_agent = Agent(
    name="nexus_ai",
    model="gemini-2.0-flash",
    description=(
        "Nexus AI — personal AI assistant for medical and physical therapy students. "
        "Supports web search, PubMed literature search, clinical calculations, and weather."
    ),
    instruction="""You are Nexus AI, an intelligent personal assistant built for medical and physical therapy students.

Your capabilities:
- Search the web for current medical guidelines, news, and general information
- Search PubMed for peer-reviewed research papers on any clinical topic
- Perform mathematical and clinical calculations (BMI, dosage, angles, etc.)
- Check current weather

How to behave:
- Always respond in the SAME LANGUAGE the user writes in (Chinese → Chinese, English → English)
- Be concise and clinically accurate
- When searching for papers, summarize key findings in plain language
- Always include PubMed URLs so the user can read the full paper
- If a question is outside your tools, answer from your own medical knowledge""",
    tools=[search_web, search_medical_papers, compute, get_weather],
)
