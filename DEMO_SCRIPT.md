# NEXUS AI — Demo Video Script
### Microsoft AI Dev Days Hackathon 2026 · Multi-Agent Systems
### Target Runtime: 2:00 — every second counts

---

## Production Brief

| Item | Detail |
|------|--------|
| Runtime | 2 minutes (± 5 sec) |
| Resolution | 1920 × 1080, 60 fps |
| Language | Narration: English · Subtitles: 繁體中文 |
| Voice | Calm, precise — let the system speak |
| Music | Ambient electronic, ≤ 20% volume |
| Accent color | `#00d4ff` cyan · `#00ffaa` green · `#05080f` void |
| Competition | Microsoft AI Dev Days Hackathon 2026 |

---

## ⏱ Scene Timeline

---

### 🎬 Scene 1 — Cold Open `0:00 – 0:08`

**Screen:** Pure black. The Nexus diamond SVG logo pulses in from center, glowing cyan.
The hex grid canvas draws in from corners.
Title: **NEXUS AI** (Orbitron 900, white). Tagline fades below.

**Narration:**
> "One system. Nine specialist agents. Twenty-two skills. Built by a physical therapy student — for problems that are real, urgent, and personal."

**Subtitle:** 一套系統。九個代理人。二十二項技能。由物理治療系學生打造，為了真實而急迫的需求。

---

### 🎬 Scene 2 — Dashboard Overview `0:08 – 0:20`

**Screen:** Navigate to `localhost:8000/dashboard`
- Header shows **NEXUS · Multi-Agent Neural System**, live clock ticking, green ONLINE badge pulsing
- Left panel: SYSTEM row — `9 agents · 22 skills · N requests`
- CHANNELS row — Web UI online (green), Telegram online (green)
- Center: Nexus Core SVG — two hexagons counter-rotating, three orbital dots
- Right panel: DAILY BRIEF — today's scheduled tasks
- Click **「技能演化」** tab → D3.js force graph renders, nodes orbit into position

**Narration:**
> "The Nexus dashboard gives a live view of the entire agent network. Nine specialists, twenty-two skills, all orchestrated in real time. This D3.js skill graph reflects the actual system topology — every node is a running component."

**Subtitle:** Nexus 主控台即時呈現整個代理人網路。九個專家代理、二十二項技能即時協作。技能演化圖由 D3.js 繪製，每個節點都是正在運行的真實元件。

---

### 🎬 Scene 3 — Integrated Chat `0:20 – 0:27`

**Screen:** Click **「對話」** tab in the same Dashboard page — no page navigation.
The 3-column chat interface slides in: Analysis Log (left) · Messages (center) · Active Agent (right).
Cursor moves to the input field, which glows cyan on focus.

**Narration:**
> "Everything lives in one place. No switching between pages — the chat interface is embedded directly into the dashboard. The left panel shows the agent's real-time reasoning trace."

**Subtitle:** 所有功能整合在同一頁面。對話介面直接嵌入主控台，左側即時顯示代理人的推理過程。

---

### 🎬 Scene 4 — ACL Paper Search `0:27 – 0:55` ★ HERO SEQUENCE ★

**Screen:** User types slowly into the chat input (allow viewers to read Chinese):

```
幫我找前十字韌帶復健的相關論文
```

Press Enter. Subtle send animation.

**Narration:**
> "I'm a PT student preparing for clinical exams. I need research papers — now. I type entirely in Chinese: 'Find papers on ACL rehabilitation.' No commands, no skill prefix. Just natural language."

**Subtitle:** 我是物理治療系學生，正在備考。輸入純粹自然語言：「幫我找前十字韌帶復健的相關論文」——無需特殊指令。

---

**Screen:** Analysis Log panel fills with the routing trace (monospace, dim):

```
◈  received: 幫我找前十字韌帶復健的相關論文
✦  memory_scan: checking session context...
→  routing: intent analysis...
✓  routed: Agents: ['academic_search']  score=0.92
✎  generating: querying PubMed API...
```

**Narration:**
> "In the Analysis Log — the system's internal monologue — you can watch every decision unfold. It matches '前十字韌帶' to PubMed's MeSH vocabulary, bypasses the LLM entirely for this step, and fires a direct API call. Deterministic routing — zero hallucination risk."

**Subtitle:** 分析日誌即時顯示每一個決策。系統辨識「前十字韌帶」對應 PubMed MeSH 術語，跳過 LLM 直接呼叫 API——確定性路由，零幻覺風險。

---

**Screen:** Response streams into chat. Formatted card:

