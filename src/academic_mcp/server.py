import asyncio
import logging
import os
import sys
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP
from academic_mcp.search_engine import (
    download_pdf,
    get_paper_citations as _get_citations,
    get_paper_references as _get_references,
    resolve_paper_access,
    search_europe_pmc,
    search_openalex,
    search_preprints,
    search_scielo,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("academic_mcp_server")

mcp = FastMCP("academic_research_mcp")


@mcp.tool()
async def search_academic_papers(
    query: str,
    num_results: int = 10,
    sort_by: str = "citations",
    database: str = "europe_pmc",
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Search academic papers with citation ranking, multi-database support, and automated PDF resolution.

    Args:
        query: Search keywords or topic (e.g. 'climate change dengue equatorial humidity').
        num_results: Number of papers to return (default: 10, max: 50).
        sort_by: Ranking criteria ('citations' for most cited papers, or 'relevance'/'date').
        database: Primary database to query:
            - 'europe_pmc': PubMed + Europe PMC (best for health, medicine, biology).
            - 'openalex': Global academic catalog across all sciences (250M+ works).
            - 'scielo': SciELO network (Latin America, Brazil, public health).
            - 'preprints': All preprints (bioRxiv, medRxiv, arXiv, etc.).
            - 'biorxiv': Biology and genetics preprints.
            - 'medrxiv': Medical and public health preprints.
            - 'arxiv': Physics, computer science, and mathematical epidemiology.
        year_min: Filter papers published from this year onwards (e.g. 2020).
        year_max: Filter papers published up to this year (e.g. 2026).

    Returns:
        List of papers with title, author, year, citation count, DOI, and direct PDF URL if available.
    """
    def _do_search():
        db = database.lower().strip()
        if db == "openalex":
            items = search_openalex(query, num_results=num_results, sort_by=sort_by, year_min=year_min, year_max=year_max)
        elif db == "scielo":
            items = search_scielo(query, num_results=num_results, sort_by=sort_by, year_min=year_min, year_max=year_max)
        elif db in {"preprints", "biorxiv", "medrxiv", "arxiv"}:
            repo = "all" if db == "preprints" else db
            items = search_preprints(query, repository=repo, num_results=num_results, sort_by=sort_by, year_min=year_min)
        else:
            items = search_europe_pmc(query, num_results=num_results, sort_by=sort_by)

        for item in items:
            doi = item.get("doi")
            if doi or item.get("oa_url"):
                res = resolve_paper_access(doi or "", known_oa_url=item.get("oa_url"))
                if res.get("status") == "success":
                    item["pdf_url"] = res.get("pdf_url")
                    item["pdf_source"] = res.get("source_type")
                else:
                    item["pdf_url"] = item.get("oa_url")
                    item["pdf_source"] = "direct_oa" if item.get("oa_url") else "not_found"
        return items

    return await asyncio.to_thread(_do_search)


@mcp.tool()
async def search_scielo_latin_america(
    query: str,
    num_results: int = 10,
    sort_by: str = "citations",
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Search Latin American and Brazilian health and scientific literature indexed in SciELO.
    Ideal for DATASUS, public health, tropical medicine, and regional Brazilian epidemiology.

    Args:
        query: Search term in Portuguese, Spanish, or English.
        num_results: Number of papers to retrieve (default: 10).
        sort_by: 'citations' (most cited first) or 'relevance'.
    """
    return await search_academic_papers(
        query=query,
        num_results=num_results,
        sort_by=sort_by,
        database="scielo",
        year_min=year_min,
        year_max=year_max,
    )


@mcp.tool()
async def search_preprints_database(
    query: str,
    repository: str = "all",
    num_results: int = 10,
    sort_by: str = "date",
    year_min: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Search cutting-edge preprints from bioRxiv, medRxiv, and arXiv before peer-reviewed publication.

    Args:
        query: Topic keywords.
        repository: 'all', 'medrxiv', 'biorxiv', or 'arxiv'.
        num_results: Number of preprints to return.
        sort_by: 'date' (most recent first) or 'citations'.
        year_min: Minimum publication year (e.g. 2024).
    """
    return await search_academic_papers(
        query=query,
        num_results=num_results,
        sort_by=sort_by,
        database=repository if repository != "all" else "preprints",
        year_min=year_min,
    )


@mcp.tool()
async def search_scihub_by_doi(doi: str) -> Dict[str, Any]:
    """
    Resolve and retrieve a paper PDF from Sci-Hub or Open Access repositories using its DOI.

    Args:
        doi: The DOI string (e.g. '10.1016/j.antiviral.2009.10.008').
    """
    return await asyncio.to_thread(resolve_paper_access, doi)


@mcp.tool()
async def search_scihub_by_title(title: str) -> Dict[str, Any]:
    """
    Search a paper by exact or partial title, retrieve its DOI and resolve PDF.

    Args:
        title: Title of the academic article.
    """
    def _by_title():
        res = search_openalex(title, num_results=1, sort_by="relevance")
        if not res:
            res = search_europe_pmc(title, num_results=1, sort_by="relevance")
        if res and res[0].get("doi"):
            item = res[0]
            access = resolve_paper_access(item["doi"], known_oa_url=item.get("oa_url"))
            item.update(access)
            return item
        return {"status": "not_found", "error": f"No paper found matching title '{title}'"}

    return await asyncio.to_thread(_by_title)


@mcp.tool()
async def download_scihub_pdf(pdf_url: str, output_path: str) -> Dict[str, Any]:
    """
    Download paper PDF from Sci-Hub or Open Access URL directly to local storage.

    Args:
        pdf_url: Direct PDF URL obtained from search results.
        output_path: File path on disk to save the PDF.
    """
    return await asyncio.to_thread(download_pdf, pdf_url, output_path)


@mcp.tool()
async def get_paper_citations(doi: str, num_results: int = 10) -> List[Dict[str, Any]]:
    """
    Forward Snowballing: Get the most cited papers that cited this DOI.
    Enables tracking subsequent discoveries, debates, and advancements building on this paper.

    Args:
        doi: The DOI of the paper (e.g. '10.1016/j.antiviral.2009.10.008').
        num_results: Max number of citing papers to return (default: 10).
    """
    return await asyncio.to_thread(_get_citations, doi, num_results)


@mcp.tool()
async def get_paper_references(doi: str, num_results: int = 10) -> List[Dict[str, Any]]:
    """
    Backward Snowballing: Get the most influential papers referenced/cited by this DOI.
    Enables finding the foundational theoretical and methodological basis of this paper.

    Args:
        doi: The DOI of the paper (e.g. '10.1016/j.antiviral.2009.10.008').
        num_results: Max number of referenced papers to return (default: 10).
    """
    return await asyncio.to_thread(_get_references, doi, num_results)


@mcp.tool()
async def get_paper_tldr(doi: str) -> Dict[str, Any]:
    """
    Ai2 Asta / Semantic Scholar AI Summary: Get a single-sentence executive TLDR summary
    and influential citation metrics for a paper.

    Args:
        doi: The DOI of the target paper.
    """
    from academic_mcp.search_engine import get_paper_tldr as _tldr
    return await asyncio.to_thread(_tldr, doi)


@mcp.tool()
async def get_similar_papers(doi: str, num_results: int = 10) -> List[Dict[str, Any]]:
    """
    ResearchRabbit-style discovery: Find semantically and co-citationally related papers
    building on or complementing a seed paper.

    Args:
        doi: The DOI of the seed paper.
        num_results: Max number of related papers to return (default: 10).
    """
    from academic_mcp.search_engine import get_similar_papers as _similar
    return await asyncio.to_thread(_similar, doi, num_results)


@mcp.tool()
async def export_papers_to_bibtex(dois: List[str], output_path: str) -> Dict[str, Any]:
    """
    Zotero & VOSviewer Integration: Export official BibTeX citations for a list of DOIs
    directly into a .bib file. Ready to import into reference managers or bibliometric network tools.

    Args:
        dois: List of DOI strings to export.
        output_path: File path on disk (e.g. 'C:/Users/User/Downloads/my_library.bib').
    """
    from academic_mcp.search_engine import export_to_bibtex as _bibtex
    return await asyncio.to_thread(_bibtex, dois, output_path)


@mcp.tool()
async def generate_author_request_template(doi: str, language: str = "pt") -> Dict[str, Any]:
    """
    Direct Author Request Generator: When all automated routes fail to retrieve a paywalled paper,
    generates a polite, ready-to-send email or ResearchGate message to the corresponding author
    requesting a personal academic copy/preprint.

    Args:
        doi: The DOI of the target paper.
        language: 'pt' for Portuguese, 'en' for English.
    """
    from academic_mcp.search_engine import generate_author_request as _req
    return await asyncio.to_thread(_req, doi, language)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
