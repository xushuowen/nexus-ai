"""Chain-of-thought reasoning agent with self-verification."""

from __future__ import annotations

from typing import Any

from nexus.core.agent_base import AgentCapability, AgentMessage, AgentResult, BaseAgent

COT_SYSTEM = """你是邏輯推理與分析專家。面對複雜問題：
1. 釐清核心問題（去掉無關假設）
2. 列出已知條件和前提
3. 逐步推導，每步說明理由
4. 給出結論，附上信心程度（高/中/低）和原因
5. 若存在多種可能，列出並評估各自可能性

比較類問題：用表格或條列對比，最後給建議
數學計算：逐步列式，不跳步驟
回應語言跟用戶相同。"""

VERIFY_SYSTEM = """你是邏輯審查員。針對以下推理內容，找出潛在問題：
- 邏輯跳躍（前提到結論之間缺少步驟）
- 未考慮的反例或邊界情況
- 錯誤的假設
- 數字計算錯誤

請簡潔列出問題（每項一行）。若推理完全正確則只回覆「推理無誤」。"""

REVISE_SYSTEM = """你是邏輯修訂專家。
根據原始問題、初步推理和審查意見，給出修正後的最終完整答案。
保持原本的格式風格，但修正所有審查指出的問題。
回應語言跟用戶相同。"""

# Queries longer than this threshold get the full 2-step verification
_VERIFY_THRESHOLD = 35  # characters


class ReasoningAgent(BaseAgent):
    name = "reasoning"
    description = "Chain-of-thought reasoning with multi-step self-verification"
    capabilities = [AgentCapability.REASONING]
    priority = 7

    def __init__(self) -> None:
        super().__init__()
        self._llm = None

    def set_llm(self, llm) -> None:
        self._llm = llm

    def can_handle(self, message: AgentMessage, context: dict[str, Any]) -> float:
        text = message.content.lower()
        keywords = [
            "why", "how", "reason", "logic", "analyze", "think", "solve",
            "prove", "calculate", "if then", "therefore", "because",
            "step by step", "break down", "figure out",
        ]
        score = sum(0.12 for kw in keywords if kw in text)
        if context.get("complexity") == "complex":
            score += 0.2
        return min(1.0, score)

    async def process(self, message: AgentMessage, context: dict[str, Any]) -> AgentResult:
        if not self._llm:
            return AgentResult(
                content="Reasoning agent not connected.", confidence=0.0, source_agent=self.name
            )

        memory_ctx = context.get("memory", "")
        base_prompt = message.content
        if memory_ctx:
            base_prompt = f"Context:\n{memory_ctx}\n\nProblem:\n{message.content}"

        # ── Step 1: initial chain-of-thought reasoning ────────────────
        reasoning = await self._llm.complete(
            base_prompt,
            task_type="complex_reasoning",
            source="reasoning_agent",
            system_prompt=COT_SYSTEM,
        )
        trace = ["Chain-of-thought reasoning"]

        is_complex = len(message.content) >= _VERIFY_THRESHOLD

        if is_complex:
            # ── Step 2: self-verification critique ────────────────────
            verify_prompt = (
                f"原始問題：{message.content}\n\n"
                f"推理過程：\n{reasoning}"
            )
            critique = await self._llm.complete(
                verify_prompt,
                task_type="complex_reasoning",
                source="reasoning_agent",
                system_prompt=VERIFY_SYSTEM,
            )
            trace.append("Self-verification critique")

            # ── Step 3: revise only if real issues were found ─────────
            no_issues = "無誤" in critique or len(critique.strip()) < 15
            if not no_issues:
                revise_prompt = (
                    f"問題：{message.content}\n\n"
                    f"初步推理：\n{reasoning}\n\n"
                    f"審查意見：\n{critique}\n\n"
                    "請給出修正後的最終完整答案。"
                )
                final = await self._llm.complete(
                    revise_prompt,
                    task_type="complex_reasoning",
                    source="reasoning_agent",
                    system_prompt=REVISE_SYSTEM,
                )
                trace.append("Revised based on critique")
            else:
                final = reasoning
                trace.append("Verification passed: no revision needed")
        else:
            final = reasoning

        # ── Confidence from content ────────────────────────────────────
        confidence = 0.78
        final_lower = final.lower()
        if "高信心" in final or "high confidence" in final_lower:
            confidence = 0.92
        elif "不確定" in final or "uncertain" in final_lower or "低信心" in final:
            confidence = 0.55

        return AgentResult(
            content=final,
            confidence=confidence,
            source_agent=self.name,
            reasoning_trace=trace,
        )
