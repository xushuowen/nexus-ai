"""Browser-in-the-Loop Gemini provider using Playwright to control Google AI Studio."""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING

from nexus import config

logger = logging.getLogger(__name__)

_AISTUDIO_URL = "https://aistudio.google.com/prompts/new_chat"

# Use system Chrome to avoid Google's bot detection
_CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Users\Xushu\AppData\Local\Google\Chrome\Application\chrome.exe",
]


def _find_chrome() -> str | None:
    for p in _CHROME_PATHS:
        if Path(p).exists():
            return p
    return None
_RESP_START_TAG = "[NEXUS_RESP_START]"
_RESP_END_TAG = "[NEXUS_RESP_END]"
_SYSTEM_INSTRUCTION = (
    "Always wrap your response content between "
    "[NEXUS_RESP_START] and [NEXUS_RESP_END] tags"
)

# Default selector candidates (tried in order until one works)
_INPUT_SELECTORS = [
    "ms-text-chunk .ql-editor",
    "[placeholder='Type something']",
    "textarea",
]
_SEND_SELECTORS = [
    "button[aria-label='Run']",
    "button[mattooltip='Run']",
    "run-button button",
]
_RESPONSE_SELECTORS = [
    "ms-chat-turn:last-of-type .model-response-text",
    "[data-message-author-role='model']:last-child",
    ".response-container:last-child",
]

_MAX_RETRIES = 3
_RESPONSE_POLL_INTERVAL = 0.5   # seconds between polls for response completion
_RESPONSE_TIMEOUT = 120.0       # max seconds to wait for a complete response


