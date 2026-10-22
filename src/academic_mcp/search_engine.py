import logging
import os
import re
import urllib.parse
from typing import Any, Dict, List, Optional
import requests
import urllib3
from bs4 import BeautifulSoup

try:
    from curl_cffi import requests as curl_requests
except Exception:
    curl_requests = None

# Suppress HTTPS warnings for mirrors with broken certificate chains
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DEFAULT_SCIHUB_MIRROR = os.getenv("SCIHUB_BASE_URL", "https://sci-hub.ren").rstrip("/")
DEFAULT_TIMEOUT = float(os.getenv("SCIHUB_TIMEOUT_SECONDS", "12"))
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

logger = logging.getLogger("academic_mcp")


def _get_curl_session():
    """Build a session with browser TLS fingerprint impersonation to bypass Cloudflare/bot shields."""
    if curl_requests is not None:
        return curl_requests.Session(impersonate="chrome124")
    return requests.Session()


def _clean_doi(doi: str) -> str:
    """Normalize DOI string by stripping URL prefixes."""
    doi = (doi or "").strip()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)
    match = re.search(r"(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)", doi)
    return match.group(1) if match else doi


def _resolve_scihub_pdf(doi: str, mirror: str = DEFAULT_SCIHUB_MIRROR) -> Optional[str]:
    """Query active Sci-Hub mirror to resolve full-text PDF URL."""
    clean = _clean_doi(doi)
    session = _get_curl_session()
    headers = {"User-Agent": DEFAULT_USER_AGENT, "Referer": f"{mirror}/"}

    url = f"{mirror}/{clean}"
    try:
        resp = session.get(url, headers=headers, timeout=DEFAULT_TIMEOUT, verify=False)
        if resp.status_code != 200:
            return None

        # Content-type check
        ct = resp.headers.get("content-type", "").lower()
        if "application/pdf" in ct:
            return resp.url

        soup = BeautifulSoup(resp.text, "html.parser")
        for tag, attr in [("iframe", "src"), ("embed", "src"), ("object", "data"), ("a", "href")]:
            for el in soup.find_all(tag):
                val = el.get(attr)
                if val:
                    if val.startswith("//"):
                        return f"https:{val}"
                    if val.startswith("/"):
                        return urllib.parse.urljoin(mirror, val)
                    if "pdf" in val.lower():
                        return val

        # Fallback regex for direct link in scripts
        match = re.search(r"https?://[^\s\"'<>]+\.pdf[^\s\"'<>]*", resp.text, re.IGNORECASE)
        if match:
            return match.group(0)
    except Exception as e:
        logger.debug(f"Sci-Hub lookup failed for {clean}: {e}")
    return None


def _check_unpaywall_oa(doi: str) -> Optional[str]:
    """Fallback query to Unpaywall for legal Open Access versions (author manuscripts, institutional repos)."""
    try:
        clean = _clean_doi(doi)
        url = f"https://api.unpaywall.org/v2/{clean}?email=academic_research_mcp@gmail.com"
        resp = requests.get(url, timeout=6)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("is_oa"):
                best_loc = data.get("best_oa_location") or {}
                return best_loc.get("url_for_pdf") or best_loc.get("url")
    except Exception:
        pass
    return None


def search_europe_pmc(query: str, num_results: int = 10, sort_by: str = "citations") -> List[Dict[str, Any]]:
    """Search Europe PMC / PubMed database with citation sorting."""
    sort_param = "CITED desc" if sort_by == "citations" else ""
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    params = {
        "query": query,
        "format": "json",
        "pageSize": min(num_results, 50),
        "resultType": "core",
    }
    if sort_param:
        params["sort"] = sort_param

    results = []
    try:
        resp = requests.get(url, params=params, timeout=12)
        if resp.status_code == 200:
            items = resp.json().get("resultList", {}).get("result", [])
            for it in items:
                doi = it.get("doi")
                title = it.get("title", "").rstrip(".")
                citations = it.get("citedByCount", 0)
                year = it.get("pubYear", "")
                authors = it.get("authorString", "")
                is_oa = it.get("isOpenAccess", "N") == "Y"

                oa_url = None
                for url_item in it.get("fullTextUrlList", {}).get("fullTextUrl", []):
                    if url_item.get("documentStyle") == "pdf":
                        oa_url = url_item.get("url")
                        break

                results.append({
                    "title": title,
                    "author": authors,
                    "year": year,
                    "doi": doi,
                    "citations": citations,
                    "is_open_access": is_oa,
                    "oa_url": oa_url,
                    "source": "europe_pmc"
                })
    except Exception as e:
        logger.error(f"Europe PMC search failed: {e}")
    return results


