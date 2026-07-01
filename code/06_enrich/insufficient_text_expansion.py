from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "lib"))

from econqt_common import clean_text, normalize_doi  # noqa: E402


EXPANSION_PLAN_COLUMNS = [
    "expansion_lane",
    "lane_type",
    "recovery_action",
    "journal_short",
    "decade",
    "row_count",
    "high_priority_rows",
    "medium_priority_rows",
    "low_priority_rows",
    "min_recovery_rank",
    "max_recovery_rank",
    "doi_rows",
    "openalex_rows",
    "oa_pdf_rows",
    "partial_short_text_rows",
    "suggested_command",
    "review_note",
]

EXPANSION_OVERVIEW_COLUMNS = [
    "expansion_lane",
    "lane_type",
    "row_count",
    "high_priority_rows",
    "medium_priority_rows",
    "low_priority_rows",
    "min_recovery_rank",
    "top_journal_decades",
    "suggested_command",
    "review_note",
]

DOI_PREFIX_COLUMNS = [
    "doi_prefix",
    "row_count",
    "high_priority_rows",
    "medium_priority_rows",
    "low_priority_rows",
    "min_recovery_rank",
    "expansion_lanes",
    "journal_decades",
    "prior_attempted_articles",
    "prior_found_articles",
    "prior_error_attempts",
    "prior_not_found_attempts",
    "prior_skipped_attempts",
    "prior_not_cached_attempts",
    "prior_rate_limited_attempts",
    "prior_attempt_note",
    "suggested_command",
]

ATTEMPT_SUMMARY_COLUMNS = [
    "doi_prefix",
    "attempt_source",
    "attempt_rows",
    "attempted_articles",
    "found_articles",
    "found_attempts",
    "error_attempts",
    "not_found_attempts",
    "skipped_attempts",
    "not_cached_attempts",
    "rate_limited_attempts",
    "other_attempts",
    "top_errors",
]

RECOVERY_DECISION_COLUMNS = [
    "decision_unit",
    "unit_type",
    "row_count",
    "high_priority_rows",
    "min_recovery_rank",
    "prior_attempted_articles",
    "prior_found_articles",
    "prior_failed_attempts",
    "best_prior_source",
    "best_prior_source_found_articles",
    "top_failure_source",
    "top_failure_attempts",
    "decision",
    "recommended_next_step",
    "rationale",
    "supporting_command_or_artifact",
]

SOURCE_INVESTIGATION_COLUMNS = [
    "investigation_rank",
    "decision_unit",
    "unit_type",
    "decision",
    "investigation_type",
    "doi_prefix",
    "expansion_lane",
    "attempt_source",
    "attempt_status",
    "recovery_rank",
    "recovery_batch",
    "recovery_action",
    "article_id",
    "journal_short",
    "publication_year",
    "decade",
    "title",
    "doi",
    "attempt_url",
    "attempt_error",
    "attempt_detail",
    "article_url",
    "openalex_id",
    "oa_pdf_url",
    "doi_url",
    "crossref_work_url",
    "openalex_work_url",
    "source_note",
]

SOURCE_ROUTE_MATRIX_COLUMNS = [
    "route_unit",
    "unit_type",
    "row_count",
    "high_priority_rows",
    "decision",
    "current_route_status",
    "prior_best_source",
    "prior_found_articles",
    "prior_failed_attempts",
    "probe_rows",
    "probe_abstract_found_rows",
    "probe_pdf_candidate_rows",
    "probe_access_challenge_rows",
    "probe_not_found_rows",
    "probe_error_rows",
    "recommended_route_action",
    "source_route_note",
    "next_artifact",
]

FAILURE_ATTEMPT_STATUSES = {"error", "not_found", "skipped", "not_cached", "rate_limited"}