class GeminiBrowserProvider:
    """Controls Google AI Studio via Playwright to use Gemini without API key."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._playwright = None
        self._browser = None
        self._page = None
        self._initialized = False
        self._system_injected = False

        # Paths
        base_dir = config.base_dir()
        data_dir = config.data_dir()
        self._profile_dir = str(data_dir / "gemini_profile")
        self._selectors_file = data_dir / "gemini_selectors.json"

        # Selector cache (populated from file or defaults)
        self._selectors: dict[str, str] = self._load_selectors()

    # ──────────────────────────────────────────────
    # Public properties
    # ──────────────────────────────────────────────

    @property
    def is_available(self) -> bool:
        """Returns True if playwright package is importable."""
        try:
            import playwright  # noqa: F401
            return True
        except ImportError:
            return False

    # ──────────────────────────────────────────────
    # Selector cache helpers
    # ──────────────────────────────────────────────

    def _load_selectors(self) -> dict[str, str]:
        """Load cached selectors from disk, fall back to first defaults."""
        defaults = {
            "input": _INPUT_SELECTORS[0],
            "send": _SEND_SELECTORS[0],
            "response": _RESPONSE_SELECTORS[0],
        }
        if self._selectors_file.exists():
            try:
                data = json.loads(self._selectors_file.read_text(encoding="utf-8"))
                defaults.update(data)
                logger.debug("Loaded selector cache from %s", self._selectors_file)
            except Exception as e:
                logger.warning("Could not load selector cache: %s", e)
        return defaults

    def _save_selectors(self) -> None:
        """Persist current selector cache to disk."""
        try:
            self._selectors_file.write_text(
                json.dumps(self._selectors, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning("Could not save selector cache: %s", e)

    # ──────────────────────────────────────────────
    # Browser lifecycle
    # ──────────────────────────────────────────────

    async def _ensure_browser(self) -> None:
        """Lazily initialise browser via CDP (launch Chrome normally, connect via remote debug port)."""
        if self._initialized:
            return

        from playwright.async_api import async_playwright

        chrome_path = _find_chrome()
        if not chrome_path:
            raise RuntimeError("Chrome not found. Install Chrome or set CHROME_PATH.")

        Path(self._profile_dir).mkdir(parents=True, exist_ok=True)
        logger.info("GeminiBrowserProvider: launching Chrome via CDP (port 9222)…")

        # Launch Chrome normally (no Playwright control = no bot detection banner)
        self._chrome_proc = subprocess.Popen([
            chrome_path,
            f"--user-data-dir={self._profile_dir}",
            "--remote-debugging-port=9222",
            "--no-first-run",
            "--no-default-browser-check",
            "--window-position=-32000,-32000",
            _AISTUDIO_URL,
        ])

        # Wait for Chrome to be ready
        await asyncio.sleep(4)

        # Connect Playwright to the running Chrome via CDP
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.connect_over_cdp("http://localhost:9222")

        contexts = self._browser.contexts
        pages = contexts[0].pages if contexts else []
        self._page = pages[0] if pages else await contexts[0].new_page()

        # Navigate to AI Studio if not already there
        if _AISTUDIO_URL not in self._page.url:
            await self._page.goto(_AISTUDIO_URL, wait_until="domcontentloaded", timeout=30_000)
        await asyncio.sleep(2)

        await self._inject_system_instruction()
        self._initialized = True
        logger.info("GeminiBrowserProvider: connected via CDP, ready")

    async def _inject_system_instruction(self) -> None:
        """Type the system instruction into AI Studio's system prompt field if present."""
        if self._system_injected:
            return
        try:
            # AI Studio has a "System instructions" expandable panel
            sys_panel = self._page.locator("ms-system-prompt, [aria-label*='system'], .system-instructions")
            if await sys_panel.count() > 0:
                await sys_panel.first.click(timeout=3_000)
                await asyncio.sleep(0.5)

            sys_input = self._page.locator(
                "ms-system-prompt textarea, [placeholder*='system'], .system-prompt-input"
            )
            if await sys_input.count() > 0:
                await sys_input.first.fill(_SYSTEM_INSTRUCTION)
                logger.info("GeminiBrowserProvider: system instruction injected")
                self._system_injected = True
                return
        except Exception as e:
            logger.debug("System instruction injection skipped: %s", e)
        # Mark as done even if panel not found — we'll rely on prepending to prompt
        self._system_injected = True

    async def setup(self) -> None:
        """Open browser for manual login (headless=False, one-time setup).

        Call this once from CLI: `python -m nexus.providers.gemini_browser_provider`
        User must log in manually, then close the window.
        """
        from playwright.async_api import async_playwright

        Path(self._profile_dir).mkdir(parents=True, exist_ok=True)
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch_persistent_context(
            user_data_dir=self._profile_dir,
            headless=False,
        )
        pages = browser.pages
        page = pages[0] if pages else await browser.new_page()
        await page.goto("https://accounts.google.com/", wait_until="domcontentloaded")
        logger.info(
            "GeminiBrowserProvider setup: browser opened. "
            "Please log in to Google, then close the browser window."
        )
        # Wait until user closes browser
        try:
            await browser.wait_for_event("close", timeout=300_000)
        except Exception:
            pass
        await playwright.stop()
        logger.info("GeminiBrowserProvider setup: profile saved.")

    async def reset_chat(self) -> None:
        """Navigate to a fresh AI Studio chat."""
        async with self._lock:
            if self._page:
                try:
                    await self._page.goto(
                        _AISTUDIO_URL, wait_until="domcontentloaded", timeout=20_000
                    )
                    await asyncio.sleep(1.5)
                    self._system_injected = False
                    await self._inject_system_instruction()
                    logger.info("GeminiBrowserProvider: chat reset")
                except Exception as e:
                    logger.warning("reset_chat failed: %s", e)

    async def close(self) -> None:
        """Gracefully close browser and Playwright."""
        try:
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.warning("GeminiBrowserProvider close error: %s", e)
        finally:
            # Also terminate the Chrome subprocess
            chrome_proc = getattr(self, "_chrome_proc", None)
            if chrome_proc:
                try:
                    chrome_proc.terminate()
                except Exception:
                    pass
            self._browser = None
            self._page = None
            self._playwright = None
            self._initialized = False

    # ──────────────────────────────────────────────
    # Self-healing selector resolution
    # ──────────────────────────────────────────────

    async def _find_selector(self, role: str, candidates: list[str]) -> str:
        """Try each candidate in order; return first visible one and cache it."""
        cached = self._selectors.get(role)
        if cached:
            try:
                loc = self._page.locator(cached)
                if await loc.count() > 0 and await loc.first.is_visible(timeout=2_000):
                    return cached
            except Exception:
                pass
            logger.debug("Cached selector '%s' for role '%s' failed, trying alternates", cached, role)

        for sel in candidates:
            try:
                loc = self._page.locator(sel)
                if await loc.count() > 0 and await loc.first.is_visible(timeout=2_000):
                    if self._selectors.get(role) != sel:
                        self._selectors[role] = sel
                        self._save_selectors()
                        logger.info("Selector healed: role=%s selector=%s", role, sel)
                    return sel
            except Exception:
                continue

        raise RuntimeError(
            f"No working selector found for role '{role}'. Tried: {candidates}"
        )

    # ──────────────────────────────────────────────
    # Core completion
    # ──────────────────────────────────────────────

    async def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str:
        """Type prompt into AI Studio, run it, and return the response text.

        Args:
            prompt: The user prompt to send.
            system_prompt: If given, prepended to the prompt text.

        Returns:
            The model's response text.
        """
        if not self.is_available:
            raise RuntimeError("playwright is not installed — run: pip install playwright && playwright install chromium")

        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        last_error: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                return await self._do_complete(full_prompt)
            except Exception as e:
                last_error = e
                wait = 2 ** attempt
                logger.warning(
                    "GeminiBrowserProvider attempt %d/%d failed: %s — retrying in %ds",
                    attempt + 1, _MAX_RETRIES, e, wait,
                )
                await asyncio.sleep(wait)
                # Re-initialize browser on repeated failures
                if attempt >= 1:
                    try:
                        await self.close()
                    except Exception:
                        pass
                    self._initialized = False
                    self._system_injected = False

        raise RuntimeError(
            f"GeminiBrowserProvider: all {_MAX_RETRIES} attempts failed"
        ) from last_error

    async def _do_complete(self, full_prompt: str) -> str:
        """Single attempt at completing a prompt (called by retry wrapper)."""
        async with self._lock:
            await self._ensure_browser()

            # ── Find and fill input ──
            input_sel = await self._find_selector("input", _INPUT_SELECTORS)
            input_loc = self._page.locator(input_sel).first
            await input_loc.click(timeout=5_000)
            await input_loc.fill("", timeout=3_000)   # clear
            await asyncio.sleep(0.2)

            # Type in chunks to avoid losing characters in quick-type
            chunk_size = 200
            for i in range(0, len(full_prompt), chunk_size):
                await input_loc.type(full_prompt[i : i + chunk_size], delay=10)
            await asyncio.sleep(0.3)

            # ── Click Run ──
            send_sel = await self._find_selector("send", _SEND_SELECTORS)
            send_loc = self._page.locator(send_sel).first
            await send_loc.click(timeout=5_000)
            logger.debug("GeminiBrowserProvider: prompt sent, waiting for response…")

            # ── Wait for response with [NEXUS_RESP_END] tag ──
            return await self._wait_for_response()

    async def _wait_for_response(self) -> str:
        """Poll until the response contains the end tag (or timeout)."""
        deadline = time.monotonic() + _RESPONSE_TIMEOUT
        resp_sel = await self._find_selector("response", _RESPONSE_SELECTORS)

        while time.monotonic() < deadline:
            await asyncio.sleep(_RESPONSE_POLL_INTERVAL)
            try:
                loc = self._page.locator(resp_sel).last
                if await loc.count() == 0:
                    continue
                text = await loc.inner_text(timeout=3_000)
                if _RESP_END_TAG in text:
                    return self._extract_response(text)
                # Check for common "generating" indicators
                is_generating = await self._page.locator(
                    ".loading-indicator, [aria-label*='loading'], .spinner"
                ).count()
                if not is_generating and text.strip():
                    # Model might have responded but without the tags
                    # Give it a couple more seconds then fall back
                    await asyncio.sleep(2)
                    text = await loc.inner_text(timeout=3_000)
                    if _RESP_END_TAG in text:
                        return self._extract_response(text)
                    if text.strip():
                        logger.warning(
                            "GeminiBrowserProvider: response missing tags, using plain text"
                        )
                        return text.strip()
            except Exception as e:
                logger.debug("Response poll error (will retry): %s", e)

        raise TimeoutError(
            f"GeminiBrowserProvider: no response within {_RESPONSE_TIMEOUT}s"
        )

    @staticmethod
    def _extract_response(text: str) -> str:
        """Extract content between tags, fall back to full text."""
        start_idx = text.find(_RESP_START_TAG)
        end_idx = text.find(_RESP_END_TAG)
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            content = text[start_idx + len(_RESP_START_TAG) : end_idx].strip()
            if content:
                return content
        # Fallback: strip the tags themselves and return the rest
        cleaned = (
            text.replace(_RESP_START_TAG, "")
                .replace(_RESP_END_TAG, "")
                .strip()
        )
        return cleaned or text.strip()


# ──────────────────────────────────────────────────────────────
# CLI entry point for one-time setup / manual login
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import asyncio

    async def _main():
        provider = GeminiBrowserProvider()
        print("Opening browser for Google login setup…")
        await provider.setup()
        print("Setup complete. Profile saved.")

    asyncio.run(_main())
