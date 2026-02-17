"""LiteLLM wrapper with budget checking for all LLM calls."""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator

import litellm

from nexus.core.budget import BudgetController, BudgetExhausted
from nexus.providers.model_config import ModelRouter, ModelSpec

logger = logging.getLogger(__name__)

# Suppress litellm's verbose logging
litellm.set_verbose = False


class LLMProvider:
    """Unified LLM interface with automatic budget enforcement."""

    def __init__(self, budget: BudgetController, router: ModelRouter) -> None:
        self.budget = budget
        self.router = router

    async def complete(
        self,
        prompt: str,
        task_type: str = "general",
        model_spec: ModelSpec | None = None,
        source: str = "user",
        temperature: float | None = None,
        max_tokens: int | None = None,
        system_prompt: str | None = None,
    ) -> str:
        """Send a completion request with budget checks."""
        spec = model_spec or self.router.route(task_type)
        tokens_est = len(prompt.split()) * 2  # rough estimate
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
            response = await litellm.acompletion(
                model=spec.model_id,
                messages=messages,
                max_tokens=mt,
                temperature=temperature if temperature is not None else spec.temperature,
            )
            content = response.choices[0].message.content or ""
            # Track actual usage
            usage = response.usage
            total_tokens = (usage.total_tokens if usage else tokens_est + len(content.split()))
            await self.budget.consume_tokens(total_tokens, source=source, metadata={
                "model": spec.model_id,
                "task_type": task_type,
            })
            return content
        except BudgetExhausted:
            raise
        except Exception as e:
            logger.error(f"LLM call failed ({spec.model_id}): {e}")
            # Try fallback model
            if spec.model_id != self.router.get_fallback().model_id:
                logger.info("Trying fallback model...")
                return await self.complete(
                    prompt=prompt,
                    model_spec=self.router.get_fallback(),
                    source=source,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    system_prompt=system_prompt,
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
        tokens_est = len(prompt.split()) * 2
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
            )
            total_tokens = tokens_est
            async for chunk in response:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    total_tokens += 1
                    yield delta.content

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
        tokens_est = sum(len(m.get("content", "").split()) for m in messages) * 2
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
            )
            content = response.choices[0].message.content or ""
            usage = response.usage
            total_tokens = (usage.total_tokens if usage else tokens_est + len(content.split()))
            await self.budget.consume_tokens(total_tokens, source=source, metadata={
                "model": spec.model_id,
                "task_type": task_type,
            })
            return content
        except BudgetExhausted:
            raise
        except Exception as e:
            logger.error(f"LLM chat call failed ({spec.model_id}): {e}")
            if spec.model_id != self.router.get_fallback().model_id:
                logger.info("Trying fallback model...")
                return await self.complete_chat(
                    messages=messages,
                    model_spec=self.router.get_fallback(),
                    source=source,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            raise

    async def simple_call(self, prompt: str, source: str = "system") -> str:
        """Quick call using primary model for internal tasks."""
        return await self.complete(prompt, task_type="simple_tasks", source=source)
