from __future__ import annotations

import argparse
import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

import pandas as pd
import requests

sys.path.append(str(Path(__file__).resolve().parents[1] / "lib"))
sys.path.append(str(Path(__file__).resolve().parent))

from econqt_common import clean_text, normalize_doi, normalize_title  # noqa: E402
from recovery_batch_split import df_to_markdown  # noqa: E402
from text_enrichment import text_chars  # noqa: E402


SCIENCEON_SOURCE = "ScienceOn article metadata"
SCIENCEON_EVIDENCE_TIER = "tier_a_formal_abstract"
SCIENCEON_LIST_URL = "https://scienceon.kisti.re.kr/srch/selectPORSrchArticleList.do?searchKeyword={query}"
SCIENCEON_DETAIL_URL = "https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn={nart_id}"

CANDIDATE_COLUMNS = [
    "article_id",
    "split_group",
    "quick_win_tier",
    "title",
    "doi",
    "nart_id",
    "abstract_chars",
    "usable_text_chars",
    "abstract",
    "source",
    "source_url",
    "source_record_id",
    "evidence_tier",
    "notes",
]

SKIP_COLUMNS = [
    "article_id",
    "title",
    "doi",
    "status",
    "nart_id",
    "abstract_chars",
    "usable_text_chars",
    "source_url",
    "detail",
]

EXPORT_COLUMNS = [
    "article_id",
    "split_group",
    "quick_win_tier",
    "abstract",
    "source",
    "source_url",
    "source_record_id",
    "evidence_tier",
    "notes",
]


class MetaTagParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "meta":
            return
        attr_map = {key.lower(): value or "" for key, value in attrs}
        name = clean_text(attr_map.get("name"))
        content = clean_text(attr_map.get("content"))
        if name and content and name not in self.meta:
            self.meta[name] = content


class ScienceOnFetcher:
    def __init__(self, *, timeout_seconds: int = 20, sleep_seconds: float = 0.2, cache_dir: Path | None = None) -> None:
        self.timeout_seconds = timeout_seconds
        self.sleep_seconds = sleep_seconds
        self.cache_dir = cache_dir
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (compatible; econ-question-trends/0.1)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )

    def __call__(self, url: str) -> str:
        cache_path = self.cache_path(url)
        if cache_path and cache_path.exists() and cache_path.stat().st_size > 1000:
            return cache_path.read_text(encoding="utf-8", errors="replace")
        response = self.session.get(url, timeout=self.timeout_seconds)
        response.raise_for_status()
        text = response.text
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(text, encoding="utf-8")
        if self.sleep_seconds:
            time.sleep(self.sleep_seconds)
        return text

    def cache_path(self, url: str) -> Path | None:
        if self.cache_dir is None:
            return None
        safe = re.sub(r"[^A-Za-z0-9]+", "_", url).strip("_")[:180]
        return self.cache_dir / f"{safe}.html"


def parse_meta_tags(html_text: str) -> dict[str, str]:
    parser = MetaTagParser()
    parser.feed(html_text)
    return parser.meta


def scienceon_title(value: Any) -> str:
    title = clean_text(value)
    title = re.sub(r"^\[논문\]\s*", "", title).strip()
    return title


def title_matches(expected: Any, observed: Any) -> bool:
    expected_norm = normalize_title(expected)
    observed_norm = normalize_title(scienceon_title(observed))
    return bool(expected_norm and observed_norm and (expected_norm == observed_norm or expected_norm in observed_norm or observed_norm in expected_norm))


def nart_ids_from_html(html_text: str) -> list[str]:
    seen: set[str] = set()
    ids: list[str] = []
    for value in re.findall(r"NART\d+", html_text):
        if value not in seen:
            seen.add(value)
            ids.append(value)
    return ids


def split_lookup_from_summary(split_summary_path: Path) -> dict[str, tuple[str, str]]:
    if not split_summary_path.exists():
        return {}
    summary = pd.read_csv(split_summary_path, dtype=str).fillna("")
    lookup: dict[str, tuple[str, str]] = {}
    if "output_csv" not in summary.columns:
        return lookup
    for _, summary_row in summary.iterrows():
        split_group = clean_text(summary_row.get("split_group"))
        output_csv = clean_text(summary_row.get("output_csv"))
        if not split_group or not output_csv:
            continue
        path = Path(output_csv)
        if not path.exists():
            continue
        rows = pd.read_csv(path, dtype=str).fillna("")
        if "article_id" not in rows.columns:
            continue
        for _, row in rows.iterrows():
            article_id = clean_text(row.get("article_id"))
            quick_win_tier = clean_text(row.get("quick_win_tier"))
            if article_id:
                lookup[article_id] = (split_group, quick_win_tier)
    return lookup


