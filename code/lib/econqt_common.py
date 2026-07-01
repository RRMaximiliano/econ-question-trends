from __future__ import annotations

import hashlib
import html
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import requests
import yaml


SOURCE_PRIORITY = {
    "bibliographic": ["crossref", "openalex"],
    "abstract": ["openalex", "crossref"],
    "authors": ["openalex", "crossref"],
    "affiliations": ["openalex", "crossref"],
    "keywords": ["openalex", "crossref"],
}

SOURCE_TEXT_QUALITY_PATTERNS = {
    "jstor_terms_boilerplate": [
        r"your use of the jstor archive indicates your acceptance",
        r"jstor(?:'|\u2019)s terms and conditions of use",
        r"terms and conditions of use,?\s+available at",
        r"this content downloaded from .{0,240}? all use subject to https?://about\.jstor\.org/terms",
        r"\ball use subject to https?://about\.jstor\.org/terms\b",
    ],
    "access_or_rights_boilerplate": [
        r"copyright\s*(?:\u00a9|\(c\))?\s*\d{4}\s*all rights reserved",
        r"\ball rights reserved\b",
    ],
}

SOURCE_BOILERPLATE_STRIP_PATTERNS = [
    r"your use of the jstor archive indicates your acceptance of jstor(?:'|\u2019)s terms and conditions of use,?\s+available at(?:\s+\S+)?",
    r"jstor(?:'|\u2019)s terms and conditions of use",
    r"terms and conditions of use,?\s+available at(?:\s+\S+)?",
    r"this content downloaded from .{0,240}? all use subject to https?://about\.jstor\.org/terms",
    r"\ball use subject to https?://about\.jstor\.org/terms\b",
    r"copyright\s*(?:\u00a9|\(c\))?\s*\d{4}\s*all rights reserved",
    r"\ball rights reserved\b",
]


def project_root_from_arg(path: Optional[str]) -> Path:
    return Path(path).expanduser().resolve() if path else Path.cwd().resolve()


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_journals(project_root: Path) -> List[Dict[str, Any]]:
    config = load_yaml(project_root / "config" / "journals.yml")
    return list(config["journals"])


def ensure_dirs(project_root: Path) -> None:
    for rel in [
        "data/raw/crossref",
        "data/raw/openalex",
        "data/intermediate",
        "data/final",
        "docs",
        "outputs/tables",
        "outputs/figures",
        "outputs/logs",
    ]:
        (project_root / rel).mkdir(parents=True, exist_ok=True)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def contact_email() -> Optional[str]:
    for env_name in ["CONTACT_EMAIL", "CROSSREF_MAILTO", "OPENALEX_MAILTO"]:
        value = os.environ.get(env_name)
        if value:
            return value
    return None


def request_headers(source: str) -> Dict[str, str]:
    email = contact_email()
    suffix = f" (mailto:{email})" if email else ""
    headers = {
        "User-Agent": f"econ-question-trends-pilot/0.1{suffix}",
        "Accept": "application/json",
    }
    if source == "semantic_scholar" and os.environ.get("SEMANTIC_SCHOLAR_API_KEY"):
        headers["x-api-key"] = os.environ["SEMANTIC_SCHOLAR_API_KEY"]
    return headers


def get_json(
    url: str,
    params: Dict[str, Any],
    *,
    source: str,
    timeout: int = 45,
    sleep_seconds: float = 0.25,
) -> Tuple[Dict[str, Any], str]:
    response = requests.get(
        url,
        params=params,
        headers=request_headers(source),
        timeout=timeout,
    )
    final_url = response.url
    response.raise_for_status()
    if sleep_seconds:
        time.sleep(sleep_seconds)
    return response.json(), final_url


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=True)


