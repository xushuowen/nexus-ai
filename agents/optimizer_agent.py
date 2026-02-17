"""Self-optimization agent - analyzes and improves system performance."""

from __future__ import annotations

from typing import Any

from nexus.core.agent_base import AgentCapability, AgentMessage, AgentResult, BaseAgent


class OptimizerAgent(BaseAgent):
    name = "optimizer"
    description = "System performance analysis and self-optimization"
    capabilities = [AgentCapability.OPTIMIZATION]
    priority = 3

    def __init__(self) -> None:
        super().__init__()
        self._budget = None
        self._memory = None

    def set_dependencies(self, budget, memory) -> None:
        self._budget = budget
        self._memory = memory

    def can_handle(self, message: AgentMessage, context: dict[str, Any]) -> float:
        text = message.content.lower()
        keywords = ["optimize", "performance", "speed", "budget", "usage",
                     "statistics", "stats", "efficiency", "status"]
        return min(1.0, sum(0.2 for kw in keywords if kw in text))

    async def process(self, message: AgentMessage, context: dict[str, Any]) -> AgentResult:
        report_parts = ["**System Status Report**\n"]

        if self._budget:
            status = self._budget.get_status()
            report_parts.append(f"**Token Budget:**")
            report_parts.append(f"- Used: {status['tokens_used']:,} / {status['daily_limit']:,}")
            report_parts.append(f"- Remaining: {status['tokens_remaining']:,} ({(1-status['usage_ratio'])*100:.1f}%)")
            report_parts.append(f"- Requests today: {status['request_count']}")
            report_parts.append(f"- Curiosity ops remaining: {status['curiosity_ops_remaining']}")

        if self._memory:
            report_parts.append(f"\n**Memory:**")
            report_parts.append(f"- Working memory slots: {self._memory.working.size}")
            try:
                fts_count = await self._memory.fts.count()
                report_parts.append(f"- Knowledge entries: {fts_count}")
            except Exception:
                pass
            try:
                vec_count = await self._memory.vector.count()
                report_parts.append(f"- Vector entries: {vec_count}")
            except Exception:
                pass

        content = "\n".join(report_parts)
        return AgentResult(content=content, confidence=0.9, source_agent=self.name)
