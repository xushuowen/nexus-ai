"""
Google Cloud Vertex AI integration for Nexus AI.

This module demonstrates how to configure Nexus AI to use
Vertex AI (Google Cloud) instead of AI Studio for Gemini API calls.

Requirements:
    pip install google-cloud-aiplatform litellm

Setup:
    1. Create a Google Cloud project
    2. Enable Vertex AI API: https://console.cloud.google.com/apis/library/aiplatform.googleapis.com
    3. Authenticate: gcloud auth application-default login
    4. Set environment variables (see below)
"""

from __future__ import annotations

import os


# ── Vertex AI Configuration ──────────────────────────────────────────────────

VERTEX_PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "your-gcp-project-id")
VERTEX_LOCATION   = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

# Vertex AI model IDs via LiteLLM
VERTEX_FLASH_MODEL = f"vertex_ai/gemini-2.0-flash"
VERTEX_PRO_MODEL   = f"vertex_ai/gemini-1.5-pro"


# ── LiteLLM Vertex AI Example ────────────────────────────────────────────────

async def call_vertex_gemini(prompt: str, model: str = VERTEX_FLASH_MODEL) -> str:
    """
    Call Gemini on Vertex AI via LiteLLM.

    LiteLLM automatically uses Application Default Credentials (ADC)
    when the vertex_ai/ prefix is used — no API key required.

    Example API call to Vertex AI endpoint:
        POST https://{location}-aiplatform.googleapis.com/v1/projects/{project}/
             locations/{location}/publishers/google/models/gemini-2.0-flash:generateContent
    """
    import litellm

    response = await litellm.acompletion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        vertex_project=VERTEX_PROJECT_ID,
        vertex_location=VERTEX_LOCATION,
        max_tokens=1024,
    )
    return response.choices[0].message.content or ""


# ── Nexus AI Config Override for Vertex AI ───────────────────────────────────

VERTEX_AI_CONFIG = {
    "providers": {
        "primary": "gemini-flash-vertex",
        "fallback": "gemini-pro-vertex",
        "models": {
            "gemini-flash-vertex": {
                "model_id": VERTEX_FLASH_MODEL,
                "max_tokens": 4096,
                "temperature": 0.7,
                "use_for": ["general", "routing", "simple_tasks", "classification", "analysis"],
            },
            "gemini-pro-vertex": {
                "model_id": VERTEX_PRO_MODEL,
                "max_tokens": 8192,
                "temperature": 0.7,
                "use_for": ["complex_reasoning", "code_generation"],
            },
        },
    }
}


# ── Cloud Run Deployment Helper ───────────────────────────────────────────────

CLOUD_RUN_DEPLOY_CMD = """
# Deploy Nexus AI to Google Cloud Run
# Prerequisites: gcloud CLI installed and authenticated

gcloud run deploy nexus-ai \\
  --source . \\
  --region us-central1 \\
  --platform managed \\
  --allow-unauthenticated \\
  --set-env-vars GOOGLE_CLOUD_PROJECT={project_id} \\
  --set-env-vars GOOGLE_CLOUD_LOCATION=us-central1 \\
  --memory 1Gi \\
  --cpu 1 \\
  --port 8000
"""


if __name__ == "__main__":
    import asyncio

    async def demo():
        print("Testing Vertex AI Gemini connection...")
        print(f"Project: {VERTEX_PROJECT_ID}")
        print(f"Location: {VERTEX_LOCATION}")
        print(f"Model: {VERTEX_FLASH_MODEL}\n")

        result = await call_vertex_gemini(
            "Say 'Nexus AI connected to Vertex AI successfully!' in Traditional Chinese."
        )
        print("Response:", result)

    asyncio.run(demo())
