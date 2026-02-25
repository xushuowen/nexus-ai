# NEXUS AI — Demo Video Script
### Gemini Live Agent Challenge 2026 · Creative Storytellers Track
### Target Runtime: 3:30 — under 4-minute limit

---

## Production Brief

| Item | Detail |
|------|--------|
| Runtime | 3:30 (hard limit: 4:00) |
| Resolution | 1920 × 1080, 60 fps |
| Language | Narration: English · Subtitles: 繁體中文 |
| Voice | Calm, precise — let Gemini speak |
| Music | Ambient electronic, ≤ 20% volume |
| Accent color | `#00d4ff` cyan · `#00ffaa` green · `#05080f` void |
| Competition | Gemini Live Agent Challenge 2026 |
| Track | Creative Storytellers (Multimodal) |

---

## ⏱ Scene Timeline

---

### 🎬 Scene 1 — Cold Open `0:00 – 0:08`

**Screen:** Pure black. The Nexus diamond SVG logo pulses in from center, glowing cyan.
The hex grid canvas draws in from corners.
Title: **NEXUS AI** (Orbitron 900, white). Tagline fades below.

**Narration:**
> "Nine specialist agents. Twenty-two skills. Powered by Gemini 2.0 Flash. Built by a physical therapy student — to go beyond the text box."

**Subtitle:** 九個代理人。二十二項技能。由 Gemini 2.0 Flash 驅動。由物理治療系學生打造——突破文字框架。

---

### 🎬 Scene 2 — Dashboard Overview `0:08 – 0:20`

**Screen:** Navigate to `localhost:8001/dashboard`
- Header shows **NEXUS AI**, live clock ticking, green ONLINE badge pulsing
- Left panel: SYSTEM row — `9 agents · 22 skills`
- Center: Nexus Core SVG — two hexagons counter-rotating, three orbital dots
- Right panel: DAILY BRIEF — today's scheduled tasks
- Click **「技能演化」** tab → D3.js force graph renders, nodes orbit into position

**Narration:**
> "The Nexus dashboard gives a live view of the entire agent network — built on FastAPI, powered by Google GenAI SDK, running on Google Cloud. This D3.js skill graph reflects the actual system topology. Every node is a live component."

**Subtitle:** Nexus 主控台即時呈現整個代理人網路——以 FastAPI 構建，由 Google GenAI SDK 驅動，運行於 Google Cloud。每個節點都是正在運行的真實元件。

---

### 🎬 Scene 3 — Integrated Chat `0:20 – 0:27`

**Screen:** Click **「對話」** tab — no page navigation.
The 3-column interface slides in: Analysis Log (left) · Messages (center) · Active Agent (right).
Cursor moves to the input field, which glows cyan on focus.

**Narration:**
> "Everything lives in one place — the chat interface is embedded directly into the dashboard. The left panel shows the agent's real-time reasoning trace, powered by Gemini."

**Subtitle:** 所有功能整合在同一頁面。對話介面直接嵌入主控台，左側即時顯示由 Gemini 驅動的代理人推理過程。

---

### 🎬 Scene 4 — ACL Paper Search `0:27 – 0:55` ★ HERO SEQUENCE ★

**Screen:** User types slowly into the chat input:

```
幫我找前十字韌帶復健的相關論文
```

Press Enter.

**Narration:**
> "I'm a PT student preparing for clinical exams. I type entirely in Chinese: 'Find papers on ACL rehabilitation.' No commands, no prefix. Just natural language into Gemini."

**Subtitle:** 輸入純粹自然語言：「幫我找前十字韌帶復健的相關論文」——無需特殊指令，直接交給 Gemini。

---

**Screen:** Analysis Log fills with routing trace:

```
◈  received: 幫我找前十字韌帶復健的相關論文
✦  memory_scan: checking session context...
→  routing: intent analysis via Gemini...
✓  routed: Agents: ['academic_search']  score=0.92
✎  generating: querying PubMed API...
```

**Narration:**
> "In the Analysis Log — the system's internal monologue — you can watch every decision unfold. Gemini maps '前十字韌帶' to PubMed MeSH vocabulary and fires a direct API call. Deterministic routing — zero hallucination risk for the database query itself."

**Subtitle:** 分析日誌即時顯示每一個決策。Gemini 識別「前十字韌帶」並對應 PubMed MeSH 術語——確定性路由，直接呼叫 API。

---