```
📚 PubMed 搜尋結果（共 847 筆，顯示 5 筆）

[1] Early versus delayed ACL reconstruction: randomized controlled trial
    Frobell RB et al. · New England Journal of Medicine (2023)
    ↗ pubmed.ncbi.nlm.nih.gov/PMID

[2] Neuromuscular rehabilitation after ACL injury — systematic review
    ...
```

Hold on results for 3 seconds. Camera gently zooms on one paper entry.

**Narration:**
> "Five real papers. Real PMIDs. Real links to PubMed. The query was automatically enhanced from '前十字韌帶' to 'Anterior Cruciate Ligament[MeSH] AND rehabilitation' — the way a medical librarian would search it."

**Subtitle:** 五篇真實論文，真實 PMID，直連 PubMed。查詢自動升級為 MeSH 格式——與醫學圖書館員的搜尋方式相同。

---

### 🎬 Scene 5 — Save to Study Notes `0:55 – 1:07`

**Screen:** User types follow-up:

```
把這些論文存進我的骨科筆記
```

Analysis Log shows:
```
→  routing: skill trigger "筆記" matched study_notes  score=0.88
✔  selected: subject detected: "骨科" → orthopedics
✎  generating: INSERT INTO notes (subject='orthopedics')...
```

**Narration:**
> "'Save these papers to my orthopedics notes.' One sentence. Nexus detects the keyword '骨科', maps it to the orthopedics subject category, and writes to a local SQLite database — persistent across sessions, searchable by keyword or subject."

**Subtitle:** 「把這些論文存進我的骨科筆記」——系統識別「骨科」科目，寫入本地 SQLite，跨 session 持久存在，可按科目或關鍵字搜尋。

---

**Screen:** Response:
```
📝 筆記已儲存 [骨科]

> 已儲存 5 筆論文摘要 (2026-02-24)
  科目：骨科 (orthopedics)
  輸入「筆記 複習 骨科」可複習 · 「筆記 考試 骨科」可生成考題
```

**Narration:**
> "Confirmed. I can now review these notes, search by keyword, or ask Nexus to generate quiz questions from them — without ever leaving the dashboard."

**Subtitle:** 已確認儲存。可隨時複習、搜尋，或讓 Nexus 生成考題——所有操作都在同一介面完成。

---

### 🎬 Scene 6 — Telegram: Vision Agent `1:07 – 1:25`

**Screen:** Cut to Telegram on phone (vertical, centered in frame).
Nexus bot chat is open. User sends a photo — clinical anatomy diagram of the knee (ACL, PCL, meniscus labeled).
Caption: **「這是什麼結構？」**

**Narration:**
> "The same system runs as a Telegram bot. I send a clinical anatomy diagram — a photo from my textbook — and ask what it shows."

**Subtitle:** 相同系統作為 Telegram 機器人運行。傳送一張教科書解剖圖，詢問圖中結構。

---

**Screen:** Bot reply appears:
```
[Vision Agent — Confidence: 87%]

圖中顯示右膝關節矢狀面切面，可識別以下結構：

• 前十字韌帶 (ACL)
  起自股骨外側髁，止於脛骨平台前方
  功能：防止脛骨前移、控制旋轉穩定性

• 後十字韌帶 (PCL)

• 內側半月板 / 外側半月板
```

**Narration:**
> "Gemini's multimodal API identifies the anatomical structures, labels them in Traditional Chinese, adds clinical function descriptions — and returns a confidence score. Same language as the user, always."

**Subtitle:** Gemini 多模態 API 識別解剖結構，以繁體中文回應，加上臨床功能說明與信心分數。語言永遠跟隨使用者。

---

### 🎬 Scene 7 — Architecture `1:25 – 1:40`

**Screen:** Smooth fade to architecture diagram (animated, cyan on dark):

```
   ┌──────── INTERFACES ────────────────┐
   │  Web UI · Telegram Bot · REST API  │
   └──────────────┬─────────────────────┘
                  │
   ┌──────────────▼─────────────────────┐
   │        TOKEN BUDGET CONTROLLER     │  ← 50,000 tokens/day hard cap
   └──────────────┬─────────────────────┘
                  │
   ┌──────────────▼─────────────────────┐
   │     ORCHESTRATOR + MEMORY          │  ← 4-layer: Working→Episodic→Semantic→Cache
   └──────┬───────────────────┬─────────┘
          │                   │
   ┌──────▼──────┐   ┌────────▼──────┐
   │  9 AGENTS   │   │  22 SKILLS    │
   └─────────────┘   └───────────────┘
          │
   ┌──────▼──────────────────────────────┐
   │  Gemini 2.0 Flash  ·  Groq fallback │
   └─────────────────────────────────────┘
```

Each layer illuminates in sequence, cyan accent.