def read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def first_nonempty(values: Iterable[Any]) -> Optional[Any]:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and value.strip() == "":
            continue
        if isinstance(value, (list, dict)) and not value:
            continue
        return value
    return None


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        value = first_nonempty(value) or ""
    text = str(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def source_text_quality_flags(value: Any) -> List[str]:
    text = clean_text(value).lower()
    if not text:
        return []
    flags: List[str] = []
    for flag, patterns in SOURCE_TEXT_QUALITY_PATTERNS.items():
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns):
            flags.append(flag)
    return flags


def source_text_quality_flag(value: Any) -> str:
    return "|".join(source_text_quality_flags(value))


def strip_source_boilerplate(value: Any) -> str:
    cleaned = clean_text(value)
    if not cleaned:
        return ""
    for pattern in SOURCE_BOILERPLATE_STRIP_PATTERNS:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+([,.;:])", r"\1", cleaned)
    cleaned = re.sub(r"(^|\s)[_|]+(\s|$)", " ", cleaned)
    return clean_text(cleaned)


def normalize_doi(value: Any) -> str:
    if value is None:
        return ""
    doi = str(value).strip().lower()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)
    doi = re.sub(r"^doi:\s*", "", doi)
    return doi.strip()


def normalize_title(value: Any) -> str:
    title = clean_text(value).lower()
    title = re.sub(r"[^a-z0-9]+", " ", title)
    return re.sub(r"\s+", " ", title).strip()


def make_article_id(doi: str, journal_short: str, year: Any, title: str) -> str:
    if doi:
        base = f"doi:{normalize_doi(doi)}"
    else:
        base = f"title:{journal_short}:{year}:{normalize_title(title)}"
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]
    return f"eqt_{digest}"


def source_key(doi: str, journal_short: str, year: Any, title: str) -> Tuple[str, str]:
    if doi:
        return "doi", normalize_doi(doi)
    return "title_journal_year", f"{journal_short}|{year}|{normalize_title(title)}"


def crossref_date(item: Dict[str, Any]) -> Tuple[str, Optional[int]]:
    for key in ["published-print", "published-online", "published", "issued", "created"]:
        date_parts = item.get(key, {}).get("date-parts")
        if not date_parts or not date_parts[0]:
            continue
        parts = list(date_parts[0])
        if not parts:
            continue
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 1
        day = int(parts[2]) if len(parts) > 2 else 1
        return f"{year:04d}-{month:02d}-{day:02d}", year
    return "", None


def parse_pages(page_raw: Any) -> Tuple[str, str]:
    if not page_raw:
        return "", ""
    text = str(page_raw).strip()
    if not text:
        return "", ""
    parts = re.split(r"\s*[-–—]\s*", text, maxsplit=1)
    first = parts[0].strip()
    last = parts[1].strip() if len(parts) > 1 else ""
    return first, last


def author_name_from_crossref(author: Dict[str, Any]) -> str:
    given = clean_text(author.get("given"))
    family = clean_text(author.get("family"))
    name = clean_text(author.get("name"))
    return " ".join(part for part in [given, family] if part).strip() or name


def reconstruct_openalex_abstract(inverted_index: Optional[Dict[str, List[int]]]) -> str:
    if not inverted_index:
        return ""
    max_position = max((pos for positions in inverted_index.values() for pos in positions), default=-1)
    if max_position < 0:
        return ""
    words: List[str] = [""] * (max_position + 1)
    for word, positions in inverted_index.items():
        for pos in positions:
            words[pos] = word
    return clean_text(" ".join(words))


def openalex_source_id_short(source_id: str) -> str:
    return str(source_id).rstrip("/").split("/")[-1]


def as_json_string(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, (list, dict)) and not value:
        return ""
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def list_raw_files(project_root: Path, source: str) -> List[Path]:
    return sorted((project_root / "data" / "raw" / source).glob("*.json"))


def write_log(project_root: Path, name: str, lines: Sequence[str]) -> None:
    path = project_root / "outputs" / "logs" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for line in lines:
            fh.write(f"{line}\n")
