# -*- coding: utf-8 -*-
"""Google AI Studio login setup (run once).

Usage:
    cd C:\\Users\\Xushu\\nexus
    python gemini_login_setup.py
"""

import asyncio
import subprocess
import sys
import time
from pathlib import Path

PROFILE_DIR = Path(__file__).parent / "data" / "gemini_profile"
STUDIO_URL = "https://aistudio.google.com/prompts/new_chat"

CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Users\Xushu\AppData\Local\Google\Chrome\Application\chrome.exe",
]


def find_chrome():
    for p in CHROME_PATHS:
        if Path(p).exists():
            return p
    return None


def step1_open_chrome_normally():
    """Launch Chrome normally (no Playwright = no bot detection) so user can log in."""
    chrome = find_chrome()
    if not chrome:
        print("[ERROR] Chrome not found.")
        sys.exit(1)

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    print("[INFO] Using Chrome: " + chrome)
    print("[INFO] Profile dir:  " + str(PROFILE_DIR))
    print("")
    print("Opening Chrome... please log in to your Google account.")
    print("")

    # Launch Chrome as a normal process (NOT via Playwright - avoids bot detection)
    proc = subprocess.Popen([
        chrome,
        f"--user-data-dir={PROFILE_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        "https://accounts.google.com/",
    ])
    return proc


async def step2_verify_with_playwright():
    """Launch Chrome with remote debug port, connect via CDP, verify AI Studio."""
    chrome = find_chrome()
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("[ERROR] Playwright not installed.")
        return False

    print("[INFO] Verifying with Playwright (CDP mode)...")
    proc = None
    try:
        # Launch Chrome normally with a remote debugging port (no Playwright control = no bot detection)
        proc = subprocess.Popen([
            chrome,
            f"--user-data-dir={PROFILE_DIR}",
            "--remote-debugging-port=9222",
            "--no-first-run",
            "--no-default-browser-check",
            STUDIO_URL,
        ])
        # Wait for Chrome to start and load the page
        await asyncio.sleep(4)

        # Connect Playwright to the already-running Chrome via CDP
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            contexts = browser.contexts
            pages = contexts[0].pages if contexts else []
            page = pages[0] if pages else await contexts[0].new_page()

            # Give page time to load if not already there
            if STUDIO_URL not in page.url:
                await page.goto(STUDIO_URL, wait_until="domcontentloaded", timeout=20000)

            title = await page.title()
            await browser.close()

        if "sign" in title.lower() or "login" in title.lower():
            print("[WARN] Still showing login page (title: " + title + ")")
            return False

        print("[OK] AI Studio accessible! Title: " + title)
        return True
    except Exception as e:
        print("[WARN] Playwright verify failed: " + str(e))
        return False
    finally:
        if proc:
            proc.terminate()


def main():
    print("=" * 55)
    print("  Nexus AI - Google AI Studio Login Setup")
    print("=" * 55)
    print("")

    # Step 1: open normal Chrome for login
    proc = step1_open_chrome_normally()

    print("Steps:")
    print("  1. Log in to your Google account in the Chrome window")
    print("  2. Wait until you see the AI Studio or Google homepage")
    print("  3. Come back here and press Enter")
    print("")
    input("Press Enter after logging in to Google... ")

    # Close the Chrome process
    print("[INFO] Closing Chrome...")
    proc.terminate()
    time.sleep(2)

    # Step 2: verify session was saved
    print("[INFO] Verifying session...")
    ok = asyncio.run(step2_verify_with_playwright())

    print("")
    if ok:
        print("[DONE] Setup successful! Profile saved at:")
        print("  " + str(PROFILE_DIR))
        print("")
        print("You can now use brain_mode: gemini_web in Nexus.")
    else:
        print("[WARN] Could not verify AI Studio access automatically.")
        print("  The login data is saved - it may still work.")
        print("  Try starting Nexus and switching to gemini_web mode.")


if __name__ == "__main__":
    main()