def nonempty(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip().ne("")


def numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(0, index=df.index, dtype="int64")
    return pd.to_numeric(df[column], errors="coerce").fillna(0).astype(int)


def doi_starts_with(value: Any, prefix: str) -> bool:
    return normalize_doi(value).startswith(prefix)


def doi_prefix_family(value: Any) -> str:
    doi = normalize_doi(value)
    if not doi:
        return ""
    known_prefixes = ["10.1257", "10.7916", "10.1086", "10.3982", "10.2307", "10.1111"]
    for prefix in known_prefixes:
        if doi.startswith(prefix):
            return prefix
    parts = doi.split("/")
    if len(parts) >= 2 and parts[0] == "10.1093":
        journal_part = parts[1].split(".")[0].strip()
        return f"10.1093/{journal_part}" if journal_part else "10.1093"
    return parts[0]


def expansion_lane(row: pd.Series | dict[str, Any]) -> str:
    action = clean_text(row.get("recovery_action", "") if hasattr(row, "get") else "")
    doi = normalize_doi(row.get("doi", "") if hasattr(row, "get") else "")
    if action == "review_oa_pdf_or_first_pages":
        return "oa_pdf_review"
    if action == "extend_existing_short_abstract":
        return "partial_short_text_extension"
    if action == "review_openalex_or_title_match":
        return "openalex_or_title_search"
    if action == "review_article_landing_page":
        return "article_landing_page_review"
    if action == "manual_title_year_search":
        return "manual_title_year_search"
    if action == "recover_abstract_from_doi_or_publisher":
        if doi.startswith("10.1257"):
            return "aea_publisher_metadata_10_1257"
        if doi.startswith("10.7916"):
            return "academic_commons_metadata_10_7916"
        if doi.startswith("10.1086"):
            return "jpe_chicago_or_repec_10_1086"
        if doi.startswith("10.3982"):
            return "econometric_society_10_3982"
        if doi.startswith("10.2307"):
            return "jstor_or_legacy_metadata_10_2307"
        if doi.startswith("10.1111"):
            return "wiley_or_society_metadata_10_1111"
        return "doi_publisher_metadata_other"
    return "unassigned_review"


def lane_type(lane: str) -> str:
    if lane in {
        "aea_publisher_metadata_10_1257",
        "academic_commons_metadata_10_7916",
        "jpe_chicago_or_repec_10_1086",
        "econometric_society_10_3982",
        "jstor_or_legacy_metadata_10_2307",
        "wiley_or_society_metadata_10_1111",
        "doi_publisher_metadata_other",
    }:
        return "targeted_source_pass"
    if lane == "oa_pdf_review":
        return "pdf_or_ocr_review"
    if lane in {"partial_short_text_extension", "openalex_or_title_search", "article_landing_page_review", "manual_title_year_search"}:
        return "manual_recovery"
    return "review"


def lane_command(lane: str, rows: int) -> str:
    max_queries = max(rows, 20)
    if lane == "aea_publisher_metadata_10_1257":
        return f"python3 run_text_enrichment.py --classified-input data/final/articles_classified_enriched_pilot.csv --articles-input data/final/articles_pilot.csv --sources publisher_metadata --doi-prefixes 10.1257 --max-queries {max_queries}"
    if lane == "academic_commons_metadata_10_7916":
        return f"python3 run_text_enrichment.py --classified-input data/final/articles_classified_enriched_pilot.csv --articles-input data/final/articles_pilot.csv --sources publisher_metadata --doi-prefixes 10.7916 --max-queries {max_queries}"
    if lane == "jpe_chicago_or_repec_10_1086":
        return f"python3 run_text_enrichment.py --classified-input data/final/articles_classified_enriched_pilot.csv --articles-input data/final/articles_pilot.csv --sources publisher_metadata,econpapers --doi-prefixes 10.1086 --max-queries {max_queries}"
    if lane == "econometric_society_10_3982":
        return f"python3 run_text_enrichment.py --classified-input data/final/articles_classified_enriched_pilot.csv --articles-input data/final/articles_pilot.csv --sources publisher_metadata --doi-prefixes 10.3982 --max-queries {max_queries}"
    if lane == "jstor_or_legacy_metadata_10_2307":
        return "Use run_scienceon_recovery_scan.py in bounded recovery-batch passes for exact DOI/title ScienceOn citation_abstract matches; do not scrape JSTOR access-challenge pages."
    if lane == "wiley_or_society_metadata_10_1111":
        return "No automated publisher_metadata route is currently enabled for 10.1111; Wiley landing pages returned access challenges in probe."
    if lane == "doi_publisher_metadata_other":
        return "Review top DOI prefixes in the detail CSV, then run a bounded publisher_metadata pass for one prefix at a time."
    if lane == "oa_pdf_review":
        return "Review OA PDF blockers or run targeted OCR only for reachable PDFs; do not scrape restricted full text."
    if lane == "partial_short_text_extension":
        return "Use recovery batch forms to extend short existing abstracts from publisher or index metadata."
    if lane == "openalex_or_title_search":
        return "Use recovery batch links for OpenAlex/Crossref title searches; import only high-confidence title matches."
    if lane == "article_landing_page_review":
        return "Open article landing-page links in recovery batches and backfill only explicit abstracts."
    if lane == "manual_title_year_search":
        return "Use title/year search manually; keep title-only guesses as review notes, not final labels."
    return "Inspect rows manually before choosing an enrichment command."


def lane_note(lane: str) -> str:
    if lane == "doi_publisher_metadata_other":
        return "Large mixed DOI lane; split by DOI prefix before running network calls."
    if lane == "jstor_or_legacy_metadata_10_2307":
        return "Use the tested ScienceOn public metadata route in bounded batches; import only exact DOI/title citation_abstract matches."
    if lane == "wiley_or_society_metadata_10_1111":
        return "Use manual/index recovery until a public metadata route is tested; do not scrape Wiley access-challenge pages."
    if lane == "oa_pdf_review":
        return "Some PDFs may already be blocked by HTTP errors; prefer cached/reachable PDFs and OCR only first pages."
    if lane == "manual_title_year_search":
        return "Lowest automation yield; use after source-family passes and keep source URLs for each accepted abstract."
    return "Run bounded passes, inspect yield, then rebuild classification diagnostics."


def prepare_queue(queue: pd.DataFrame) -> pd.DataFrame:
    work = queue.copy().fillna("")
    if work.empty:
        return work.assign(expansion_lane=[], lane_type=[])
    for column in ["recovery_action", "journal_short", "decade", "doi", "openalex_id", "oa_pdf_url", "text_enrichment_status"]:
        if column not in work.columns:
            work[column] = ""
    work["expansion_lane"] = work.apply(expansion_lane, axis=1)
    work["lane_type"] = work["expansion_lane"].map(lane_type)
    work["doi_prefix"] = work["doi"].map(doi_prefix_family)
    work["_recovery_rank"] = numeric_series(work, "recovery_rank")
    work["_is_high"] = work["recovery_priority"].astype(str).eq("high") if "recovery_priority" in work else False
    work["_is_medium"] = work["recovery_priority"].astype(str).eq("medium") if "recovery_priority" in work else False
    work["_is_low"] = work["recovery_priority"].astype(str).eq("low") if "recovery_priority" in work else False
    work["_has_doi"] = nonempty(work["doi"])
    work["_has_openalex"] = nonempty(work["openalex_id"])
    work["_has_oa_pdf"] = nonempty(work["oa_pdf_url"])
    work["_is_partial_short_text"] = work["text_enrichment_status"].astype(str).eq("partial_short_text")
    return work


def top_cells_for_lane(work: pd.DataFrame, lane: str, max_cells: int = 3) -> str:
    lane_rows = work[work["expansion_lane"].eq(lane)]
    if lane_rows.empty:
        return ""
    cells = (
        lane_rows.groupby(["journal_short", "decade"], dropna=False)
        .size()
        .reset_index(name="rows")
        .sort_values(["rows", "journal_short", "decade"], ascending=[False, True, True])
        .head(max_cells)
    )
    return "; ".join(f"{clean_text(row['journal_short']) or 'missing'} {clean_text(row['decade']) or 'missing'} ({int(row['rows'])})" for _, row in cells.iterrows())


def compact_unique(values: pd.Series, max_items: int = 5) -> str:
    items = [clean_text(value) for value in values if clean_text(value)]
    unique = sorted(set(items))
    shown = unique[:max_items]
    suffix = f"; +{len(unique) - max_items} more" if len(unique) > max_items else ""
    return "; ".join(shown) + suffix


def top_values(values: pd.Series, max_items: int = 3, max_value_chars: int = 140) -> str:
    cleaned = [clean_text(value) for value in values if clean_text(value)]
    if not cleaned:
        return ""
    counts = pd.Series(cleaned).value_counts().head(max_items)
    shown = []
    for index, value in counts.items():
        label = str(index)
        if len(label) > max_value_chars:
            label = label[: max_value_chars - 3].rstrip() + "..."
        shown.append(f"{label} ({int(value)})")
    return "; ".join(shown)


def prepare_attempts(attempts: pd.DataFrame) -> pd.DataFrame:
    work = attempts.copy().fillna("")
    if work.empty or "doi" not in work.columns:
        return pd.DataFrame(columns=["doi_prefix"])
    for column in ["article_id", "attempt_source", "attempt_status", "attempt_error"]:
        if column not in work.columns:
            work[column] = ""
    work["doi_prefix"] = work["doi"].map(doi_prefix_family)
    work = work[work["doi_prefix"].astype(str).str.strip().ne("")].copy()
    return work


def with_required_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    work = df.copy()
    for column in columns:
        if column not in work.columns:
            work[column] = ""
    return work


def attempt_status_count(group: pd.DataFrame, status: str) -> int:
    return int(group["attempt_status"].astype(str).eq(status).sum()) if "attempt_status" in group else 0


def attempt_summary_by_prefix_source(attempts: pd.DataFrame) -> pd.DataFrame:
    work = prepare_attempts(attempts)
    if work.empty:
        return pd.DataFrame(columns=ATTEMPT_SUMMARY_COLUMNS)
    rows: list[dict[str, Any]] = []
    for (prefix, source), group in work.groupby(["doi_prefix", "attempt_source"], dropna=False):
        found = group[group["attempt_status"].astype(str).eq("found")]
        known_statuses = {"found", "error", "not_found", "skipped", "not_cached", "rate_limited"}
        rows.append(
            {
                "doi_prefix": clean_text(prefix),
                "attempt_source": clean_text(source),
                "attempt_rows": len(group),
                "attempted_articles": group["article_id"].astype(str).str.strip().replace("", pd.NA).dropna().nunique(),
                "found_articles": found["article_id"].astype(str).str.strip().replace("", pd.NA).dropna().nunique(),
                "found_attempts": attempt_status_count(group, "found"),
                "error_attempts": attempt_status_count(group, "error"),
                "not_found_attempts": attempt_status_count(group, "not_found"),
                "skipped_attempts": attempt_status_count(group, "skipped"),
                "not_cached_attempts": attempt_status_count(group, "not_cached"),
                "rate_limited_attempts": attempt_status_count(group, "rate_limited"),
                "other_attempts": int((~group["attempt_status"].astype(str).isin(known_statuses)).sum()),
                "top_errors": top_values(
                    group.loc[group["attempt_status"].astype(str).eq("error"), "attempt_error"],
                    max_items=2,
                    max_value_chars=80,
                ),
            }
        )
    return pd.DataFrame(rows, columns=ATTEMPT_SUMMARY_COLUMNS).sort_values(
        ["doi_prefix", "attempt_source"],
        ascending=[True, True],
    ).reset_index(drop=True)


def attempt_rollup_by_prefix(attempts: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "doi_prefix",
        "prior_attempted_articles",
        "prior_found_articles",
        "prior_error_attempts",
        "prior_not_found_attempts",
        "prior_skipped_attempts",
        "prior_not_cached_attempts",
        "prior_rate_limited_attempts",
    ]
    work = prepare_attempts(attempts)
    if work.empty:
        return pd.DataFrame(columns=columns)
    rows: list[dict[str, Any]] = []
    for prefix, group in work.groupby("doi_prefix", dropna=False):
        found = group[group["attempt_status"].astype(str).eq("found")]
        rows.append(
            {
                "doi_prefix": clean_text(prefix),
                "prior_attempted_articles": group["article_id"].astype(str).str.strip().replace("", pd.NA).dropna().nunique(),
                "prior_found_articles": found["article_id"].astype(str).str.strip().replace("", pd.NA).dropna().nunique(),
                "prior_error_attempts": attempt_status_count(group, "error"),
                "prior_not_found_attempts": attempt_status_count(group, "not_found"),
                "prior_skipped_attempts": attempt_status_count(group, "skipped"),
                "prior_not_cached_attempts": attempt_status_count(group, "not_cached"),
                "prior_rate_limited_attempts": attempt_status_count(group, "rate_limited"),
            }
        )
    grouped = pd.DataFrame(rows, columns=columns)
    return grouped[columns]


def prior_attempt_note(row: pd.Series | dict[str, Any]) -> str:
    attempted = int(row.get("prior_attempted_articles", 0) or 0)
    found = int(row.get("prior_found_articles", 0) or 0)
    errors = int(row.get("prior_error_attempts", 0) or 0)
    not_found = int(row.get("prior_not_found_attempts", 0) or 0)
    skipped = int(row.get("prior_skipped_attempts", 0) or 0)
    if attempted == 0:
        return "No prior source attempts recorded for this DOI prefix."
    if found > 0 and (errors + not_found) > found:
        return "Prior attempts recovered some rows but mostly failed or found no abstract; inspect source-specific failures before rerunning the full prefix."
    if found > 0:
        return "Prior attempts recovered rows; rerun only if new source logic or cache state changed."
    if errors or not_found:
        return "Prior attempts did not recover rows; prefer manual/index recovery or source-specific code changes over rerunning unchanged logic."
    if skipped:
        return "Prior attempts were skipped; rerun only if source routing changed."
    return "Prior attempts recorded; inspect attempt summary before rerunning."


def source_context_by_prefix(attempt_summary: pd.DataFrame) -> dict[str, dict[str, Any]]:
    if attempt_summary.empty:
        return {}
    work = attempt_summary.copy()
    numeric_columns = [
        "attempt_rows",
        "found_articles",
        "found_attempts",
        "error_attempts",
        "not_found_attempts",
        "skipped_attempts",
        "not_cached_attempts",
        "rate_limited_attempts",
    ]
    for column in numeric_columns:
        if column not in work.columns:
            work[column] = 0
        work[column] = pd.to_numeric(work[column], errors="coerce").fillna(0).astype(int)
    work["_failed_attempts"] = (
        work["error_attempts"]
        + work["not_found_attempts"]
        + work["skipped_attempts"]
        + work["not_cached_attempts"]
        + work["rate_limited_attempts"]
    )
    context: dict[str, dict[str, Any]] = {}
    for prefix, group in work.groupby("doi_prefix", dropna=False):
        best = group.sort_values(
            ["found_articles", "found_attempts", "attempt_rows", "attempt_source"],
            ascending=[False, False, False, True],
        ).iloc[0]
        failure = group.sort_values(
            ["_failed_attempts", "attempt_rows", "attempt_source"],
            ascending=[False, False, True],
        ).iloc[0]
        context[clean_text(prefix)] = {
            "best_prior_source": clean_text(best.get("attempt_source", "")),
            "best_prior_source_found_articles": int(best.get("found_articles", 0) or 0),
            "top_failure_source": clean_text(failure.get("attempt_source", "")),
            "top_failure_attempts": int(failure.get("_failed_attempts", 0) or 0),
        }
    return context


def doi_prefix_decision(row: pd.Series | dict[str, Any]) -> tuple[str, str, str]:
    prefix = clean_text(row.get("doi_prefix", ""))
    row_count = int(row.get("row_count", 0) or 0)
    attempted = int(row.get("prior_attempted_articles", 0) or 0)
    found = int(row.get("prior_found_articles", 0) or 0)
    failed = (
        int(row.get("prior_error_attempts", 0) or 0)
        + int(row.get("prior_not_found_attempts", 0) or 0)
        + int(row.get("prior_skipped_attempts", 0) or 0)
        + int(row.get("prior_not_cached_attempts", 0) or 0)
        + int(row.get("prior_rate_limited_attempts", 0) or 0)
    )
    suggested = clean_text(row.get("suggested_command", ""))
    unsupported = suggested.startswith("No automated")

    if prefix == "10.2307":
        return (
            "bounded_scienceon_recovery",
            "Run the ScienceOn recovery scanner in bounded recovery-batch passes, then stage/preflight/import only exact DOI/title citation_abstract matches.",
            f"{prefix} has {row_count} unresolved rows, and bounded R002/R003 ScienceOn scans recovered tier-A formal abstracts with high yield.",
        )
    if unsupported and row_count >= 50:
        return (
            "new_source_template_or_manual_recovery",
            "Do not rerun existing enrichment logic. Either test a lawful public metadata route for this prefix or move rows through recovery batches.",
            f"{prefix} has {row_count} unresolved rows and no enabled automated metadata route; prior attempts found {found} articles but logged {failed} failed/skipped/not-cached/rate-limited attempts.",
        )
    if unsupported:
        return (
            "low_volume_manual_recovery",
            "Handle this prefix inside the ordinary recovery batches unless a tested metadata route is cheap to add.",
            f"{prefix} has only {row_count} unresolved rows and no enabled automated metadata route.",
        )
    if attempted == 0:
        return (
            "bounded_source_pass",
            "Run the suggested bounded source-family command, inspect yield, then rebuild classification diagnostics.",
            f"{prefix} has {row_count} unresolved rows and no prior attempts recorded in the current attempt log.",
        )
    if found > 0 and failed > max(found * 2, 25):
        return (
            "source_specific_investigation_before_rerun",
            "Sample failed source URLs/errors, add parser or routing changes if justified, then rerun a bounded prefix pass.",
            f"{prefix} recovered {found} prior articles but logged {failed} failed/skipped/not-cached/rate-limited attempts, so an unchanged full-prefix rerun is likely low yield.",
        )
    if found > 0:
        return (
            "bounded_rerun_only_if_logic_changed",
            "Rerun only after source logic, credentials, or cache state changes; otherwise prioritize unrecovered manual batches.",
            f"{prefix} already recovered {found} prior articles from {attempted} attempted articles.",
        )
    if failed > 0:
        return (
            "do_not_rerun_unchanged_logic",
            "Prefer manual/index recovery or source-specific code changes before another automated pass.",
            f"{prefix} has prior attempts but no recovered articles and {failed} failed/skipped/not-cached/rate-limited attempts.",
        )
    return (
        "inspect_before_rerun",
        "Inspect the source attempt summary before running another pass.",
        f"{prefix} has prior attempts recorded but no clear recovery signal.",
    )


def lane_decision(row: pd.Series | dict[str, Any]) -> tuple[str, str, str, str]:
    lane = clean_text(row.get("expansion_lane", ""))
    if lane == "oa_pdf_review":
        return (
            "inspect_pdf_blockers",
            "Review blocker rows first; run OCR only for reachable OA PDFs and never scrape restricted full text.",
            "The OA-PDF lane is small and high priority, but prior blockers include HTTP errors, HTML responses, and timeouts.",
            "outputs/tables/enriched/remaining_oa_pdf_download_blockers.csv",
        )
    if lane == "partial_short_text_extension":
        return (
            "manual_abstract_extension",
            "Use recovery batch forms to extend short abstracts from explicit publisher/index metadata, then import completed rows with --skip-empty-abstracts.",
            "These rows already contain partial text, so manual extension is more controlled than source-wide scraping.",
            "data/intermediate/insufficient_text_recovery_batches/",
        )
    if lane == "openalex_or_title_search":
        return (
            "manual_index_search",
            "Use OpenAlex/Crossref/title-search links in recovery batches and import only high-confidence abstract backfills.",
            "This lane has many rows without a DOI route; title-only suggestions remain triage and must not change final labels.",
            "data/intermediate/insufficient_text_recovery_batches/",
        )
    if lane == "manual_title_year_search":
        return (
            "manual_low_yield_search",
            "Handle after higher-priority DOI, PDF, and partial-text lanes.",
            "Title/year search has the weakest automation signal and should be used only for targeted backfills.",
            "data/intermediate/insufficient_text_recovery_batches/",
        )
    if clean_text(row.get("lane_type", "")) == "targeted_source_pass":
        return (
            "see_doi_prefix_decisions",
            "Use the DOI-prefix decision rows before running this lane command.",
            "Targeted source lanes can mix supported and unsupported prefixes; prefix-level attempt history is more informative.",
            clean_text(row.get("suggested_command", "")),
        )
    return (
        "inspect_lane",
        "Inspect the lane detail table before choosing a recovery action.",
        "No specific decision rule matched this lane.",
        clean_text(row.get("suggested_command", "")),
    )


def doi_prefix_suggested_command(prefix: str, rows: int) -> str:
    if not prefix:
        return ""
    max_queries = max(rows, 20)
    supported = {
        "10.1257": f"python3 run_text_enrichment.py --classified-input data/final/articles_classified_enriched_pilot.csv --articles-input data/final/articles_pilot.csv --sources publisher_metadata --doi-prefixes 10.1257 --max-queries {max_queries}",
        "10.7916": f"python3 run_text_enrichment.py --classified-input data/final/articles_classified_enriched_pilot.csv --articles-input data/final/articles_pilot.csv --sources publisher_metadata --doi-prefixes 10.7916 --max-queries {max_queries}",
        "10.1086": f"python3 run_text_enrichment.py --classified-input data/final/articles_classified_enriched_pilot.csv --articles-input data/final/articles_pilot.csv --sources publisher_metadata,econpapers --doi-prefixes 10.1086 --max-queries {max_queries}",
        "10.3982": f"python3 run_text_enrichment.py --classified-input data/final/articles_classified_enriched_pilot.csv --articles-input data/final/articles_pilot.csv --sources publisher_metadata --doi-prefixes 10.3982 --max-queries {max_queries}",
    }
    if prefix in supported:
        return supported[prefix]
    unsupported = {
        "10.1111": "No automated publisher_metadata route is currently enabled for 10.1111; Wiley landing pages returned access challenges in probe.",
        "10.1093/qje": "No automated publisher_metadata route is currently enabled for 10.1093/qje; OUP landing pages returned access challenges in probe.",
        "10.1093/restud": "No automated publisher_metadata route is currently enabled for 10.1093/restud; OUP landing pages returned access challenges in probe.",
        "10.1093/res": "No automated publisher_metadata route is currently enabled for 10.1093/res; OUP landing pages returned access challenges in probe.",
        "10.1162": "No automated publisher_metadata route is currently enabled for 10.1162; sampled MIT Press legacy DOI pages returned not-found pages.",
    }
    if prefix == "10.2307":
        return "python3 run_scienceon_recovery_scan.py --action-packet outputs/tables/enriched/recovery_batch_BATCH_ID_review_queue.csv --split-summary outputs/tables/enriched/recovery_batch_BATCH_ID_split_summary.csv --confirmed-export data/intermediate/insufficient_text_recovery_review_exports/BATCH_ID/recovery_batch_BATCH_ID_confirmed_source_rows.csv --append-export --max-rows 25"
    if prefix in unsupported:
        return unsupported[prefix]
    return f"No automated publisher_metadata route is currently enabled for {prefix}; add a tested public metadata template before running network calls."


def doi_prefix_expansion_summary(work: pd.DataFrame, attempts: pd.DataFrame | None = None) -> pd.DataFrame:
    if work.empty or "doi_prefix" not in work.columns:
        return pd.DataFrame(columns=DOI_PREFIX_COLUMNS)
    doi_rows = work[work["doi_prefix"].astype(str).str.strip().ne("")].copy()
    if doi_rows.empty:
        return pd.DataFrame(columns=DOI_PREFIX_COLUMNS)
    doi_rows["_journal_decade"] = doi_rows["journal_short"].astype(str).str.strip() + " " + doi_rows["decade"].astype(str).str.strip()
    out = (
        doi_rows.groupby("doi_prefix", dropna=False)
        .agg(
            row_count=("article_id", "size"),
            high_priority_rows=("_is_high", "sum"),
            medium_priority_rows=("_is_medium", "sum"),
            low_priority_rows=("_is_low", "sum"),
            min_recovery_rank=("_recovery_rank", "min"),
            expansion_lanes=("expansion_lane", compact_unique),
            journal_decades=("_journal_decade", compact_unique),
        )
        .reset_index()
    )
    rollup = attempt_rollup_by_prefix(attempts if attempts is not None else pd.DataFrame())
    if not rollup.empty:
        out = out.merge(rollup, on="doi_prefix", how="left")
    for column in [
        "prior_attempted_articles",
        "prior_found_articles",
        "prior_error_attempts",
        "prior_not_found_attempts",
        "prior_skipped_attempts",
        "prior_not_cached_attempts",
        "prior_rate_limited_attempts",
    ]:
        if column not in out.columns:
            out[column] = 0
        out[column] = pd.to_numeric(out[column], errors="coerce").fillna(0).astype(int)
    out["prior_attempt_note"] = out.apply(prior_attempt_note, axis=1)
    out["suggested_command"] = [doi_prefix_suggested_command(prefix, int(rows)) for prefix, rows in zip(out["doi_prefix"], out["row_count"])]
    return out[DOI_PREFIX_COLUMNS].sort_values(["min_recovery_rank", "row_count", "doi_prefix"], ascending=[True, False, True]).reset_index(drop=True)


def insufficient_text_expansion_plan(queue: pd.DataFrame, attempts: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    raw_attempts = attempts if attempts is not None else pd.DataFrame()
    attempt_summary = attempt_summary_by_prefix_source(raw_attempts)
    if queue.empty:
        return (
            pd.DataFrame(columns=EXPANSION_OVERVIEW_COLUMNS),
            pd.DataFrame(columns=EXPANSION_PLAN_COLUMNS),
            pd.DataFrame(columns=DOI_PREFIX_COLUMNS),
            attempt_summary,
        )
    work = prepare_queue(queue)
    if work.empty:
        return (
            pd.DataFrame(columns=EXPANSION_OVERVIEW_COLUMNS),
            pd.DataFrame(columns=EXPANSION_PLAN_COLUMNS),
            pd.DataFrame(columns=DOI_PREFIX_COLUMNS),
            attempt_summary,
        )

    group_cols = ["expansion_lane", "lane_type", "recovery_action", "journal_short", "decade"]
    detail = (
        work.groupby(group_cols, dropna=False)
        .agg(
            row_count=("article_id", "size"),
            high_priority_rows=("_is_high", "sum"),
            medium_priority_rows=("_is_medium", "sum"),
            low_priority_rows=("_is_low", "sum"),
            min_recovery_rank=("_recovery_rank", "min"),
            max_recovery_rank=("_recovery_rank", "max"),
            doi_rows=("_has_doi", "sum"),
            openalex_rows=("_has_openalex", "sum"),
            oa_pdf_rows=("_has_oa_pdf", "sum"),
            partial_short_text_rows=("_is_partial_short_text", "sum"),
        )
        .reset_index()
    )
    detail["suggested_command"] = [lane_command(lane, int(rows)) for lane, rows in zip(detail["expansion_lane"], detail["row_count"])]
    detail["review_note"] = detail["expansion_lane"].map(lane_note)
    detail = detail[EXPANSION_PLAN_COLUMNS].sort_values(
        ["min_recovery_rank", "row_count", "expansion_lane", "journal_short", "decade"],
        ascending=[True, False, True, True, True],
    ).reset_index(drop=True)

    overview = (
        work.groupby(["expansion_lane", "lane_type"], dropna=False)
        .agg(
            row_count=("article_id", "size"),
            high_priority_rows=("_is_high", "sum"),
            medium_priority_rows=("_is_medium", "sum"),
            low_priority_rows=("_is_low", "sum"),
            min_recovery_rank=("_recovery_rank", "min"),
        )
        .reset_index()
    )
    overview["top_journal_decades"] = overview["expansion_lane"].map(lambda lane: top_cells_for_lane(work, lane))
    overview["suggested_command"] = [lane_command(lane, int(rows)) for lane, rows in zip(overview["expansion_lane"], overview["row_count"])]
    overview["review_note"] = overview["expansion_lane"].map(lane_note)
    overview = overview[EXPANSION_OVERVIEW_COLUMNS].sort_values(
        ["min_recovery_rank", "row_count", "expansion_lane"],
        ascending=[True, False, True],
    ).reset_index(drop=True)
    doi_prefixes = doi_prefix_expansion_summary(work, raw_attempts)
    return overview, detail, doi_prefixes, attempt_summary


def recovery_decision_plan(overview: pd.DataFrame, doi_prefixes: pd.DataFrame, attempt_summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    source_context = source_context_by_prefix(attempt_summary)

    for _, row in doi_prefixes.iterrows():
        prefix = clean_text(row.get("doi_prefix", ""))
        context = source_context.get(prefix, {})
        decision, next_step, rationale = doi_prefix_decision(row)
        failed = (
            int(row.get("prior_error_attempts", 0) or 0)
            + int(row.get("prior_not_found_attempts", 0) or 0)
            + int(row.get("prior_skipped_attempts", 0) or 0)
            + int(row.get("prior_not_cached_attempts", 0) or 0)
            + int(row.get("prior_rate_limited_attempts", 0) or 0)
        )
        rows.append(
            {
                "decision_unit": prefix,
                "unit_type": "doi_prefix",
                "row_count": int(row.get("row_count", 0) or 0),
                "high_priority_rows": int(row.get("high_priority_rows", 0) or 0),
                "min_recovery_rank": int(row.get("min_recovery_rank", 0) or 0),
                "prior_attempted_articles": int(row.get("prior_attempted_articles", 0) or 0),
                "prior_found_articles": int(row.get("prior_found_articles", 0) or 0),
                "prior_failed_attempts": failed,
                "best_prior_source": context.get("best_prior_source", ""),
                "best_prior_source_found_articles": context.get("best_prior_source_found_articles", 0),
                "top_failure_source": context.get("top_failure_source", ""),
                "top_failure_attempts": context.get("top_failure_attempts", 0),
                "decision": decision,
                "recommended_next_step": next_step,
                "rationale": rationale,
                "supporting_command_or_artifact": clean_text(row.get("suggested_command", "")),
            }
        )

    for _, row in overview.iterrows():
        decision, next_step, rationale, artifact = lane_decision(row)
        rows.append(
            {
                "decision_unit": clean_text(row.get("expansion_lane", "")),
                "unit_type": "expansion_lane",
                "row_count": int(row.get("row_count", 0) or 0),
                "high_priority_rows": int(row.get("high_priority_rows", 0) or 0),
                "min_recovery_rank": int(row.get("min_recovery_rank", 0) or 0),
                "prior_attempted_articles": 0,
                "prior_found_articles": 0,
                "prior_failed_attempts": 0,
                "best_prior_source": "",
                "best_prior_source_found_articles": 0,
                "top_failure_source": "",
                "top_failure_attempts": 0,
                "decision": decision,
                "recommended_next_step": next_step,
                "rationale": rationale,
                "supporting_command_or_artifact": artifact,
            }
        )

    if not rows:
        return pd.DataFrame(columns=RECOVERY_DECISION_COLUMNS)
    return pd.DataFrame(rows, columns=RECOVERY_DECISION_COLUMNS).sort_values(
        ["min_recovery_rank", "unit_type", "row_count", "decision_unit"],
        ascending=[True, True, False, True],
    ).reset_index(drop=True)


def row_int(value: Any, default: int = 999999) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def build_investigation_row(
    *,
    rank: int,
    decision_row: pd.Series | dict[str, Any],
    investigation_type: str,
    source_note: str,
    queue_row: pd.Series | dict[str, Any] | None = None,
    attempt_row: pd.Series | dict[str, Any] | None = None,
) -> dict[str, Any]:
    queue_data = queue_row if queue_row is not None else {}
    attempt_data = attempt_row if attempt_row is not None else {}

    def value(column: str) -> str:
        queue_value = queue_data.get(column, "") if hasattr(queue_data, "get") else ""
        if clean_text(queue_value):
            return clean_text(queue_value)
        attempt_value = attempt_data.get(column, "") if hasattr(attempt_data, "get") else ""
        return clean_text(attempt_value)

    return {
        "investigation_rank": rank,
        "decision_unit": clean_text(decision_row.get("decision_unit", "")),
        "unit_type": clean_text(decision_row.get("unit_type", "")),
        "decision": clean_text(decision_row.get("decision", "")),
        "investigation_type": investigation_type,
        "doi_prefix": value("doi_prefix"),
        "expansion_lane": value("expansion_lane"),
        "attempt_source": value("attempt_source"),
        "attempt_status": value("attempt_status"),
        "recovery_rank": value("recovery_rank"),
        "recovery_batch": value("recovery_batch"),
        "recovery_action": value("recovery_action"),
        "article_id": value("article_id"),
        "journal_short": value("journal_short"),
        "publication_year": value("publication_year"),
        "decade": value("decade"),
        "title": value("title"),
        "doi": value("doi"),
        "attempt_url": value("attempt_url"),
        "attempt_error": value("attempt_error"),
        "attempt_detail": value("attempt_detail"),
        "article_url": value("article_url"),
        "openalex_id": value("openalex_id"),
        "oa_pdf_url": value("oa_pdf_url"),
        "doi_url": value("doi_url"),
        "crossref_work_url": value("crossref_work_url"),
        "openalex_work_url": value("openalex_work_url"),
        "source_note": source_note,
    }


def sample_attempts_for_investigation(attempts: pd.DataFrame, queue_rows: pd.DataFrame, max_rows_per_group: int) -> pd.DataFrame:
    if attempts.empty:
        return attempts
    work = attempts.copy()
    rank_map = {}
    if not queue_rows.empty and "article_id" in queue_rows.columns:
        rank_map = queue_rows.set_index("article_id")["_recovery_rank"].to_dict()
    work["_sort_recovery_rank"] = work["article_id"].map(rank_map).map(row_int) if "article_id" in work else 999999
    work["_sort_publication_year"] = work["publication_year"].map(lambda value: row_int(value, default=9999)) if "publication_year" in work else 9999
    work = work.sort_values(["_sort_recovery_rank", "_sort_publication_year", "article_id", "attempt_source", "attempt_status"])
    work = work.drop_duplicates(subset=["article_id", "attempt_source", "attempt_status", "attempt_url", "attempt_error"], keep="first")
    return work.groupby(["attempt_source", "attempt_status"], dropna=False).head(max_rows_per_group).reset_index(drop=True)


def source_investigation_packet(
    queue: pd.DataFrame,
    attempts: pd.DataFrame,
    decisions: pd.DataFrame,
    *,
    max_rows_per_group: int = 5,
) -> pd.DataFrame:
    if queue.empty or decisions.empty:
        return pd.DataFrame(columns=SOURCE_INVESTIGATION_COLUMNS)

    queue_work = with_required_columns(
        prepare_queue(queue),
        [
            "article_id",
            "recovery_rank",
            "recovery_batch",
            "recovery_action",
            "journal_short",
            "publication_year",
            "decade",
            "title",
            "doi",
            "article_url",
            "openalex_id",
            "oa_pdf_url",
            "doi_url",
            "crossref_work_url",
            "openalex_work_url",
        ],
    )
    attempts_work = with_required_columns(
        prepare_attempts(attempts),
        [
            "article_id",
            "journal_short",
            "publication_year",
            "title",
            "doi",
            "article_url",
            "attempt_source",
            "attempt_status",
            "attempt_url",
            "attempt_error",
            "attempt_detail",
        ],
    )
    queue_lookup = queue_work.set_index("article_id", drop=False) if "article_id" in queue_work.columns else pd.DataFrame()
    current_article_ids = set(queue_work["article_id"].astype(str).str.strip())
    rows: list[dict[str, Any]] = []
    rank = 1

    doi_decisions = decisions[
        decisions["unit_type"].astype(str).eq("doi_prefix")
        & decisions["decision"].astype(str).isin(
            [
                "source_specific_investigation_before_rerun",
                "new_source_template_or_manual_recovery",
                "do_not_rerun_unchanged_logic",
                "bounded_rerun_only_if_logic_changed",
            ]
        )
    ]
    for _, decision_row in doi_decisions.iterrows():
        prefix = clean_text(decision_row.get("decision_unit", ""))
        if not prefix:
            continue
        prefix_queue = queue_work[queue_work["doi_prefix"].astype(str).eq(prefix)].copy()
        if prefix_queue.empty:
            continue
        prefix_attempts = attempts_work[attempts_work["doi_prefix"].astype(str).eq(prefix)].copy()
        unresolved_attempts = prefix_attempts[prefix_attempts["article_id"].astype(str).isin(current_article_ids)].copy()

        source_candidates = [
            clean_text(decision_row.get("top_failure_source", "")),
            clean_text(decision_row.get("best_prior_source", "")),
        ]
        sources = [source for index, source in enumerate(source_candidates) if source and source not in source_candidates[:index]]
        failure_attempts = unresolved_attempts[
            unresolved_attempts["attempt_status"].astype(str).isin(FAILURE_ATTEMPT_STATUSES)
            & (unresolved_attempts["attempt_source"].astype(str).isin(sources) if sources else True)
        ].copy()
        for _, attempt_row in sample_attempts_for_investigation(failure_attempts, prefix_queue, max_rows_per_group).iterrows():
            article_id = clean_text(attempt_row.get("article_id", ""))
            queue_row = queue_lookup.loc[article_id] if article_id in queue_lookup.index else None
            rows.append(
                build_investigation_row(
                    rank=rank,
                    decision_row=decision_row,
                    investigation_type="failed_current_queue_attempt",
                    queue_row=queue_row,
                    attempt_row=attempt_row,
                    source_note="Inspect this current unresolved row before changing or rerunning source logic.",
                )
            )
            rank += 1

        best_source = clean_text(decision_row.get("best_prior_source", ""))
        found_attempts = prefix_attempts[
            prefix_attempts["attempt_status"].astype(str).eq("found")
            & (prefix_attempts["attempt_source"].astype(str).eq(best_source) if best_source else True)
        ].copy()
        for _, attempt_row in sample_attempts_for_investigation(found_attempts, prefix_queue, min(max_rows_per_group, 3)).iterrows():
            article_id = clean_text(attempt_row.get("article_id", ""))
            queue_row = queue_lookup.loc[article_id] if article_id in queue_lookup.index else None
            rows.append(
                build_investigation_row(
                    rank=rank,
                    decision_row=decision_row,
                    investigation_type="found_reference_attempt",
                    queue_row=queue_row,
                    attempt_row=attempt_row,
                    source_note="Use this recovered prior attempt as a reference for URL patterns, metadata shape, or parser behavior.",
                )
            )
            rank += 1

        if failure_attempts.empty:
            queue_sample = prefix_queue.sort_values(["_recovery_rank", "journal_short", "publication_year", "article_id"]).head(max_rows_per_group)
            for _, queue_row in queue_sample.iterrows():
                rows.append(
                    build_investigation_row(
                        rank=rank,
                        decision_row=decision_row,
                        investigation_type="unresolved_prefix_queue_sample",
                        queue_row=queue_row,
                        source_note="No current failed attempt sample matched this decision; inspect the unresolved queue row directly.",
                    )
                )
                rank += 1

    lane_decisions = decisions[
        decisions["unit_type"].astype(str).eq("expansion_lane")
        & decisions["decision"].astype(str).isin(["inspect_pdf_blockers", "manual_abstract_extension", "manual_index_search"])
    ]
    for _, decision_row in lane_decisions.iterrows():
        lane = clean_text(decision_row.get("decision_unit", ""))
        lane_queue = queue_work[queue_work["expansion_lane"].astype(str).eq(lane)].copy()
        lane_sample = lane_queue.sort_values(["_recovery_rank", "journal_short", "publication_year", "article_id"]).head(max_rows_per_group)
        for _, queue_row in lane_sample.iterrows():
            rows.append(
                build_investigation_row(
                    rank=rank,
                    decision_row=decision_row,
                    investigation_type="lane_queue_sample",
                    queue_row=queue_row,
                    source_note="Use this row to start the lane-specific recovery workflow.",
                )
            )
            rank += 1

    if not rows:
        return pd.DataFrame(columns=SOURCE_INVESTIGATION_COLUMNS)
    return pd.DataFrame(rows, columns=SOURCE_INVESTIGATION_COLUMNS)


def numeric_value(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def probe_context_by_unit(probe_results: pd.DataFrame) -> dict[str, dict[str, int]]:
    if probe_results.empty or "decision_unit" not in probe_results.columns:
        return {}
    work = probe_results.copy().fillna("")
    if "result_status" not in work.columns:
        work["result_status"] = ""
    context: dict[str, dict[str, int]] = {}
    for unit, group in work.groupby("decision_unit", dropna=False):
        statuses = group["result_status"].astype(str)
        context[clean_text(unit)] = {
            "probe_rows": len(group),
            "probe_abstract_found_rows": int(statuses.eq("abstract_found").sum()),
            "probe_pdf_candidate_rows": int(statuses.eq("pdf_candidate").sum()),
            "probe_access_challenge_rows": int(statuses.eq("access_challenge").sum()),
            "probe_not_found_rows": int(statuses.eq("not_found").sum()),
            "probe_error_rows": int(statuses.isin(["probe_error", "http_error"]).sum()),
        }
    return context


def route_status_and_action(decision_row: pd.Series | dict[str, Any], probe: dict[str, int]) -> tuple[str, str, str, str]:
    decision = clean_text(decision_row.get("decision", ""))
    unit_type = clean_text(decision_row.get("unit_type", ""))
    supporting_artifact = clean_text(decision_row.get("supporting_command_or_artifact", ""))
    found_probe_route = probe.get("probe_abstract_found_rows", 0) > 0 or probe.get("probe_pdf_candidate_rows", 0) > 0
    blocked_probe_route = probe.get("probe_rows", 0) > 0 and not found_probe_route

    if unit_type == "expansion_lane":
        if decision == "inspect_pdf_blockers":
            return (
                "manual_pdf_blocker_review",
                "Review blocker rows and run OCR only for reachable OA PDFs.",
                "Current PDF lane is constrained by prior download errors; this should stay batch-scoped.",
                supporting_artifact,
            )
        if decision == "manual_abstract_extension":
            return (
                "manual_partial_abstract_extension",
                "Use recovery forms to extend existing short abstracts from explicit metadata.",
                "These rows already have partial text, so manual source-confirmed extension is safer than source-wide reruns.",
                supporting_artifact,
            )
        if decision == "manual_index_search":
            return (
                "manual_index_search",
                "Use index/title-search links and import only high-confidence abstract matches.",
                "Title-only matches should remain triage notes unless an explicit abstract source is recorded.",
                supporting_artifact,
            )
        return (
            "lane_decision_reference",
            "Use the lane decision to choose the next batch-level recovery action.",
            "No automated source route is implied by this lane row.",
            supporting_artifact,
        )

    if decision == "new_source_template_or_manual_recovery":
        if found_probe_route:
            return (
                "candidate_public_route_found",
                "Implement a narrowly tested source template, then run a small prefix pass before scaling.",
                "The bounded probe found usable public metadata, so a new source template may be justified.",
                "outputs/tables/enriched/source_route_probe_results.csv",
            )
        return (
            "unsupported_existing_route",
            "Do not rerun existing logic; use recovery batches unless a separate public metadata template is proven.",
            "Existing routes have no enabled publisher template for this prefix, and the bounded probe did not find usable metadata.",
            "data/intermediate/insufficient_text_recovery_batches/",
        )

    if decision == "bounded_scienceon_recovery":
        return (
            "scienceon_bounded_recovery",
            "Run ScienceOn in 25-row recovery-batch passes; stage, preflight, import, and reclassify accepted exact DOI/title citation_abstract matches.",
            "ScienceOn is a tested public metadata route for 10.2307; title-only hits and no-abstract matches remain non-importable.",
            supporting_artifact,
        )

    if decision == "source_specific_investigation_before_rerun":
        if found_probe_route:
            return (
                "candidate_route_requires_parser_or_url_update",
                "Patch the specific source parser or URL template, then rerun this prefix with a low query cap.",
                "The probe found a usable public route, so a source-specific code change can be tested.",
                "outputs/tables/enriched/source_route_probe_results.csv",
            )
        if blocked_probe_route:
            return (
                "do_not_rerun_landing_pages",
                "Use the investigation packet to inspect failed/found source patterns; avoid broad DOI landing-page reruns.",
                "The bounded probe found access challenges or not-found pages rather than abstracts or PDFs.",
                "outputs/tables/enriched/insufficient_text_source_investigation_packet.csv",
            )
        return (
            "source_specific_probe_needed",
            "Run the bounded source-route probe before another full-prefix rerun.",
            "Prior attempts found some rows but mostly failed, so evidence is needed before spending more queries.",
            "python3 run_source_route_probe.py --max-urls-per-decision 4 --max-total-urls 24",
        )

    if decision == "bounded_source_pass":
        return (
            "ready_bounded_source_pass",
            "Run the suggested bounded source command, inspect yield, then rebuild diagnostics.",
            "No prior attempt evidence blocks this route.",
            supporting_artifact,
        )

    if decision == "bounded_rerun_only_if_logic_changed":
        return (
            "rerun_only_after_logic_or_cache_change",
            "Rerun only after parser, source routing, credentials, or cache state changes.",
            "Prior attempts already recovered some rows; an unchanged rerun is unlikely to teach much.",
            supporting_artifact,
        )

    if decision in {"do_not_rerun_unchanged_logic", "low_volume_manual_recovery"}:
        return (
            "manual_or_new_template_only",
            "Use manual recovery or add a tested source template before rerunning automation.",
            "Existing evidence does not support another unchanged automated pass.",
            "data/intermediate/insufficient_text_recovery_batches/",
        )

    return (
        "inspect_decision",
        "Inspect the decision row before choosing a route.",
        "No source-route rule matched this decision.",
        supporting_artifact,
    )


def source_route_matrix(decisions: pd.DataFrame, probe_results: pd.DataFrame | None = None) -> pd.DataFrame:
    if decisions.empty:
        return pd.DataFrame(columns=SOURCE_ROUTE_MATRIX_COLUMNS)
    probe_context = probe_context_by_unit(probe_results if probe_results is not None else pd.DataFrame())
    rows: list[dict[str, Any]] = []
    for _, decision_row in decisions.iterrows():
        unit = clean_text(decision_row.get("decision_unit", ""))
        probe = probe_context.get(
            unit,
            {
                "probe_rows": 0,
                "probe_abstract_found_rows": 0,
                "probe_pdf_candidate_rows": 0,
                "probe_access_challenge_rows": 0,
                "probe_not_found_rows": 0,
                "probe_error_rows": 0,
            },
        )
        current_route_status, route_action, route_note, next_artifact = route_status_and_action(decision_row, probe)
        rows.append(
            {
                "route_unit": unit,
                "unit_type": clean_text(decision_row.get("unit_type", "")),
                "row_count": numeric_value(decision_row.get("row_count", 0)),
                "high_priority_rows": numeric_value(decision_row.get("high_priority_rows", 0)),
                "decision": clean_text(decision_row.get("decision", "")),
                "current_route_status": current_route_status,
                "prior_best_source": clean_text(decision_row.get("best_prior_source", "")),
                "prior_found_articles": numeric_value(decision_row.get("prior_found_articles", 0)),
                "prior_failed_attempts": numeric_value(decision_row.get("prior_failed_attempts", 0)),
                **probe,
                "recommended_route_action": route_action,
                "source_route_note": route_note,
                "next_artifact": next_artifact,
            }
        )
    return pd.DataFrame(rows, columns=SOURCE_ROUTE_MATRIX_COLUMNS).sort_values(
        ["row_count", "high_priority_rows", "route_unit"],
        ascending=[False, False, True],
    ).reset_index(drop=True)


def markdown_cell(value: Any) -> str:
    return str(value).replace("\r", " ").replace("\n", " ").replace("|", "\\|")


def df_to_markdown(df: pd.DataFrame, max_rows: int = 30) -> str:
    if df.empty:
        return "_No rows._"
    shown = df.head(max_rows).fillna("")
    headers = [markdown_cell(column) for column in shown.columns]
    rows = [headers] + [[markdown_cell(value) for value in row] for row in shown.astype(str).values.tolist()]
    widths = [max(len(row[i]) for row in rows) for i in range(len(headers))]
    header = "| " + " | ".join(headers[i].ljust(widths[i]) for i in range(len(headers))) + " |"
    separator = "| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |"
    body = ["| " + " | ".join(row[i].ljust(widths[i]) for i in range(len(headers))) + " |" for row in rows[1:]]
    suffix = f"\n\n_Only first {max_rows} rows shown._" if len(df) > max_rows else ""
    return "\n".join([header, separator] + body) + suffix


def write_expansion_report(
    path: Path,
    overview: pd.DataFrame,
    detail: pd.DataFrame,
    doi_prefixes: pd.DataFrame,
    attempt_summary: pd.DataFrame,
    decisions: pd.DataFrame,
    investigation_packet: pd.DataFrame,
    route_matrix: pd.DataFrame,
    queue_path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    top = overview.iloc[0].to_dict() if not overview.empty else {}
    lines = [
        "# Insufficient Text Expansion Plan",
        "",
        f"- Recovery queue: `{queue_path}`",
        f"- Expansion lanes: {len(overview)}",
        f"- Remaining rows in plan: {int(pd.to_numeric(overview.get('row_count', pd.Series(dtype=int)), errors='coerce').fillna(0).sum()) if not overview.empty else 0}",
        f"- First lane: `{top.get('expansion_lane', '')}`",
        f"- First action: {top.get('suggested_command', '') or 'None'}",
        "",
        "Use this report to choose bounded source-family passes. After any accepted backfill import, rerun classification, diagnostics, recovery batches, recovery progress, and this expansion plan.",
        "",
        "## Recommended Decisions",
        "",
        df_to_markdown(decisions, max_rows=30),
        "",
        "## Source Route Matrix",
        "",
        df_to_markdown(route_matrix, max_rows=30),
        "",
        "## Source Investigation Packet",
        "",
        df_to_markdown(investigation_packet, max_rows=30),
        "",
        "## Lane Overview",
        "",
        df_to_markdown(overview, max_rows=20),
        "",
        "## Detail By Journal And Decade",
        "",
        df_to_markdown(detail, max_rows=40),
        "",
        "## DOI Prefixes",
        "",
        df_to_markdown(doi_prefixes, max_rows=30),
        "",
        "## Prior Source Attempts",
        "",
        df_to_markdown(attempt_summary, max_rows=40),
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("") if path.exists() else pd.DataFrame()


def run_expansion_plan(
    *,
    queue_path: Path,
    attempts_path: Path,
    output_overview: Path,
    output_detail: Path,
    output_doi_prefixes: Path,
    output_attempt_summary: Path,
    output_decisions: Path,
    output_investigation_packet: Path,
    report_path: Path,
    output_route_matrix: Path | None = None,
    probe_results_path: Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    queue = read_csv_if_exists(queue_path)
    attempts = read_csv_if_exists(attempts_path)
    probe_results = read_csv_if_exists(probe_results_path) if probe_results_path is not None else pd.DataFrame()
    overview, detail, doi_prefixes, attempt_summary = insufficient_text_expansion_plan(queue, attempts)
    decisions = recovery_decision_plan(overview, doi_prefixes, attempt_summary)
    investigation_packet = source_investigation_packet(queue, attempts, decisions)
    route_matrix = source_route_matrix(decisions, probe_results)
    output_overview.parent.mkdir(parents=True, exist_ok=True)
    output_detail.parent.mkdir(parents=True, exist_ok=True)
    output_doi_prefixes.parent.mkdir(parents=True, exist_ok=True)
    output_attempt_summary.parent.mkdir(parents=True, exist_ok=True)
    output_decisions.parent.mkdir(parents=True, exist_ok=True)
    output_investigation_packet.parent.mkdir(parents=True, exist_ok=True)
    if output_route_matrix is not None:
        output_route_matrix.parent.mkdir(parents=True, exist_ok=True)
    overview.to_csv(output_overview, index=False)
    detail.to_csv(output_detail, index=False)
    doi_prefixes.to_csv(output_doi_prefixes, index=False)
    attempt_summary.to_csv(output_attempt_summary, index=False)
    decisions.to_csv(output_decisions, index=False)
    investigation_packet.to_csv(output_investigation_packet, index=False)
    if output_route_matrix is not None:
        route_matrix.to_csv(output_route_matrix, index=False)
    write_expansion_report(report_path, overview, detail, doi_prefixes, attempt_summary, decisions, investigation_packet, route_matrix, queue_path)
    first_lane = clean_text(overview.iloc[0]["expansion_lane"]) if not overview.empty else ""
    print(f"expansion_lanes={len(overview)}")
    print(f"planned_rows={int(pd.to_numeric(overview.get('row_count', pd.Series(dtype=int)), errors='coerce').fillna(0).sum()) if not overview.empty else 0}")
    print(f"route_matrix_rows={len(route_matrix)}")
    print(f"first_lane={first_lane}")
    print(f"report={report_path}")
    return overview, detail, doi_prefixes, attempt_summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", default="outputs/tables/enriched/insufficient_text_recovery_queue.csv")
    parser.add_argument("--attempts", default="data/intermediate/text_enrichment_attempts.csv")
    parser.add_argument("--output-overview", default="outputs/tables/enriched/insufficient_text_expansion_overview.csv")
    parser.add_argument("--output-detail", default="outputs/tables/enriched/insufficient_text_expansion_plan.csv")
    parser.add_argument("--output-doi-prefixes", default="outputs/tables/enriched/insufficient_text_expansion_doi_prefixes.csv")
    parser.add_argument("--output-attempt-summary", default="outputs/tables/enriched/insufficient_text_expansion_attempt_summary.csv")
    parser.add_argument("--output-decisions", default="outputs/tables/enriched/insufficient_text_recovery_decisions.csv")
    parser.add_argument("--output-investigation-packet", default="outputs/tables/enriched/insufficient_text_source_investigation_packet.csv")
    parser.add_argument("--output-route-matrix", default="outputs/tables/enriched/insufficient_text_source_route_matrix.csv")
    parser.add_argument("--probe-results", default="outputs/tables/enriched/source_route_probe_results.csv")
    parser.add_argument("--report", default="docs/insufficient_text_expansion_plan.md")
    args = parser.parse_args()
    run_expansion_plan(
        queue_path=Path(args.queue),
        attempts_path=Path(args.attempts),
        output_overview=Path(args.output_overview),
        output_detail=Path(args.output_detail),
        output_doi_prefixes=Path(args.output_doi_prefixes),
        output_attempt_summary=Path(args.output_attempt_summary),
        output_decisions=Path(args.output_decisions),
        output_investigation_packet=Path(args.output_investigation_packet),
        output_route_matrix=Path(args.output_route_matrix),
        probe_results_path=Path(args.probe_results),
        report_path=Path(args.report),
    )


if __name__ == "__main__":
    main()