def load_article_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    rows = pd.read_csv(path, dtype=str).fillna("")
    if "article_id" not in rows.columns:
        return set()
    return {article_id for article_id in rows["article_id"].map(clean_text).tolist() if article_id}


def candidate_from_match(row: pd.Series, split_group: str, quick_win_tier: str, nart_id: str, detail_url: str, abstract: str) -> dict[str, str]:
    doi = normalize_doi(row.get("doi"))
    title = clean_text(row.get("title"))
    source_record_id = f"ScienceOn:{nart_id}; doi:{doi}"
    return {
        "article_id": clean_text(row.get("article_id")),
        "split_group": split_group,
        "quick_win_tier": quick_win_tier or clean_text(row.get("quick_win_tier")),
        "title": title,
        "doi": doi,
        "nart_id": nart_id,
        "abstract_chars": str(len(abstract)),
        "usable_text_chars": str(text_chars(title, abstract)),
        "abstract": abstract,
        "source": SCIENCEON_SOURCE,
        "source_url": detail_url,
        "source_record_id": source_record_id,
        "evidence_tier": SCIENCEON_EVIDENCE_TIER,
        "notes": f"ScienceOn public metadata page exposes citation_abstract and matching DOI {doi} for the exact article.",
    }


def skip_row(row: pd.Series, status: str, detail: str, *, nart_id: str = "", abstract: str = "", source_url: str = "") -> dict[str, str]:
    title = clean_text(row.get("title"))
    return {
        "article_id": clean_text(row.get("article_id")),
        "title": title,
        "doi": normalize_doi(row.get("doi")),
        "status": status,
        "nart_id": nart_id,
        "abstract_chars": str(len(clean_text(abstract))) if abstract else "0",
        "usable_text_chars": str(text_chars(title, abstract)) if abstract else "0",
        "source_url": source_url,
        "detail": detail,
    }


def recover_scienceon_row(
    row: pd.Series,
    *,
    split_group: str,
    quick_win_tier: str,
    fetch_text: Callable[[str], str],
    minimum_chars: int,
    max_detail_candidates: int,
) -> tuple[dict[str, str] | None, dict[str, str]]:
    doi = normalize_doi(row.get("doi"))
    if not doi:
        return None, skip_row(row, "missing_doi", "ScienceOn lookup requires a DOI.")

    list_url = SCIENCEON_LIST_URL.format(query=quote(doi))
    try:
        list_html = fetch_text(list_url)
    except Exception as exc:  # pragma: no cover - exact requests errors vary by environment
        return None, skip_row(row, "list_fetch_error", repr(exc))

    nart_ids = nart_ids_from_html(list_html)
    if not nart_ids:
        return None, skip_row(row, "no_scienceon_result", "No NART identifier found for DOI search.")

    title_mismatches: list[str] = []
    for nart_id in nart_ids[:max_detail_candidates]:
        detail_url = SCIENCEON_DETAIL_URL.format(nart_id=nart_id)
        try:
            detail_html = fetch_text(detail_url)
        except Exception as exc:  # pragma: no cover - exact requests errors vary by environment
            return None, skip_row(row, "detail_fetch_error", repr(exc), nart_id=nart_id, source_url=detail_url)
        meta = parse_meta_tags(detail_html)
        detail_doi = normalize_doi(meta.get("citation_doi"))
        if detail_doi != doi:
            continue
        detail_title = scienceon_title(meta.get("citation_title") or meta.get("title"))
        if not title_matches(row.get("title"), detail_title):
            title_mismatches.append(f"{nart_id}:{detail_title}")
            continue
        abstract = clean_text(meta.get("citation_abstract"))
        if not abstract:
            return None, skip_row(row, "doi_title_match_no_abstract", "ScienceOn detail page matched DOI/title but exposed no citation_abstract.", nart_id=nart_id, source_url=detail_url)
        usable_chars = text_chars(row.get("title"), abstract)
        if usable_chars < minimum_chars:
            return None, skip_row(
                row,
                "abstract_below_threshold",
                f"ScienceOn detail page matched DOI/title but usable text chars {usable_chars} < {minimum_chars}.",
                nart_id=nart_id,
                abstract=abstract,
                source_url=detail_url,
            )
        return candidate_from_match(row, split_group, quick_win_tier, nart_id, detail_url, abstract), skip_row(row, "accepted", "Accepted ScienceOn citation_abstract.", nart_id=nart_id, abstract=abstract, source_url=detail_url)

    detail = "No DOI-matched ScienceOn detail page found."
    if title_mismatches:
        detail = "DOI matched but title did not match: " + " | ".join(title_mismatches[:3])
    return None, skip_row(row, "no_exact_doi_title_match", detail)


