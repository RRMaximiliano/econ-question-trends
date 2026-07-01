from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import time
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "lib"))

from econqt_common import (  # noqa: E402
    clean_text,
    contact_email,
    get_json,
    load_yaml,
    normalize_doi,
    normalize_title,
    reconstruct_openalex_abstract,
    request_headers,
    source_text_quality_flag,
    strip_source_boilerplate,
)


CLASSIFICATION_COLUMNS = {
    "causal_predictive_category",
    "classification_confidence",
    "classification_reason",
    "causal_language_indicator",
    "predictive_language_indicator",
    "causal_language_terms",
    "predictive_language_terms",
    "classification_method",
    "classification_text_chars",
    "has_usable_classification_text",
}

NONRESEARCH_SCOPES = {"review_erratum_paratext", "comment_reply", "lecture_address"}
ENRICHMENT_STATUS_RANK = {
    "enriched": 60,
    "pdf_candidate": 50,
    "partial_short_text": 40,
    "not_found": 30,
    "rate_limited": 20,
    "error": 20,
    "skipped_nonresearch_scope": 10,
    "not_attempted_query_limit": 0,
    "not_cached": 0,
    "": 0,
}
METADATA_ABSTRACT_SOURCES = {
    "crossref",
    "econpapers",
    "openalex",
    "publisher_metadata",
    "semantic_scholar",
}
TIER_A_FORMAL_ABSTRACT = "tier_a_formal_abstract"
TIER_C_FIRST_PAGE_TEXT = "tier_c_first_page_abstract_or_intro"


def stable_key(*parts: Any) -> str:
    text = "|".join(clean_text(part) for part in parts)
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:24]


def text_chars(title: Any, abstract: Any) -> int:
    return len(" ".join(part for part in [clean_text(title), strip_source_boilerplate(abstract)] if part))


def infer_enrichment_evidence_tier(row: dict[str, Any] | pd.Series) -> str:
    explicit = clean_text(row.get("evidence_tier"))
    if explicit:
        return explicit

    status = clean_text(row.get("enrichment_status") or row.get("status"))
    abstract = clean_text(row.get("enriched_abstract") or row.get("abstract"))
    if status != "enriched" or not abstract:
        return ""

    source = clean_text(row.get("enrichment_source") or row.get("source"))
    detail = clean_text(row.get("enrichment_detail") or row.get("detail")).lower()
    if source == "oa_pdf_first_pages" or "pdf_text_first_pages" in detail or "source_text_type=first_pages" in detail:
        return TIER_C_FIRST_PAGE_TEXT
    if source in METADATA_ABSTRACT_SOURCES:
        return TIER_A_FORMAL_ABSTRACT
    return ""


def is_nonmissing(value: Any) -> bool:
    return clean_text(value) != ""


def candidate_rows(classified_df: pd.DataFrame, minimum_chars: int, candidate_category: str) -> pd.DataFrame:
    if "causal_predictive_category" not in classified_df.columns:
        raise ValueError("Missing causal_predictive_category column. Run classification before enrichment.")
    work = classified_df.copy().fillna("")
    if "classification_text_chars" in work.columns:
        chars = pd.to_numeric(work["classification_text_chars"], errors="coerce").fillna(0)
    else:
        chars = work.apply(lambda row: text_chars(row.get("title", ""), row.get("abstract", "")), axis=1)
    mask = work["causal_predictive_category"].astype(str).eq(candidate_category) | (chars < minimum_chars)
    out = work.loc[mask].copy()
    out["current_text_chars"] = chars.loc[mask].astype(int)
    out["current_abstract_chars"] = out["abstract"].astype(str).map(lambda value: len(clean_text(value))) if "abstract" in out else 0
    out["has_current_abstract"] = out["abstract"].astype(str).map(is_nonmissing) if "abstract" in out else False
    return out.reset_index(drop=True)


def prioritize_candidates(candidates: pd.DataFrame) -> pd.DataFrame:
    work = candidates.copy()
    work["_has_doi_sort"] = work["doi"].astype(str).map(lambda value: normalize_doi(value) != "") if "doi" in work else False
    work["_has_title_sort"] = work["title"].astype(str).map(is_nonmissing) if "title" in work else False
    work["_year_sort"] = pd.to_numeric(work.get("publication_year", ""), errors="coerce").fillna(0)
    work["_text_chars_sort"] = pd.to_numeric(work.get("current_text_chars", ""), errors="coerce").fillna(0)
    work = work.sort_values(
        ["_has_doi_sort", "_has_title_sort", "_year_sort", "_text_chars_sort"],
        ascending=[False, False, False, False],
    )
    return work.drop(columns=["_has_doi_sort", "_has_title_sort", "_year_sort", "_text_chars_sort"]).reset_index(drop=True)


def classify_article_scope(row: dict[str, Any], patterns: dict[str, list[str]] | None = None) -> tuple[str, str]:
    title = clean_text(row.get("title", "")).lower()
    article_type = clean_text(row.get("article_type", "")).lower()
    if article_type in {"paratext", "erratum", "review"}:
        return "review_erratum_paratext", f"article_type={article_type}"

    patterns = patterns or {}
    for scope, regexes in patterns.items():
        for pattern in regexes or []:
            if re.search(pattern, title, flags=re.IGNORECASE):
                return scope, f"title_pattern={pattern}"

    if not title:
        return "unknown", "missing_title"
    return "research_article", ""


class RepecMetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta: dict[str, list[str]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "meta":
            return
        attr_lookup = {clean_text(key).lower(): clean_text(value) for key, value in attrs if key}
        name = clean_text(attr_lookup.get("name") or attr_lookup.get("property")).lower()
        content = clean_text(attr_lookup.get("content"))
        if name and content:
            self.meta.setdefault(name, []).append(content)


def reject_repec_abstract_boilerplate(text: str) -> bool:
    text_lower = clean_text(text).lower()
    return (
        not text_lower
        or "no abstract is available" in text_lower
        or "no abstract available" in text_lower
        or text_lower.startswith("downloadable (with restrictions)! no abstract")
    )


def clean_repec_abstract(text: str) -> str:
    cleaned = clean_text(text)
    cleaned = re.sub(r"^downloadable(?:\s*\([^)]*\))?!\s*", "", cleaned, flags=re.IGNORECASE)
    return "" if reject_repec_abstract_boilerplate(cleaned) else cleaned


def repec_meta_values(html_text: str, names: list[str]) -> list[str]:
    parser = RepecMetaParser()
    try:
        parser.feed(html_text)
    except Exception:  # noqa: BLE001
        return []
    values: list[str] = []
    for name in names:
        values.extend(parser.meta.get(name.lower(), []))
    return values


def extract_econpapers_abstract(html_text: str) -> str:
    for value in repec_meta_values(html_text, ["citation_abstract", "description", "dc.description"]):
        abstract = clean_repec_abstract(value)
        if abstract:
            return abstract

    patterns = [
        r"<b>\s*Abstract\s*:?\s*</b>\s*(.*?)(?:<p>\s*<b>|<br>\s*<b>|</td>|<div|<p><a)",
        r"<strong>\s*Abstract\s*:?\s*</strong>\s*(.*?)(?:<p>\s*<strong>|<br>\s*<strong>|</td>|<div|<p><a)",
        r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, html_text, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        text = re.sub(r"<[^>]+>", " ", match.group(1))
        text = clean_repec_abstract(html.unescape(text))
        text_lower = text.lower()
        if text and not text_lower.startswith("econpapers:"):
            return text
    return ""


def strip_html_fragment(fragment: str) -> str:
    fragment = re.sub(r"<(script|style)\b.*?</\1>", " ", fragment, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", fragment)
    return clean_text(html.unescape(text))


def clean_publisher_metadata_abstract(text: str, *, title: Any = "") -> str:
    cleaned = clean_text(text)
    cleaned = re.sub(r"^abstract\s*:?\s*", "", cleaned, flags=re.IGNORECASE)
    lower = cleaned.lower()
    if not lower or "no abstract is available" in lower or "no abstract available" in lower:
        return ""

    title_norm = normalize_title(title)
    cleaned_norm = normalize_title(cleaned)
    if title_norm and cleaned_norm == title_norm:
        return ""
    if title_norm and lower.startswith(clean_text(title).lower()) and "published in volume" in lower:
        return ""
    if "published in volume" in lower and "abstract:" not in lower:
        return ""
    return cleaned


def extract_publisher_metadata_abstract(html_text: str, *, title: Any = "") -> str:
    section_patterns = [
        r'<section\b[^>]*class=["\'][^"\']*\babstract\b[^"\']*["\'][^>]*>(.*?)</section>',
        r'<div\b[^>]*class=["\'][^"\']*\babstract\b[^"\']*["\'][^>]*>(.*?)</div>',
    ]
    for pattern in section_patterns:
        match = re.search(pattern, html_text, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        abstract = clean_publisher_metadata_abstract(strip_html_fragment(match.group(1)), title=title)
        if abstract:
            return abstract

    direct_meta_names = [
        "citation_abstract",
        "dc.description",
        "dcterms.abstract",
        "description.abstract",
    ]
    for value in repec_meta_values(html_text, direct_meta_names):
        abstract = clean_publisher_metadata_abstract(value, title=title)
        if abstract:
            return abstract

    for value in repec_meta_values(html_text, ["description", "og:description", "twitter:description"]):
        match = re.search(r"\babstract\s*:\s*(.+)$", value, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        abstract = clean_publisher_metadata_abstract(match.group(1), title=title)
        if abstract:
            return abstract
    return ""


def extract_publisher_metadata_pdf_url(html_text: str, *, base_url: str = "") -> str:
    for value in repec_meta_values(html_text, ["citation_pdf_url", "citation_pdf", "dc.identifier"]):
        candidate = clean_text(value)
        if candidate and (candidate.lower().endswith(".pdf") or "/download" in candidate.lower()):
            return urljoin(base_url, candidate)

    for match in re.finditer(r'href=["\']([^"\']+)["\']', html_text, flags=re.IGNORECASE):
        candidate = clean_text(html.unescape(match.group(1)))
        if candidate and (candidate.lower().endswith(".pdf") or "/download" in candidate.lower()):
            return urljoin(base_url, candidate)
    return ""


def repec_candidate_urls(row: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    article_url = clean_text(row.get("article_url"))
    if "econpapers" in article_url.lower() or "repec" in article_url.lower():
        urls.append(article_url)

    doi = normalize_doi(row.get("doi"))
    journal_short = clean_text(row.get("journal_short")).lower()
    if journal_short == "jpe" and doi.startswith("10.1086/"):
        urls.append(f"https://ideas.repec.org/a/ucp/jpolec/doi{doi.replace('/', '-')}.html")

    deduped: list[str] = []
    for url in urls:
        if url and url not in deduped:
            deduped.append(url)
    return deduped


def publisher_metadata_candidate_urls(row: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    article_url = clean_text(row.get("article_url"))
    if "aeaweb.org/articles" in article_url.lower():
        urls.append(article_url)

    doi = normalize_doi(row.get("doi"))
    if doi.startswith("10.1257/"):
        urls.append(f"https://www.aeaweb.org/articles?id={quote(doi, safe='/.')}")
    if doi.startswith("10.7916/"):
        urls.append(f"https://academiccommons.columbia.edu/doi/{quote(doi.upper(), safe='/.')}")
    if doi.startswith("10.3982/"):
        urls.append(f"https://www.econometricsociety.org/doi/{quote(doi.upper(), safe='/.')}")

    deduped: list[str] = []
    for url in urls:
        if url and url not in deduped:
            deduped.append(url)
    return deduped


def response_cache_path(cache_dir: Path, source: str, key: str, suffix: str = "json") -> Path:
    return cache_dir / source / f"{key}.{suffix}"


def read_cached(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_cached(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)


def cached_json_request(
    *,
    cache_dir: Path,
    source: str,
    key: str,
    url: str,
    params: dict[str, Any] | None,
    timeout: int,
    sleep_seconds: float,
    refresh: bool,
    cached_only: bool = False,
) -> dict[str, Any]:
    cache_path = response_cache_path(cache_dir, source, key)
    if not refresh:
        cached = read_cached(cache_path)
        if cached is not None:
            cached["from_cache"] = True
            return cached
    if cached_only:
        return {"ok": False, "status_code": "", "url": url, "error": "not_cached", "from_cache": False, "not_cached": True}
    try:
        data, final_url = get_json(url, params or {}, source=source, timeout=timeout, sleep_seconds=sleep_seconds)
        payload = {"ok": True, "status_code": 200, "url": final_url, "data": data, "from_cache": False}
    except Exception as exc:  # noqa: BLE001
        payload = {"ok": False, "status_code": "", "url": url, "error": f"{type(exc).__name__}: {exc}", "from_cache": False}
        if sleep_seconds:
            time.sleep(sleep_seconds)
    write_cached(cache_path, payload)
    return payload


def cached_text_request(
    *,
    cache_dir: Path,
    source: str,
    key: str,
    url: str,
    timeout: int,
    sleep_seconds: float,
    refresh: bool,
    cached_only: bool = False,
) -> dict[str, Any]:
    import requests

    cache_path = response_cache_path(cache_dir, source, key, suffix="html.json")
    if not refresh:
        cached = read_cached(cache_path)
        if cached is not None:
            cached["from_cache"] = True
            return cached
    if cached_only:
        return {"ok": False, "status_code": "", "url": url, "content_type": "", "text": "", "error": "not_cached", "from_cache": False, "not_cached": True}
    try:
        headers = request_headers(source)
        headers["Accept"] = "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8"
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        payload = {
            "ok": response.ok,
            "status_code": response.status_code,
            "url": response.url,
            "content_type": response.headers.get("content-type", ""),
            "text": response.text if response.ok else "",
            "error": "" if response.ok else response.reason,
            "from_cache": False,
        }
    except Exception as exc:  # noqa: BLE001
        payload = {"ok": False, "status_code": "", "url": url, "content_type": "", "text": "", "error": f"{type(exc).__name__}: {exc}", "from_cache": False}
    if sleep_seconds:
        time.sleep(sleep_seconds)
    write_cached(cache_path, payload)
    return payload


def source_result(
    *,
    source: str,
    status: str,
    abstract: str = "",
    url: str = "",
    source_record_id: str = "",
    detail: str = "",
    oa_pdf_url: str = "",
    error: str = "",
    cached: bool = False,
) -> dict[str, Any]:
    return {
        "source": source,
        "status": status,
        "abstract": clean_text(abstract),
        "url": clean_text(url),
        "source_record_id": clean_text(source_record_id),
        "detail": clean_text(detail),
        "oa_pdf_url": clean_text(oa_pdf_url),
        "error": clean_text(error),
        "cached": bool(cached),
    }


def openalex_oa_pdf_url(work: dict[str, Any]) -> str:
    locations: list[dict[str, Any]] = []
    for key in ["best_oa_location", "primary_location"]:
        location = work.get(key)
        if isinstance(location, dict) and location:
            locations.append(location)
    locations.extend(location for location in work.get("locations") or [] if isinstance(location, dict))

    for location in locations:
        pdf_url = clean_text(location.get("pdf_url"))
        if pdf_url and location.get("is_oa") is True:
            return pdf_url
    open_access = work.get("open_access") or {}
    oa_url = clean_text(open_access.get("oa_url"))
    if oa_url.lower().endswith(".pdf"):
        return oa_url
    return ""


def fetch_openalex(row: dict[str, Any], *, cache_dir: Path, timeout: int, sleep_seconds: float, refresh: bool, cached_only: bool = False) -> dict[str, Any]:
    doi = normalize_doi(row.get("doi"))
    openalex_id = clean_text(row.get("openalex_id"))
    if openalex_id:
        work_id = openalex_id.rstrip("/").split("/")[-1]
        url = f"https://api.openalex.org/works/{work_id}"
        params: dict[str, Any] = {}
        key = stable_key("openalex", work_id)
    elif doi:
        url = "https://api.openalex.org/works"
        params = {"filter": f"doi:{doi}", "per-page": 1}
        key = stable_key("openalex", doi)
    else:
        return source_result(source="openalex", status="skipped", detail="missing_openalex_id_and_doi")

    payload = cached_json_request(
        cache_dir=cache_dir,
        source="openalex",
        key=key,
        url=url,
        params=params,
        timeout=timeout,
        sleep_seconds=sleep_seconds,
        refresh=refresh,
        cached_only=cached_only,
    )
    if payload.get("not_cached"):
        return source_result(source="openalex", status="not_cached", detail="cached_only_no_response")
    if not payload.get("ok"):
        return source_result(source="openalex", status="error", error=payload.get("error", ""), url=payload.get("url", url), cached=payload.get("from_cache", False))

    data = payload.get("data") or {}
    if "results" in data:
        results = data.get("results") or []
        data = results[0] if results else {}
    abstract = reconstruct_openalex_abstract(data.get("abstract_inverted_index"))
    pdf_url = openalex_oa_pdf_url(data)
    if abstract:
        return source_result(
            source="openalex",
            status="found",
            abstract=abstract,
            url=payload.get("url", ""),
            source_record_id=data.get("id", ""),
            oa_pdf_url=pdf_url,
            cached=payload.get("from_cache", False),
        )
    return source_result(
        source="openalex",
        status="not_found",
        url=payload.get("url", ""),
        source_record_id=data.get("id", ""),
        oa_pdf_url=pdf_url,
        cached=payload.get("from_cache", False),
    )


def fetch_crossref(row: dict[str, Any], *, cache_dir: Path, timeout: int, sleep_seconds: float, refresh: bool, cached_only: bool = False) -> dict[str, Any]:
    doi = normalize_doi(row.get("doi"))
    if not doi:
        return source_result(source="crossref", status="skipped", detail="missing_doi")
    url = f"https://api.crossref.org/works/{quote(doi, safe='')}"
    payload = cached_json_request(
        cache_dir=cache_dir,
        source="crossref",
        key=stable_key("crossref", doi),
        url=url,
        params={},
        timeout=timeout,
        sleep_seconds=sleep_seconds,
        refresh=refresh,
        cached_only=cached_only,
    )
    if payload.get("not_cached"):
        return source_result(source="crossref", status="not_cached", detail="cached_only_no_response")
    if not payload.get("ok"):
        return source_result(source="crossref", status="error", error=payload.get("error", ""), url=payload.get("url", url), cached=payload.get("from_cache", False))
    message = (payload.get("data") or {}).get("message") or {}
    abstract = clean_text(message.get("abstract"))
    if abstract:
        return source_result(source="crossref", status="found", abstract=abstract, url=payload.get("url", ""), source_record_id=doi, cached=payload.get("from_cache", False))
    return source_result(source="crossref", status="not_found", url=payload.get("url", ""), source_record_id=doi, cached=payload.get("from_cache", False))


def title_match_score(left: Any, right: Any) -> float:
    left_norm = normalize_title(left)
    right_norm = normalize_title(right)
    if not left_norm or not right_norm:
        return 0.0
    if left_norm == right_norm:
        return 1.0
    return SequenceMatcher(None, left_norm, right_norm).ratio()


def semantic_scholar_payload_to_result(data: dict[str, Any], row: dict[str, Any], url: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        return source_result(source="semantic_scholar", status="error", error="non_dict_response", url=url)
    if data.get("message") and not data.get("paperId"):
        code = clean_text(data.get("code"))
        status = "rate_limited" if code == "429" or "rate limit" in clean_text(data.get("message")).lower() else "error"
        return source_result(source="semantic_scholar", status=status, error=data.get("message", ""), url=url)
    abstract = clean_text(data.get("abstract"))
    if not abstract:
        return source_result(source="semantic_scholar", status="not_found", url=url, source_record_id=data.get("paperId", ""))
    score = title_match_score(row.get("title", ""), data.get("title", ""))
    if score < 0.82:
        return source_result(
            source="semantic_scholar",
            status="rejected_title_mismatch",
            abstract=abstract,
            url=url,
            source_record_id=data.get("paperId", ""),
            detail=f"title_match_score={score:.3f}",
        )
    return source_result(
        source="semantic_scholar",
        status="found",
        abstract=abstract,
        url=url,
        source_record_id=data.get("paperId", ""),
        detail=f"title_match_score={score:.3f}",
    )


def fetch_semantic_scholar(
    row: dict[str, Any],
    *,
    cache_dir: Path,
    timeout: int,
    sleep_seconds: float,
    refresh: bool,
    allow_title_search: bool,
    cached_only: bool = False,
) -> dict[str, Any]:
    doi = normalize_doi(row.get("doi"))
    if doi:
        url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{quote(doi, safe='')}"
        payload = cached_json_request(
            cache_dir=cache_dir,
            source="semantic_scholar",
            key=stable_key("semantic_scholar", "doi", doi),
            url=url,
            params={"fields": "title,year,abstract,externalIds,url,venue"},
            timeout=timeout,
            sleep_seconds=sleep_seconds,
            refresh=refresh,
            cached_only=cached_only,
        )
        if payload.get("not_cached"):
            return source_result(source="semantic_scholar", status="not_cached", detail="cached_only_no_response")
        if payload.get("ok"):
            result = semantic_scholar_payload_to_result(payload.get("data") or {}, row, payload.get("url", url))
            result["cached"] = payload.get("from_cache", False)
            if result["status"] in {"found", "rate_limited"}:
                return result
        elif payload.get("error"):
            if "429" in payload.get("error", ""):
                return source_result(source="semantic_scholar", status="rate_limited", error=payload.get("error", ""), url=payload.get("url", url), cached=payload.get("from_cache", False))
            return source_result(source="semantic_scholar", status="error", error=payload.get("error", ""), url=payload.get("url", url), cached=payload.get("from_cache", False))

    if not allow_title_search or not is_nonmissing(row.get("title")):
        return source_result(source="semantic_scholar", status="not_found" if doi else "skipped", detail="title_search_disabled")

    title = clean_text(row.get("title"))
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    payload = cached_json_request(
        cache_dir=cache_dir,
        source="semantic_scholar",
        key=stable_key("semantic_scholar", "title", title, row.get("publication_year")),
        url=url,
        params={"query": title, "limit": 5, "fields": "title,year,abstract,externalIds,url,venue"},
        timeout=timeout,
        sleep_seconds=sleep_seconds,
        refresh=refresh,
        cached_only=cached_only,
    )
    if payload.get("not_cached"):
        return source_result(source="semantic_scholar", status="not_cached", detail="cached_only_no_response")
    if not payload.get("ok"):
        return source_result(source="semantic_scholar", status="error", error=payload.get("error", ""), url=payload.get("url", url), cached=payload.get("from_cache", False))
    data = payload.get("data") or {}
    if data.get("message"):
        result = semantic_scholar_payload_to_result(data, row, payload.get("url", url))
        result["cached"] = payload.get("from_cache", False)
        return result
    results = data.get("data") or []
    scored = sorted(((title_match_score(title, item.get("title", "")), item) for item in results), reverse=True, key=lambda pair: pair[0])
    for score, item in scored:
        if score >= 0.90 and clean_text(item.get("abstract")):
            result = semantic_scholar_payload_to_result(item, row, payload.get("url", url))
            result["detail"] = f"title_search;{result['detail']}"
            result["cached"] = payload.get("from_cache", False)
            return result
    return source_result(source="semantic_scholar", status="not_found", url=payload.get("url", url), detail="no_title_search_abstract_match", cached=payload.get("from_cache", False))


def fetch_econpapers(row: dict[str, Any], *, cache_dir: Path, timeout: int, sleep_seconds: float, refresh: bool, cached_only: bool = False) -> dict[str, Any]:
    urls = repec_candidate_urls(row)
    if not urls:
        return source_result(source="econpapers", status="skipped", detail="no_repec_url")

    saw_not_cached = False
    errors: list[str] = []
    last_url = urls[-1]
    last_cached = False
    for index, url in enumerate(urls):
        payload = cached_text_request(
            cache_dir=cache_dir,
            source="econpapers",
            key=stable_key("econpapers", url),
            url=url,
            timeout=timeout,
            sleep_seconds=sleep_seconds,
            refresh=refresh,
            cached_only=cached_only,
        )
        if payload.get("not_cached"):
            saw_not_cached = True
            continue
        last_url = payload.get("url", url)
        last_cached = payload.get("from_cache", False)
        if not payload.get("ok"):
            errors.append(clean_text(payload.get("error", "")))
            continue
        abstract = extract_econpapers_abstract(payload.get("text", ""))
        if abstract:
            detail = "generated_repec_doi_url" if index > 0 or url != clean_text(row.get("article_url")) else ""
            return source_result(source="econpapers", status="found", abstract=abstract, url=last_url, detail=detail, cached=last_cached)

    if saw_not_cached and len(errors) < len(urls):
        return source_result(source="econpapers", status="not_cached", detail="cached_only_no_response")
    if errors and len(errors) == len(urls):
        return source_result(source="econpapers", status="error", error="; ".join(error for error in errors if error), url=last_url, cached=last_cached)
    return source_result(source="econpapers", status="not_found", url=last_url, cached=last_cached)


def fetch_publisher_metadata(row: dict[str, Any], *, cache_dir: Path, timeout: int, sleep_seconds: float, refresh: bool, cached_only: bool = False) -> dict[str, Any]:
    urls = publisher_metadata_candidate_urls(row)
    if not urls:
        return source_result(source="publisher_metadata", status="skipped", detail="no_publisher_metadata_url")

    saw_not_cached = False
    errors: list[str] = []
    last_url = urls[-1]
    last_cached = False
    for url in urls:
        payload = cached_text_request(
            cache_dir=cache_dir,
            source="publisher_metadata",
            key=stable_key("publisher_metadata", url),
            url=url,
            timeout=timeout,
            sleep_seconds=sleep_seconds,
            refresh=refresh,
            cached_only=cached_only,
        )
        if payload.get("not_cached"):
            saw_not_cached = True
            continue
        last_url = payload.get("url", url)
        last_cached = payload.get("from_cache", False)
        if not payload.get("ok"):
            errors.append(clean_text(payload.get("error", "")))
            continue
        abstract = extract_publisher_metadata_abstract(payload.get("text", ""), title=row.get("title", ""))
        pdf_url = extract_publisher_metadata_pdf_url(payload.get("text", ""), base_url=last_url)
        if abstract:
            return source_result(
                source="publisher_metadata",
                status="found",
                abstract=abstract,
                url=last_url,
                source_record_id=normalize_doi(row.get("doi")),
                detail="publisher_metadata_url",
                oa_pdf_url=pdf_url,
                cached=last_cached,
            )
        if pdf_url:
            return source_result(
                source="publisher_metadata",
                status="pdf_candidate",
                url=last_url,
                source_record_id=normalize_doi(row.get("doi")),
                detail="publisher_metadata_pdf_url",
                oa_pdf_url=pdf_url,
                cached=last_cached,
            )

    if saw_not_cached and len(errors) < len(urls):
        return source_result(source="publisher_metadata", status="not_cached", detail="cached_only_no_response")
    if errors and len(errors) == len(urls):
        return source_result(source="publisher_metadata", status="error", error="; ".join(error for error in errors if error), url=last_url, cached=last_cached)
    return source_result(source="publisher_metadata", status="not_found", url=last_url, cached=last_cached)


def fetch_unpaywall(row: dict[str, Any], *, cache_dir: Path, timeout: int, sleep_seconds: float, refresh: bool, cached_only: bool = False) -> dict[str, Any]:
    doi = normalize_doi(row.get("doi"))
    email = contact_email()
    if not doi:
        return source_result(source="unpaywall", status="skipped", detail="missing_doi")
    if not email:
        return source_result(source="unpaywall", status="skipped", detail="missing_contact_email")
    url = f"https://api.unpaywall.org/v2/{quote(doi, safe='')}"
    payload = cached_json_request(
        cache_dir=cache_dir,
        source="unpaywall",
        key=stable_key("unpaywall", doi),
        url=url,
        params={"email": email},
        timeout=timeout,
        sleep_seconds=sleep_seconds,
        refresh=refresh,
        cached_only=cached_only,
    )
    if payload.get("not_cached"):
        return source_result(source="unpaywall", status="not_cached", detail="cached_only_no_response")
    if not payload.get("ok"):
        return source_result(source="unpaywall", status="error", error=payload.get("error", ""), url=payload.get("url", url), cached=payload.get("from_cache", False))
    data = payload.get("data") or {}
    best = data.get("best_oa_location") or {}
    pdf_url = clean_text(best.get("url_for_pdf") or best.get("url"))
    status = "pdf_candidate" if pdf_url else "not_found"
    return source_result(
        source="unpaywall",
        status=status,
        url=payload.get("url", url),
        source_record_id=doi,
        oa_pdf_url=pdf_url,
        detail=f"is_oa={data.get('is_oa')};oa_status={data.get('oa_status')}",
        cached=payload.get("from_cache", False),
    )


def try_sources(
    row: dict[str, Any],
    *,
    sources: list[str],
    config: dict[str, Any],
    cache_dir: Path,
    refresh: bool,
    allow_title_search: bool,
    cached_only: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    default_timeout = int(config.get("source_timeout_seconds", 45))
    timeouts = config.get("source_timeout_seconds_by_source", {}) or {}
    sleeps = config.get("source_sleep_seconds", {}) or {}
    attempts: list[dict[str, Any]] = []
    best_pdf_url = ""
    best_pdf_source = ""
    best_pdf_detail = ""

    for source in sources:
        timeout = int(timeouts.get(source, default_timeout))
        sleep_seconds = float(sleeps.get(source, 0.25))
        if source == "openalex":
            result = fetch_openalex(row, cache_dir=cache_dir, timeout=timeout, sleep_seconds=sleep_seconds, refresh=refresh, cached_only=cached_only)
        elif source == "crossref":
            result = fetch_crossref(row, cache_dir=cache_dir, timeout=timeout, sleep_seconds=sleep_seconds, refresh=refresh, cached_only=cached_only)
        elif source == "semantic_scholar":
            result = fetch_semantic_scholar(
                row,
                cache_dir=cache_dir,
                timeout=timeout,
                sleep_seconds=sleep_seconds,
                refresh=refresh,
                allow_title_search=allow_title_search,
                cached_only=cached_only,
            )
        elif source == "econpapers":
            result = fetch_econpapers(row, cache_dir=cache_dir, timeout=timeout, sleep_seconds=sleep_seconds, refresh=refresh, cached_only=cached_only)
        elif source == "publisher_metadata":
            result = fetch_publisher_metadata(row, cache_dir=cache_dir, timeout=timeout, sleep_seconds=sleep_seconds, refresh=refresh, cached_only=cached_only)
        elif source == "unpaywall":
            result = fetch_unpaywall(row, cache_dir=cache_dir, timeout=timeout, sleep_seconds=sleep_seconds, refresh=refresh, cached_only=cached_only)
        else:
            result = source_result(source=source, status="skipped", detail="unknown_source")

        attempts.append(result)
        if result.get("oa_pdf_url") and not best_pdf_url:
            best_pdf_url = result["oa_pdf_url"]
            best_pdf_source = result.get("source", "")
            best_pdf_detail = result.get("detail", "")
        if result.get("status") == "found" and result.get("abstract"):
            result["oa_pdf_url"] = result.get("oa_pdf_url") or best_pdf_url
            return result, attempts
        if result.get("status") == "rate_limited":
            return result, attempts

    if attempts and all(attempt.get("status") in {"skipped", "not_cached"} for attempt in attempts):
        fallback_status = "not_cached" if any(attempt.get("status") == "not_cached" for attempt in attempts) else "skipped"
    else:
        fallback_status = "not_found"
    fallback = source_result(source=best_pdf_source, status=fallback_status, oa_pdf_url=best_pdf_url, detail=best_pdf_detail)
    return fallback, attempts


def enrichment_status_for_result(row: dict[str, Any], result: dict[str, Any], minimum_chars: int) -> str:
    if result.get("status") == "not_cached":
        return "not_cached"
    if result.get("status") == "rate_limited":
        return "rate_limited"
    if result.get("oa_pdf_url") and not result.get("abstract"):
        return "pdf_candidate"
    if not result.get("abstract"):
        return "not_found"
    return "enriched" if text_chars(row.get("title", ""), result.get("abstract")) >= minimum_chars else "partial_short_text"


def enrich_candidates(
    candidates: pd.DataFrame,
    *,
    config: dict[str, Any],
    sources: list[str],
    cache_dir: Path,
    refresh: bool = False,
    limit: int | None = None,
    max_queries: int | None = None,
    allow_title_search: bool = False,
    skip_nonresearch: bool = True,
    cached_only: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    minimum_chars = int(config.get("minimum_usable_text_chars", 250))
    patterns = config.get("article_scope_patterns", {}) or {}
    rows: list[dict[str, Any]] = []
    attempt_rows: list[dict[str, Any]] = []
    query_count = 0
    iterator = candidates.head(limit).to_dict(orient="records") if limit else candidates.to_dict(orient="records")
    halted_by_rate_limit = False

    for row in iterator:
        article_scope, scope_reason = classify_article_scope(row, patterns)
        base = {
            "article_id": clean_text(row.get("article_id")),
            "journal_short": clean_text(row.get("journal_short")),
            "publication_year": clean_text(row.get("publication_year")),
            "title": clean_text(row.get("title")),
            "doi": normalize_doi(row.get("doi")),
            "article_url": clean_text(row.get("article_url")),
            "current_abstract_chars": len(clean_text(row.get("abstract"))),
            "current_text_chars": int(row.get("current_text_chars") or text_chars(row.get("title", ""), row.get("abstract", ""))),
            "article_scope": article_scope,
            "article_scope_reason": scope_reason,
        }
        if skip_nonresearch and article_scope in NONRESEARCH_SCOPES:
            rows.append(
                {
                    **base,
                    "enrichment_status": "skipped_nonresearch_scope",
                    "enrichment_source": "",
                    "enriched_abstract": "",
                    "enriched_text_chars": 0,
                    "enrichment_url": "",
                    "source_record_id": "",
                    "evidence_tier": "",
                    "oa_pdf_url": "",
                    "attempted_sources": "",
                    "enrichment_quality_flags": "",
                    "enrichment_detail": "nonresearch_scope",
                    "enrichment_error": "",
                }
            )
            continue
        if halted_by_rate_limit:
            rows.append(
                {
                    **base,
                    "enrichment_status": "not_attempted_query_limit",
                    "enrichment_source": "",
                    "enriched_abstract": "",
                    "enriched_text_chars": 0,
                    "enrichment_url": "",
                    "source_record_id": "",
                    "evidence_tier": "",
                    "oa_pdf_url": "",
                    "attempted_sources": "",
                    "enrichment_quality_flags": "",
                    "enrichment_detail": "halted_after_rate_limit",
                    "enrichment_error": "",
                }
            )
            continue
        if max_queries is not None and query_count >= max_queries:
            rows.append(
                {
                    **base,
                    "enrichment_status": "not_attempted_query_limit",
                    "enrichment_source": "",
                    "enriched_abstract": "",
                    "enriched_text_chars": 0,
                    "enrichment_url": "",
                    "source_record_id": "",
                    "evidence_tier": "",
                    "oa_pdf_url": "",
                    "attempted_sources": "",
                    "enrichment_quality_flags": "",
                    "enrichment_detail": "",
                    "enrichment_error": "",
                }
            )
            continue

        result, attempts = try_sources(
            row,
            sources=sources,
            config=config,
            cache_dir=cache_dir,
            refresh=refresh,
            allow_title_search=allow_title_search,
            cached_only=cached_only,
        )
        query_count += sum(1 for attempt in attempts if attempt["status"] not in {"skipped", "not_cached"} and not attempt.get("cached"))
        for attempt in attempts:
            attempt_rows.append({**base, **{f"attempt_{key}": value for key, value in attempt.items()}})
        status = enrichment_status_for_result(row, result, minimum_chars)
        raw_abstract = result.get("abstract", "")
        quality_flags = source_text_quality_flag(raw_abstract)
        enriched_abstract = strip_source_boilerplate(raw_abstract)
        evidence_tier = infer_enrichment_evidence_tier(
            {
                "enrichment_status": status,
                "enrichment_source": result.get("source", ""),
                "enriched_abstract": enriched_abstract,
                "enrichment_detail": result.get("detail", ""),
                "evidence_tier": result.get("evidence_tier", ""),
            }
        )
        rows.append(
            {
                **base,
                "enrichment_status": status,
                "enrichment_source": result.get("source", ""),
                "enriched_abstract": enriched_abstract,
                "enriched_text_chars": text_chars(row.get("title", ""), enriched_abstract) if enriched_abstract else 0,
                "enrichment_url": result.get("url", ""),
                "source_record_id": result.get("source_record_id", ""),
                "evidence_tier": evidence_tier,
                "oa_pdf_url": result.get("oa_pdf_url", ""),
                "attempted_sources": "|".join(attempt["source"] for attempt in attempts),
                "enrichment_quality_flags": quality_flags,
                "enrichment_detail": result.get("detail", ""),
                "enrichment_error": result.get("error", ""),
            }
        )
        if result.get("status") == "rate_limited":
            halted_by_rate_limit = True
    return pd.DataFrame(rows), pd.DataFrame(attempt_rows)


def apply_enrichment_to_articles(
    articles_df: pd.DataFrame,
    enrichment_df: pd.DataFrame,
    *,
    minimum_chars: int,
    scope_patterns: dict[str, list[str]] | None = None,
) -> pd.DataFrame:
    articles = articles_df.copy().fillna("")
    for column in CLASSIFICATION_COLUMNS:
        if column in articles.columns:
            articles = articles.drop(columns=[column])
    articles["abstract_original"] = articles["abstract"] if "abstract" in articles else ""
    articles["abstract_source_original"] = articles["abstract_source"] if "abstract_source" in articles else ""
    articles["text_enrichment_status"] = "not_needed"
    articles["text_enrichment_source"] = ""
    articles["text_enrichment_url"] = ""
    articles["text_enrichment_source_record_id"] = ""
    articles["text_enrichment_evidence_tier"] = ""
    articles["text_enrichment_chars"] = ""
    articles["text_enrichment_quality_flags"] = ""
    articles["oa_pdf_url"] = ""
    if scope_patterns is None:
        articles["article_scope"] = "not_evaluated"
        articles["article_scope_reason"] = ""
    else:
        scopes = articles.apply(lambda row: classify_article_scope(row.to_dict(), scope_patterns), axis=1)
        articles["article_scope"] = scopes.map(lambda pair: pair[0])
        articles["article_scope_reason"] = scopes.map(lambda pair: pair[1])

    if enrichment_df.empty:
        return articles

    enrichment_lookup = enrichment_df.set_index("article_id", drop=False)
    for idx, article in articles.iterrows():
        article_id = article.get("article_id", "")
        if article_id not in enrichment_lookup.index:
            continue
        enrich = enrichment_lookup.loc[article_id]
        if isinstance(enrich, pd.DataFrame):
            enrich = enrich.iloc[0]
        status = clean_text(enrich.get("enrichment_status"))
        raw_enriched_abstract = clean_text(enrich.get("enriched_abstract"))
        enriched_abstract = strip_source_boilerplate(raw_enriched_abstract)
        enrichment_quality_flags = clean_text(enrich.get("enrichment_quality_flags")) or source_text_quality_flag(raw_enriched_abstract)
        enriched_chars = text_chars(article.get("title", ""), enriched_abstract) if enriched_abstract else 0
        effective_status = status
        if status == "enriched" and enrichment_quality_flags and enriched_chars < minimum_chars:
            effective_status = "partial_short_text"
        evidence_tier = infer_enrichment_evidence_tier(enrich)
        if effective_status != "enriched" or not enriched_abstract:
            evidence_tier = ""
        articles.at[idx, "text_enrichment_status"] = effective_status
        articles.at[idx, "text_enrichment_source"] = clean_text(enrich.get("enrichment_source"))
        articles.at[idx, "text_enrichment_url"] = clean_text(enrich.get("enrichment_url"))
        articles.at[idx, "text_enrichment_source_record_id"] = clean_text(enrich.get("source_record_id"))
        articles.at[idx, "text_enrichment_evidence_tier"] = evidence_tier
        articles.at[idx, "text_enrichment_chars"] = str(enriched_chars) if raw_enriched_abstract else clean_text(enrich.get("enriched_text_chars"))
        articles.at[idx, "text_enrichment_quality_flags"] = enrichment_quality_flags
        articles.at[idx, "oa_pdf_url"] = clean_text(enrich.get("oa_pdf_url"))
        if scope_patterns is None and clean_text(enrich.get("article_scope")):
            articles.at[idx, "article_scope"] = clean_text(enrich.get("article_scope"))
            articles.at[idx, "article_scope_reason"] = clean_text(enrich.get("article_scope_reason"))
        if effective_status == "enriched" and enriched_abstract:
            current_chars = text_chars(article.get("title", ""), article.get("abstract", ""))
            if enriched_chars >= current_chars or current_chars < minimum_chars:
                articles.at[idx, "abstract"] = enriched_abstract
                articles.at[idx, "abstract_source"] = f"text_enrichment:{clean_text(enrich.get('enrichment_source'))}"
    return articles


def merge_enrichment_results(previous_df: pd.DataFrame, current_df: pd.DataFrame) -> pd.DataFrame:
    if previous_df.empty:
        return current_df.copy()
    if current_df.empty:
        return previous_df.copy()

    previous = previous_df.copy().fillna("")
    current = current_df.copy().fillna("")
    all_columns = list(dict.fromkeys(list(previous.columns) + list(current.columns)))
    previous = previous.reindex(columns=all_columns, fill_value="")
    current = current.reindex(columns=all_columns, fill_value="")
    current_lookup = current.set_index("article_id", drop=False)
    merged_rows: list[pd.Series] = []
    seen: set[str] = set()

    for _, prev_row in previous.iterrows():
        article_id = clean_text(prev_row.get("article_id"))
        if article_id in current_lookup.index:
            cur_row = current_lookup.loc[article_id]
            if isinstance(cur_row, pd.DataFrame):
                cur_row = cur_row.iloc[0]
            prev_rank = ENRICHMENT_STATUS_RANK.get(clean_text(prev_row.get("enrichment_status")), 0)
            cur_rank = ENRICHMENT_STATUS_RANK.get(clean_text(cur_row.get("enrichment_status")), 0)
            force_current_nonresearch = clean_text(cur_row.get("article_scope")) in NONRESEARCH_SCOPES and clean_text(cur_row.get("enrichment_status")) == "skipped_nonresearch_scope"
            if force_current_nonresearch:
                best = cur_row.copy()
                other = prev_row
            else:
                best = cur_row.copy() if cur_rank >= prev_rank else prev_row.copy()
                other = prev_row if cur_rank >= prev_rank else cur_row
            if not clean_text(best.get("oa_pdf_url")) and clean_text(other.get("oa_pdf_url")):
                best["oa_pdf_url"] = clean_text(other.get("oa_pdf_url"))
            if clean_text(cur_row.get("article_scope")):
                best["article_scope"] = clean_text(cur_row.get("article_scope"))
                best["article_scope_reason"] = clean_text(cur_row.get("article_scope_reason"))
            if not clean_text(best.get("attempted_sources")) and clean_text(other.get("attempted_sources")):
                best["attempted_sources"] = clean_text(other.get("attempted_sources"))
            elif clean_text(other.get("attempted_sources")):
                sources = []
                for value in [best.get("attempted_sources"), other.get("attempted_sources")]:
                    for source in str(value).split("|"):
                        source = source.strip()
                        if source and source not in sources:
                            sources.append(source)
                best["attempted_sources"] = "|".join(sources)
            merged_rows.append(best)
            seen.add(article_id)
        else:
            merged_rows.append(prev_row)
            seen.add(article_id)

    for _, cur_row in current.iterrows():
        article_id = clean_text(cur_row.get("article_id"))
        if article_id not in seen:
            merged_rows.append(cur_row)

    merged = pd.DataFrame(merged_rows).reindex(columns=all_columns).reset_index(drop=True)
    if "evidence_tier" not in merged.columns:
        merged["evidence_tier"] = ""
    merged["evidence_tier"] = merged.apply(lambda row: clean_text(row.get("evidence_tier")) or infer_enrichment_evidence_tier(row), axis=1)
    return merged


def merge_attempt_results(previous_df: pd.DataFrame, current_df: pd.DataFrame) -> pd.DataFrame:
    if previous_df.empty:
        return current_df.copy()
    if current_df.empty:
        return previous_df.copy()
    all_columns = list(dict.fromkeys(list(previous_df.columns) + list(current_df.columns)))
    previous = previous_df.reindex(columns=all_columns, fill_value="")
    current = current_df.reindex(columns=all_columns, fill_value="")
    return pd.concat([previous, current], ignore_index=True).drop_duplicates().reset_index(drop=True)


def df_to_markdown(df: pd.DataFrame, max_rows: int = 30) -> str:
    if df.empty:
        return "_No rows._"
    shown = df.head(max_rows).fillna("")
    headers = list(shown.columns)
    rows = [headers] + shown.astype(str).values.tolist()
    widths = [max(len(row[i]) for row in rows) for i in range(len(headers))]
    header = "| " + " | ".join(headers[i].ljust(widths[i]) for i in range(len(headers))) + " |"
    separator = "| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |"
    body = ["| " + " | ".join(row[i].ljust(widths[i]) for i in range(len(headers))) + " |" for row in rows[1:]]
    suffix = f"\n\n_Only first {max_rows} rows shown._" if len(df) > max_rows else ""
    return "\n".join([header, separator] + body) + suffix


def write_summary(report_path: Path, enrichment_df: pd.DataFrame, attempts_df: pd.DataFrame, pdf_df: pd.DataFrame) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    status_table = (
        enrichment_df["enrichment_status"].value_counts(dropna=False).rename_axis("status").reset_index(name="rows")
        if not enrichment_df.empty
        else pd.DataFrame()
    )
    source_table = (
        enrichment_df["enrichment_source"].replace("", "(none)").value_counts(dropna=False).rename_axis("source").reset_index(name="rows")
        if not enrichment_df.empty
        else pd.DataFrame()
    )
    scope_table = (
        enrichment_df["article_scope"].value_counts(dropna=False).rename_axis("scope").reset_index(name="rows")
        if not enrichment_df.empty
        else pd.DataFrame()
    )
    lines = [
        "# Text Enrichment Report",
        "",
        f"- Candidate rows: {len(enrichment_df)}",
        f"- Source attempts: {len(attempts_df)}",
        f"- OA PDF candidates: {len(pdf_df)}",
        "",
        "## Enrichment Status",
        "",
        df_to_markdown(status_table),
        "",
        "## Enrichment Source",
        "",
        df_to_markdown(source_table),
        "",
        "## Article Scope",
        "",
        df_to_markdown(scope_table),
    ]
    report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parse_sources(value: str | None, config: dict[str, Any]) -> list[str]:
    if value:
        return [part.strip() for part in value.split(",") if part.strip()]
    return list(config.get("default_sources", []))


def parse_csv_filter(value: str | None) -> list[str]:
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def filter_enrichment_candidates(
    candidates: pd.DataFrame,
    *,
    doi_prefixes: list[str] | None = None,
    journals: list[str] | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> pd.DataFrame:
    work = candidates.copy()
    mask = pd.Series(True, index=work.index)

    normalized_prefixes = [normalize_doi(prefix).lower() for prefix in doi_prefixes or [] if normalize_doi(prefix)]
    if normalized_prefixes:
        doi_values = work["doi"].astype(str).map(lambda value: normalize_doi(value).lower()) if "doi" in work else pd.Series("", index=work.index)
        mask &= doi_values.map(lambda value: any(value.startswith(prefix) for prefix in normalized_prefixes))

    normalized_journals = {clean_text(journal).lower() for journal in journals or [] if clean_text(journal)}
    if normalized_journals:
        journal_values = work["journal_short"].astype(str).map(lambda value: clean_text(value).lower()) if "journal_short" in work else pd.Series("", index=work.index)
        mask &= journal_values.isin(normalized_journals)

    if start_year is not None or end_year is not None:
        years = pd.to_numeric(work.get("publication_year", ""), errors="coerce")
        if start_year is not None:
            mask &= years >= start_year
        if end_year is not None:
            mask &= years <= end_year

    return work.loc[mask].reset_index(drop=True)


def run_text_enrichment(
    *,
    classified_input: Path,
    articles_input: Path,
    config_path: Path,
    output_candidates: Path,
    output_attempts: Path,
    output_articles: Path,
    output_pdf_candidates: Path,
    report_path: Path,
    cache_dir: Path,
    sources_value: str | None,
    refresh: bool,
    limit: int | None,
    max_queries: int | None,
    allow_title_search: bool,
    skip_nonresearch: bool,
    preserve_order: bool,
    merge_existing: bool,
    cached_only: bool,
    doi_prefixes_value: str | None = None,
    journals_value: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> None:
    config = load_yaml(config_path)
    minimum_chars = int(config.get("minimum_usable_text_chars", 250))
    classified = pd.read_csv(classified_input, dtype=str).fillna("")
    articles = pd.read_csv(articles_input, dtype=str).fillna("")
    sources = parse_sources(sources_value, config)
    candidates = candidate_rows(classified, minimum_chars, str(config.get("candidate_category", "insufficient_text")))
    candidates = filter_enrichment_candidates(
        candidates,
        doi_prefixes=parse_csv_filter(doi_prefixes_value),
        journals=parse_csv_filter(journals_value),
        start_year=start_year,
        end_year=end_year,
    )
    if not preserve_order:
        candidates = prioritize_candidates(candidates)
    enrichment, attempts = enrich_candidates(
        candidates,
        config=config,
        sources=sources,
        cache_dir=cache_dir,
        refresh=refresh,
        limit=limit,
        max_queries=max_queries,
        allow_title_search=allow_title_search,
        skip_nonresearch=skip_nonresearch,
        cached_only=cached_only,
    )
    if merge_existing and output_candidates.exists():
        previous_enrichment = pd.read_csv(output_candidates, dtype=str).fillna("")
        enrichment = merge_enrichment_results(previous_enrichment, enrichment)
    if merge_existing and output_attempts.exists():
        previous_attempts = pd.read_csv(output_attempts, dtype=str).fillna("")
        attempts = merge_attempt_results(previous_attempts, attempts)
    enriched_articles = apply_enrichment_to_articles(
        articles,
        enrichment,
        minimum_chars=minimum_chars,
        scope_patterns=config.get("article_scope_patterns", {}) or {},
    )
    pdf_candidates = enrichment[enrichment["oa_pdf_url"].astype(str).str.strip() != ""].copy() if not enrichment.empty else pd.DataFrame()

    for path, frame in [
        (output_candidates, enrichment),
        (output_attempts, attempts),
        (output_articles, enriched_articles),
        (output_pdf_candidates, pdf_candidates),
    ]:
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)
    write_summary(report_path, enrichment, attempts, pdf_candidates)
    print(f"candidates={len(candidates)}")
    print(f"enrichment_rows={len(enrichment)}")
    if not enrichment.empty:
        print(enrichment["enrichment_status"].value_counts(dropna=False).to_string())
    print(f"pdf_candidates={len(pdf_candidates)}")
    print(f"enriched_articles={output_articles}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--classified-input", default="data/final/articles_classified_pilot.csv")
    parser.add_argument("--articles-input", default="data/final/articles_pilot.csv")
    parser.add_argument("--config", default="config/text_enrichment.yml")
    parser.add_argument("--output-candidates", default="data/intermediate/text_enrichment_candidates.csv")
    parser.add_argument("--output-attempts", default="data/intermediate/text_enrichment_attempts.csv")
    parser.add_argument("--output-articles", default="data/final/articles_enriched_pilot.csv")
    parser.add_argument("--output-pdf-candidates", default="data/intermediate/text_enrichment_pdf_candidates.csv")
    parser.add_argument("--report", default="docs/text_enrichment_report.md")
    parser.add_argument("--cache-dir", default="data/intermediate/text_enrichment_cache")
    parser.add_argument("--sources", default=None, help="Comma-separated sources. Defaults to config default_sources.")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--max-queries", type=int, default=None)
    parser.add_argument("--allow-title-search", action="store_true")
    parser.add_argument("--include-nonresearch", action="store_true")
    parser.add_argument("--preserve-order", action="store_true")
    parser.add_argument("--no-merge-existing", action="store_true")
    parser.add_argument("--cached-only", action="store_true")
    parser.add_argument("--doi-prefixes", default=None, help="Comma-separated DOI prefixes to keep before enrichment, e.g. 10.1257,10.1086.")
    parser.add_argument("--journals", default=None, help="Comma-separated journal_short values to keep before enrichment.")
    parser.add_argument("--start-year", type=int, default=None, help="Earliest publication year to keep before enrichment.")
    parser.add_argument("--end-year", type=int, default=None, help="Latest publication year to keep before enrichment.")
    args = parser.parse_args()
    run_text_enrichment(
        classified_input=Path(args.classified_input),
        articles_input=Path(args.articles_input),
        config_path=Path(args.config),
        output_candidates=Path(args.output_candidates),
        output_attempts=Path(args.output_attempts),
        output_articles=Path(args.output_articles),
        output_pdf_candidates=Path(args.output_pdf_candidates),
        report_path=Path(args.report),
        cache_dir=Path(args.cache_dir),
        sources_value=args.sources,
        refresh=args.refresh,
        limit=args.limit,
        max_queries=args.max_queries,
        allow_title_search=args.allow_title_search,
        skip_nonresearch=not args.include_nonresearch,
        preserve_order=args.preserve_order,
        merge_existing=not args.no_merge_existing,
        cached_only=args.cached_only,
        doi_prefixes_value=args.doi_prefixes,
        journals_value=args.journals,
        start_year=args.start_year,
        end_year=args.end_year,
    )


if __name__ == "__main__":
    main()
