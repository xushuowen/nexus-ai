"""Image analysis tool - OpenClaw-style image understanding.
Uses multimodal LLM for image description, OCR, and analysis."""

from __future__ import annotations

import base64
import logging
from pathlib import Path

from nexus.tools.tool_base import BaseTool, ToolParameter, ToolResult

logger = logging.getLogger(__name__)


class ImageAnalysisTool(BaseTool):
    name = "image_analyze"
    description = "Analyze an image: describe, extract text (OCR), detect objects"
    category = "vision"
    parameters = [
        ToolParameter("image_path", "string", "Path to the image file", required=False),
        ToolParameter("image_base64", "string", "Base64-encoded image data", required=False),
        ToolParameter("prompt", "string", "What to analyze (e.g., 'describe', 'extract text', 'what objects')",
                       required=False, default="Describe this image in detail."),
    ]

    def __init__(self) -> None:
        self._llm = None

    def set_llm(self, llm) -> None:
        self._llm = llm

    async def execute(self, **kwargs) -> ToolResult:
        image_path = kwargs.get("image_path", "")
        image_b64 = kwargs.get("image_base64", "")
        prompt = kwargs.get("prompt", "Describe this image in detail.")

        # Get base64 image data
        if image_path:
            p = Path(image_path)
            if not p.exists():
                return ToolResult(success=False, output="", error=f"Image not found: {image_path}")
            image_b64 = base64.b64encode(p.read_bytes()).decode()

        if not image_b64:
            return ToolResult(success=False, output="", error="No image provided (need image_path or image_base64)")

        if not self._llm:
            return ToolResult(success=False, output="", error="LLM not connected for vision analysis")

        # Use Gemini's multimodal capability via LiteLLM
        try:
            import litellm
            response = await litellm.acompletion(
                model="gemini/gemini-2.0-flash-exp",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                    ],
                }],
                max_tokens=1000,
            )
            content = response.choices[0].message.content or ""
            return ToolResult(success=True, output=content)
        except Exception as e:
            logger.error(f"Image analysis error: {e}")
            return ToolResult(success=False, output="", error=str(e))