def search_openalex(query: str, num_results: int = 10, sort_by: str = "citations", year_min: Optional[int] = None, year_max: Optional[int] = None) -> List[Dict[str, Any]]:
    """Search OpenAlex global academic catalog (250M+ works)."""
    sort_param = "cited_by_count:desc" if sort_by == "citations" else "relevance_score:desc"
    filter_parts = ["has_doi:true"]
    if year_min and year_max:
        filter_parts.append(f"publication_year:{year_min}-{year_max}")
    elif year_min:
        filter_parts.append(f"from_publication_date:{year_min}-01-01")
    elif year_max:
        filter_parts.append(f"to_publication_date:{year_max}-12-31")

    url = "https://api.openalex.org/works"
    params = {
        "search": query,
        "filter": ",".join(filter_parts),
        "sort": sort_param,
        "per-page": min(num_results, 50),
    }

    results = []
    try:
        headers = {"User-Agent": "academic-research-mcp/1.0 (mailto:academic_research_mcp@gmail.com)"}
        resp = requests.get(url, params=params, headers=headers, timeout=12)
        if resp.status_code == 200:
            for it in resp.json().get("results", []):
                raw_doi = it.get("doi", "")
                doi = _clean_doi(raw_doi) if raw_doi else ""
                title = it.get("title", "")
                citations = it.get("cited_by_count", 0)
                year = str(it.get("publication_year", ""))
                authors = ", ".join(a.get("author", {}).get("display_name", "") for a in it.get("authorships", []))
                oa_url = it.get("open_access", {}).get("oa_url")
                is_oa = it.get("open_access", {}).get("is_oa", False)

                results.append({
                    "title": title,
                    "author": authors,
                    "year": year,
                    "doi": doi,
                    "citations": citations,
                    "is_open_access": is_oa,
                    "oa_url": oa_url,
                    "source": "openalex"
                })
    except Exception as e:
        logger.error(f"OpenAlex search failed: {e}")
    return results


def search_scielo(query: str, num_results: int = 10, sort_by: str = "citations", year_min: Optional[int] = None, year_max: Optional[int] = None) -> List[Dict[str, Any]]:
    """Search Latin American and Brazilian journals indexed in SciELO."""
    sort_param = "cited_by_count:desc" if sort_by == "citations" else "relevance_score:desc"
    filter_parts = ["primary_location.source.publisher_lineage:P4310312277"]
    if year_min and year_max:
        filter_parts.append(f"publication_year:{year_min}-{year_max}")
    elif year_min:
        filter_parts.append(f"from_publication_date:{year_min}-01-01")
    elif year_max:
        filter_parts.append(f"to_publication_date:{year_max}-12-31")

    url = "https://api.openalex.org/works"
    params = {
        "search": query,
        "filter": ",".join(filter_parts),
        "sort": sort_param,
        "per-page": min(num_results, 50),
    }

    results = []
    try:
        headers = {"User-Agent": "academic-research-mcp/1.0 (mailto:academic_research_mcp@gmail.com)"}
        resp = requests.get(url, params=params, headers=headers, timeout=12)
        if resp.status_code == 200:
            for it in resp.json().get("results", []):
                raw_doi = it.get("doi", "")
                doi = _clean_doi(raw_doi) if raw_doi else ""
                title = it.get("title", "")
                citations = it.get("cited_by_count", 0)
                year = str(it.get("publication_year", ""))
                authors = ", ".join(a.get("author", {}).get("display_name", "") for a in it.get("authorships", []))
                oa_url = it.get("open_access", {}).get("oa_url")

                results.append({
                    "title": title,
                    "author": authors,
                    "year": year,
                    "doi": doi,
                    "citations": citations,
                    "is_open_access": True,
                    "oa_url": oa_url,
                    "source": "scielo"
                })
    except Exception as e:
        logger.error(f"SciELO search failed: {e}")
    return results


