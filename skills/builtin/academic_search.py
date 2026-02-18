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
    "膝關節": "Knee Joint[MeSH]",
    "肩關節": "Shoulder Joint[MeSH]",
    "腰痛": "Low Back Pain[MeSH]",
    "low back pain": "Low Back Pain[MeSH]",
}


class AcademicSearchSkill(BaseSkill):
    name = "academic_search"
    description = "學術論文搜尋 — PubMed、Semantic Scholar、OpenAlex（免費，物理治療專用）"
    triggers = [
        "論文", "paper", "期刊", "journal", "pubmed", "研究", "文獻",
        "學術", "academic", "physical therapy", "物理治療", "文獻搜尋",
        "semantic scholar", "openalex",
    ]
    category = "academic"
    requires_llm = False

    instructions = (
        "學術搜尋：\n"
        "1. PubMed：「論文 physical therapy stroke」\n"
        "2. Semantic Scholar：「論文 semantic scholar knee rehabilitation」\n"
        "3. 自動增強 PT 相關 MeSH 術語"
    )

    async def execute(self, query: str, context: dict[str, Any]) -> SkillResult:
        # Clean query
        for t in self.triggers:
            query = query.replace(t, "").strip()
        query = query.strip()

        if not query or len(query) < 2:
            return SkillResult(
                content="請提供搜尋關鍵字，例如：「論文 physical therapy stroke rehabilitation」",
                success=False, source=self.name,
            )

        text_lower = query.lower()

        # Decide which database to search
        if "semantic scholar" in text_lower or "s2" in text_lower:
            query = query.replace("semantic scholar", "").replace("s2", "").strip()
            return await self._search_semantic_scholar(query)
        elif "openalex" in text_lower:
            query = query.replace("openalex", "").strip()
            return await self._search_openalex(query)
        else:
            # Default: PubMed (best for PT/medical)
            return await self._search_pubmed(query)

    async def _search_pubmed(self, query: str) -> SkillResult:
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

                return SkillResult(content="\n".join(lines), success=True, source=self.name)

        except Exception as e:
            return SkillResult(content=f"PubMed 搜尋失敗: {e}", success=False, source=self.name)

    async def _search_semantic_scholar(self, query: str) -> SkillResult:
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

            return SkillResult(content="\n".join(lines), success=True, source=self.name)

        except Exception as e:
            return SkillResult(content=f"Semantic Scholar 搜尋失敗: {e}", success=False, source=self.name)

    async def _search_openalex(self, query: str) -> SkillResult:
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