**Screen:** Response streams in:

```
📚 PubMed 搜尋結果（共 847 筆，顯示 5 筆）

[1] Early versus delayed ACL reconstruction: randomized controlled trial
    Frobell RB et al. · New England Journal of Medicine (2023)
    ↗ pubmed.ncbi.nlm.nih.gov/PMID
...
```

Hold 3 seconds. Camera gently zooms on one paper entry.

**Narration:**
> "Five real papers. Real PMIDs. Real PubMed links. The query was enhanced from '前十字韌帶' to 'Anterior Cruciate Ligament[MeSH] AND rehabilitation' — the way a medical librarian searches."

**Subtitle:** 五篇真實論文，真實 PMID，直連 PubMed。查詢自動升級為 MeSH 格式——與醫學圖書館員的搜尋方式相同。

---

### 🎬 Scene 5 — Save to Study Notes `0:55 – 1:07`

**Screen:** User types follow-up:

```
把這些論文存進我的骨科筆記
```

Analysis Log:
```
→  routing: skill trigger "筆記" matched study_notes  score=0.88
✔  selected: subject detected: "骨科" → orthopedics
✎  generating: INSERT INTO notes (subject='orthopedics')...
```

**Narration:**
> "'Save these papers to my orthopedics notes.' Gemini detects the keyword '骨科', maps it to the orthopedics category, and writes to a local SQLite database — persistent, searchable, and reviewable."

**Subtitle:** Gemini 識別「骨科」科目，寫入本地 SQLite——跨 session 持久存在，可按科目或關鍵字搜尋。

---

### 🎬 Scene 6 — Telegram: Gemini Vision `1:07 – 1:35` ★ MULTIMODAL ★

**Screen:** Cut to Telegram on phone (vertical, centered in frame).
User sends a photo — clinical anatomy diagram of the knee.
Caption: **「這是什麼結構？」**

**Narration:**
> "Now — beyond the text box. The same system runs as a Telegram bot. I send a photo from my anatomy textbook — a clinical diagram of the knee — and ask what it shows. Gemini's multimodal Vision API handles this."

**Subtitle:** 超越文字框架。傳送教科書解剖圖，詢問圖中結構——由 Gemini 多模態視覺 API 處理。

---

**Screen:** Bot reply appears:

```
[Vision Agent · Gemini 2.0 Flash · Confidence: 87%]

圖中顯示右膝關節矢狀面切面，可識別以下結構：

• 前十字韌帶 (ACL)
  起自股骨外側髁，止於脛骨平台前方
  功能：防止脛骨前移、控制旋轉穩定性

• 後十字韌帶 (PCL)

• 內側半月板 / 外側半月板
```

**Narration:**
> "Gemini's multimodal API identifies the anatomical structures, labels them in Traditional Chinese — the user's language — adds clinical function descriptions, and returns a confidence score. Text in, image in — rich structured output."

**Subtitle:** Gemini 多模態 API 識別解剖結構，以繁體中文回應，加上臨床功能說明。文字輸入、圖像輸入——輸出豐富的結構化內容。

---

### 🎬 Scene 7 — Architecture `1:35 – 1:50`

**Screen:** Smooth fade to architecture diagram (animated, cyan on dark).

Each layer illuminates in sequence:

```
   ┌──────── INTERFACES ─────────────────┐
   │  Web UI · Telegram Bot · REST API   │
   └──────────────┬──────────────────────┘
                  │
   ┌──────────────▼──────────────────────┐
   │        TOKEN BUDGET CONTROLLER      │  ← 50,000 tokens/day
   └──────────────┬──────────────────────┘
                  │
   ┌──────────────▼──────────────────────┐
   │     ORCHESTRATOR + 4-LAYER MEMORY   │
   └──────┬───────────────────┬──────────┘
          │                   │
   ┌──────▼──────┐   ┌────────▼──────┐
   │  9 AGENTS   │   │  22 SKILLS    │
   └─────────────┘   └───────────────┘
          │
   ┌──────▼──────────────────────────────┐
   │  Gemini 2.0 Flash · Google GenAI SDK│
   └──────────────────────────────────────┘
          │
   ┌──────▼──────────────────────────────┐
   │  Google Cloud Run                   │
   └──────────────────────────────────────┘
```

**Narration:**
> "Under the hood: FastAPI, WebSocket, a hard token budget controller, nine specialist agents, twenty-two skills with three-layer NLP routing, and a four-layer memory system. All intelligence flows through Gemini 2.0 Flash via Google GenAI SDK. Deployed on Google Cloud Run."

