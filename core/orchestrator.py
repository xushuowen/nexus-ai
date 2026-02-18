"""Brain: Multi-path reasoning orchestrator with skill-first routing."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, AsyncIterator

from nexus import config
from nexus.core.agent_base import AgentMessage, AgentResult
from nexus.core.agent_registry import AgentRegistry
from nexus.core.budget import BudgetController
from nexus.core.three_stream import StreamEvent, ThreeStreamProcessor
from nexus.core.verifier import Verifier
from nexus.providers.llm_provider import LLMProvider
from nexus.providers.model_config import ModelRouter

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Nexus AI, an advanced multi-agent AI assistant system.

Core traits:
- You are helpful, accurate, and concise
- You respond in the SAME LANGUAGE the user writes in (Chinese → Chinese, English → English, etc.)
- You can handle coding, research, reasoning, file operations, web search, and more
- You remember conversation context and refer back to it naturally
- When uncertain, you say so honestly rather than making things up

Your personality:
- Professional but friendly
- Direct and clear, not verbose
- You use clean formatting when appropriate (bullet points, code blocks, etc.)

System info:
- You are running locally on the user's machine
- You have a daily token budget, so you are efficient with your responses
- You have 9 specialist agents and multiple skills that can be activated for complex tasks"""

# Keywords that suggest specialist agent routing is needed
SPECIALIST_TRIGGERS = {
    "coder": [
        "寫程式", "寫代碼", "code", "程式碼", "debug", "function", "class",
        "python", "javascript", "java", "寫一個", "實作", "implement",
        "bug", "error", "compile", "def ", "import ", "api",
    ],
    "research": [
        "搜尋", "search", "查一下", "找一下", "google", "最新", "新聞",
        "what is the latest", "look up", "find information",
    ],
    "reasoning": [
        "為什麼", "why", "分析", "analyze", "推理", "邏輯", "prove",
        "step by step", "calculate", "計算", "數學", "math",
    ],
    "file": [
        "檔案", "file", "讀取", "read file", "write file", "open",
        "目錄", "directory", "folder", "path",
    ],
    "shell": [
        "執行", "run command", "terminal", "命令", "shell", "bash",
        "pip install", "npm", "git",
    ],
    "web": [
        "網頁", "website", "url", "瀏覽", "browse", "scrape",
        "download", "http",
    ],
    "vision": [
        "圖片", "image", "照片", "photo", "screenshot", "看看這張",
        "OCR", "辨識", "recognize",
    ],
}