def search_preprints(query: str, repository: str = "all", num_results: int = 10, sort_by: str = "date", year_min: Optional[int] = None) -> List[Dict[str, Any]]:
    """Search preprints across bioRxiv, medRxiv, arXiv, or all preprint repositories."""
    source_map = {
        "arxiv": "S4306400194",
        "biorxiv": "S4306402567",
        "medrxiv": "S3005729997",
    }
    repo_key = repository.lower().strip()
    filter_parts = []
    if repo_key in source_map:
        filter_parts.append(f"locations.source.id:{source_map[repo_key]}")
    else:
        filter_parts.append("type:preprint")

    if year_min:
        filter_parts.append(f"from_publication_date:{year_min}-01-01")

    sort_param = "publication_year:desc,publication_date:desc" if sort_by == "date" else "cited_by_count:desc"
    url = "https://api.openalex.org/works"
    params = {
        "search": query,
        "filter": ",".join(filter_parts),
        "sort": sort_param,
        "per-page": min(num_results, 50),
    }

    results = []
    try:
        headers = {"User-Agent": "academic-research-mcp/1.0 (mailto:academic_research_mcp@gmail.com)"}
        resp = requests.get(url, params=params, headers=headers, timeout=12)
        if resp.status_code == 200:
            for it in resp.json().get("results", []):
                raw_doi = it.get("doi", "")
                doi = _clean_doi(raw_doi) if raw_doi else ""
                title = it.get("title", "")
                citations = it.get("cited_by_count", 0)
                year = str(it.get("publication_year", ""))
                authors = ", ".join(a.get("author", {}).get("display_name", "") for a in it.get("authorships", []))
                oa_url = it.get("open_access", {}).get("oa_url")
                src_name = it.get("primary_location", {}).get("source", {}).get("display_name", "Preprint")

                results.append({
                    "title": title,
                    "author": authors,
                    "year": year,
                    "doi": doi,
                    "citations": citations,
                    "repository": src_name,
                    "is_open_access": True,
                    "oa_url": oa_url,
                    "source": "preprints"
                })
    except Exception as e:
        logger.error(f"Preprint search failed: {e}")
    return results


def resolve_paper_access(doi: str, known_oa_url: Optional[str] = None) -> Dict[str, Any]:
    """Resolve full-text PDF using multi-tiered strategy (Direct OA -> Sci-Hub -> Repository Fallback -> Unpaywall)."""
    clean = _clean_doi(doi)
    if not clean:
        return {"doi": doi, "status": "error", "error": "Invalid DOI"}

    # 1. Direct verified PDF URL if ending in .pdf
    if known_oa_url and known_oa_url.lower().split("?")[0].endswith(".pdf"):
        return {
            "doi": clean,
            "status": "success",
            "pdf_url": known_oa_url,
            "source_type": "open_access",
            "provider": "direct_oa"
        }

    # 2. Sci-Hub mirror (bypasses paywalls and delivers official publisher PDF)
    scihub_url = _resolve_scihub_pdf(clean)
    if scihub_url:
        return {
            "doi": clean,
            "status": "success",
            "pdf_url": scihub_url,
            "source_type": "scihub",
            "provider": DEFAULT_SCIHUB_MIRROR
        }

    # 3. Known Open Access / repository landing page
    if known_oa_url:
        return {
            "doi": clean,
            "status": "success",
            "pdf_url": known_oa_url,
            "source_type": "open_access_repo",
            "provider": "repository_or_oa"
        }

    # 4. Fallback to Unpaywall
    oa_url = _check_unpaywall_oa(clean)
    if oa_url:
        return {
            "doi": clean,
            "status": "success",
            "pdf_url": oa_url,
            "source_type": "open_access_fallback",
            "provider": "unpaywall"
        }

    return {
        "doi": clean,
        "status": "not_found",
        "error": "PDF could not be resolved on Sci-Hub or Open Access repositories."
    }