**Narration:**
> "Under the hood: FastAPI, WebSocket, a hard token budget controller, nine specialist agents each with a distinct domain, twenty-two skills with three-layer NLP routing — and a four-layer memory system that learns from every interaction. Deployed on Azure App Service, powered by Gemini 2.0 Flash."

**Subtitle:** 底層架構：FastAPI、WebSocket、Token 預算控制、九個代理人、二十二項技能三層路由、四層記憶體系統。部署於 Azure App Service，由 Gemini 2.0 Flash 驅動。

---

### 🎬 Scene 8 — Closing `1:40 – 2:00`

**Screen:** Return to Dashboard. The Nexus Core SVG glows — hexagons rotating, orbital dots alive.
Status: **ONLINE · 9 AGENTS · 22 SKILLS · MEMORY: ACTIVE**

Final title card fades in, clean Orbitron:

```
NEXUS AI

Multi-Agent Personal Intelligence System

Microsoft AI Dev Days Hackathon 2026

github.com/xushuowen/nexus-ai
```

**Narration:**
> "Nexus isn't a prototype. It's a system I use every single day — for literature review, for clinical notes, for exam prep, for scheduling. Built to solve real problems. With the Microsoft AI ecosystem at its core."

**Subtitle:** Nexus 不是原型，是我每天真實使用的系統。文獻檢索、臨床筆記、備考準備、排程管理——解決真實問題，以 Microsoft AI 生態系為核心。

---

## Director's Notes

### Scene 1 (0:00–0:08) — Cold Open
- Record the actual browser loading the page from scratch
- The hex canvas draws in organically — do not skip this animation
- Hold on the title card for 2 full seconds before scene transition

### Scene 2 (0:08–0:20) — Dashboard
- Open `localhost:8000/dashboard` fresh (no pre-loaded data)
- Let the API fetch run naturally (`/api/dashboard` call visible in network tab is fine)
- Click **技能演化** tab and wait for D3.js force simulation to settle (~3 sec)
- Pan: start on left stat panel, sweep right to the D3 graph

### Scene 3 (0:20–0:27) — Chat Tab
- Click **對話** tab from within dashboard — emphasize no page navigation
- The WebSocket connection ping should be visible in the Analysis Log ("◈ received" trace)

### Scene 4 (0:27–0:55) — ACL Search ★
- Type at conversational speed — not too fast, not staged-slow
- The Analysis Log entries should appear in real time as the system works
- Do **not** cut away from the thinking trace — it's the key differentiator
- Hold on the 5-paper result for 3 full seconds

### Scene 5 (0:55–1:07) — Study Notes
- Continue from same chat session (no page reload)
- The routing trace should show `"骨科" → orthopedics` detection clearly

### Scene 6 (1:07–1:25) — Telegram
- Use actual phone, not emulator, if possible
- Send a real anatomy diagram (knee sagittal section works well)
- Bot response must be real (not mocked) — allow ~10 sec for response
- Frame: portrait phone, held steady or on stand

### Scene 7 (1:25–1:40) — Architecture
- Animate the diagram programmatically if possible (each layer lights up with 0.5s delay)
- OR use a pre-made motion graphic with the exact colors from the UI theme

### Scene 8 (1:40–2:00) — Closing
- Return to the live dashboard — system should still be active from earlier scenes
- Final card: clean fade-in, hold for 5 seconds, then fade to black

---

## What to Prepare Before Recording

| Item | Action |
|------|--------|
| Server | `python run.py` — verify `/api/status` returns `"init_complete": true` |
| Telegram | Bot must be running (`TELEGRAM_BOT_TOKEN` set) |
| Test query | Pre-run the ACL query once to warm up the cache |
| Anatomy image | Prepare a clear knee anatomy diagram (sagittal section) |
| Screen | Clean browser, no tabs visible, zoom at 100% |
| Browser | Full-screen, DevTools closed |
| Mic | Test narration audio separately, then merge in post |
| Clock | Record during a time when the DAILY BRIEF shows real schedules |

---

## Key Talking Points (for extended Q&A)

1. **No hardcoded routing** — all agent selection is scored dynamically
2. **MeSH vocabulary** — PT-domain-specific medical term expansion
3. **Token budget** — 50,000/day hard cap, never exceeds free tier
4. **4-layer memory** — working (7 slots) → episodic (SQLite) → semantic (ChromaDB) → procedural cache
5. **22 skills, 3-layer NLP** — trigger keywords → intent patterns → LLM fallback
6. **Azure deployment** — production URL live during hackathon
7. **Responsible AI** — filesystem sandbox, SSRF protection, rate limiter, local data only