class Orchestrator:
    """Central brain: skill-first → specialist agents → direct chat."""

    def __init__(
        self,
        budget: BudgetController,
        llm: LLMProvider,
        router: ModelRouter,
        registry: AgentRegistry,
    ) -> None:
        self.budget = budget
        self.llm = llm
        self.router = router
        self.registry = registry
        self.verifier = Verifier(
            confidence_threshold=config.get("orchestrator.confidence_threshold", 0.7)
        )
        self.streams = ThreeStreamProcessor()
        self.max_hypotheses = config.get("orchestrator.max_parallel_hypotheses", 3)
        self._memory = None
        self._skill_loader = None
        self._event_callbacks: list = []

    def set_memory(self, memory) -> None:
        self._memory = memory

    def set_skill_loader(self, loader) -> None:
        self._skill_loader = loader

    def on_event(self, callback) -> None:
        self._event_callbacks.append(callback)

    async def _emit(self, event_type: str, content: str, **meta) -> None:
        event = StreamEvent(
            stream="orchestrator",
            event_type=event_type,
            content=content,
            metadata=meta,
        )
        await self.streams.emit(event)
        for cb in self._event_callbacks:
            try:
                await cb(event)
            except Exception:
                pass

    async def process(self, user_input: str, session_id: str = "default") -> AsyncIterator[StreamEvent]:
        """Process user input: skills → agents → chat, yielding events."""
        ts = time.strftime("%H:%M:%S")
        await self._emit("received", f"[{ts}] Received: {user_input[:80]}")

        # Step 1: Check budget
        if self.budget.is_exhausted:
            await self._emit("budget_exhausted", "Daily budget exhausted.")
            yield StreamEvent("orchestrator", "final_answer",
                              "今日的 API 額度已用完，請等待午夜自動重置。")
            return

        # Step 2: Save user message to session
        if self._memory:
            try:
                await self._memory.session.add_message(session_id, "user", user_input)
            except Exception as e:
                logger.warning(f"Session save error: {e}")

        # Step 3: Load conversation history
        history = []
        if self._memory:
            try:
                history = await self._memory.session.get_context_for_prompt(session_id, max_messages=16)
            except Exception as e:
                logger.warning(f"Session load error: {e}")

        # Step 4: Check skills first (Level 1 index match, 0 tokens)
        if self._skill_loader:
            skill = self._skill_loader.match(user_input)
            if skill:
                await self._emit("routing", f"[{ts}] Skill matched: {skill.name}")
                result = await self._skill_path(user_input, skill, session_id)
                yield StreamEvent("orchestrator", "final_answer", result.content)
                await self._post_process(user_input, result, session_id)
                status = self.budget.get_status()
                await self._emit("budget_status", json.dumps(status))
                return

        # Step 5: Check specialist agents (keyword match, 0 tokens)
        specialist = self._detect_specialist(user_input)
        if specialist:
            await self._emit("routing", f"[{ts}] Specialist detected: {specialist}")
            result = await self._specialist_path(user_input, specialist, history, session_id)
        else:
            await self._emit("routing", f"[{ts}] Direct chat mode")
            result = await self._chat_path(user_input, history, session_id)

        # Step 6: Yield final answer
        logger.info(f"Final answer: {len(result.content)} chars, confidence={result.confidence}")
        await self._emit("generating", f"[{ts}] Response ready")
        yield StreamEvent("orchestrator", "final_answer", result.content)

        await self._post_process(user_input, result, session_id)

        # Emit budget status
        status = self.budget.get_status()
        await self._emit("budget_status", json.dumps(status))

    async def _post_process(self, user_input: str, result: AgentResult, session_id: str) -> None:
        """Save response and remember interaction."""
        if self._memory:
            try:
                await self._memory.session.add_message(session_id, "assistant", result.content)
            except Exception as e:
                logger.warning(f"Session save error: {e}")
            asyncio.create_task(self._remember(user_input, result))

    async def _skill_path(self, user_input: str, skill, session_id: str) -> AgentResult:
        """Execute a skill directly."""
        await self._emit("routed", f"Skill: '{skill.name}' activated")

        context = {"llm": self.llm, "memory": self._memory, "session_id": session_id}
        result = await self._skill_loader.execute(skill, user_input, context)

        return AgentResult(
            content=result.content,
            confidence=0.9 if result.success else 0.3,
            source_agent=f"skill:{skill.name}",
            metadata=result.metadata,
        )

    def _detect_specialist(self, user_input: str) -> str | None:
        """Detect if a specialist agent is needed using keyword matching (0 tokens)."""
        text = user_input.lower()
        scores: dict[str, int] = {}
        for agent_name, keywords in SPECIALIST_TRIGGERS.items():
            count = sum(1 for kw in keywords if kw in text)
            if count >= 2:
                scores[agent_name] = count
            elif count == 1 and len(text.split()) <= 5:
                scores[agent_name] = count

        if not scores:
            return None
        return max(scores, key=scores.get)

    async def _chat_path(
        self, user_input: str, history: list[dict], session_id: str
    ) -> AgentResult:
        """Direct chat: send conversation history + new message to LLM."""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        memory_context = await self._get_memory_context(user_input)
        if memory_context:
            messages.append({
                "role": "system",
                "content": f"Relevant memories:\n{memory_context}",
            })

        for msg in history[:-1]:
            messages.append(msg)
        messages.append({"role": "user", "content": user_input})

        try:
            content = await self.llm.complete_chat(
                messages=messages, task_type="general", source="chat",
            )
            return AgentResult(content=content, confidence=0.8, source_agent="chat")
        except Exception as e:
            logger.error(f"Chat path error: {e}", exc_info=True)
            return AgentResult(content=f"抱歉，處理時發生錯誤: {e}", confidence=0.0, source_agent="error")

    async def _specialist_path(
        self, user_input: str, agent_name: str, history: list[dict], session_id: str
    ) -> AgentResult:
        """Route to a specialist agent with context."""
        await self._emit("routed", f"Complexity: specialist, Agents: ['{agent_name}']")

        agent = self.registry.get(agent_name)
        if not agent:
            logger.warning(f"Agent '{agent_name}' not found, falling back to chat")
            return await self._chat_path(user_input, history, session_id)

        memory_context = await self._get_memory_context(user_input)
        recent_history = ""
        if history:
            recent = history[-6:]
            parts = []
            for msg in recent:
                role = "User" if msg["role"] == "user" else "Assistant"
                parts.append(f"{role}: {msg['content'][:200]}")
            recent_history = "\n".join(parts)

        message = AgentMessage(role="user", content=user_input, sender="user")
        context = {
            "memory": memory_context,
            "history": recent_history,
            "session_id": session_id,
            "complexity": "moderate",
        }

        try:
            result = await agent.process(message, context)
            await self._emit("selected", f"Agent '{agent_name}' responded (confidence={result.confidence:.2f})")

            if result.confidence < 0.6:
                try:
                    vr = await self.verifier.verify(
                        user_input, result.content, self.llm.simple_call,
                    )
                    if not vr.passed and vr.suggestion:
                        result.content += f"\n\n(Note: {vr.suggestion})"
                    await self._emit("verified", f"Verification: confidence={vr.confidence:.2f}")
                except Exception:
                    pass

            return result
        except Exception as e:
            logger.error(f"Specialist '{agent_name}' failed: {e}", exc_info=True)
            return await self._chat_path(user_input, history, session_id)

    async def _get_memory_context(self, query: str) -> str:
        if not self._memory:
            return ""
        try:
            results = await self._memory.search(query, top_k=3)
            if results:
                parts = [r.get("content", "")[:200] for r in results if r.get("content")]
                if parts:
                    return "\n".join(f"- {p}" for p in parts)
        except Exception as e:
            logger.warning(f"Memory search error: {e}")
        return ""

    async def _remember(self, query: str, result: AgentResult) -> None:
        try:
            if self._memory:
                await self._memory.store_interaction(query, result.content, result.metadata)
                if result.confidence > 0.85:
                    await self._memory.store_procedural(query, result.content)
        except Exception as e:
            logger.warning(f"Memory store error: {e}")
