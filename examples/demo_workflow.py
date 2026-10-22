"""
Academic Research MCP - Example Real-World Literature Review Workflow
======================================================================
This script demonstrates the complete 4-step workflow:
1. Multi-database screening (Europe PMC, SciELO, Preprints).
2. Core seminal paper selection.
3. Snowballing (Forward citations & Backward references).
4. Full-text PDF resolution & download.
"""

import asyncio
import os
import sys

# Add src to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from academic_mcp.server import (
    download_scihub_pdf,
    get_paper_citations,
    get_paper_references,
    search_academic_papers,
    search_preprints_database,
    search_scielo_latin_america,
)


async def main():
    print("=" * 70)
    print("STEP 1: MULTI-DATABASE SCREENING")
    print("=" * 70)

    # 1.1 Global PubMed/Europe PMC query
    query = "deforestation climate malaria amazon basin"
    print(f"\n[Europe PMC] Top cited papers for: '{query}'")
    papers = await search_academic_papers(query, num_results=2, sort_by="citations", database="europe_pmc")
    for i, p in enumerate(papers, 1):
        print(f"  {i}. {p['title']} ({p['year']}) | {p['citations']} citations | DOI: {p['doi']}")

    # 1.2 Regional SciELO query
    print(f"\n[SciELO Latin America] Regional studies for: 'dengue brasil clima'")
    scielo_papers = await search_scielo_latin_america("dengue brasil clima", num_results=1, sort_by="citations")
    for p in scielo_papers:
        print(f"  - {p['title']} ({p['year']}) | DOI: {p['doi']}")

    # 1.3 Preprints query (bioRxiv, medRxiv, arXiv)
    print(f"\n[Preprints (2025-2026)] Recent unpublished papers:")
    preprints = await search_preprints_database("dengue climate brasil", num_results=1, sort_by="date")
    for p in preprints:
        print(f"  - {p['title']} [{p.get('repository')}] ({p['year']}) | DOI: {p['doi']}")

    if not papers:
        return

    top_paper = papers[0]
    doi = top_paper["doi"]

    print("\n" + "=" * 70)
    print(f"STEP 2 & 3: CITATION SNOWBALLING FOR CORE PAPER")
    print(f"Paper: {top_paper['title']}")
    print(f"DOI: {doi}")
    print("=" * 70)

    # Backward snowballing
    print("\n[Backward Snowballing] Foundational references cited by this paper:")
    refs = await get_paper_references(doi, num_results=2)
    for r in refs:
        print(f"  <- {r['title']} ({r['year']}) | {r['citations']} citations")

    # Forward snowballing
    print("\n[Forward Snowballing] Seminal papers that cited this work later:")
    cites = await get_paper_citations(doi, num_results=2)
    for c in cites:
        print(f"  -> {c['title']} ({c['year']}) | {c['citations']} citations")

    print("\n" + "=" * 70)
    print("STEP 4: FULL-TEXT RETRIEVAL & DOWNLOAD")
    print("=" * 70)
    if top_paper.get("pdf_url"):
        target_path = os.path.join(os.path.dirname(__file__), "sample_downloaded_paper.pdf")
        print(f"Downloading from: {top_paper['pdf_url']}")
        res = await download_scihub_pdf(top_paper["pdf_url"], target_path)
        print(f"Download result: {res}")


if __name__ == "__main__":
    asyncio.run(main())
