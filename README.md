# Nexus AI — Personal Multi-Agent Intelligence System

> A production-ready multi-agent AI assistant powered by **Gemini 2.0 Flash**, built for real-world daily use across Web, Telegram, and REST API interfaces.

![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)
![Gemini](https://img.shields.io/badge/Google-Gemini%202.0%20Flash-blue.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

---

## What is Nexus AI?

Nexus AI is a personal AI operating system that routes every user request through the most suitable specialist agent automatically, in real time. It replaces the need for multiple separate AI tools by consolidating reasoning, research, vision, coding assistance, scheduling, and memory into a single self-hosted system.

Built and used daily as a personal productivity tool. Not a demo — a real working assistant.

---

## System Architecture

```
┌─────────────────────────────────────────────────────┐
│                    INTERFACES                        │
│   Web UI (WebSocket)  │  Telegram Bot  │  REST API  │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│              TOKEN BUDGET CONTROLLER                 │
│         Daily limit enforcement · Auto-reset         │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│                  ORCHESTRATOR                        │
│   Intent detection → Agent routing → Memory recall   │
└──────┬───────────────────────────────────────┬──────┘
       │                                       │
┌──────▼──────────────────────────┐   ┌────────▼──────┐
│        SPECIALIST AGENTS (9)    │   │  SKILL ENGINE  │
│                                 │   │   (18 skills)  │
│  Reasoning   — multi-step COT   │   │                │
│  Research    — web + synthesis  │   │  web_search    │
│  Vision      — image / OCR      │   │  weather       │
│  Coder       — code generation  │   │  translator    │
│  Knowledge   — fact recall      │   │  pdf_reader    │
│  File        — local files      │   │  news          │
│  Web         — browser ops      │   │  reminder      │
│  Shell       — system commands  │   │  auto_schedule │
│  Optimizer   — daily reports    │   │  diary · more  │
└─────────────────────────────────┘   └───────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│               4-LAYER MEMORY SYSTEM                  │
│  Working (7 slots) → Episodic (SQLite) →             │
│  Semantic (ChromaDB + FTS5) → Procedural cache       │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│            LLM PROVIDER (LiteLLM + Google GenAI SDK)  │
│  Primary:  Gemini 2.0 Flash (Google AI)               │
│  Fallback: Groq Llama 3.3 70B                         │
│  Cloud:    Vertex AI (see deploy/vertex_ai.py)        │
└─────────────────────────────────────────────────────┘
```

---

## Key Features

### Multi-Agent Orchestration
9 specialist agents, each with a defined domain. The orchestrator scores every request against all agents and routes to the best match — no manual selection needed.

### Gemini 2.0 Flash Integration
Uses **Gemini 2.0 Flash** as the primary LLM via both the Google GenAI SDK and LiteLLM. Supports Vertex AI deployment (see `deploy/vertex_ai.py`). Automatic fallback chain: Gemini → Groq Llama 3.3 70B.

### Multimodal — Image & File Support
- **Photos**: Send any image via Telegram → Vision agent analyzes with GPT-4o (OCR, description, Q&A)
- **PDFs**: Automatically extracted and summarized
- **Text files**: Content injected directly into context

### Responsible AI by Design
- Hard daily token budget with configurable limits
- Per-request token cap
- Filesystem sandbox (read/write only within allowed paths)
- Rate limiter (30 req/min)
- No data leaves the device beyond the LLM API call itself

### Dual Interface
| Interface | Features |
|---|---|
| **Web UI** | Real-time WebSocket chat, thinking trace display, dark sci-fi theme |
| **Dashboard** | Live agent status, D3.js skill network graph, schedule view |
| **Telegram** | Full feature parity — text, images, files, documents |

### Autonomous Scheduling
Built-in cron scheduler lets the AI set its own reminders and tasks. Daily morning report delivered automatically at 6 AM via Telegram.

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | Gemini 2.0 Flash (Google GenAI SDK + LiteLLM), Groq fallback |
| Backend | Python 3.11, FastAPI, asyncio |
| Memory | SQLite FTS5, ChromaDB, NetworkX |
| Frontend | Vanilla JS, WebSocket, D3.js |
| Bot | python-telegram-bot |
| Deployment | Azure App Service (East Asia) |

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/xushuowen/nexus-ai.git
cd nexus-ai

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env and add your API keys (see Environment Variables below)

# 4. Run
python run.py

# Web UI:    http://localhost:8000
# Dashboard: http://localhost:8000/dashboard
```

## Reproducible Test Instructions (for Judges)

After starting the server at `http://localhost:8000`, open the Web UI and try:

| Test | Input | Expected Output |
|------|-------|-----------------|
| Weather | `台北天氣` | Current temp + 3-day forecast |
| Translation | `幫我翻譯：人工智慧改變了世界` | English translation via Gemini |
| GitHub | `github trending` | Top repos from past 7 days |
| Academic | `search papers on transformer architecture` | arXiv papers |
| Image Prompt | `畫一隻在月光下的貓` | Stable Diffusion prompt |

All skills run without additional setup — just a valid `GEMINI_API_KEY`.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Google AI Studio key — get free at aistudio.google.com |
| `TELEGRAM_BOT_TOKEN` | Optional | Telegram bot from @BotFather |
| `GROQ_API_KEY` | Optional | Groq fallback LLM (free tier) |
| `GITHUB_TOKEN` | Optional | GitHub API for repo search skill |

---

## Project Structure

```
nexus/
├── main.py                  # FastAPI entry point
├── config.yaml              # Model routing, budget, memory config
├── core/
│   ├── orchestrator.py      # Central routing engine
│   ├── budget.py            # Token budget enforcement
│   ├── memory_engine.py     # 4-layer memory system
│   └── schedule_runner.py   # Async cron scheduler
├── agents/                  # 9 specialist agents
├── skills/builtin/          # 18 built-in skills
├── providers/
│   ├── llm_provider.py      # LiteLLM wrapper + GitHub Models support
│   └── model_config.py      # Model routing config
├── gateway/
│   ├── web_channel.py       # WebSocket handler
│   └── telegram_channel.py  # Telegram bot (text + image + file)
└── web/
    ├── templates/           # dashboard.html, index.html
    └── static/              # D3.js dashboard, chat UI
```

---

## Responsible AI

- **Budget Controller** — hard daily token limits, never exceeds free tier
- **Filesystem Sandbox** — agents can only access explicitly allowed paths
- **Rate Limiting** — 30 requests/minute per gateway
- **Local memory** — all history stored on-device (SQLite + ChromaDB)
- **Transparent reasoning** — every response shows which agent handled it and confidence score

---

## Hackathon

**Gemini Live Agent Challenge 2026**
Category: **Multi-Agent Systems**

Nexus AI demonstrates sophisticated agent orchestration powered by Gemini 2.0 Flash, with real-world deployment and daily active use as a personal productivity system. Google Cloud integration via Vertex AI is available in `deploy/vertex_ai.py`.

See also:
- [`deploy/vertex_ai.py`](deploy/vertex_ai.py) — Vertex AI (Google Cloud) integration
- [`deploy/google_genai_sdk_example.py`](deploy/google_genai_sdk_example.py) — Google GenAI SDK usage

---

## License

MIT
