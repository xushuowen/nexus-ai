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
from nexus.core.agent_conference import AgentConference
from nexus.core.titan_protocol import TitanProtocol, TitanResult
from nexus.providers.llm_provider import LLMProvider
from nexus.providers.model_config import ModelRouter

logger = logging.getLogger(__name__)

_BASE_SYSTEM_PROMPT = """你是 Nexus AI，一個在本機運行的先進多代理人 AI 助理系統。

語言規則（最優先遵守）:
- 使用者用繁體中文 → 你必須用繁體中文回應，使用台灣慣用語彙
- 使用者用英文 → 你用英文回應
- 混合語言 → 以使用者主要語言為準
- 絕對不要在中文回應中插入不必要的英文，除非是專有名詞或程式碼

核心能力:
- 程式開發（Python / JS / SQL / 爬蟲 / 自動化等）
- 研究調查（網路搜尋、資料整合、知識問答）
- 邏輯推理（分析、計算、比較、驗證）
- 檔案操作、Shell 命令執行
- 圖片辨識與分析

回應風格:
- 直接切入重點，不說廢話，不重複問題
- 清楚但不囉嗦；需要條列時才條列，不濫用格式
- 不確定就直說，不猜測、不捏造
- 語氣自然親切，如同一個懂技術的朋友

系統資訊:
- 本機執行，有每日 Token 預算，請精簡回應
- 擁有多個專門代理人（Coder / Research / Reasoning / Vision 等）和技能模組可調用"""

# Language detection patterns
_LANG_CJK_RE = __import__('re').compile(r'[\u4e00-\u9fff\u3040-\u30ff]')
_LANG_EN_RE  = __import__('re').compile(r'[a-zA-Z]{3,}')