def filter_scan_rows(
    action_packet: pd.DataFrame,
    doi_prefixes: list[str],
    already_imported: set[str],
    already_exported: set[str],
    already_scanned: set[str] | None = None,
) -> pd.DataFrame:
    work = action_packet.copy().fillna("")
    if "article_id" not in work.columns or "doi" not in work.columns:
        return pd.DataFrame(columns=work.columns)
    excluded = already_imported | already_exported | (already_scanned or set())
    mask = ~work["article_id"].map(clean_text).isin(excluded)
    prefixes = [normalize_doi(prefix) for prefix in doi_prefixes if clean_text(prefix)]
    if prefixes:
        mask &= work["doi"].map(normalize_doi).map(lambda value: any(value.startswith(prefix) for prefix in prefixes))
    return work.loc[mask].copy().reset_index(drop=True)


def limit_scan_rows(scan_rows: pd.DataFrame, max_rows: int) -> pd.DataFrame:
    if max_rows <= 0 or scan_rows.empty:
        return scan_rows
    return scan_rows.head(max_rows).copy().reset_index(drop=True)


def append_candidates_to_export(candidates: pd.DataFrame, export_path: Path) -> int:
    if candidates.empty:
        return 0
    export_path.parent.mkdir(parents=True, exist_ok=True)
    existing = pd.read_csv(export_path, dtype=str).fillna("") if export_path.exists() else pd.DataFrame(columns=EXPORT_COLUMNS)
    existing_ids = load_article_ids(export_path)
    export_rows = candidates.loc[~candidates["article_id"].map(clean_text).isin(existing_ids), EXPORT_COLUMNS].copy()
    if export_rows.empty:
        return 0
    combined = pd.concat([existing.reindex(columns=EXPORT_COLUMNS, fill_value=""), export_rows], ignore_index=True)
    combined.to_csv(export_path, index=False)
    return len(export_rows)


