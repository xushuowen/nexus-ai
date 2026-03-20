# NEXUS AI — Demo Video Script
### Gemini Live Agent Challenge 2026 · Creative Storyteller Track
### Target Runtime: 2:50 — under 4-minute limit

---

## Production Brief

| Item | Detail |
|------|--------|
| Runtime | 2:50 (hard limit: 4:00) |
| Resolution | 1920 × 1080, 60 fps |
| Language | Narration: English · Subtitles: 繁體中文 |
| Voice | Calm, precise — let Gemini speak |
| Music | Ambient electronic, ≤ 20% volume |
| Accent color | `#00d4ff` cyan · `#00ffaa` green · `#05080f` void |
| Competition | Gemini Live Agent Challenge 2026 |
| Track | Creative Storyteller (Multimodal) |

---

## ⏱ Scene Timeline

---

### 🎬 Scene 1 — Cold Open `0:00 – 0:08`

**Screen:** Pure black. The Nexus diamond SVG logo pulses in from center, glowing cyan.
The hex grid canvas draws in from corners.
Title: **NEXUS AI** (Orbitron 900, white). Tagline fades below.

**Narration:**
> "Nine specialist agents. Twenty-four skills. Powered by Gemini 2.5 Flash. Built by a physical therapy student — to go beyond the text box."

**Subtitle:** 九個代理人。二十四項技能。由 Gemini 2.5 Flash 驅動。由物理治療系學生打造——突破文字框架。

---

### 🎬 Scene 2 — Dashboard Overview `0:08 – 0:20`

**Screen:** Navigate to `localhost:8000/dashboard`
- Header shows **NEXUS AI**, live clock ticking, green ONLINE badge pulsing
- Left panel: SYSTEM row — `9 agents · 24 skills`
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

### 🎬 Scene 6 — Telegram: Gemini Vision `1:07 – 1:30` ★ MULTIMODAL ★

**Screen:** Cut to Telegram on phone (vertical, centered in frame).
User sends a photo — clinical anatomy diagram of the knee.
Caption: **「這是什麼結構？」**

**Narration:**
> "The same system runs as a Telegram bot. I send a photo from my anatomy textbook and ask what it shows. Gemini's multimodal Vision API handles this."

**Subtitle:** 同一系統也作為 Telegram 機器人運行。傳送教科書解剖圖——由 Gemini 多模態視覺 API 處理。

---

**Screen:** Bot reply appears:

```
[Vision Agent · Gemini 2.5 Flash · Confidence: 87%]

圖中顯示右膝關節矢狀面切面，可識別以下結構：

• 前十字韌帶 (ACL)
  起自股骨外側髁，止於脛骨平台前方
  功能：防止脛骨前移、控制旋轉穩定性

• 後十字韌帶 (PCL)

• 內側半月板 / 外側半月板
```

**Narration:**
> "Gemini identifies the anatomical structures, labels them in Traditional Chinese, and adds clinical function descriptions. Text in, image in — rich structured output."

**Subtitle:** Gemini 識別解剖結構，以繁體中文回應，加上臨床功能說明。文字輸入、圖像輸入——輸出豐富的結構化內容。

---

### 🎬 Scene 7 — Gemini Creates: Exam Questions from Memory `1:30 – 2:05` ★ CREATIVE STORYTELLER ★

**Screen:** Return to same chat session from Scene 5 (orthopedics notes saved).
Cursor moves to input field.

**Narration:**
> "Now — the creative moment. I don't just store notes. I ask Gemini to turn them into something entirely new."

**Subtitle:** 現在是創作時刻。我不只是儲存筆記——我讓 Gemini 將它們轉化成全新的東西。

---

**Screen:** User types:

```
從我剛存的骨科筆記出5道考試題目
```

Analysis Log:
```
◈  received: 從我剛存的骨科筆記出5道考試題目
→  routing: study_notes + reasoning_agent
✓  retrieved: notes from subject='orthopedics'
✎  generating: exam questions via Gemini...
```

Response streams in:

```
📝 骨科考試題目（共 5 題）

【1】關於旋轉肌群（Rotator Cuff），下列何者正確？
  A) 由四條肌肉組成
  B) 棘上肌負責內旋
  C) 受傷後無法保守治療
  D) 與三角肌無關
  答案：A

【2】前十字韌帶（ACL）損傷後，手術最佳時機為何？
  A) 立即手術（24小時內）
  B) 急性期消腫後（3–6週）
  C) 1年後
  D) 不需手術
  答案：B
...
```

Hold 4 seconds. Camera slowly pans down the questions.

**Narration:**
> "Gemini reads my saved orthopedics notes — the PubMed papers I stored moments ago — and generates five clinical exam questions in Traditional Chinese. Multiple choice, correct answers, clinical reasoning baked in. Text in, image in, knowledge in — original content out. This is the Creative Storyteller."

**Subtitle:** Gemini 讀取我剛儲存的骨科筆記，生成五道繁體中文臨床考題，附正確答案與臨床推理。文字輸入、圖像輸入、知識輸入——原創內容輸出。這就是 Creative Storyteller。

---

### 🎬 Scene 8 — Architecture `2:05 – 2:20`

**Screen:** Smooth fade to architecture diagram (animated, cyan on dark).

Each layer illuminates in sequence:

```
   ┌──────── INPUT MODALITIES ────────────────────────┐
   │  Text (Web/Telegram) · Image (Telegram Vision)   │
   └──────────────┬───────────────────────────────────┘
                  │
   ┌──────────────▼───────────────────────────────────┐
   │        TOKEN BUDGET CONTROLLER                   │  ← 50,000 tokens/day
   └──────────────┬───────────────────────────────────┘
                  │
   ┌──────────────▼───────────────────────────────────┐
   │     ORCHESTRATOR + 5-LAYER MEMORY                │
   └──────┬────────────────────┬─────────────────────┘
          │                    │
   ┌──────▼──────┐   ┌─────────▼──────┐
   │  9 AGENTS   │   │  24 SKILLS     │
   └─────────────┘   └────────────────┘
          │
   ┌──────▼───────────────────────────────────────────┐
   │  Gemini 2.5 Flash · Google GenAI SDK             │
   │  Vision · Embedding · Generation                 │
   └──────────────────────────────────────────────────┘
          │
   ┌──────▼───────────────────────────────────────────┐
   ┌──────── OUTPUT MODALITIES ───────────────────────┐
   │  Structured text · Citation cards · Exam Qs      │
   │  Anatomy analysis · Telegram push · Dashboard    │
   └──────────────────────────────────────────────────┘
          │
   ┌──────▼───────────────────────────────────────────┐
   │  Google Cloud Run (asia-east1)                   │
   └──────────────────────────────────────────────────┘
```

**Narration:**
> "Under the hood: multiple input modalities — text and image — flow through nine specialist agents and twenty-four skills, powered by Gemini 2.5 Flash. The output is equally varied: structured citation cards, anatomy analysis, clinical exam questions, Telegram push notifications. Input is anything. Output is everything."

**Subtitle:** 底層架構：多種輸入模態——文字與圖像——流經九個代理人、二十四項技能，由 Gemini 2.5 Flash 驅動。輸出同樣多元：引用卡片、解剖分析、考試題目、Telegram 推播。輸入是任何東西，輸出是一切。

---

### 🎬 Scene 9 — Closing `2:20 – 2:50`

**Screen:** Slow montage — 3 seconds each:
1. The exam questions from Scene 7 (Gemini-generated content)
2. The anatomy analysis from Scene 6 (image → structured Chinese)
3. The PubMed citation cards from Scene 4 (text → research)
Then cut to Dashboard — Nexus Core SVG glows, hexagons rotating, orbital dots alive.
Status: **ONLINE · 9 AGENTS · 24 SKILLS · GEMINI: ACTIVE**

Final title card (fade in, hold 5 seconds, fade to black):

```
NEXUS AI

Multi-Agent Personal Intelligence System
Gemini 2.5 Flash · Google GenAI SDK · Google Cloud Run

Gemini Live Agent Challenge 2026
Creative Storyteller Track

nexus-ai-758633716956.asia-east1.run.app
github.com/xushuowen/nexus-ai
```

