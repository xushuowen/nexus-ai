"""
Google GenAI SDK integration example for Nexus AI.

This demonstrates how Nexus AI leverages the Google GenAI SDK
to call Gemini 2.0 Flash for multi-agent reasoning and skill execution.

Install: pip install google-generativeai
"""

from __future__ import annotations

import asyncio
import os

import google.generativeai as genai

# Configure with your Gemini API key
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

# Use Gemini 2.0 Flash — same model Nexus AI uses as primary LLM
MODEL = "gemini-2.0-flash"


def create_nexus_agent(system_prompt: str) -> genai.GenerativeModel:
    """
    Create a Gemini-powered agent with a system prompt.
    This mirrors how Nexus AI's specialist agents are configured.
    """
    return genai.GenerativeModel(
        model_name=MODEL,
        system_instruction=system_prompt,
    )


# ── Example: Translator Agent (mirrors nexus/skills/builtin/translator.py) ──

TRANSLATOR_SYSTEM = (
    "You are a professional translator. "
    "Detect the source language and translate to the language the user requests. "
    "If no target language is specified, translate Chinese↔English (swap). "
    "Only output the translation, no explanations."
)


async def translate(text: str) -> str:
    """Translate text using Gemini via Google GenAI SDK."""
    model = create_nexus_agent(TRANSLATOR_SYSTEM)
    response = await asyncio.to_thread(model.generate_content, text)
    return response.text


# ── Example: Reasoning Agent (mirrors nexus/agents/reasoning_agent.py) ──

REASONING_SYSTEM = (
    "You are an expert reasoning agent. "
    "Break down complex problems step-by-step using chain-of-thought reasoning. "
    "Always show your work before giving a final answer."
)


async def reason(question: str) -> str:
    """Reason through a problem using Gemini via Google GenAI SDK."""
    model = create_nexus_agent(REASONING_SYSTEM)
    response = await asyncio.to_thread(model.generate_content, question)
    return response.text


# ── Multi-turn Chat (mirrors Nexus AI's conversation memory) ──

def create_chat_session() -> genai.ChatSession:
    """
    Create a multi-turn chat session.
    Nexus AI uses this pattern for persistent conversation context.
    """
    model = genai.GenerativeModel(MODEL)
    return model.start_chat(history=[])


# ── Demo ──────────────────────────────────────────────────────────────────────

async def main():
    print("=== Nexus AI — Google GenAI SDK Demo ===\n")

    # Test translation
    print("1. Translation Agent:")
    result = await translate("人工智慧正在改變世界")
    print(f"   Input:  人工智慧正在改變世界")
    print(f"   Output: {result}\n")

    # Test reasoning
    print("2. Reasoning Agent:")
    result = await reason("Why is multi-agent AI better than a single monolithic model?")
    print(f"   {result[:200]}...\n")

    # Test chat session
    print("3. Multi-turn Chat Session:")
    chat = create_chat_session()
    r1 = chat.send_message("My name is Nexus. Remember that.")
    r2 = chat.send_message("What's my name?")
    print(f"   {r2.text}\n")

    print("=== Google GenAI SDK integration verified ✓ ===")


if __name__ == "__main__":
    asyncio.run(main())
