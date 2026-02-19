"""Vision / multimodal analysis specialist agent — uses Gemini Vision API."""

from __future__ import annotations

from typing import Any

from nexus.core.agent_base import AgentCapability, AgentMessage, AgentResult, BaseAgent

VISION_SYSTEM = """你是視覺分析專家，能夠精確分析圖片內容。分析時：
1. 描述圖片的主要內容和場景
2. 注意重要細節（文字、數字、顏色、版面）
3. 若圖片含有文字，完整列出（OCR）
4. 回答用戶針對圖片的具體問題
5. 若是截圖、文件、表格，優先提取關鍵資訊

回應語言跟用戶相同。"""


class VisionAgent(BaseAgent):
    name = "vision"
    description = "Image analysis, OCR, and visual content extraction using Gemini Vision"
    capabilities = [AgentCapability.VISION]
    priority = 5

    def __init__(self) -> None:
        super().__init__()
        self._llm = None

    def set_llm(self, llm) -> None:
        self._llm = llm

    def can_handle(self, message: AgentMessage, context: dict[str, Any]) -> float:
        score = 0.0
        if message.metadata.get("has_image"):
            score += 0.8
        text = message.content.lower()
        keywords = ["image", "picture", "photo", "screenshot", "pdf",
                    "diagram", "chart", "ocr", "這張圖", "圖片", "照片", "截圖"]
        score += sum(0.1 for kw in keywords if kw in text)
        return min(1.0, score)

    async def process(self, message: AgentMessage, context: dict[str, Any]) -> AgentResult:
        image_path = message.metadata.get("image_path") or context.get("image_path")

        if not image_path:
            return AgentResult(
                content="請傳送圖片或截圖，我可以幫你分析內容、辨識文字（OCR）、解讀圖表。",
                confidence=0.3,
                source_agent=self.name,
            )

        return await self._analyze_image(image_path, message.content)

    async def _analyze_image(self, path: str, query: str) -> AgentResult:
        if not self._llm:
            return AgentResult(
                content="Vision agent 未連接 LLM。",
                confidence=0.0,
                source_agent=self.name,
            )

        # Check if the LLM supports multimodal
        if not hasattr(self._llm, "complete_with_image"):
            return AgentResult(
                content="目前的 LLM 不支援圖片分析。",
                confidence=0.0,
                source_agent=self.name,
            )

        try:
            user_prompt = query if query else "請描述這張圖片的內容。"
            response = await self._llm.complete_with_image(
                prompt=user_prompt,
                image_path=path,
                system_prompt=VISION_SYSTEM,
                source="vision_agent",
            )
            return AgentResult(
                content=response,
                confidence=0.88,
                source_agent=self.name,
                reasoning_trace=["Image loaded", "Gemini Vision analysis complete"],
            )
        except Exception as e:
            return AgentResult(
                content=f"圖片分析失敗：{e}",
                confidence=0.0,
                source_agent=self.name,
            )
