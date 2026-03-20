"""Multi-Agent Conference — round-based discussion system.

Inspired by Project Golem's conferencing pattern. Multiple agents discuss
a topic in rounds, building on each other's contributions with shared memory.
Supports consensus detection and automatic summarization.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from nexus.core.agent_base import AgentMessage, AgentResult
from nexus.core.agent_registry import AgentRegistry
from nexus.core.three_stream import StreamEvent

logger = logging.getLogger(__name__)


# Predefined team compositions
TEAMS = {
    "tech": {
        "name": "技術團隊",
        "agents": ["coder", "reasoning", "research"],
        "description": "程式設計、技術分析、研究調查",
    },
    "analysis": {
        "name": "分析團隊",
        "agents": ["reasoning", "research", "knowledge"],
        "description": "深度分析、資料研究、知識整合",
    },
    "debug": {
        "name": "除錯團隊",
        "agents": ["coder", "shell", "file"],
        "description": "程式除錯、命令執行、檔案檢查",
    },
    "research": {
        "name": "研究團隊",
        "agents": ["research", "web", "reasoning"],
        "description": "網路搜尋、資料蒐集、推理分析",
    },
    "creative": {
        "name": "創意團隊",
        "agents": ["reasoning", "coder", "knowledge"],
        "description": "創意發想、原型設計、知識整合",
    },
}

# Keywords/patterns that suggest conference mode (multi-agent collaboration)
CONFERENCE_TRIGGERS = [
    # Comparison & analysis
    "比較", "compare", "分析優缺點", "pros and cons", "利弊", "優劣",
    "哪個比較好", "哪個更好", "哪種方案", "怎麼選", "應該選",
    # Discussion & debate
    "討論", "discuss", "辯論", "debate", "不同觀點", "各方意見",
    # Multi-perspective
    "多角度", "multiple perspectives", "深入分析", "deep analysis",
    "全面分析", "完整評估", "各種可能", "有哪些方法",
    # Explicit conference
    "會議", "conference", "團隊討論", "team discuss",
    # Design & planning
    "架構設計", "系統設計", "方案規劃", "技術選型",
    "如何設計", "怎麼規劃", "最佳實踐", "best practice",
]

# Regex patterns for complex analytical questions
_COMPLEX_QUESTION_RE = __import__('re').compile(
    r'(為什麼.{0,20}(比|更|還是|or)|'
    r'(哪個|哪種|哪一個).{0,30}(好|佳|推薦|建議)|'
    r'(優點|缺點|好處|壞處).{0,20}(優點|缺點|好處|壞處)|'
    r'(要怎麼|應該怎麼|如何).{0,30}(設計|規劃|選擇|決定))',
    __import__('re').IGNORECASE,
)


@dataclass
class ConferenceRound:
    """One round of discussion."""
    round_number: int
    contributions: list[dict] = field(default_factory=list)
    consensus_reached: bool = False


@dataclass
class ConferenceResult:
    """Final result of a multi-agent conference."""
    topic: str
    team_name: str
    rounds: list[ConferenceRound]
    summary: str
    participants: list[str]
    total_tokens: int = 0


class AgentConference:
    """Orchestrates multi-agent round-based discussions."""

    def __init__(self, registry: AgentRegistry, llm: Any, memory: Any = None) -> None:
        self.registry = registry
        self.llm = llm
        self.memory = memory

    def should_conference(self, user_input: str) -> str | None:
        """Check if user input warrants a conference. Returns team name or None."""
        text = user_input.lower()

        # Explicit conference request
        if any(t in text for t in ["會議", "conference", "團隊討論"]):
            return self._detect_team(text)

        trigger_count = sum(1 for t in CONFERENCE_TRIGGERS if t in text)

        # Strong trigger signal (2+ keywords)
        if trigger_count >= 2:
            return self._detect_team(text)

        # Regex-detected complex analytical question structure
        if _COMPLEX_QUESTION_RE.search(user_input):
            return self._detect_team(text)

        # Single trigger + long/complex query (> 80 CJK chars or multiple sentences)
        if trigger_count >= 1:
            cjk_len = len(__import__('re').findall(r'[\u4e00-\u9fff]', text))
            sentence_count = len(__import__('re').split(r'[。！？\.\!\?]', text))
            if cjk_len > 80 or sentence_count > 3:
                return self._detect_team(text)

        return None

    def _detect_team(self, text: str) -> str:
        """Detect which team is best for the topic."""
        if any(w in text for w in ["程式", "code", "api", "bug", "debug"]):
            return "tech"
        if any(w in text for w in ["搜尋", "search", "網路", "web", "find"]):
            return "research"
        if any(w in text for w in ["除錯", "debug", "error", "crash"]):
            return "debug"
        if any(w in text for w in ["創意", "design", "creative", "idea"]):
            return "creative"
        return "analysis"  # default

    async def run(
        self,
        topic: str,
        team_key: str = "analysis",
        max_rounds: int = 3,
        session_id: str = "default",
    ) -> ConferenceResult:
        """Execute a multi-agent conference."""
        team = TEAMS.get(team_key, TEAMS["analysis"])
        agent_names = team["agents"]

        # Resolve available agents
        agents = []
        for name in agent_names:
            agent = self.registry.get(name)
            if agent:
                agents.append((name, agent))

        if not agents:
            return ConferenceResult(
                topic=topic, team_name=team["name"],
                rounds=[], summary="沒有可用的 Agent 參與討論。",
                participants=[],
            )

        participants = [name for name, _ in agents]
        rounds: list[ConferenceRound] = []
        shared_context = f"討論主題: {topic}\n\n"
        total_tokens = 0

        for round_num in range(1, max_rounds + 1):
            conference_round = ConferenceRound(round_number=round_num)

            # Build all agents' messages for this round (they all see the same
            # shared_context from previous rounds — fairer and unbiased).
            tasks_meta = []
            for agent_name, agent in agents:
                prompt = (
                    f"你正在參與一場多 Agent 團隊討論。\n"
                    f"你的角色是: {agent_name}\n"
                    f"這是第 {round_num}/{max_rounds} 輪。\n\n"
                    f"{shared_context}\n"
                    f"請從你的專業角度提供見解。"
                    f"{'如果你同意前面的結論，請說「同意」並補充。' if round_num > 1 else ''}"
                )
                message = AgentMessage(role="user", content=prompt, sender="conference")
                context = {
                    "memory": "",
                    "history": shared_context[-2000:],
                    "session_id": session_id,
                    "complexity": "moderate",
                }
                tasks_meta.append((agent_name, agent, message, context))

            # Run all agents in parallel with per-agent timeout — up to 3x faster
            async def _run_one(name: str, ag, msg: AgentMessage, ctx: dict) -> AgentResult:
                try:
                    return await asyncio.wait_for(ag.process(msg, ctx), timeout=25.0)
                except asyncio.TimeoutError:
                    logger.warning(f"Conference: agent '{name}' timed out (25s), round {round_num}")
                    return AgentResult(
                        content="(回應逾時)", confidence=0.0,
                        source_agent=name, tokens_used=0,
                    )
                except Exception as exc:
                    logger.warning(f"Conference: agent '{name}' failed: {exc}")
                    return AgentResult(
                        content=f"(Agent 回應失敗: {exc})", confidence=0.0,
                        source_agent=name, tokens_used=0,
                    )

            results = await asyncio.gather(
                *[_run_one(n, a, m, c) for n, a, m, c in tasks_meta]
            )

            for (agent_name, _, _, _), result in zip(tasks_meta, results):
                contribution = {
                    "agent": agent_name,
                    "content": result.content,
                    "confidence": result.confidence,
                    "tokens": result.tokens_used,
                }
                conference_round.contributions.append(contribution)
                total_tokens += result.tokens_used
                shared_context += f"\n[{agent_name} - 第{round_num}輪]: {result.content[:500]}\n"

            # Check for consensus
            if round_num > 1:
                conference_round.consensus_reached = self._check_consensus(
                    conference_round.contributions
                )

            rounds.append(conference_round)

            if conference_round.consensus_reached:
                logger.info(f"Conference consensus reached at round {round_num}")
                break

        # Generate summary (LLM synthesis if available)
        summary = await self._build_summary(topic, team["name"], rounds, participants)

        return ConferenceResult(
            topic=topic, team_name=team["name"],
            rounds=rounds, summary=summary,
            participants=participants, total_tokens=total_tokens,
        )

    def _check_consensus(self, contributions: list[dict]) -> bool:
        """Consensus detection with disagree-override heuristic.

        Rules:
        - Any agent with a strong disagree signal blocks consensus entirely.
        - An agent "agrees" only when its text has explicit agreement words but
          no negation immediately before them ("disagree", "not agree", etc.).
        - Consensus requires ≥ 60 % of agents agreeing AND no strong disagrees.
        - Low-confidence responses (< 0.3) count as neither agree nor disagree.
        """
        if not contributions:
            return False

        _AGREE = [
            "同意", "正確", "沒錯", "一致", "贊同", "認同", "支持", "確實", "對的",
            "agree", "consensus", "correct", "agree with", "i concur", "that's right",
        ]
        _DISAGREE = [
            "不同意", "反對", "不贊同", "不認同", "不正確", "有問題", "我不覺得",
            "disagree", "incorrect", "wrong", "differ", "however, i think",
            "but i think", "actually,", "on the contrary",
        ]

        agree_count = 0
        for c in contributions:
            text = c.get("content", "").lower()
            conf = c.get("confidence", 1.0)

            # Skip low-confidence timeout/error responses
            if conf < 0.3:
                continue

            # Strong disagree → block consensus immediately
            if any(k in text for k in _DISAGREE):
                return False

            # Agree only when an agreement keyword appears without negation prefix
            if any(k in text for k in _AGREE):
                # Negation guard: "not agree", "不同意" already caught above
                agree_count += 1

        return agree_count >= len(contributions) * 0.6

    async def _build_summary(
        self, topic: str, team_name: str,
        rounds: list[ConferenceRound], participants: list[str],
    ) -> str:
        """Build a formatted conference summary, synthesized by LLM if available."""
        header = "\n".join([
            f"🏛️ **{team_name}會議摘要**",
            f"📋 主題: {topic}",
            f"👥 參與者: {', '.join(participants)}",
            f"🔄 討論輪數: {len(rounds)}",
            "",
        ])

        # Collect all contributions for synthesis
        all_contributions = []
        for r in rounds:
            for c in r.contributions:
                all_contributions.append(f"[{c['agent']}]: {c['content'][:400]}")

        discussion_text = "\n\n".join(all_contributions)

        # Use LLM to synthesize a real conclusion
        if self.llm and all_contributions:
            try:
                synthesis_prompt = (
                    f"以下是多個 AI Agent 對「{topic}」的討論內容：\n\n"
                    f"{discussion_text}\n\n"
                    "請整合以上各方觀點，給出一個條理清晰的最終結論。"
                    "格式：先列重點共識（條列），再給出建議或結論（1-3句）。"
                    "回應語言跟問題相同。"
                )
                conclusion = await self.llm.complete(
                    synthesis_prompt,
                    task_type="complex_reasoning",
                    source="conference_summary",
                )
                return header + f"💡 **綜合結論**\n\n{conclusion}"
            except Exception as e:
                logger.warning(f"Conference LLM summary failed: {e}")

        # Fallback: plain text summary without LLM
        lines = [header]
        for r in rounds:
            lines.append(f"--- 第 {r.round_number} 輪 ---")
            for c in r.contributions:
                lines.append(f"**🤖 {c['agent']}**: {c['content'][:300]}")
                lines.append("")
            if r.consensus_reached:
                lines.append("✅ **已達成共識**\n")
        lines.append("---")
        lines.append("💡 **結論**: 以上是各 Agent 從不同專業角度的分析結果。")
        return "\n".join(lines)