**Narration:**
> "Nexus isn't a prototype. It's a system I use every single day — for literature review, for clinical notes, for exam prep. Text in. Image in. Knowledge in. Rich, structured, multilingual content out. Built to go beyond the text box. Powered by Gemini."

**Subtitle:** Nexus 不是原型，是我每天真實使用的系統。文字輸入、圖像輸入、知識輸入。豐富、結構化、多語言的內容輸出。突破文字框架，由 Gemini 驅動。

---

## Director's Notes

### Scene 1 (0:00–0:08) — Cold Open
- Record the actual browser loading the page from scratch
- Hold title card for 2 full seconds before transition

### Scene 2 (0:08–0:20) — Dashboard
- Open `localhost:8000/dashboard` fresh (no pre-loaded data)
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

### Scene 6 (1:07–1:30) — Telegram Vision ★ MULTIMODAL ★
- Use actual phone, not emulator
- Send a real knee anatomy diagram (sagittal section works well)
- Allow ~10 sec for Gemini vision response
- Frame: portrait phone, held steady or on stand

### Scene 7 (1:30–2:05) — Exam Generation ★ CREATIVE STORYTELLER ★
- Continue SAME chat session from Scene 5 — no page reload, shows persistent context
- Type slowly: 「從我剛存的骨科筆記出5道考試題目」
- Analysis Log must show `study_notes + reasoning_agent` routing trace — this shows multimodal pipeline
- **Hold on each generated question** — let judges read the clinical content
- Camera slowly pans down the question list — 4 full seconds minimum
- This scene is the emotional climax: stored knowledge → original creative output

### Scene 8 (2:05–2:20) — Architecture
- Animate INPUT layer first, then OUTPUT layer last — bookend the multimodal story
- Show "Google Cloud Run" at bottom clearly — judges require Cloud deployment proof

### Scene 9 (2:20–2:50) — Closing
- Montage of 3 outputs: exam questions → anatomy analysis → PubMed cards (3 sec each)
- Then dashboard — show the system is live and complete
- Final card: fade-in, hold 5 seconds, fade to black

---

## What to Prepare Before Recording

| Item | Action |
|------|--------|
| Server | `python run.py` — verify `/api/status` returns `"init_complete": true` |
| Telegram | Bot must be running (`TELEGRAM_BOT_TOKEN` set) |
| Anatomy image | Prepare a clear knee sagittal section diagram (sagittal view works best) |
| Test queries | Pre-run ACL query + exam generation once to warm cache |
| Screen | Clean browser, no tabs visible, zoom 100% |
| Browser | Full-screen, DevTools closed |
| Narration | Record narration separately, merge in post |

---

## Key Talking Points (for Devpost description / Q&A)

1. **Multimodal input** — text (chat) AND image (Telegram anatomy diagrams) both go through Gemini 2.5 Flash
2. **Multimodal output** — structured citation cards, Traditional Chinese anatomy analysis, generated exam questions, Telegram push — all from one system
3. **Creative generation** — Gemini transforms stored notes into original exam questions: stored knowledge → new content
4. **PT domain expertise** — MeSH vocabulary expansion for 30+ PT terms; `search_medical_papers()` hits NCBI PubMed E-utilities directly
5. **Gemini 2.5 Flash** — every agent call uses Google GenAI SDK (`gemini-2.5-flash`); Vision API for image analysis; Embedding API for semantic memory
6. **No hardcoded routing** — Gemini scores all 9 agents dynamically per request via 3-layer NLP
7. **5-layer memory** — working → episodic (SQLite FTS5) → semantic (Gemini Embedding) → procedural → PyramidMemory (LLM long-term compression)
8. **Token budget** — 50,000/day hard cap, never exceeds free tier
9. **Google Cloud Run** — containerized deployment, live at nexus-ai-758633716956.asia-east1.run.app
10. **Responsible AI** — filesystem sandbox, SSRF protection, rate limiter, 5-sec code timeout