**Subtitle:** 底層架構：FastAPI、WebSocket、Token 預算控制、九個代理人、二十二項技能三層路由、四層記憶體系統。所有智能通過 Gemini 2.0 Flash 處理。部署於 Google Cloud Run。

---

### 🎬 Scene 8 — Closing `1:50 – 2:10`

**Screen:** Return to Dashboard. The Nexus Core SVG glows — hexagons rotating, orbital dots alive.
Status: **ONLINE · 9 AGENTS · 22 SKILLS · GEMINI: ACTIVE**

Final title card:

```
NEXUS AI

Multi-Agent Personal Intelligence System
Powered by Gemini 2.0 Flash · Google GenAI SDK

Gemini Live Agent Challenge 2026
Creative Storytellers Track

github.com/xushuowen/nexus-ai
```

**Narration:**
> "Nexus isn't a prototype. It's a system I use every single day — for literature review, for clinical notes, for exam prep, for scheduling. Built to go beyond the text box. Powered by Gemini."

**Subtitle:** Nexus 不是原型，是我每天真實使用的系統。突破文字框架，由 Gemini 驅動。

---

## Director's Notes

### Scene 1 (0:00–0:08) — Cold Open
- Record the actual browser loading the page from scratch
- Hold title card for 2 full seconds before transition

### Scene 2 (0:08–0:20) — Dashboard
- Open `localhost:8001/dashboard` fresh (no pre-loaded data)
- Click **技能演化** tab and wait for D3.js force simulation to settle (~3 sec)
- Pan: left stat panel → sweep right to D3 graph

### Scene 3 (0:20–0:27) — Chat Tab
- Click **對話** tab from within dashboard — emphasize no page navigation
- WebSocket "◈ received" trace should appear in Analysis Log

### Scene 4 (0:27–0:55) — ACL Search ★
- Type at conversational speed
- Analysis Log entries must appear in real time
- Do **not** cut away from the routing trace — this is the key differentiator
- Hold on 5-paper result for 3 full seconds

### Scene 5 (0:55–1:07) — Study Notes
- Continue same chat session (no page reload)
- Show `"骨科" → orthopedics` detection in routing trace

### Scene 6 (1:07–1:35) — Telegram Vision ★ MULTIMODAL ★
- Use actual phone, not emulator
- Send a real knee anatomy diagram (sagittal section works well)
- Allow ~10 sec for Gemini vision response
- Frame: portrait phone, held steady or on stand
- This scene demonstrates the **"beyond text box"** requirement — do not cut short

### Scene 7 (1:35–1:50) — Architecture
- Animate each layer lighting up with 0.5s delay
- Show "Google Cloud Run" at bottom clearly — judges require Cloud deployment proof

### Scene 8 (1:50–2:10) — Closing
- Return to live dashboard — still active from earlier scenes
- Final card: fade-in, hold 5 seconds, fade to black

---

## What to Prepare Before Recording

| Item | Action |
|------|--------|
| Server | `python run.py` — verify `/api/status` returns `"init_complete": true` |
| Telegram | Bot must be running (`TELEGRAM_BOT_TOKEN` set) |
| Anatomy image | Prepare a clear knee sagittal section diagram |
| Test query | Pre-run ACL query once to warm cache |
| Screen | Clean browser, no tabs visible, zoom 100% |
| Browser | Full-screen, DevTools closed |
| Mic | Record narration separately, merge in post |

---

## Key Talking Points (for Devpost description / Q&A)

1. **Gemini 2.0 Flash** — every agent call uses Google GenAI SDK (`gemini-2.0-flash`)
2. **Multimodal vision** — Telegram image → Gemini vision API → Traditional Chinese anatomical description
3. **Beyond text box** — input is text OR image; output is structured mixed content
4. **No hardcoded routing** — Gemini scores all 9 agents dynamically per request
5. **MeSH vocabulary** — PT-domain medical term expansion via Gemini
6. **Token budget** — 50,000/day hard cap, never exceeds free tier
7. **4-layer memory** — working (7 slots) → episodic (SQLite) → semantic (ChromaDB) → procedural cache
8. **Google Cloud Run** — containerized deployment with documented proof
9. **Responsible AI** — filesystem sandbox, SSRF protection, rate limiter, local data only