# Keywords that suggest specialist agent routing is needed
SPECIALIST_TRIGGERS = {
    "coder": [
        "寫程式", "寫代碼", "code", "程式碼", "debug", "function", "class",
        "python", "javascript", "java", "寫一個", "實作", "implement",
        "bug", "error", "compile", "def ", "import ", "api",
        "做一個", "建立一個", "幫我寫", "程式", "腳本", "script",
        "算法", "algorithm", "資料結構", "html", "css", "sql",
        "爬蟲", "自動化", "for迴圈", "遞迴", "recursion",
        "幫我做", "幫我建", "寫個", "寫段",
    ],
    "research": [
        "搜尋", "search", "查一下", "找一下", "google", "最新", "新聞",
        "what is the latest", "look up", "find information",
        "有沒有", "查詢", "找找", "調查", "蒐集",
        "怎麼做到", "有研究說", "根據資料", "幫我找",
        "現在", "目前", "近期", "最近有",
    ],
    "reasoning": [
        "為什麼", "why", "分析", "analyze", "推理", "邏輯", "prove",
        "step by step", "calculate", "計算", "數學", "math",
        "比較", "差異", "差別", "優缺點", "pros and cons",
        "如果", "假設", "suppose", "應該選哪個", "哪個比較好",
        "推導", "驗證", "矛盾", "怎麼判斷", "分析一下",
        "哪個更", "利弊", "評估", "考量",
    ],
    "file": [
        "檔案", "file", "讀取", "read file", "write file", "open",
        "目錄", "directory", "folder", "path",
        "存到", "儲存", "保存", "建立檔案", "刪除檔案",
        "哪個資料夾", "副檔名", "打開這個", "找一下檔案",
    ],
    "shell": [
        "執行", "run command", "terminal", "命令", "shell", "bash",
        "pip install", "npm", "git",
        "安裝", "套件", "啟動服務", "程序", "process",
        "環境變數", "chmod", "管理員權限", "終端機",
    ],
    "web": [
        "網頁", "website", "url", "瀏覽", "browse", "scrape",
        "download", "http", "https://", "www.",
        "這個網站", "打開連結", "從網路下載", "抓取網頁",
    ],
    "vision": [
        "圖片", "image", "照片", "photo", "screenshot", "看看這張",
        "OCR", "辨識", "recognize",
        "這張圖", "圖中", "圖上", "截圖", "掃描文字",
        "看一下這個圖", "幫我看圖",
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
        self._conference = AgentConference(registry, llm, memory=None)
        self._event_callbacks: list = []
        self._request_count: int = 0  # for periodic working memory decay

    def set_memory(self, memory) -> None:
        self._memory = memory
        self._conference.memory = memory

    def set_skill_loader(self, loader) -> None:
        self._skill_loader = loader

    def _build_system_prompt(self, user_input: str = "") -> str:
        """Build system prompt with dynamic skill index injection."""
        prompt = _BASE_SYSTEM_PROMPT

        # Dynamic Skill Prompt injection (Golem Pattern 3)
        if self._skill_loader:
            skill_index = self._skill_loader.get_index_text()
            if skill_index:
                prompt += (
                    "\n\n可用技能（使用者可直接觸發）:\n"
                    + skill_index
                )

        # Inject language reinforcement based on detected user language
        if user_input:
            lang_hint = self._detect_language(user_input)
            if lang_hint:
                prompt += f"\n\n{lang_hint}"

        # Inject Titan Protocol format instructions
        prompt = TitanProtocol.inject_prompt(prompt)
        return prompt

    @staticmethod
    def _detect_language(text: str) -> str:
        """Return a language reinforcement hint based on detected script in text."""
        cjk = len(_LANG_CJK_RE.findall(text))
        eng = len(_LANG_EN_RE.findall(text))
        if cjk > eng:
            return "【重要】使用者使用繁體中文，請務必以流暢繁體中文回應。"
        if eng > cjk and eng >= 2:
            return "【Important】User is writing in English. Reply in English."
        return ""

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

    async def process(
        self,
        user_input: str,
        session_id: str = "default",
        extra_context: dict | None = None,
        force_agent: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
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
                history = await self._memory.session.get_context_for_prompt(session_id, max_messages=24)
            except Exception as e:
                logger.warning(f"Session load error: {e}")

        # Step 4: Check skills first (Level 1 index match, 0 tokens)
        # Skip skill matching if a specific agent is forced (e.g. vision with image upload)
        if self._skill_loader and not force_agent:
            skill = self._skill_loader.match(user_input)
            if skill:
                await self._emit("routing", f"[{ts}] Skill matched: {skill.name}")
                result = await self._skill_path(user_input, skill, session_id)
                yield StreamEvent("orchestrator", "final_answer", result.content)
                await self._post_process(user_input, result, session_id)
                status = self.budget.get_status()
                await self._emit("budget_status", json.dumps(status))
                return

        # Step 5: Check if conference mode is warranted
        team_key = self._conference.should_conference(user_input)
        if team_key:
            await self._emit("routing", f"[{ts}] Conference mode: team={team_key}")
            conf_result = await self._conference.run(
                topic=user_input, team_key=team_key, session_id=session_id,
            )
            yield StreamEvent("orchestrator", "final_answer", conf_result.summary)
            result = AgentResult(
                content=conf_result.summary, confidence=0.85,
                source_agent=f"conference:{team_key}",
                tokens_used=conf_result.total_tokens,
            )
            await self._post_process(user_input, result, session_id)
            status = self.budget.get_status()
            await self._emit("budget_status", json.dumps(status))
            return

        # Step 6: Check specialist agents (keyword match, 0 tokens)
        specialist = force_agent or self._detect_specialist(user_input)
        if specialist:
            await self._emit("routing", f"[{ts}] Specialist detected: {specialist}")
            result = await self._specialist_path(user_input, specialist, history, session_id, extra_context)
        else:
            await self._emit("routing", f"[{ts}] Direct chat mode")
            result = await self._chat_path(user_input, history, session_id)

        # Step 7: Yield final answer
        logger.info(f"Final answer: {len(result.content)} chars, confidence={result.confidence}")
        await self._emit("generating", f"[{ts}] Response ready")
        yield StreamEvent("orchestrator", "final_answer", result.content)

        await self._post_process(user_input, result, session_id)

        # Emit budget status
        status = self.budget.get_status()
        await self._emit("budget_status", json.dumps(status))

    async def _post_process(self, user_input: str, result: AgentResult, session_id: str) -> None:
        """Save response and remember interaction."""
        self._request_count += 1
        if self._memory:
            try:
                await self._memory.session.add_message(session_id, "assistant", result.content)
            except Exception as e:
                logger.warning(f"Session save error: {e}")
            asyncio.create_task(self._remember(user_input, result))
            # Periodically decay working memory attention weights (every 10 requests)
            if self._request_count % 10 == 0:
                try:
                    self._memory.working.decay_all()
                    logger.debug("Working memory decay applied")
                except Exception:
                    pass

    async def _skill_path(self, user_input: str, skill, session_id: str) -> AgentResult:
        """Execute a skill directly."""
        await self._emit("routed", f"Skill: '{skill.name}' activated")

        context = {
            "llm": self.llm, "memory": self._memory,
            "session_id": session_id, "skill_loader": self._skill_loader,
        }
        result = await self._skill_loader.execute(skill, user_input, context)

        return AgentResult(
            content=result.content,
            confidence=0.9 if result.success else 0.3,
            source_agent=f"skill:{skill.name}",
            metadata=result.metadata,
        )

    def _detect_specialist(self, user_input: str) -> str | None:
        """Detect specialist agent using length-weighted keyword scoring (0 tokens).

        Scoring: longer/more-specific keywords get higher weight (1 + len*0.08).
        Threshold scales with input length to reduce false positives on long texts.
        """
        import re
        text = user_input.lower()

        # CJK-aware approximate word count
        cjk_chars = len(re.findall(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7ff]', text))
        approx_words = max(len(text.split()), cjk_chars)

        # Explicit command prefix lowers the threshold (user clearly wants action)
        is_explicit_cmd = bool(re.search(
            r'^[\s]*(幫我|請你|請幫|麻煩|幫|寫一個|做一個|建立|查詢|搜尋|分析|找一下)',
            user_input,
        ))

        scores: dict[str, float] = {}
        for agent_name, keywords in SPECIALIST_TRIGGERS.items():
            total = 0.0
            for kw in keywords:
                if kw.lower() in text:
                    # Longer keywords are more specific → higher weight
                    total += 1.0 + len(kw) * 0.08

            if total == 0:
                continue

            # Adaptive minimum score: stricter for long inputs to avoid false routes
            if is_explicit_cmd or approx_words <= 6:
                min_score = 0.9     # single keyword enough for very short/command queries
            elif approx_words <= 14:
                min_score = 1.6
            else:
                min_score = 2.8    # long texts need stronger evidence

            if total >= min_score:
                scores[agent_name] = total

        if not scores:
            return None
        return max(scores, key=scores.get)

    async def _get_pyramid_context(self) -> str:
        """Retrieve long-term pyramid memory context."""
        if not self._memory:
            return ""
        try:
            return await self._memory.get_long_term_context()
        except Exception as e:
            logger.warning(f"Pyramid context error: {e}")
            return ""

    async def _chat_path(
        self, user_input: str, history: list[dict], session_id: str
    ) -> AgentResult:
        """Direct chat: send conversation history + new message to LLM."""
        system_prompt = self._build_system_prompt(user_input)
        messages = [{"role": "system", "content": system_prompt}]

        memory_context = await self._get_memory_context(user_input)
        if memory_context:
            messages.append({
                "role": "system",
                "content": f"Relevant memories:\n{memory_context}",
            })

        # Experience Memory injection (Golem Pattern 4)
        experience_context = await self._get_experience_context()
        if experience_context:
            messages.append({
                "role": "system",
                "content": f"User experience context:\n{experience_context}",
            })

        # Pyramid long-term memory injection
        pyramid_context = await self._get_pyramid_context()
        if pyramid_context:
            messages.append({
                "role": "system",
                "content": pyramid_context,
            })

        for msg in history:
            messages.append(msg)
        messages.append({"role": "user", "content": user_input})

        try:
            raw_content = await self.llm.complete_chat(
                messages=messages, task_type="general", source="chat",
            )

            # Titan Protocol: parse structured response
            titan = TitanProtocol.parse(raw_content)
            await self._process_titan_result(titan, session_id)

            return AgentResult(content=titan.reply, confidence=0.8, source_agent="chat")
        except Exception as e:
            logger.error(f"Chat path error: {e}", exc_info=True)
            return AgentResult(content="⚠️ 處理時發生錯誤，請稍後再試。", confidence=0.0, source_agent="error")

    async def _specialist_path(
        self, user_input: str, agent_name: str, history: list[dict],
        session_id: str, extra_context: dict | None = None,
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

        # Pyramid long-term memory context
        pyramid_context = await self._get_pyramid_context()

        message = AgentMessage(
            role="user", content=user_input, sender="user",
            metadata=extra_context or {},
        )
        context: dict = {
            "memory": memory_context,
            "history": recent_history,
            "session_id": session_id,
            "complexity": "moderate",
        }
        if pyramid_context:
            context["long_term_memory"] = pyramid_context
        if extra_context:
            context.update(extra_context)

        try:
            agent_timeout = 60.0 if agent_name == "vision" else 30.0
            result = await asyncio.wait_for(agent.process(message, context), timeout=agent_timeout)

            # Titan Protocol: parse agent response for memory extraction
            titan = TitanProtocol.parse(result.content)
            await self._process_titan_result(titan, session_id)
            result.content = titan.reply

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
        except asyncio.TimeoutError:
            logger.error(f"Specialist '{agent_name}' timed out (30s), falling back to chat")
            return await self._chat_path(user_input, history, session_id)
        except Exception as e:
            logger.error(f"Specialist '{agent_name}' failed: {e}", exc_info=True)
            return await self._chat_path(user_input, history, session_id)

    async def _process_titan_result(self, titan: TitanResult, session_id: str) -> None:
        """Process Titan Protocol memory and action sections."""
        # Store memories
        if titan.memory and self._memory:
            try:
                for line in titan.memory.split("\n"):
                    line = line.strip().lstrip("- ")
                    if line and len(line) > 3:
                        await self._memory.store_knowledge(
                            title=line[:100],
                            content=line,
                            category="titan_memory",
                        )
                        logger.debug(f"Titan memory stored: {line[:60]}")
            except Exception as e:
                logger.warning(f"Titan memory store error: {e}")

        # Process actions (extensible — currently logs them)
        for action in titan.actions:
            action_type = action.get("type", "unknown")
            logger.info(f"Titan action: {action_type} — {action}")

    async def _get_memory_context(self, query: str) -> str:
        if not self._memory:
            return ""
        # Cache in working memory to avoid repeated 5-layer searches for same query
        import hashlib
        cache_key = f"_mem:{hashlib.md5(query.encode()).hexdigest()}"
        cached = self._memory.working.retrieve(cache_key)
        if cached is not None:
            return cached
        try:
            results = await self._memory.search(query, top_k=3)
            if results:
                parts = [r.get("content", "")[:200] for r in results if r.get("content")]
                if parts:
                    context = "\n".join(f"- {p}" for p in parts)
                    self._memory.working.store(cache_key, context, attention=0.4)
                    return context
        except Exception as e:
            logger.warning(f"Memory search error: {e}")
        return ""

    async def _get_experience_context(self) -> str:
        """Get experience-based preferences for prompt injection."""
        if not self._memory:
            return ""
        try:
            return await self._memory.experience.inject_context()
        except Exception as e:
            logger.warning(f"Experience context error: {e}")
            return ""

    async def _remember(self, query: str, result: AgentResult) -> None:
        try:
            if self._memory:
                await self._memory.store_interaction(query, result.content, result.metadata)
                if result.confidence > 0.85:
                    await self._memory.store_procedural(query, result.content)
        except Exception as e:
            logger.warning(f"Memory store error: {e}")
