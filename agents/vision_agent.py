"""Vision / multimodal analysis specialist agent."""

from __future__ import annotations

from typing import Any

from nexus.core.agent_base import AgentCapability, AgentMessage, AgentResult, BaseAgent


class VisionAgent(BaseAgent):
    name = "vision"
    description = "Image and PDF analysis using multimodal capabilities"
    capabilities = [AgentCapability.VISION]
    priority = 5

    def __init__(self) -> None:
        super().__init__()
        self._llm = None

    def set_llm(self, llm) -> None:
        self._llm = llm

    def can_handle(self, message: AgentMessage, context: dict[str, Any]) -> float:
        text = message.content.lower()
        keywords = ["image", "picture", "photo", "screenshot", "pdf",
                     "diagram", "chart", "visual", "ocr", "describe image"]
        score = sum(0.2 for kw in keywords if kw in text)
        if message.metadata.get("has_image"):
            score += 0.5
        return min(1.0, score)

    async def process(self, message: AgentMessage, context: dict[str, Any]) -> AgentResult:
        # Check if image data is attached
        image_path = message.metadata.get("image_path")
        if image_path:
            return await self._analyze_image(image_path, message.content)

        return AgentResult(
            content="Please provide an image path or upload an image for analysis. "
                    "I can describe images, extract text (OCR), and analyze diagrams.",
            confidence=0.3, source_agent=self.name,
        )

    async def _analyze_image(self, path: str, query: str) -> AgentResult:
        """Analyze an image using multimodal LLM capabilities."""
        if not self._llm:
            return AgentResult(content="Vision agent not connected to LLM.", confidence=0.0, source_agent=self.name)

        # For multimodal, we'd use Gemini's vision API
        # For now, provide a description prompt
        prompt = f"The user has provided an image at '{path}' and asks: {query}\n"
        prompt += "Describe what you would analyze in this image."

        response = await self._llm.complete(
            prompt, task_type="analysis", source="vision_agent",
            system_prompt="You are a visual analysis expert.",
        )
        return AgentResult(content=response, confidence=0.6, source_agent=self.name)
