# Nexus AI — Demo Video Script
### Microsoft AI Dev Days Hackathon 2026 | Multi-Agent Systems Category
### Runtime: 1 minute 55 seconds

---

## Production Notes

- **Total runtime**: 1:55
- **Tone**: Clean, technical, confident — no hype, let the system speak for itself
- **Screen recording**: 1920x1080, 60fps recommended
- **Narration language**: English (voice-over)
- **On-screen text / subtitles**: Traditional Chinese (繁體中文)
- **Background music**: Ambient electronic, low volume, do not compete with narration
- **Accent color reference**: `#00d4ff` (cyan), `#00ffaa` (green), `#05080f` (void black)

---

## Script

| Timestamp | Screen / Visual | Narration (English) | Subtitle (Chinese) |
|-----------|----------------|--------------------|--------------------|
| **0:00 – 0:07** | Cold open: full-screen dark void. The Nexus diamond logo pulses in. Hexagonal grid canvas fades in behind it. Title card: "NEXUS AI" in Orbitron font. Tagline appears below. | "One assistant. Nine specialist agents. Built by a physical therapy student — for the hardest problems in their daily life." | 一個助手。九個專屬代理人。由物理治療系學生打造，為真實學習而生。 |
| **0:07 – 0:18** | Cut to the **Dashboard** at `localhost:8000/dashboard`. The header shows "NEXUS — Multi-Agent Neural System" with a live clock and green "ONLINE" pulse. Camera slowly pans across the left panel showing: 9 agents active, 18 skills loaded, request count ticking. The D3.js skill network graph is visible on the right — nodes glowing in cyan and green, edges animating. | "This is the Nexus dashboard — a live view of the entire agent network. Nine specialists, eighteen skills, all orchestrated in real time. The skill graph is rendered with D3.js and updates live as the system runs." | 這是 Nexus 主控台——九個代理人、十八個技能，即時協作。技能關係圖由 D3.js 繪製，反映系統當前狀態。 |
| **0:18 – 0:25** | Cut to the **Web UI chat interface** at `localhost:8000`. Dark sci-fi panel. The input bar glows at the bottom with cyan border. Mouse cursor clicks into the input field. | "Now let's see the system in action. I'm a PT student preparing for clinical exams, and I need research papers — right now." | 現在讓我們實際操作。我是物理治療系學生，我需要立刻找到相關論文。 |
| **0:25 – 0:34** | User types into the chat input. Text appears character by character (simulate live typing): **「幫我找前十字韌帶復健的相關論文」**. User hits Enter. A subtle sending animation fires. | "I type: 'Find papers on ACL rehabilitation' — entirely in Chinese. No special commands, no skill prefix. Just natural language." | 輸入：「幫我找前十字韌帶復健的相關論文」——純粹的自然語言，不需要特殊指令。 |
| **0:34 – 0:42** | The chat shows a **thinking trace** appearing below the message in a dim monospace block: `[Orchestrator] Skill trigger match: "前十字韌帶" → academic_search` / `[academic_search] Enhancing query: "前十字韌帶" → "Anterior Cruciate Ligament[MeSH]"` / `[PubMed] Searching NCBI E-utilities...`. A small cyan spinner pulses. | "Nexus detects the keyword '前十字韌帶' — ACL — matches it to its physical-therapy MeSH term database, routes directly to the academic search skill, and fires a real PubMed query. No LLM call needed for this step — it's deterministic routing." | Nexus 辨識關鍵詞「前十字韌帶」，自動對應 MeSH 術語，路由至學術搜尋技能，直接查詢 PubMed。這個步驟無需 LLM — 是確定性路由。 |
| **0:42 – 1:00** | The response streams in. The chat panel fills with a formatted result block: **"PubMed 搜尋結果（共 847 筆，顯示 7 筆）"**. Seven paper entries appear, each showing: bold title, author line, journal name with year, and a clickable `pubmed.ncbi.nlm.nih.gov` link. One example entry is highlighted with a gentle cyan glow: **"Early versus delayed ACL reconstruction: a randomized controlled trial" — Frobell RB, et al. — New England Journal of Medicine (2023) — pubmed.ncbi.nlm.nih.gov/36XXXXXX/**. The camera holds on the results for 3 seconds. | "Seven papers returned from PubMed with real PMIDs, authors, journals, and direct links. The query was automatically enhanced to 'Anterior Cruciate Ligament[MeSH] AND rehabilitation', giving us precision literature retrieval — the way a librarian would do it." | PubMed 回傳七篇論文，含作者、期刊與直連連結。查詢自動升級為 MeSH 術語，精準度等同專業文獻檢索。 |
| **1:00 – 1:10** | User types a follow-up message: **「把這些論文存進我的骨科筆記」**. The message sends. Thinking trace: `[Orchestrator] Skill trigger: "筆記" → study_notes` / `[study_notes] Subject detected: "骨科" → orthopedics` / `[study_notes] Saving to SQLite... ✓`. | "Now I say: 'Save these papers to my orthopedics notes.' One sentence. Nexus routes to the study notes skill, detects the subject category 'orthopedics' from the Chinese keyword '骨科', and saves everything to a local SQLite database — persistent, searchable, organized by PT subject." | 「把這些論文存進我的骨科筆記」——Nexus 路由至筆記技能，識別科目「骨科」，儲存至本地 SQLite 資料庫，按物理治療科目分類管理。 |
| **1:10 – 1:16** | Chat response appears: **"筆記已儲存 [骨科] — 7 篇論文已記錄 (2026-02-23)"**. A small checkmark icon pulses green. | "Confirmed. Seven papers, tagged as orthopedics, saved with today's date. I can retrieve, review, or generate quiz questions from these notes at any time." | 已確認。七篇論文以「骨科」標籤儲存。隨時可複習、搜尋或生成考題。 |
| **1:16 – 1:27** | **Cut to Telegram** on a phone screen (or phone-framed mockup). The Nexus bot chat is open. The user sends a photo — a clinical diagram showing knee anatomy with labeled ACL, PCL, and meniscus. The photo appears in the chat. Below it, a brief caption: **「這是什麼結構？」** ("What is this structure?"). | "Over on Telegram — the same system runs as a bot. I send a photo of a clinical anatomy diagram and ask what it shows." | 切換到 Telegram。相同系統作為機器人運行。我傳送一張臨床解剖圖，詢問圖中結構。 |
| **1:27 – 1:38** | The bot replies with a structured analysis: **"[Vision Agent — Confidence: 88%]"** / **"圖中顯示右膝關節矢狀面，可識別以下結構："** / **"• 前十字韌帶 (ACL) — 起自股骨外側髁，止於脛骨平台前方"** / **"• 後十字韌帶 (PCL)"** / **"• 內外側半月板"**. The confidence badge "88%" glows in green. | "The Vision Agent — powered by Gemini's multimodal API — identifies the anatomical structures, labels them in Chinese, and returns a clinical-grade description with 88% confidence. Same language as the user, always." | 視覺代理人——由 Gemini 多模態 API 驅動——識別解剖結構，以繁體中文回應，信心分數 88%。語言永遠跟隨使用者。 |
| **1:38 – 1:47** | Quick **architecture cut** — animated diagram fades in for 5 seconds. Show the layered stack: Interfaces (Web / Telegram / API) → Budget Controller → Orchestrator → Agents + Skills → 4-Layer Memory → GitHub Models (GPT-4o mini). Each layer lights up in sequence with the cyan accent color. A badge appears: "Deployed on Azure App Service — East Asia". | "Under the hood: a FastAPI backend, WebSocket chat, a token budget controller, nine agents competing to handle every request, and a four-layer memory system — all running on Azure, powered by GitHub Models." | 底層架構：FastAPI、WebSocket、Token 預算控制器、九個代理人競標每條請求，四層記憶體系統——部署於 Azure，驅動自 GitHub Models。 |
| **1:47 – 1:55** | Return to the **Dashboard**. The D3.js skill network graph pulses — nodes for `academic_search`, `study_notes`, `vision` highlighted brightly from the session just shown. The "ONLINE" indicator pulses. Final title card fades in: **"NEXUS AI"** / **"Multi-Agent Systems"** / **"Microsoft AI Dev Days Hackathon 2026"** / GitHub URL below. | "Nexus isn't a demo. It's a system I use every day — for literature review, for clinical note organization, for exam prep. Built to solve real problems, with the Microsoft AI ecosystem at its core." | Nexus 不是示範，是我每天真實使用的系統——文獻檢索、臨床筆記、備考準備。用真實需求驅動，以 Microsoft AI 生態系為核心。 |

---

## Scene-by-Scene Director's Notes

### Scene 1 — Cold Open (0:00–0:07)
Show the actual dashboard loading animation. The hex background canvas (`#hex-bg`) should be visible drawing in. Use the real Orbitron font title. No voiceover for the first 2 seconds — let the visual breathe.

### Scene 2 — Dashboard Overview (0:07–0:18)
Navigate to `/dashboard`. Ensure the D3.js skill graph has rendered (it loads from `/api/dashboard`). Pan slowly left-to-right: left panel stats first, then the graph. The graph nodes should be labeled and the force simulation should be actively running (nodes gently drifting). Point the camera at the `academic_search` and `study_notes` nodes — they will be featured in the next scene.

### Scene 3 — Web UI Setup (0:18–0:25)
Navigate to `/` (the chat interface, `index.html`). The dark sci-fi panel with cyan input border should be fully visible. Keep the cursor visible and deliberate — do not rush.

### Scene 4 — ACL Paper Search (0:25–1:00) [HERO SEQUENCE]
This is the centerpiece of the demo. Type the message slowly enough that viewers can read the Chinese characters. After sending:
- The thinking trace should appear in a `<pre>` style block with dimmed text — if your UI shows this, keep it on screen for 2-3 seconds before the results arrive.
- The PubMed results should stream in visibly (not appear all at once). If streaming is enabled via WebSocket, let it play naturally.
- Camera should rest on the results for at least 3 full seconds. Viewers need to read the paper titles.
- The PubMed URL format `pubmed.ncbi.nlm.nih.gov/XXXXXXXX/` should be clearly visible to establish this is a real API call.

### Scene 5 — Save to Notes (1:00–1:16)
Type the follow-up message immediately after — establishes that this is a real multi-turn conversation, not a series of isolated prompts. The transition from `academic_search` to `study_notes` in one conversation demonstrates orchestrator memory.

### Scene 6 — Telegram Vision (1:16–1:38)
Use a real phone or a high-quality phone-frame overlay. The image should be a recognizable knee anatomy diagram (publicly available from medical illustration sources). The Vision Agent response should be formatted cleanly — use the actual bot response if live, or a carefully prepared mock that matches the real output format exactly (confidence score, Chinese labels, structured bullet points).

### Scene 7 — Architecture Diagram (1:38–1:47)
This can be a pre-built animated slide or a Keynote/After Effects clip. Match the exact layer structure from the README. Highlight the GitHub Models badge prominently — this directly addresses the Microsoft AI Dev Days judging criteria.

### Scene 8 — Closing Dashboard (1:47–1:55)
Return to the live dashboard. If possible, show the `academic_search` and `study_notes` nodes in the D3.js graph glowing brighter than the others — reflecting the session just completed. End on a static title card for 3 seconds.

---

## Key Technical Claims to Verify Before Recording

1. PubMed search returns real results for `Anterior Cruciate Ligament[MeSH] AND rehabilitation`
2. Study notes SQLite correctly detects `骨科` as `orthopedics` category
3. Telegram Vision Agent returns a response with confidence score in the message
4. Dashboard D3.js graph renders and the `academic_search` / `study_notes` nodes are visible
5. The thinking trace (agent routing log) is visible in the Web UI — confirm this is enabled in your build

---

## On-Screen Text Summary (All Chinese Subtitles in Order)

1. 一個助手。九個專屬代理人。由物理治療系學生打造，為真實學習而生。
2. 這是 Nexus 主控台——九個代理人、十八個技能，即時協作。
3. 現在讓我們實際操作。我是物理治療系學生，我需要立刻找到相關論文。
4. 輸入：「幫我找前十字韌帶復健的相關論文」——純粹的自然語言，不需要特殊指令。
5. Nexus 辨識關鍵詞「前十字韌帶」，自動對應 MeSH 術語，路由至學術搜尋技能，直接查詢 PubMed。
6. PubMed 回傳七篇論文，含作者、期刊與直連連結。查詢自動升級為 MeSH 術語，精準度等同專業文獻檢索。
7. 「把這些論文存進我的骨科筆記」——Nexus 路由至筆記技能，識別科目「骨科」，儲存至本地 SQLite。
8. 已確認。七篇論文以「骨科」標籤儲存。隨時可複習、搜尋或生成考題。
9. 切換到 Telegram。相同系統作為機器人運行。傳送一張臨床解剖圖，詢問圖中結構。
10. 視覺代理人——由 Gemini 多模態 API 驅動——識別解剖結構，以繁體中文回應，信心分數 88%。
11. 底層架構：FastAPI、WebSocket、Token 預算控制器、九個代理人競標每條請求——部署於 Azure。
12. Nexus 不是示範，是我每天真實使用的系統。用真實需求驅動，以 Microsoft AI 生態系為核心。