def download_pdf(pdf_url: str, output_path: str) -> Dict[str, Any]:
    """Download full-text PDF stream to local storage and verify PDF integrity."""
    session = _get_curl_session()
    headers = {"User-Agent": DEFAULT_USER_AGENT, "Referer": "https://sci-hub.ren/"}

    dest = os.path.abspath(os.path.expanduser(output_path))
    os.makedirs(os.path.dirname(dest), exist_ok=True)

    try:
        resp = session.get(pdf_url, headers=headers, timeout=25, verify=False, stream=True)
        if resp.status_code >= 400:
            return {"success": False, "error": f"HTTP {resp.status_code}"}

        first_chunk = b""
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    if not first_chunk:
                        first_chunk = chunk
                    f.write(chunk)

        if not first_chunk.startswith(b"%PDF"):
            return {
                "success": False,
                "error": "Downloaded file is not a valid PDF binary.",
                "path": dest
            }

        return {
            "success": True,
            "path": dest,
            "size_bytes": os.path.getsize(dest),
            "source_url": pdf_url
        }
    except Exception as e:
        return {"success": False, "error": str(e), "path": dest}


def get_paper_citations(doi: str, num_results: int = 10) -> List[Dict[str, Any]]:
    """Forward Snowballing: retrieve top citing works."""
    clean = _clean_doi(doi)
    headers = {"User-Agent": "academic-research-mcp/1.0 (mailto:academic_research_mcp@gmail.com)"}
    try:
        work_resp = requests.get(f"https://api.openalex.org/works/https://doi.org/{clean}", headers=headers, timeout=12)
        if work_resp.status_code != 200:
            return []
        work_id = work_resp.json().get("id", "").split("/")[-1]
        if not work_id:
            return []

        cite_url = "https://api.openalex.org/works"
        params = {
            "filter": f"cites:{work_id}",
            "sort": "cited_by_count:desc",
            "per-page": min(num_results, 50),
        }
        resp = requests.get(cite_url, params=params, headers=headers, timeout=12)
        if resp.status_code != 200:
            return []

        items = []
        for w in resp.json().get("results", []):
            raw_doi = w.get("doi")
            items.append({
                "title": w.get("title"),
                "author": ", ".join(a.get("author", {}).get("display_name", "") for a in w.get("authorships", [])[:3]),
                "year": str(w.get("publication_year", "")),
                "citations": w.get("cited_by_count", 0),
                "doi": _clean_doi(raw_doi) if raw_doi else None,
                "oa_url": w.get("open_access", {}).get("oa_url"),
                "source": "forward_citation"
            })
        return items
    except Exception as e:
        logger.error(f"Failed to get paper citations: {e}")
        return []


def get_paper_references(doi: str, num_results: int = 10) -> List[Dict[str, Any]]:
    """Backward Snowballing: retrieve top foundational references cited by this work."""
    clean = _clean_doi(doi)
    headers = {"User-Agent": "academic-research-mcp/1.0 (mailto:academic_research_mcp@gmail.com)"}
    try:
        work_resp = requests.get(f"https://api.openalex.org/works/https://doi.org/{clean}", headers=headers, timeout=12)
        if work_resp.status_code != 200:
            return []
        ref_ids = [ref.split("/")[-1] for ref in work_resp.json().get("referenced_works", [])[:50]]
        if not ref_ids:
            return []

        filter_str = "|".join(ref_ids[:min(len(ref_ids), 25)])
        resp = requests.get(f"https://api.openalex.org/works?filter=openalex_id:{filter_str}&sort=cited_by_count:desc&per-page={min(num_results, 50)}", headers=headers, timeout=12)
        if resp.status_code != 200:
            return []

        items = []
        for w in resp.json().get("results", []):
            raw_doi = w.get("doi")
            items.append({
                "title": w.get("title"),
                "author": ", ".join(a.get("author", {}).get("display_name", "") for a in w.get("authorships", [])[:3]),
                "year": str(w.get("publication_year", "")),
                "citations": w.get("cited_by_count", 0),
                "doi": _clean_doi(raw_doi) if raw_doi else None,
                "oa_url": w.get("open_access", {}).get("oa_url"),
                "source": "backward_reference"
            })
        return items
    except Exception as e:
        logger.error(f"Failed to get paper references: {e}")
        return []
