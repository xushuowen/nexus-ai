# Nexus AI - Multi-Agent Neural Assistant

> An advanced multi-agent AI assistant system approaching AGI capabilities, built with Python.

![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

## Architecture

```
Gateway (Web UI / Telegram / REST API)
    ↓
Token Budget Controller (daily limit protection)
    ↓
Orchestrator (smart routing + conversation history)
    ↓
9 Specialist Agents (Coder, Reasoning, Research, Knowledge, File, Web, Shell, Vision, Optimizer)
    ↓
4-Layer Adaptive Neural Memory (Working → Episodic → Semantic → Procedural)
    ↓
LLM Providers (Groq / Gemini Free Tier via LiteLLM)
```

## Key Features

- **Multi-Agent System**: 9 specialist agents auto-selected by context
- **4-Layer Memory**: Working memory, episodic (SQLite), semantic (FTS5 + ChromaDB + knowledge graph with Hebbian learning), procedural cache
- **Token Budget Control**: Daily limits with auto-reset, never exceeds free tier
- **SAO x Tensura UI**: Anime-inspired holographic interface with real-time thinking display
- **Telegram Integration**: Chat with your AI from your phone
- **15+ Tools**: Web search, browser automation, file ops, shell, cron jobs, image analysis, and more
- **100% Local**: Runs on your machine, no cloud dependency, CPU-only

## Quick Start

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/nexus-ai.git
cd nexus-ai

# Setup
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys (Groq free: https://console.groq.com)

# Run
python run.py
# Open http://localhost:8000
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Yes* | Groq API key (free tier) |
| `GEMINI_API_KEY` | Yes* | Google AI Studio key (free tier) |
| `TELEGRAM_BOT_TOKEN` | No | Telegram bot token from @BotFather |

*At least one LLM provider key is required.

## Deploy to Azure

```bash
# Using Azure CLI
az webapp up --name nexus-ai --runtime "PYTHON:3.12" --sku B1

# Or with Docker
az acr build --registry YOUR_REGISTRY --image nexus-ai .
az containerapp create --name nexus-ai --image YOUR_REGISTRY.azurecr.io/nexus-ai
```

## Tech Stack

- **Backend**: Python 3.12, FastAPI, async/await
- **LLM**: LiteLLM (Groq + Gemini free tier)
- **Memory**: SQLite FTS5 + ChromaDB (CPU) + NetworkX
- **Frontend**: Vanilla JS + WebSocket, SAO/Tensura anime-style UI
- **Bot**: python-telegram-bot
- **Deploy**: Docker, Azure App Service / Container Apps

## Project Structure

```
nexus/
├── main.py              # FastAPI entry point
├── config.py            # Configuration loader
├── core/                # Brain: orchestrator, budget, agents, engines
├── agents/              # 9 specialist agents
├── memory/              # 4-layer adaptive memory system
├── tools/               # 15+ tools (browser, search, shell, etc.)
├── gateway/             # Telegram, Web, REST API channels
├── providers/           # LLM provider abstraction
├── security/            # Sandbox, rate limiter, filesystem scope
├── web/                 # SAO x Tensura style frontend
└── tests/               # Unit tests
```

## License

MIT
