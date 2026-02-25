# Nexus AI — System Architecture

```mermaid
flowchart TD
    subgraph CHANNELS["📱 Input Channels"]
        TG["🤖 Telegram Bot\n(24/7 push + receive)"]
        WEB["🖥️ Web Dashboard\n(FastAPI + WebSocket)"]
        ADK_UI["⚡ Google ADK Agent\n(adk web / adk run)"]
    end

    subgraph ORCH["🧠 Orchestrator — 3-Layer NLP Router"]
        CS["💡 Common Sense Filter\n(zero-cost local answers)"]
        NLP1["Layer 1: Keyword Triggers\n(instant, no LLM)"]
        NLP2["Layer 2: Regex Intent Patterns\n(handles 80%+ of requests)"]
        NLP3["Layer 3: LLM Semantic Fallback\n(only when needed)"]
        BUDGET["💰 Token Budget Controller\n(50K tokens/day, hard stop)"]
    end

    subgraph SKILLS["⚡ 22 Built-in Skills"]
        MS["📚 PubMed Search\n+ MeSH Expansion"]
        SN["📝 Study Notes\n(save / quiz / search)"]
        MR["🌅 Morning Report\n(auto daily push)"]
        YT["▶️ YouTube Summary"]
        WX["☀️ Weather"]
        SC["⏰ Natural Language Scheduler"]
        OT["... 16 more skills"]
    end

    subgraph AGENTS["🤖 9 Specialist Agents"]
        RA["🔬 Reasoning\n(chain-of-thought + verify)"]
        RE["🔍 Research\n(web search + synthesis)"]
        CO["💻 Coder\n(generate + debug + run)"]
        KN["🧠 Knowledge\n(memory retrieval)"]
        VI["👁️ Vision\n(anatomy / X-ray analysis)"]
        WA["🌐 Web\n(URL fetch + extract)"]
        SH["⚙️ Shell\n(sandboxed execution)"]
        FI["📁 File\n(secure operations)"]
        OP["📊 Optimizer\n(self-monitoring)"]
    end

    subgraph CONF["🏛️ Agent Conference"]
        AC["Multi-agent debate\n2–3 rounds → consensus\n(hard clinical questions)"]
    end

    subgraph MEMORY["💾 4-Layer Adaptive Memory"]
        WM["⚡ Working Memory\n7 attention slots, LRU"]
        EP["📖 Episodic Memory\nSQLite FTS5"]
        SM["🕸️ Semantic Memory\nChromaDB + NetworkX graph"]
        PC["🔄 Procedural Cache\n1-hour TTL dedup"]
    end

    subgraph AI["🤖 AI Layer"]
        GEM["✨ Gemini 2.0 Flash\nGoogle GenAI SDK\n(primary)"]
        ADKM["⚡ Google ADK\n(standalone agent)"]
        LIT["🔄 LiteLLM Fallback\n(Groq / OpenAI)"]
    end

    subgraph CLOUD["☁️ Google Cloud Infrastructure"]
        CR["🚀 Cloud Run\nmin-instances=1, max=1\nDockerized FastAPI"]
        CB["🔨 Cloud Build\n(--source deploy)"]
    end

    subgraph EXT["🌐 External APIs"]
        PUB["PubMed E-utilities"]
        OM["Open-Meteo Weather"]
        DDG["DuckDuckGo Search"]
        YTA["YouTube Transcript API"]
    end

    TG -->|message| ORCH
    WEB -->|WebSocket| ORCH
    ADK_UI -->|ADK Runner| ADKM

    ORCH --> CS
    CS -->|complex| NLP1
    NLP1 --> NLP2
    NLP2 --> NLP3
    NLP3 --> BUDGET

    BUDGET -->|skill route| SKILLS
    BUDGET -->|agent route| AGENTS
    AGENTS -->|hard problems| CONF

    SKILLS --> AI
    AGENTS --> AI
    CONF --> AI

    ORCH <-->|read/write| MEMORY
    WM --> EP --> SM

    AI --> GEM
    AI --> LIT
    ADKM --> GEM

    SKILLS --> EXT
    AGENTS --> EXT

    CLOUD --> CR
    CR -->|runs| ORCH
    CB -->|builds| CR
```

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **3-layer NLP routing** | 80%+ of requests handled without LLM call → saves tokens |
| **min-instances=1** | Telegram polling requires always-on instance |
| **max-instances=1** | Prevents Telegram polling conflicts across revisions |
| **Token Budget Controller** | Hard daily cap with atomic JSON state prevents runaway costs |
| **Agent Conference** | Multi-agent debate measurably improves complex clinical reasoning |
| **4-layer memory** | Fast cache-first lookup, only escalates to vector search on cache miss |
| **Google ADK** | Standalone agent entry point qualifying for Live Agents category |