def write_scan_report(
    path: Path,
    *,
    candidates: pd.DataFrame,
    skipped: pd.DataFrame,
    output_candidates: Path,
    output_skipped: Path,
    export_path: Path,
    appended_rows: int,
    scan_rows: int,
    doi_prefixes: list[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    skip_summary = skipped["status"].value_counts(dropna=False).rename_axis("status").reset_index(name="rows") if not skipped.empty else pd.DataFrame()
    lines = [
        "# ScienceOn Recovery Scan",
        "",
        "This scan checks ScienceOn public article metadata for exact DOI/title matches with `citation_abstract`. It does not use title-only snippets, access-challenge pages, or restricted full text.",
        "",
        f"- Scan rows: {scan_rows}",
        f"- DOI prefixes: `{', '.join(doi_prefixes) if doi_prefixes else 'all'}`",
        f"- Accepted candidates: {len(candidates)}",
        f"- Skipped rows: {len(skipped)}",
        f"- Appended export rows: {appended_rows}",
        f"- Candidates CSV: `{output_candidates}`",
        f"- Skipped CSV: `{output_skipped}`",
        f"- Confirmed-source export: `{export_path}`",
        "",
        "## Skip Summary",
        "",
        df_to_markdown(skip_summary, max_rows=40),
        "",
        "## Accepted Candidates",
        "",
        df_to_markdown(candidates[["article_id", "title", "doi", "nart_id", "usable_text_chars", "source_url"]] if not candidates.empty else candidates, max_rows=40),
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def run_scienceon_recovery_scan(
    *,
    action_packet_path: Path,
    split_summary_path: Path,
    imported_history_path: Path,
    confirmed_export_path: Path,
    output_candidates: Path,
    output_skipped: Path,
    report_path: Path,
    doi_prefixes: list[str],
    minimum_chars: int,
    max_detail_candidates: int,
    append_export: bool,
    fetch_text: Callable[[str], str] | None = None,
    cache_dir: Path | None = None,
    timeout_seconds: int = 20,
    sleep_seconds: float = 0.2,
    max_rows: int = 0,
    previous_skipped_path: Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    action_packet = pd.read_csv(action_packet_path, dtype=str).fillna("")
    already_imported = load_article_ids(imported_history_path)
    already_exported = load_article_ids(confirmed_export_path)
    already_scanned = load_article_ids(previous_skipped_path) if previous_skipped_path is not None else set()
    split_lookup = split_lookup_from_summary(split_summary_path)
    scan_rows = limit_scan_rows(filter_scan_rows(action_packet, doi_prefixes, already_imported, already_exported, already_scanned), max_rows)
    fetcher = fetch_text or ScienceOnFetcher(timeout_seconds=timeout_seconds, sleep_seconds=sleep_seconds, cache_dir=cache_dir)

    candidates: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    for _, row in scan_rows.iterrows():
        article_id = clean_text(row.get("article_id"))
        split_group, split_quick_win_tier = split_lookup.get(article_id, ("", ""))
        candidate, skip = recover_scienceon_row(
            row,
            split_group=split_group,
            quick_win_tier=split_quick_win_tier or clean_text(row.get("quick_win_tier")),
            fetch_text=fetcher,
            minimum_chars=minimum_chars,
            max_detail_candidates=max_detail_candidates,
        )
        if candidate is not None:
            candidates.append(candidate)
        skipped.append(skip)

    candidates_df = pd.DataFrame(candidates, columns=CANDIDATE_COLUMNS)
    skipped_df = pd.DataFrame(skipped, columns=SKIP_COLUMNS)
    output_candidates.parent.mkdir(parents=True, exist_ok=True)
    output_skipped.parent.mkdir(parents=True, exist_ok=True)
    candidates_df.to_csv(output_candidates, index=False)
    skipped_df.to_csv(output_skipped, index=False)
    appended_rows = append_candidates_to_export(candidates_df, confirmed_export_path) if append_export else 0
    write_scan_report(
        report_path,
        candidates=candidates_df,
        skipped=skipped_df,
        output_candidates=output_candidates,
        output_skipped=output_skipped,
        export_path=confirmed_export_path,
        appended_rows=appended_rows,
        scan_rows=len(scan_rows),
        doi_prefixes=doi_prefixes,
    )
    print(f"scan_rows={len(scan_rows)}")
    print(f"accepted_candidates={len(candidates_df)}")
    print(f"skipped_rows={len(skipped_df)}")
    print(f"appended_export_rows={appended_rows}")
    print(f"candidates={output_candidates}")
    print(f"skipped={output_skipped}")
    print(f"report={report_path}")
    return candidates_df, skipped_df


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--action-packet", default="outputs/tables/enriched/recovery_batch_R001_action_packet.csv")
    parser.add_argument("--split-summary", default="outputs/tables/enriched/recovery_batch_R001_split_summary.csv")
    parser.add_argument("--imported-history", default="data/intermediate/abstract_backfill_import_history.csv")
    parser.add_argument("--confirmed-export", default="data/intermediate/insufficient_text_recovery_review_exports/R001/recovery_batch_R001_confirmed_source_rows.csv")
    parser.add_argument("--previous-skipped", default="", help="Optional prior ScienceOn skipped-audit CSV. Article IDs in it are excluded from this run.")
    parser.add_argument("--output-candidates", default="outputs/tables/enriched/scienceon_recovery_R001_candidates.csv")
    parser.add_argument("--output-skipped", default="outputs/tables/enriched/scienceon_recovery_R001_skipped.csv")
    parser.add_argument("--report", default="docs/scienceon_recovery_R001.md")
    parser.add_argument("--doi-prefix", action="append", default=None, help="DOI prefix to scan. Repeat for multiple prefixes; pass an empty string to scan all DOI prefixes.")
    parser.add_argument("--minimum-chars", type=int, default=250)
    parser.add_argument("--max-detail-candidates", type=int, default=8)
    parser.add_argument("--append-export", action="store_true")
    parser.add_argument("--cache-dir", default="")
    parser.add_argument("--timeout-seconds", type=int, default=20)
    parser.add_argument("--sleep-seconds", type=float, default=0.2)
    parser.add_argument("--max-rows", type=int, default=0, help="Limit the number of eligible rows scanned; 0 scans all eligible rows.")
    args = parser.parse_args()
    raw_prefixes = args.doi_prefix if args.doi_prefix is not None else ["10.2307"]
    doi_prefixes = [prefix for prefix in raw_prefixes if clean_text(prefix)]
    run_scienceon_recovery_scan(
        action_packet_path=Path(args.action_packet),
        split_summary_path=Path(args.split_summary),
        imported_history_path=Path(args.imported_history),
        confirmed_export_path=Path(args.confirmed_export),
        previous_skipped_path=Path(args.previous_skipped) if clean_text(args.previous_skipped) else None,
        output_candidates=Path(args.output_candidates),
        output_skipped=Path(args.output_skipped),
        report_path=Path(args.report),
        doi_prefixes=doi_prefixes,
        minimum_chars=args.minimum_chars,
        max_detail_candidates=args.max_detail_candidates,
        append_export=args.append_export,
        cache_dir=Path(args.cache_dir) if clean_text(args.cache_dir) else None,
        timeout_seconds=args.timeout_seconds,
        sleep_seconds=args.sleep_seconds,
        max_rows=args.max_rows,
    )


if __name__ == "__main__":
    main()
