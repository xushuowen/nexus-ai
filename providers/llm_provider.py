"""LLM provider with Google GenAI SDK (primary) and LiteLLM fallback."""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any, AsyncIterator

import litellm
from google import genai
from google.genai import types as genai_types

from nexus.core.budget import BudgetController, BudgetExhausted
from nexus.providers.model_config import ModelRouter, ModelSpec

logger = logging.getLogger(__name__)

# Suppress litellm's verbose logging
litellm.set_verbose = False

_GITHUB_API_BASE = "https://models.inference.ai.azure.com"

# Configure Google GenAI SDK client
_gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
_genai_client = genai.Client(api_key=_gemini_api_key) if _gemini_api_key else None


class LLMProvider:
    """Unified LLM interface with automatic budget enforcement."""

    def __init__(self, budget: BudgetController, router: ModelRouter) -> None:
        self.budget = budget
        self.router = router

    @staticmethod
    def _count_tokens(text: str) -> int:
        """Estimate token count with CJK-aware heuristic.

        Rules (approximate):
        - CJK characters (Chinese/Japanese/Korean): ~1 token each
        - English words: ~1.3 tokens each
        - Everything else (spaces, punctuation, numbers): ~0.3 tokens per char
        Much better than the old `split() * 2` which over-counted CJK severely.
        """
        cjk = len(re.findall(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7ff]", text))
        en_words = len(re.findall(r"[a-zA-Z]+", text))
        # remaining chars (spaces, digits, punctuation)
        other_chars = max(0, len(text) - cjk - sum(len(w) for w in re.findall(r"[a-zA-Z]+", text)))
        return max(1, int(cjk * 1.0 + en_words * 1.3 + other_chars * 0.3))

    @staticmethod
    def _is_gemini(spec: ModelSpec) -> bool:
        """Check if the model should use Google GenAI SDK directly."""
        return spec.model_id.startswith("gemini/") and not spec.api_base

    @staticmethod
    def _gemini_model_name(spec: ModelSpec) -> str:
        """Strip 'gemini/' prefix for Google GenAI SDK."""
        return spec.model_id.removeprefix("gemini/")

    async def _gemini_complete(
        self,
        spec: ModelSpec,
        messages: list[dict],
        max_tokens: int,
        temperature: float,
    ) -> str:
        """Call Gemini using the official Google GenAI SDK (google-genai)."""
        if not _genai_client:
            raise RuntimeError("GEMINI_API_KEY not set — cannot use Google GenAI SDK")

        model_name = self._gemini_model_name(spec)
        system_prompt = None
        user_parts = []

        for m in messages:
            if m["role"] == "system":
                system_prompt = m["content"]
            else:
                user_parts.append(m["content"])

        prompt = "\n".join(user_parts)

        config = genai_types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
            system_instruction=system_prompt,
        )

        response = await asyncio.to_thread(
            _genai_client.models.generate_content,
            model=model_name,
            contents=prompt,
            config=config,
        )
        if not response.candidates:
            logger.warning("Gemini returned no candidates (likely safety filtered)")
            return ""
        candidate = response.candidates[0]
        if candidate.content and candidate.content.parts:
            return "".join(p.text for p in candidate.content.parts if hasattr(p, "text"))
        return response.text or ""

    @staticmethod
    def _extra_kwargs(spec: ModelSpec) -> dict:
        """Return api_base / api_key kwargs for custom endpoints (e.g. GitHub Models)."""
        if not spec.api_base:
            return {}
        kwargs: dict = {"api_base": spec.api_base}
        if _GITHUB_API_BASE in spec.api_base:
            token = os.environ.get("GITHUB_TOKEN", "")
            if token:
                kwargs["api_key"] = token
        return kwargs

    async def complete(
        self,
        prompt: str,
        task_type: str = "general",
        model_spec: ModelSpec | None = None,
        source: str = "user",
        temperature: float | None = None,
        max_tokens: int | None = None,
        system_prompt: str | None = None,
        _depth: int = 0,
    ) -> str:
        """Send a completion request with budget checks."""
        spec = model_spec or self.router.route(task_type)
        tokens_est = self._count_tokens(prompt)
        mt = min(max_tokens or spec.max_tokens, self.budget.per_request_max)

        if not await self.budget.request_tokens(tokens_est + mt, source=source):
            raise BudgetExhausted(
                f"Daily budget exhausted. Used: {self.budget.tokens_used}/{self.budget.daily_limit}"
            )

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            if self._is_gemini(spec):
                # Use Google GenAI SDK for Gemini models
                logger.debug(f"Using Google GenAI SDK for {spec.model_id}")
                content = await self._gemini_complete(
                    spec=spec,
                    messages=messages,
                    max_tokens=mt,
                    temperature=temperature if temperature is not None else spec.temperature,
                )
            else:
                # Use LiteLLM for all other models
                response = await litellm.acompletion(
                    model=spec.model_id,
                    messages=messages,
                    max_tokens=mt,
                    temperature=temperature if temperature is not None else spec.temperature,
                    timeout=60,
                    **self._extra_kwargs(spec),
                )
                content = response.choices[0].message.content or ""

            total_tokens = tokens_est + self._count_tokens(content)
            await self.budget.consume_tokens(total_tokens, source=source, metadata={
                "model": spec.model_id,
                "task_type": task_type,
            })
            return content
        except BudgetExhausted:
            raise
        except Exception as e:
            logger.error(f"LLM call failed ({spec.model_id}): {e}")
            # Try fallback model (max one retry to prevent infinite recursion)
            fallback = self.router.get_fallback()
            if _depth < 1 and spec.model_id != fallback.model_id:
                # Skip fallback if it requires an API key that isn't set
                fallback_key_env = {
                    "groq": "GROQ_API_KEY",
                    "openai": "OPENAI_API_KEY",
                }.get(fallback.model_id.split("/")[0], "")
                if fallback_key_env and not os.environ.get(fallback_key_env):
                    logger.warning(f"Fallback model {fallback.model_id} skipped — {fallback_key_env} not set")
                    raise RuntimeError(f"AI 服務暫時無法使用，請稍後再試。(primary={spec.model_id})") from e
                logger.info("Trying fallback model...")
                return await self.complete(
                    prompt=prompt,
                    model_spec=fallback,
                    source=source,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    system_prompt=system_prompt,
                    _depth=_depth + 1,
                )
            raise

    async def stream(
        self,
        prompt: str,
        task_type: str = "general",
        model_spec: ModelSpec | None = None,
        source: str = "user",
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]:
        """Stream a completion response token by token."""
        spec = model_spec or self.router.route(task_type)
        tokens_est = self._count_tokens(prompt)
        mt = min(self.budget.per_request_max, spec.max_tokens)

        if not await self.budget.request_tokens(tokens_est + mt, source=source):
            raise BudgetExhausted("Daily budget exhausted.")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await litellm.acompletion(
                model=spec.model_id,
                messages=messages,
                max_tokens=mt,
                temperature=spec.temperature,
                stream=True,
                timeout=90,  # streaming can be longer; 90 s hard cap
                **self._extra_kwargs(spec),
            )
            total_tokens = tokens_est
            output_chars = 0
            async for chunk in response:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    output_chars += len(delta.content)
                    yield delta.content

            # Better output token estimate than counting chunks 1-by-1
            total_tokens += self._count_tokens(" " * output_chars)  # approx
            await self.budget.consume_tokens(total_tokens, source=source, metadata={
                "model": spec.model_id,
                "task_type": task_type,
                "streamed": True,
            })
        except BudgetExhausted:
            raise
        except Exception as e:
            logger.error(f"LLM stream failed: {e}")
            raise

    async def complete_chat(
        self,
        messages: list[dict[str, str]],
        task_type: str = "general",
        model_spec: ModelSpec | None = None,
        source: str = "user",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Send a chat completion with full message history."""
        spec = model_spec or self.router.route(task_type)
        tokens_est = sum(self._count_tokens(m.get("content", "")) for m in messages)
        mt = min(max_tokens or spec.max_tokens, self.budget.per_request_max)

        if not await self.budget.request_tokens(tokens_est + mt, source=source):
            raise BudgetExhausted(
                f"Daily budget exhausted. Used: {self.budget.tokens_used}/{self.budget.daily_limit}"
            )

        try:
            response = await litellm.acompletion(
                model=spec.model_id,
                messages=messages,
                max_tokens=mt,
                temperature=temperature if temperature is not None else spec.temperature,
                timeout=60,
                **self._extra_kwargs(spec),
            )
            content = response.choices[0].message.content or ""
            usage = response.usage
            total_tokens = (usage.total_tokens if usage else tokens_est + self._count_tokens(content))
            await self.budget.consume_tokens(total_tokens, source=source, metadata={
                "model": spec.model_id,
                "task_type": task_type,
            })
            return content
        except BudgetExhausted:
            raise
        except Exception as e:
            logger.error(f"LLM chat call failed ({spec.model_id}): {e}")
            fallback = self.router.get_fallback()
            if spec.model_id != fallback.model_id:
                fallback_key_env = {
                    "groq": "GROQ_API_KEY",
                    "openai": "OPENAI_API_KEY",
                }.get(fallback.model_id.split("/")[0], "")
                if fallback_key_env and not os.environ.get(fallback_key_env):
                    logger.warning(f"Fallback model {fallback.model_id} skipped — {fallback_key_env} not set")
                    raise RuntimeError(f"AI 服務暫時無法使用，請稍後再試。(primary={spec.model_id})") from e
                logger.info("Trying fallback model...")
                return await self.complete_chat(
                    messages=messages,
                    model_spec=fallback,
                    source=source,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            raise

    async def complete_with_image(
        self,
        prompt: str,
        image_path: str,
        system_prompt: str | None = None,
        source: str = "vision_agent",
    ) -> str:
        """Send a multimodal request with an image. Uses primary vision-capable model."""
        import base64
        import mimetypes
        from pathlib import Path

        data = Path(image_path).read_bytes()
        b64 = base64.b64encode(data).decode()
        mime = mimetypes.guess_type(image_path)[0] or "image/jpeg"

        # Route to vision-capable model (config.yaml: gemini-vision has use_for: ["vision"])
        spec = self.router.route("vision")
        tokens_est = self._count_tokens(prompt) + 300  # +300 for image encoding overhead
        mt = min(spec.max_tokens, self.budget.per_request_max)

        if not await self.budget.request_tokens(tokens_est + mt, source=source):
            raise BudgetExhausted("Daily budget exhausted.")

        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                {"type": "text", "text": prompt},
            ],
        })

        try:
            response = await litellm.acompletion(
                model=spec.model_id,
                messages=messages,
                max_tokens=mt,
                temperature=spec.temperature,
                timeout=90,  # vision models can be slower
                **self._extra_kwargs(spec),
            )
            content = response.choices[0].message.content or ""
            total = response.usage.total_tokens if response.usage else tokens_est + self._count_tokens(content)
            await self.budget.consume_tokens(total, source=source, metadata={
                "model": spec.model_id, "task_type": "vision",
            })
            return content
        except BudgetExhausted:
            raise
        except Exception as e:
            logger.error(f"Vision LLM call failed: {e}")
            raise

    async def simple_call(self, prompt: str, source: str = "system") -> str:
        """Quick call using primary model for internal tasks."""
        return await self.complete(prompt, task_type="simple_tasks", source=source)
