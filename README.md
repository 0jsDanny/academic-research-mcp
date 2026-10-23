# 🔬 Academic Research & Sci-Hub MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Model Context Protocol](https://img.shields.io/badge/Protocol-MCP%202024--11--05-green.svg)](https://modelcontextprotocol.io/)
[![FastMCP](https://img.shields.io/badge/FastMCP-v1.3-orange.svg)](https://github.com/modelcontextprotocol/python-sdk)

> **Empower AI agents to conduct real-world academic literature reviews, citation snowballing, and multi-tiered full-text PDF retrieval.**

Unlike basic academic search tools that only perform rudimentary keyword matching, **Academic Research MCP** simulates how human researchers actually conduct literature reviews: multi-database screening, citation ranking, backward and forward citation chaining (*snowballing*), and dual-tier full-text retrieval (Sci-Hub + Open Access fallbacks).

---

## 📑 Table of Contents

- [Why This Server?](#-why-this-server)
- [Architecture & Workflow](#-architecture--workflow)
- [Databases Covered](#-databases-covered)
- [Available MCP Tools](#-available-mcp-tools)
- [Installation & Quickstart](#-installation--quickstart)
- [Configuration Guides](#-configuration-guides)
  - [Google Antigravity IDE](#google-antigravity-ide)
  - [Claude Desktop](#claude-desktop)
  - [Cursor IDE](#cursor-ide)
- [Environment Variables](#-environment-variables)
- [Usage Examples](#-usage-examples)
- [License & Disclaimer](#-license--disclaimer)

---

## 💡 Why This Server?

Standard academic tools and simple MCP servers suffer from four critical flaws:
1. **Arbitrary Ranking**: They return results sorted only by raw textual query matching, omitting foundational papers with thousands of citations.
2. **Missing Citations (Snowballing)**: Real researchers never rely on keywords alone; they follow citation graphs (*backward references* and *forward citing works*).
3. **The 2021 Sci-Hub Freeze**: The Sci-Hub repository has limited updates for papers published between 2021 and 2026. Without legal Open Access fallbacks (Unpaywall, Europe PMC), recent papers fail to resolve.
4. **Blind Spots**: They ignore regional literature (e.g., Latin American public health in **SciELO**) and cutting-edge **Preprints** (**medRxiv**, **bioRxiv**, **arXiv**).

**Academic Research MCP** solves all of these.

---

## 🏛 Architecture & Workflow

```
                        [ USER / AI AGENT ]
                                 │
                                 ▼
                     1. MULTI-DATABASE SCREENING
       ┌─────────────────────────┼─────────────────────────┐
       ▼                         ▼                         ▼
   Europe PMC / PubMed         SciELO            Preprint Repositories
   (Global Health / Bio)   (Latin America / SUS)  (bioRxiv, medRxiv, arXiv)
       │                         │                         │
       └─────────────────────────┼─────────────────────────┘
                                 ▼
                     2. SEMINAL SELECTION (Top Cited)
                                 │
                                 ▼
                     3. CITATION SNOWBALLING
              ┌──────────────────┴──────────────────┐
              ▼                                     ▼
     get_paper_references                  get_paper_citations
   (Backward: Foundational)              (Forward: State of the Art)
              │                                     │
              └──────────────────┬──────────────────┘
                                 ▼
                     4. DUAL-TIER PDF RESOLUTION
              ┌──────────────────┴──────────────────┐
              ▼                                     ▼
        Sci-Hub Mirror                        Open Access
     (Paywalled Publishers:              (Unpaywall / Repositories:
   Elsevier, Springer, Wiley)                Recent & Open Works)
              └──────────────────┬──────────────────┘
                                 ▼
                        download_scihub_pdf
                     (Direct binary download)
```

---

## 🌐 Databases Covered

| Source | Scope | Key Strengths |
| :--- | :--- | :--- |
| **Europe PMC / PubMed** | Biomedical & Health | 45M+ abstracts, PMC full text, citation counts, MeSH terms. |
| **OpenAlex** | All Academic Sciences | 250M+ works, global citation graphs, institution and author links. |
| **SciELO** | Latin America & Brazil | Regional epidemiology, public health (DATASUS, Fiocruz, CSP). |
| **Preprint Servers** | bioRxiv, medRxiv, arXiv | Cutting-edge 2024–2026 pre-prints before peer-reviewed journal release. |
| **Sci-Hub** | Subscription Journals | Automated TLS spoofing via `curl_cffi` to bypass paywalls and bot challenges. |
| **Unpaywall** | Legal Open Access | Institutional repository manuscripts, green/gold OA for recent publications. |

---

## 🛠 Available MCP Tools

### 1. `search_academic_papers`
Unified search engine with citation ranking and automated PDF resolution.
* **Arguments**:
  * `query` *(string, required)*: Keywords or topic.
  * `num_results` *(integer, default: 10)*: Max records to return (up to 50).
  * `sort_by` *(string, default: "citations")*: `"citations"` (most cited first), `"relevance"`, or `"date"`.
  * `database` *(string, default: "europe_pmc")*: `"europe_pmc"`, `"openalex"`, `"scielo"`, `"preprints"`, `"biorxiv"`, `"medrxiv"`, `"arxiv"`.
  * `year_min` / `year_max` *(integer, optional)*: Filter publication range (e.g., `2021`).

### 2. `search_scielo_latin_america`
Specialized search for Latin American and Brazilian literature.
* **Arguments**:
  * `query` *(string, required)*: Term in Portuguese, Spanish, or English.
  * `num_results` *(integer, default: 10)*: Number of papers.
  * `sort_by` *(string, default: "citations")*: `"citations"` or `"relevance"`.

### 3. `search_preprints_database`
Direct search for unpublished and pre-print research.
* **Arguments**:
  * `query` *(string, required)*: Search query.
  * `repository` *(string, default: "all")*: `"all"`, `"medrxiv"`, `"biorxiv"`, or `"arxiv"`.
  * `num_results` *(integer, default: 10)*: Number of papers.
  * `sort_by` *(string, default: "date")*: `"date"` (newest first) or `"citations"`.

### 4. `get_paper_citations` (*Forward Snowballing*)
Discovers subsequent breakthroughs and debates that cited a given paper.
* **Arguments**:
  * `doi` *(string, required)*: Target paper DOI.
  * `num_results` *(integer, default: 10)*: Max citing papers to return.

### 5. `get_paper_references` (*Backward Snowballing*)
Recovers foundational methodologies and classical works cited in the paper.
* **Arguments**:
  * `doi` *(string, required)*: Target paper DOI.
  * `num_results` *(integer, default: 10)*: Max cited references to return.

### 6. `search_scihub_by_doi`
Resolves direct PDF URL for any DOI via Sci-Hub with Open Access fallback.
* **Arguments**:
  * `doi` *(string, required)*: Target DOI.

### 7. `search_scihub_by_title`
Finds an article by exact or partial title, recovers its DOI, and resolves the PDF.
* **Arguments**:
  * `title` *(string, required)*: Article title.

### 8. `download_scihub_pdf`
Streams and writes the PDF file directly to local disk, verifying `%PDF` headers.
* **Arguments**:
  * `pdf_url` *(string, required)*: Direct PDF URL.
  * `output_path` *(string, required)*: Local file path (e.g. `C:/Users/User/Downloads/paper.pdf`).

### 9. `get_paper_tldr` (*Ai2 Asta / Semantic Scholar AI Summary*)
Retrieves a 1-sentence AI executive summary (TLDR) and influential citation count.
* **Arguments**:
  * `doi` *(string, required)*: Target paper DOI.

### 10. `get_similar_papers` (*ResearchRabbit-style Discovery*)
Finds semantically and co-citationally related papers starting from a seed paper.
* **Arguments**:
  * `doi` *(string, required)*: Seed paper DOI.
  * `num_results` *(integer, default: 10)*: Number of similar papers.

### 11. `export_papers_to_bibtex` (*Zotero & VOSviewer Integration*)
Exports official BibTeX citations for a list of DOIs into a `.bib` file for instant drag-and-drop into reference managers or network mapping tools.
* **Arguments**:
  * `dois` *(array of strings, required)*: List of DOIs.
  * `output_path` *(string, required)*: Local `.bib` destination path.

### 12. `generate_author_request_template` (*Direct Author Request*)
Generates a polite, ready-to-send email or ResearchGate message to the corresponding author when an article cannot be found in open repositories.
* **Arguments**:
  * `doi` *(string, required)*: Target paper DOI.
  * `language` *(string, default: "pt")*: `"pt"` or `"en"`.

---

## 🚀 Installation & Quickstart

### Prerequisites
* **Python 3.10+**
* [uv](https://astral.sh/uv) (recommended) or standard `pip`

### Using `uv` (Recommended)

Clone the repository and install dependencies in an isolated virtual environment:

```bash
git clone https://github.com/your-username/academic-research-mcp.git
cd academic-research-mcp

# Create environment and install
uv venv
uv pip install -e .
```

---

## ⚙ Configuration Guides

### Google Antigravity IDE

Add to `~/.gemini/config/mcp_config.json`:

```json
{
  "mcpServers": {
    "academic-scihub": {
      "command": "python",
      "args": [
        "-u",
        "/path/to/academic-research-mcp/src/academic_mcp/server.py"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1",
        "SCIHUB_BASE_URL": "https://sci-hub.ren",
        "SCIHUB_TIMEOUT_SECONDS": "10"
      }
    }
  }
}
```

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "academic-scihub": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/academic-research-mcp",
        "academic-mcp"
      ],
      "env": {
        "SCIHUB_BASE_URL": "https://sci-hub.ren"
      }
    }
  }
}
```

### Cursor IDE

Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "academic-scihub": {
      "command": "python",
      "args": ["-u", "/path/to/academic-research-mcp/src/academic_mcp/server.py"]
    }
  }
}
```

---

## 🔧 Environment Variables

| Variable | Default | Description |
| :--- | :--- | :--- |
| `SCIHUB_BASE_URL` | `https://sci-hub.ren` | Primary active mirror URL. |
| `SCIHUB_TIMEOUT_SECONDS` | `12` | Network request timeout per mirror. |
| `PYTHONUNBUFFERED` | `1` | Ensures immediate non-blocking stdio JSON-RPC transmission. |

---

## 🧪 Usage Examples

Run the complete workflow demo:

```bash
python examples/demo_workflow.py
```

Output:
```text
======================================================================
STEP 1: MULTI-DATABASE SCREENING
======================================================================
[Europe PMC] Top cited papers for: 'deforestation climate malaria amazon basin'
  1. Present and future arboviral threats (2010) | 1085 citations | DOI: 10.1016/j.antiviral.2009.10.008

[SciELO Latin America] Regional studies for: 'dengue brasil clima'
  - Leptospirosis: Puesta al día (2007) | DOI: 10.4067/s0716-10182007000300008

[Preprints (2025-2026)] Recent unpublished papers:
  - Modelling Malaria at the Human–Environment Interface in the Cross-Border Oiapoque Basin [Research Square] (2026)

======================================================================
STEP 2 & 3: CITATION SNOWBALLING FOR CORE PAPER
======================================================================
[Backward Snowballing] Foundational references:
  <- The Arboviruses: Epidemiology and Ecology (2019) | 1240 citations
[Forward Snowballing] Seminal papers citing this work later:
  -> Zika Virus (2016) | 1466 citations

======================================================================
STEP 4: FULL-TEXT RETRIEVAL & DOWNLOAD
======================================================================
Downloading from: https://sci.bban.top/pdf/10.1016/j.antiviral.2009.10.008.pdf#view=FitH
Download result: {'success': True, 'path': '.../sample_downloaded_paper.pdf', 'size_bytes': 2852792}
```

---

## 📄 License & Disclaimer

This project is licensed under the [MIT License](LICENSE).

**Disclaimer**: This tool is developed for educational, academic, and research purposes. Users are responsible for complying with copyright laws, publisher terms of service, and local intellectual property regulations.
