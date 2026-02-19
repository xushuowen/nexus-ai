# Nexus AI — Personal Multi-Agent Intelligence System

> A production-ready multi-agent AI assistant powered by **GitHub Models (GPT-4o mini)**, built for real-world daily use across Web, Telegram, and REST API interfaces.

![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)
![GitHub Models](https://img.shields.io/badge/GitHub%20Models-GPT--4o%20mini-black.svg)
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
│            LLM PROVIDER (LiteLLM)                    │
│  Primary:  GitHub Models / GPT-4o mini               │
│  Fallback: Groq Llama 3.3 70B → Gemini Flash         │
└─────────────────────────────────────────────────────┘
```

---

## Key Features

### Multi-Agent Orchestration
9 specialist agents, each with a defined domain. The orchestrator scores every request against all agents and routes to the best match — no manual selection needed.

### GitHub Models Integration
Uses **GPT-4o mini via GitHub Models** as the primary LLM — part of the Microsoft AI ecosystem, free with a GitHub account, zero credit card required. Automatic fallback chain: GitHub Models → Groq → Gemini.

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
| LLM | GitHub Models (GPT-4o mini), Groq, Gemini via LiteLLM |
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

# 2. Install
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Add your GITHUB_TOKEN (free at github.com/settings/tokens)

# 4. Run
python -m nexus.main

# Web UI:    http://localhost:8000
# Dashboard: http://localhost:8000/dashboard
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GITHUB_TOKEN` | Yes | GitHub PAT for GitHub Models (GPT-4o mini) |
| `TELEGRAM_BOT_TOKEN` | Optional | Telegram bot from @BotFather |
| `GROQ_API_KEY` | Optional | Groq fallback LLM (free tier) |
| `GEMINI_API_KEY` | Optional | Gemini fallback LLM (free tier) |

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

**Microsoft AI Dev Days Hackathon 2026**
Category: **Multi-Agent Systems**

Nexus demonstrates sophisticated agent orchestration using the Microsoft AI ecosystem (GitHub Models), with real-world deployment and daily active use as a personal productivity system.

---

## License

MIT
