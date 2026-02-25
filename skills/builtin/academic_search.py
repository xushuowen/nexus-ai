"""Academic paper search skill - PubMed + Semantic Scholar + OpenAlex (all free)."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any

from nexus.skills.skill_base import BaseSkill, SkillResult


# PT-related MeSH terms for auto-enhancement
PT_MESH_TERMS = {
    "物理治療": "Physical Therapy Modalities[MeSH]",
    "physical therapy": "Physical Therapy Modalities[MeSH]",
    "physiotherapy": "Physical Therapy Modalities[MeSH]",
    "復健": "Rehabilitation[MeSH]",
    "rehabilitation": "Rehabilitation[MeSH]",
    "運動治療": "Exercise Therapy[MeSH]",
    "exercise therapy": "Exercise Therapy[MeSH]",
    "徒手治療": "Musculoskeletal Manipulations[MeSH]",
    "manual therapy": "Musculoskeletal Manipulations[MeSH]",
    "電療": "Electric Stimulation Therapy[MeSH]",
    "超音波": "Ultrasonic Therapy[MeSH]",
    "中風": "Stroke[MeSH]",
    "stroke": "Stroke[MeSH]",
    "骨科": "Orthopedics[MeSH]",
    # Knee
    "膝關節": "Knee Joint[MeSH]",
    "前十字韌帶": "Anterior Cruciate Ligament[MeSH]",
    "十字韌帶": "Anterior Cruciate Ligament[MeSH]",
    "ACL": "Anterior Cruciate Ligament[MeSH]",
    "acl": "Anterior Cruciate Ligament[MeSH]",
    "anterior cruciate ligament": "Anterior Cruciate Ligament[MeSH]",
    "後十字韌帶": "Posterior Cruciate Ligament[MeSH]",
    "PCL": "Posterior Cruciate Ligament[MeSH]",
    "pcl": "Posterior Cruciate Ligament[MeSH]",
    "半月板": "Menisci, Tibial[MeSH]",
    "meniscus": "Menisci, Tibial[MeSH]",
    "髕骨": "Patella[MeSH]",
    "patella": "Patella[MeSH]",
    "髂脛束": "Iliotibial Band Syndrome[MeSH]",
    # Shoulder
    "肩關節": "Shoulder Joint[MeSH]",
    "旋轉肌": "Rotator Cuff[MeSH]",
    "rotator cuff": "Rotator Cuff[MeSH]",
    "肩夾擠": "Shoulder Impingement Syndrome[MeSH]",
    # Spine
    "腰痛": "Low Back Pain[MeSH]",
    "low back pain": "Low Back Pain[MeSH]",
    "頸椎": "Cervical Vertebrae[MeSH]",
    "腰椎": "Lumbar Vertebrae[MeSH]",
    "椎間盤": "Intervertebral Disc[MeSH]",
    # Neuro
    "平衡": "Postural Balance[MeSH]",
    "balance": "Postural Balance[MeSH]",
    "步態": "Gait[MeSH]",
    "gait": "Gait[MeSH]",
    "本體感覺": "Proprioception[MeSH]",
    "proprioception": "Proprioception[MeSH]",
    "肌力": "Muscle Strength[MeSH]",
    "muscle strength": "Muscle Strength[MeSH]",
}


class AcademicSearchSkill(BaseSkill):
    name = "academic_search"
    description = "學術論文搜尋 — PubMed、Semantic Scholar、OpenAlex（免費，物理治療專用）"
    triggers = [
        "論文", "paper", "期刊", "journal", "pubmed", "研究", "文獻",
        "學術", "academic", "physical therapy", "物理治療", "文獻搜尋",
        "semantic scholar", "openalex", "前十字韌帶", "ACL", "acl",
        "半月板", "meniscus", "旋轉肌", "rotator cuff", "椎間盤",
        "找文獻", "找論文", "查論文", "查文獻", "搜論文",
    ]
    category = "academic"
    requires_llm = False

    instructions = (
        "學術搜尋：\n"
        "1. PubMed：「論文 physical therapy stroke」\n"
        "2. Semantic Scholar：「論文 semantic scholar knee rehabilitation」\n"
        "3. 自動增強 PT 相關 MeSH 術語\n"
        "4. 搜尋後可說「存到骨科筆記」儲存結果"
    )

    intent_patterns = [
        r"(找|查|搜).{0,5}(相關|有關|關於).{0,15}(論文|研究|文獻|期刊)",
        r"(有沒有|有什麼).{0,10}(研究|論文|文獻).{0,10}(關於|有關|針對)",
        r"(PubMed|pubmed|Semantic Scholar).{0,20}",
        r"(ACL|PCL|半月板|旋轉肌|椎間盤|前十字韌帶|後十字韌帶).{0,20}(研究|論文|文獻|復健|治療)",
        r"(物理治療|復健|PT).{0,10}(研究|論文|實證|evidence)",
    ]

    # Only these trigger words get stripped from the query (not medical terms)
    _STRIP_TRIGGERS = [
        "論文", "paper", "期刊", "journal", "pubmed", "文獻", "學術", "academic",
        "physical therapy", "物理治療", "文獻搜尋", "semantic scholar", "openalex",
        "找文獻", "找論文", "查論文", "查文獻", "搜論文",
    ]

    # Filler words to strip from query before searching
    _FILLER = ["查有關", "查一下", "找一下", "幫我找", "幫我查", "相關的", "相關",
               "有哪些", "有沒有", "的論文", "的期刊", "的研究", "的文獻",
               "查詢", "搜尋", "搜索", "查找", "資料"]

    # Save-to-notes action keywords
    _SAVE_TRIGGERS = ["存到", "存進", "儲存", "記錄", "加到", "加入", "save to", "save"]

    # Class-level cache: last search results per session
    _last_results: dict[str, list[dict]] = {}

    async def execute(self, query: str, context: dict[str, Any]) -> SkillResult:
        session_id = context.get("session_id", "default")
        raw_query = query

        # Check if this is a "save to notes" action
        if any(kw in raw_query for kw in self._SAVE_TRIGGERS) and any(
            kw in raw_query for kw in ["筆記", "note", "骨科", "notes"]
        ):
            return await self._save_to_notes(raw_query, session_id, context)

        # Clean query — remove routing triggers and filler words (medical terms kept)
        for t in self._STRIP_TRIGGERS:
            query = re.sub(re.escape(t), " ", query, flags=re.IGNORECASE)
        for f in self._FILLER:
            query = query.replace(f, " ")
        query = re.sub(r"\s+", " ", query).strip(" ?？，,。.、")

        if not query or len(query) < 2:
            return SkillResult(
                content="請提供搜尋關鍵字，例如：「論文 前十字韌帶 復健」",
                success=False, source=self.name,
            )

        text_lower = query.lower()

        # Decide which database to search
        if "semantic scholar" in text_lower or "s2" in text_lower:
            query = query.replace("semantic scholar", "").replace("s2", "").strip()
            result = await self._search_semantic_scholar(query, session_id)
        elif "openalex" in text_lower:
            query = query.replace("openalex", "").strip()
            result = await self._search_openalex(query, session_id)
        else:
            result = await self._search_pubmed(query, session_id)

        # Append save hint and return
        if result.success:
            result.content += "\n\n💡 輸入「存到骨科筆記」可將以上論文儲存至筆記系統。"
            # Store metadata for potential save action
            result.metadata["query"] = query
            result.metadata["session_id"] = session_id
        return result

    async def _save_to_notes(self, query: str, session_id: str, context: dict[str, Any]) -> SkillResult:
        """Save last search results to study_notes DB."""
        import sqlite3, time
        from nexus import config

        cached = self._last_results.get(session_id, [])
        if not cached:
            return SkillResult(
                content="找不到可儲存的論文。請先搜尋論文，再說「存到骨科筆記」。",
                success=False, source=self.name,
            )

        # Detect subject from query
        subject = "orthopedics"
        subject_map = {
            "骨科": "orthopedics", "復健": "rehabilitation", "神經": "neurology",
            "心肺": "cardiopulmonary", "小兒": "pediatrics", "老人": "geriatrics",
        }
        for kw, subj in subject_map.items():
            if kw in query:
                subject = subj
                break

        db_path = config.data_dir() / "study_notes.db"
        try:
            conn = sqlite3.connect(str(db_path))
            conn.execute("""CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL, chapter TEXT DEFAULT '',
                content TEXT NOT NULL, tags TEXT DEFAULT '',
                timestamp REAL NOT NULL, date TEXT NOT NULL)""")
            now = time.time()
            date_str = time.strftime("%Y-%m-%d")
            saved = 0
            for paper in cached:
                content = f"[論文] {paper.get('title', '')} | {paper.get('authors', '')} | {paper.get('journal', '')} {paper.get('year', '')} | {paper.get('url', paper.get('pmid', ''))}"
                conn.execute(
                    "INSERT INTO notes (subject, content, tags, timestamp, date) VALUES (?, ?, ?, ?, ?)",
                    (subject, content[:500], "論文,academic_search", now + saved * 0.001, date_str),
                )
                saved += 1
            conn.commit()
            conn.close()

            subject_zh = {"orthopedics": "骨科", "rehabilitation": "復健"}.get(subject, subject)
            return SkillResult(
                content=f"📚 已將 **{saved} 篇論文**儲存至「{subject_zh}」筆記！\n輸入「筆記 複習 骨科」可查看。",
                success=True, source=self.name,
            )
        except Exception as e:
            return SkillResult(content=f"儲存失敗：{e}", success=False, source=self.name)

    async def _search_pubmed(self, query: str, session_id: str = "default") -> SkillResult:
        """Search PubMed via E-utilities API (free, 3 req/sec)."""
        import httpx

        # Auto-enhance with MeSH terms
        enhanced_query = self._enhance_query(query)

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                # Step 1: Search for PMIDs
                search_resp = await client.get(
                    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                    params={
                        "db": "pubmed",
                        "term": enhanced_query,
                        "retmode": "json",
                        "retmax": 8,
                        "sort": "relevance",
                    },
                )
                search_data = search_resp.json()
                pmids = search_data.get("esearchresult", {}).get("idlist", [])
                total = search_data.get("esearchresult", {}).get("count", "0")

                if not pmids:
                    return SkillResult(
                        content=f"PubMed 搜尋「{query}」沒有找到結果。\n搜尋語法: {enhanced_query}",
                        success=True, source=self.name,
                    )

                # Step 2: Fetch article details
                fetch_resp = await client.get(
                    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
                    params={
                        "db": "pubmed",
                        "id": ",".join(pmids),
                        "retmode": "xml",
                        "rettype": "abstract",
                    },
                )

                articles = self._parse_pubmed_xml(fetch_resp.text)

                # Cache for save-to-notes action
                cache_items = []
                lines = [f"📚 **PubMed 搜尋結果**（共 {total} 筆，顯示 {len(articles)} 筆）\n"]
                for i, article in enumerate(articles, 1):
                    lines.append(f"**{i}. {article['title']}**")
                    if article.get("authors"):
                        lines.append(f"   👤 {article['authors']}")
                    if article.get("journal"):
                        lines.append(f"   📖 {article['journal']} ({article.get('year', '')})")
                    if article.get("pmid"):
                        lines.append(f"   🔗 https://pubmed.ncbi.nlm.nih.gov/{article['pmid']}/")
                    if article.get("abstract"):
                        lines.append(f"   📝 {article['abstract'][:150]}...")
                    lines.append("")
                    cache_items.append({
                        "title": article.get("title", ""),
                        "authors": article.get("authors", ""),
                        "journal": article.get("journal", ""),
                        "year": article.get("year", ""),
                        "pmid": article.get("pmid", ""),
                        "url": f"https://pubmed.ncbi.nlm.nih.gov/{article.get('pmid', '')}/",
                    })

                # Save to class cache
                AcademicSearchSkill._last_results[session_id] = cache_items

                return SkillResult(content="\n".join(lines), success=True, source=self.name)

        except Exception as e:
            return SkillResult(content=f"PubMed 搜尋失敗: {e}", success=False, source=self.name)

    async def _search_semantic_scholar(self, query: str, session_id: str = "default") -> SkillResult:
        """Search Semantic Scholar API (free, no key needed)."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://api.semanticscholar.org/graph/v1/paper/search",
                    params={
                        "query": query,
                        "limit": 8,
                        "fields": "title,authors,year,abstract,url,citationCount,openAccessPdf",
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            papers = data.get("data", [])
            total = data.get("total", 0)

            if not papers:
                return SkillResult(
                    content=f"Semantic Scholar 搜尋「{query}」沒有找到結果。",
                    success=True, source=self.name,
                )

            lines = [f"📚 **Semantic Scholar 搜尋結果**（共 {total:,} 筆）\n"]
            cache_items = []
            for i, paper in enumerate(papers, 1):
                title = paper.get("title", "Untitled")
                year = paper.get("year", "")
                citations = paper.get("citationCount", 0)
                authors = ", ".join(a.get("name", "") for a in paper.get("authors", [])[:3])
                pdf = paper.get("openAccessPdf", {})
                pdf_url = pdf.get("url", "") if pdf else ""

                lines.append(f"**{i}. {title}**")
                if authors:
                    lines.append(f"   👤 {authors}")
                lines.append(f"   📅 {year} | 📊 引用: {citations}")
                if paper.get("url"):
                    lines.append(f"   🔗 {paper['url']}")
                if pdf_url:
                    lines.append(f"   📄 PDF: {pdf_url}")
                lines.append("")
                cache_items.append({
                    "title": title, "authors": authors,
                    "year": str(year), "url": paper.get("url", ""),
                })

            AcademicSearchSkill._last_results[session_id] = cache_items
            return SkillResult(content="\n".join(lines), success=True, source=self.name)

        except Exception as e:
            return SkillResult(content=f"Semantic Scholar 搜尋失敗: {e}", success=False, source=self.name)

    async def _search_openalex(self, query: str, session_id: str = "default") -> SkillResult:
        """Search OpenAlex API (free, massive coverage)."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://api.openalex.org/works",
                    params={"search": query, "per_page": 8},
                )
                resp.raise_for_status()
                data = resp.json()

            works = data.get("results", [])
            total = data.get("meta", {}).get("count", 0)

            if not works:
                return SkillResult(
                    content=f"OpenAlex 搜尋「{query}」沒有找到結果。",
                    success=True, source=self.name,
                )

            lines = [f"📚 **OpenAlex 搜尋結果**（共 {total:,} 筆）\n"]
            cache_items = []
            for i, work in enumerate(works, 1):
                title = work.get("title", "Untitled")
                year = work.get("publication_year", "")
                cited = work.get("cited_by_count", 0)
                doi = work.get("doi", "")
                oa = work.get("open_access", {})
                oa_url = oa.get("oa_url", "") if oa else ""
                is_oa = oa.get("is_oa", False) if oa else False

                lines.append(f"**{i}. {title}**")
                lines.append(f"   📅 {year} | 📊 引用: {cited}" + (" | 🔓 Open Access" if is_oa else ""))
                if doi:
                    lines.append(f"   🔗 {doi}")
                if oa_url:
                    lines.append(f"   📄 PDF: {oa_url}")
                lines.append("")
                cache_items.append({
                    "title": title, "year": str(year), "url": doi or oa_url,
                })

            AcademicSearchSkill._last_results[session_id] = cache_items
            return SkillResult(content="\n".join(lines), success=True, source=self.name)

        except Exception as e:
            return SkillResult(content=f"OpenAlex 搜尋失敗: {e}", success=False, source=self.name)

    def _enhance_query(self, query: str) -> str:
        """Auto-enhance query with MeSH terms for PT-related searches."""
        query_lower = query.lower()
        for keyword, mesh in PT_MESH_TERMS.items():
            if keyword in query_lower:
                # Replace keyword with MeSH term for better PubMed results
                query = query_lower.replace(keyword, mesh, 1)
                return query
        return query

    def _parse_pubmed_xml(self, xml_text: str) -> list[dict[str, str]]:
        """Parse PubMed XML response into article dicts."""
        articles = []
        try:
            root = ET.fromstring(xml_text)
            for article_el in root.findall(".//PubmedArticle"):
                article = {}

                # PMID
                pmid_el = article_el.find(".//PMID")
                if pmid_el is not None:
                    article["pmid"] = pmid_el.text

                # Title
                title_el = article_el.find(".//ArticleTitle")
                if title_el is not None:
                    article["title"] = "".join(title_el.itertext()).strip()

                # Authors
                authors = []
                for author_el in article_el.findall(".//Author")[:3]:
                    last = author_el.findtext("LastName", "")
                    init = author_el.findtext("Initials", "")
                    if last:
                        authors.append(f"{last} {init}".strip())
                article["authors"] = ", ".join(authors) + (" et al." if len(article_el.findall(".//Author")) > 3 else "")

                # Journal
                journal_el = article_el.find(".//Journal/Title")
                if journal_el is not None:
                    article["journal"] = journal_el.text

                # Year
                year_el = article_el.find(".//PubDate/Year")
                if year_el is not None:
                    article["year"] = year_el.text

                # Abstract
                abstract_parts = []
                for abs_el in article_el.findall(".//AbstractText"):
                    text = "".join(abs_el.itertext()).strip()
                    if text:
                        abstract_parts.append(text)
                article["abstract"] = " ".join(abstract_parts)

                if article.get("title"):
                    articles.append(article)
        except ET.ParseError:
            pass
        return articles
