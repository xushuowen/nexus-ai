"""Vision / multimodal analysis specialist agent.

Strategy (方案 B):
  1. EasyOCR (local, free) — extract text from image
  2a. If meaningful text found (≥30 chars) → Groq text LLM for analysis
  2b. If little/no text (pure image, X-ray) → Gemini Vision API
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from nexus.core.agent_base import AgentCapability, AgentMessage, AgentResult, BaseAgent

logger = logging.getLogger(__name__)

VISION_SYSTEM = """你是醫療文件與影像分析專家。分析時：
1. 若收到的是文字（來自 OCR 提取），請整理並解讀重要醫療資訊
2. 若是圖片，描述主要內容、場景、重要細節
3. 若含有數值（ROM、MMT、VAS 等），特別標示
4. 若是 X 光，描述可見的骨骼結構與任何異常
5. 完整列出所有文字（若有）

回應語言跟用戶相同。"""

OCR_MIN_CHARS = 500  # 解剖圖/X光等醫學圖片直接走 Gemini Vision；只有大量文字才用 OCR

# Module-level OCR reader (lazy init, loaded once)
_ocr_reader = None
_ocr_lock = asyncio.Lock()


def warmup_ocr() -> None:
    """Pre-load EasyOCR model into memory. Call at startup to avoid cold-start delay."""
    global _ocr_reader
    if _ocr_reader is None:
        try:
            import easyocr
            _ocr_reader = easyocr.Reader(['ch_tra', 'en'], gpu=False, verbose=False)
            logger.info("EasyOCR model pre-loaded (warmup complete)")
        except Exception as e:
            logger.warning(f"EasyOCR warmup failed (will retry on first use): {e}")


def _run_ocr_sync(path: str) -> str:
    """Run EasyOCR synchronously (called in executor)."""
    global _ocr_reader
    if _ocr_reader is None:
        try:
            import easyocr
            _ocr_reader = easyocr.Reader(['ch_tra', 'en'], gpu=False, verbose=False)
        except ImportError:
            raise RuntimeError("EasyOCR not available — will fallback to Gemini Vision")
    results = _ocr_reader.readtext(path, detail=0, paragraph=True)
    return "\n".join(results)


async def _run_ocr(path: str) -> str:
    """Run EasyOCR in a thread pool to avoid blocking the event loop."""
    loop = asyncio.get_event_loop()
    try:
        text = await loop.run_in_executor(None, _run_ocr_sync, path)
        return text.strip()
    except Exception as e:
        logger.warning(f"EasyOCR failed: {e}")
        return ""


class VisionAgent(BaseAgent):
    name = "vision"
    description = "Image analysis, OCR, and visual content extraction"
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
                    "diagram", "chart", "ocr", "這張圖", "圖片", "照片", "截圖",
                    "病歷", "x光", "x-ray", "報告"]
        score += sum(0.1 for kw in keywords if kw in text)
        return min(1.0, score)

    async def process(self, message: AgentMessage, context: dict[str, Any]) -> AgentResult:
        image_path = message.metadata.get("image_path") or context.get("image_path")

        if not image_path:
            return AgentResult(
                content="請傳送圖片或截圖，我可以幫你分析病歷、X 光、報告單，或辨識圖片中的文字。",
                confidence=0.3,
                source_agent=self.name,
            )

        # Security: ensure path is within allowed uploads directory
        from pathlib import Path
        from nexus import config
        try:
            resolved = Path(image_path).resolve()
            if not resolved.is_file():
                raise ValueError("Not a valid file")
            # Must be inside data/ or /tmp/nexus_uploads
            allowed_roots = [
                config.data_dir().resolve(),
                Path("/tmp/nexus_uploads").resolve(),
            ]
            if not any(str(resolved).startswith(str(r)) for r in allowed_roots):
                raise ValueError("Path outside allowed directories")
        except Exception:
            return AgentResult(
                content="⚠️ 無效的圖片路徑。",
                confidence=0.0,
                source_agent=self.name,
            )

        return await self._analyze_image(str(resolved), message.content)

    async def _analyze_image(self, path: str, query: str) -> AgentResult:
        if not self._llm:
            return AgentResult(
                content="Vision agent 未連接 LLM。",
                confidence=0.0,
                source_agent=self.name,
            )

        user_query = query if query else "請分析這張圖片的內容。"

        # ── Step 1: Gemini Vision (fast, handles all image types) ──
        logger.info("Vision: using Gemini Vision API directly")
        if not hasattr(self._llm, "complete_with_image"):
            # Fallback: EasyOCR only if Gemini Vision unavailable
            logger.info("Vision: Gemini Vision not available, falling back to EasyOCR...")
            ocr_text = await _run_ocr(path)
            logger.info(f"Vision: OCR extracted {len(ocr_text)} chars")
            if ocr_text:
                prompt = (
                    f"以下是從圖片中 OCR 提取的文字內容：\n\n"
                    f"---\n{ocr_text}\n---\n\n"
                    f"請根據以上內容回答：{user_query}"
                )
                try:
                    response = await self._llm.complete(
                        prompt=prompt,
                        task_type="general",
                        system_prompt=VISION_SYSTEM,
                        source="vision_ocr",
                    )
                    return AgentResult(
                        content=response,
                        confidence=0.8,
                        source_agent=self.name,
                        reasoning_trace=[f"EasyOCR 提取文字 {len(ocr_text)} 字"],
                    )
                except Exception as e:
                    logger.error(f"Text LLM failed after OCR: {e}")
            return AgentResult(
                content="圖片分析失敗，LLM 不支援視覺功能且 OCR 無結果。",
                confidence=0.0,
                source_agent=self.name,
            )

        # ── Gemini Vision ────────────────────────────────────────
        logger.info("Vision: calling Gemini Vision...")
        try:
            response = await self._llm.complete_with_image(
                prompt=user_query,
                image_path=path,
                system_prompt=VISION_SYSTEM,
                source="vision_gemini",
            )
            return AgentResult(
                content=response,
                confidence=0.88,
                source_agent=self.name,
                reasoning_trace=["Gemini Vision 影像分析完成"],
            )
        except Exception as e:
            err = str(e)
            is_quota = "429" in err or "quota" in err.lower() or "rate" in err.lower()
            logger.warning(f"Gemini Vision failed ({type(e).__name__}), trying OCR fallback...")

        # ── OCR fallback (Gemini Vision quota/error) ─────────────
        logger.info("Vision: running EasyOCR fallback (20s timeout)...")
        try:
            ocr_text = await asyncio.wait_for(_run_ocr(path), timeout=20.0)
        except asyncio.TimeoutError:
            ocr_text = ""
            logger.warning("Vision: EasyOCR timed out in fallback")

        if ocr_text and len(ocr_text) >= 10:
            logger.info(f"Vision: OCR fallback extracted {len(ocr_text)} chars, using text LLM")
            prompt = (
                f"以下是從圖片中 OCR 提取的文字內容：\n\n"
                f"---\n{ocr_text}\n---\n\n"
                f"請根據以上內容回答：{user_query}"
            )
            try:
                # Bypass browser provider — use Groq directly (fast, no Gemini quota needed)
                groq_spec = self._llm.router.get_fallback()
                response = await self._llm.complete(
                    prompt=prompt,
                    model_spec=groq_spec,
                    system_prompt=VISION_SYSTEM,
                    source="vision_ocr_fallback",
                )
                return AgentResult(
                    content=response,
                    confidence=0.75,
                    source_agent=self.name,
                    reasoning_trace=[
                        f"Gemini Vision 不可用，OCR fallback 擷取 {len(ocr_text)} 字",
                        "文字 LLM 分析完成",
                    ],
                )
            except Exception as e2:
                logger.error(f"OCR fallback LLM also failed: {e2}")

        return AgentResult(
            content="⚠️ 圖片分析暫時不可用（Gemini Vision quota 已用完且圖片無可辨識文字）。若圖片含有文字，請直接貼上文字內容。",
            confidence=0.0,
            source_agent=self.name,
        )
