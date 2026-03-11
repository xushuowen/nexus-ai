"""Local LLM provider using llama-cpp-python for offline inference."""

from __future__ import annotations

import asyncio
import base64
import logging
import mimetypes
from pathlib import Path

logger = logging.getLogger(__name__)

# Lazy-loaded to avoid import errors if llama-cpp-python is not installed
_Llama = None
_LlavaHandler = None


def _load_llama_module():
    global _Llama
    if _Llama is None:
        try:
            from llama_cpp import Llama
            _Llama = Llama
        except ImportError:
            raise RuntimeError(
                "llama-cpp-python 未安裝。請執行：pip install llama-cpp-python"
            )
    return _Llama


def _load_llava_module():
    global _LlavaHandler
    if _LlavaHandler is None:
        try:
            from llama_cpp.llama_chat_format import Llava15ChatHandler
            _LlavaHandler = Llava15ChatHandler
        except ImportError:
            raise RuntimeError(
                "llama-cpp-python 未安裝或版本不支援多模態。請執行：pip install llama-cpp-python"
            )
    return _LlavaHandler


class LocalLLMProvider:
    """執行本地 GGUF 模型（Phi-3 Vision），完全離線，不呼叫任何外部服務。"""

    def __init__(
        self,
        model_path: str,
        mmproj_path: str = "",
        n_threads: int = 4,
        n_ctx: int = 4096,
    ) -> None:
        self.model_path = model_path
        self.mmproj_path = mmproj_path
        self.n_threads = n_threads
        self.n_ctx = n_ctx
        self._llm = None

    @property
    def is_available(self) -> bool:
        """檢查模型檔案是否存在。"""
        return Path(self.model_path).exists()

    @property
    def has_vision(self) -> bool:
        """檢查是否有視覺模型（mmproj）。"""
        return bool(self.mmproj_path) and Path(self.mmproj_path).exists()

    def _load_model(self):
        if self._llm is not None:
            return self._llm

        if not Path(self.model_path).exists():
            raise RuntimeError(
                f"本地模型檔案不存在：{self.model_path}\n"
                "請先下載 Phi-3 Vision GGUF 模型。\n"
                "下載指令：python -m nexus.tools.download_phi3"
            )

        Llama = _load_llama_module()

        kwargs: dict = dict(
            model_path=self.model_path,
            n_threads=self.n_threads,
            n_ctx=self.n_ctx,
            verbose=False,
        )

        # 若有 mmproj（視覺投影器），啟用多模態支援
        if self.has_vision:
            ChatHandler = _load_llava_module()
            kwargs["chat_handler"] = ChatHandler(
                clip_model_path=self.mmproj_path, verbose=False
            )
            logger.info("本地視覺模型（mmproj）已啟用")

        logger.info(
            "載入本地模型：%s（%d 執行緒）", self.model_path, self.n_threads
        )
        self._llm = Llama(**kwargs)
        logger.info("本地模型載入完成 ✓")
        return self._llm

    def _sync_complete(
        self,
        messages: list[dict],
        max_tokens: int,
        temperature: float,
    ) -> str:
        llm = self._load_model()
        response = llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response["choices"][0]["message"].get("content") or ""

    async def complete(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> str:
        """文字聊天補全（在執行緒中跑，不阻塞 asyncio 事件迴圈）。"""
        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        return await asyncio.to_thread(
            self._sync_complete, messages, max_tokens, temperature
        )

    async def complete_with_image(
        self,
        prompt: str,
        image_path: str,
        system_prompt: str = "",
        max_tokens: int = 512,
    ) -> str:
        """圖片分析補全（需要 mmproj 檔案）。"""
        if not self.has_vision:
            raise RuntimeError(
                "mmproj 檔案未設定或不存在，無法使用看圖功能。\n"
                "請確認 config.yaml 的 mmproj_path 設定正確。"
            )

        img_data = Path(image_path).read_bytes()
        b64 = base64.b64encode(img_data).decode()
        mime = mimetypes.guess_type(image_path)[0] or "image/jpeg"

        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                {"type": "text", "text": prompt},
            ],
        })

        return await asyncio.to_thread(
            self._sync_complete, messages, max_tokens, 0.7
        )
