"""Image generation skill - generate detailed image prompts using LLM."""

from __future__ import annotations

import re
from typing import Any

from nexus.skills.skill_base import BaseSkill, SkillResult


class ImageGenSkill(BaseSkill):
    name = "image_gen"
    description = "圖片生成 — 用 AI 生成詳細圖片描述 prompt"
    triggers = ["畫", "draw", "生成圖片", "image", "generate image", "圖片", "插圖", "繪製"]
    intent_patterns = [
        r"(幫我|請).{0,5}(畫|生成|做|繪製).{0,20}(圖|插圖|圖片|圖像)",
        r"(我想要|想看|想要一張).{0,15}(圖|插畫|圖片|圖像)",
        r"(畫一張|生成一張|做一張).{0,20}",
    ]
    category = "creative"
    requires_llm = True

    instructions = "根據用戶描述，生成適合圖片生成模型使用的詳細 prompt。"

    async def execute(self, query: str, context: dict[str, Any]) -> SkillResult:
        llm = context.get("llm")
        if not llm:
            return SkillResult(content="LLM not available", success=False, source=self.name)

        # Clean query
        for t in self.triggers:
            query = re.sub(re.escape(t), "", query, flags=re.IGNORECASE)
        description = query.strip()

        if not description or len(description) < 2:
            return SkillResult(
                content="請描述你想要的圖片，例如：「畫一隻在月光下的貓」",
                success=False, source=self.name,
            )

        prompt = (
            "You are an expert image prompt engineer. "
            "Convert the user's description into a detailed, high-quality image generation prompt in English. "
            "Include: subject, style, lighting, mood, composition, colors, and technical details. "
            "Format as a single detailed paragraph suitable for Stable Diffusion or DALL-E.\n\n"
            f"User's request: {description}\n\n"
            "Generate the prompt:"
        )

        try:
            image_prompt = await llm.complete(prompt, task_type="simple_tasks", source="image_gen")

            result = (
                f"🎨 **圖片生成 Prompt**\n\n"
                f"📝 原始描述: {description}\n\n"
                f"🖼️ **生成的 Prompt:**\n```\n{image_prompt.strip()}\n```\n\n"
                f"💡 你可以將此 prompt 貼到以下工具使用：\n"
                f"- [Leonardo.ai](https://leonardo.ai/) (免費額度)\n"
                f"- [Playground AI](https://playgroundai.com/) (免費)\n"
                f"- [Bing Image Creator](https://www.bing.com/images/create) (免費)"
            )
            return SkillResult(content=result, success=True, source=self.name)

        except Exception as e:
            return SkillResult(content=f"Prompt 生成失敗: {e}", success=False, source=self.name)
