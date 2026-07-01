from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "lib"))
sys.path.append(str(Path(__file__).resolve().parent))

from abstract_backfill import df_to_markdown  # noqa: E402
from econqt_common import clean_text  # noqa: E402


DETAIL_COLUMNS = [
    "review_rank",
    "article_id",
    "title",
    "quick_win_tier",
    "source_route_family",
    "row_status",
    "current_text_quality_flag",
    "current_text_chars",
    "chars_needed_to_threshold",
    "automation_status",
    "automation_blocker",
    "safe_next_action",
    "source_route_status",
    "source_route_decision",
    "source_route_note",
]

SUMMARY_COLUMNS = [
    "automation_status",
    "rows",
    "first_review_rank",
    "quick_win_tiers",
    "source_route_families",
    "safe_next_action",
]

ROUTE_UNIT_BY_FAMILY = {
    "partial_text_extension": "partial_short_text_extension",
    "pdf_blocker_metadata": "oa_pdf_review",
    "openalex_or_title_search": "openalex_or_title_search",
    "jpe_chicago_or_repec": "10.1086",
    "jstor_or_legacy_doi": "10.2307",
    "aea_publisher_metadata": "10.1257",
    "wiley_or_society_metadata": "10.1111",
    "oup_journal_metadata": "10.1093/qje",
    "econometric_society_metadata": "10.3982",
}


def numeric_value(value: Any, default: int = 0) -> int:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return default if pd.isna(parsed) else int(parsed)


def unique_join(values: pd.Series) -> str:
    cleaned = [clean_text(value) for value in values.tolist() if clean_text(value)]
    return "|".join(dict.fromkeys(cleaned))


def route_unit_for_row(row: pd.Series) -> str:
    doi = clean_text(row.get("doi")).lower()
    if doi.startswith("10.2307"):
        return "10.2307"
    if doi.startswith("10.1086"):
        return "10.1086"
    if doi.startswith("10.1257"):
        return "10.1257"
    if doi.startswith("10.1111"):
        return "10.1111"
    if doi.startswith("10.1093/qje"):
        return "10.1093/qje"
    if doi.startswith("10.3982"):
        return "10.3982"
    family = clean_text(row.get("source_route_family"))
    return ROUTE_UNIT_BY_FAMILY.get(family, family)


def route_lookup(route_matrix: pd.DataFrame) -> dict[str, pd.Series]:
    if route_matrix.empty or "route_unit" not in route_matrix.columns:
        return {}
    return {
        clean_text(row.get("route_unit")): row
        for _, row in route_matrix.copy().fillna("").iterrows()
        if clean_text(row.get("route_unit"))
    }


def merge_queue_and_guide(queue: pd.DataFrame, source_guide: pd.DataFrame) -> pd.DataFrame:
    work = queue.copy().fillna("")
    if source_guide.empty or "article_id" not in work.columns or "article_id" not in source_guide.columns:
        if "source_route_family" not in work.columns:
            work["source_route_family"] = ""
        return work
    guide_columns = [
        "article_id",
        "source_route_family",
        "first_source_to_check",
        "fallback_source_to_check",
        "acceptable_evidence",
        "stop_rule",
    ]
    guide = source_guide[[column for column in guide_columns if column in source_guide.columns]].copy().fillna("")
    return work.merge(guide.drop_duplicates("article_id"), on="article_id", how="left", suffixes=("", "_guide")).fillna("")


def automation_classification(row: pd.Series, route_row: pd.Series | None) -> tuple[str, str, str]:
    tier = clean_text(row.get("quick_win_tier"))
    family = clean_text(row.get("source_route_family"))
    row_status = clean_text(row.get("row_status"))
    quality_flag = clean_text(row.get("current_text_quality_flag"))
    completion_status = clean_text(row.get("completion_status"))
    route_status = clean_text(route_row.get("current_route_status")) if route_row is not None else ""
    route_decision = clean_text(route_row.get("decision")) if route_row is not None else ""

    if completion_status == "ready_to_import":
        return (
            "ready_for_preflight",
            "completed row already has abstract and source provenance",
            "Stage the row and run split preflight before import.",
        )
    if completion_status == "needs_source_metadata":
        return (
            "source_metadata_incomplete",
            "filled text is missing source plus source_url or source_record_id",
            "Add source provenance before staging or importing.",
        )
    if tier == "tier_2_partial_replace_suspect_text" or quality_flag:
        return (
            "manual_replace_boilerplate",
            "current text is flagged as source boilerplate or suspect text",
            "Replace with an explicit abstract or source description; do not extend the flagged text.",
        )
    if family == "pdf_blocker_metadata" or "pdf_route_blocked" in row_status or "suspect_pdf_url" in row_status:
        return (
            "manual_metadata_after_pdf_block",
            "prior PDF route is blocked or suspect",
            "Avoid retrying the blocked PDF; use DOI, publisher, index, or library metadata.",
        )
    if tier == "tier_1_partial_near_threshold":
        return (
            "manual_near_threshold_extension",
            "text is close to threshold but still below the usable-text rule",
            "Extend only from explicit source metadata with provenance and an importable evidence_tier.",
        )
    if tier == "tier_3_partial_extension":
        return (
            "manual_partial_extension",
            "partial text needs source-confirmed extension",
            "Extend from the listed source route and stop if provenance is missing.",
        )
    if route_status in {"unsupported_existing_route", "do_not_rerun_landing_pages"} or route_decision == "new_source_template_or_manual_recovery":
        return (
            "manual_index_or_template_spike_required",
            "current source route is unsupported or bounded probes found access challenges",
            "Use manual/index recovery unless a small public metadata template spike proves usable abstracts.",
        )
    if tier == "tier_4_manual_metadata_has_context":
        return (
            "manual_metadata_recovery",
            "no sufficient abstract is present but source context exists",
            "Recover an explicit abstract or source description from DOI, publisher, index, or title-match metadata.",
        )
    return (
        "manual_review_required",
        "no safe automated recovery rule applies",
        "Review row-level source links and import only source-confirmed text.",
    )


def recovery_automation_audit(
    queue: pd.DataFrame,
    source_guide: pd.DataFrame,
    route_matrix: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if queue.empty:
        return pd.DataFrame(columns=DETAIL_COLUMNS), pd.DataFrame(columns=SUMMARY_COLUMNS)

    work = merge_queue_and_guide(queue, source_guide)
    routes = route_lookup(route_matrix)
    rows: list[dict[str, Any]] = []
    for _, row in work.iterrows():
        route_unit = route_unit_for_row(row)
        route_row = routes.get(route_unit)
        status, blocker, action = automation_classification(row, route_row)
        rows.append(
            {
                "review_rank": clean_text(row.get("review_rank")),
                "article_id": clean_text(row.get("article_id")),
                "title": clean_text(row.get("title")),
                "quick_win_tier": clean_text(row.get("quick_win_tier")),
                "source_route_family": clean_text(row.get("source_route_family")),
                "row_status": clean_text(row.get("row_status")),
                "current_text_quality_flag": clean_text(row.get("current_text_quality_flag")),
                "current_text_chars": clean_text(row.get("current_text_chars")),
                "chars_needed_to_threshold": clean_text(row.get("chars_needed_to_threshold")),
                "automation_status": status,
                "automation_blocker": blocker,
                "safe_next_action": action,
                "source_route_status": clean_text(route_row.get("current_route_status")) if route_row is not None else "",
                "source_route_decision": clean_text(route_row.get("decision")) if route_row is not None else "",
                "source_route_note": clean_text(route_row.get("source_route_note")) if route_row is not None else "",
            }
        )
    detail = pd.DataFrame(rows, columns=DETAIL_COLUMNS)
    summary_rows: list[dict[str, Any]] = []
    for status, group in detail.groupby("automation_status", sort=False, dropna=False):
        ranks = group["review_rank"].map(numeric_value)
        summary_rows.append(
            {
                "automation_status": clean_text(status),
                "rows": len(group),
                "first_review_rank": int(ranks[ranks.gt(0)].min()) if ranks.gt(0).any() else "",
                "quick_win_tiers": unique_join(group["quick_win_tier"]),
                "source_route_families": unique_join(group["source_route_family"]),
                "safe_next_action": clean_text(group["safe_next_action"].iloc[0]),
            }
        )
    summary = pd.DataFrame(summary_rows, columns=SUMMARY_COLUMNS).sort_values(["first_review_rank", "automation_status"], na_position="last").reset_index(drop=True)
    return detail, summary


def write_audit_report(path: Path, detail: pd.DataFrame, summary: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    preview_columns = [
        "review_rank",
        "automation_status",
        "quick_win_tier",
        "source_route_family",
        "current_text_quality_flag",
        "title",
        "safe_next_action",
    ]
    preview = detail[[column for column in preview_columns if column in detail.columns]].head(40).copy() if not detail.empty else pd.DataFrame(columns=preview_columns)
    lines = [
        "# Recovery Automation Audit",
        "",
        "This audit is non-mutating. It explains why the current R001 recovery rows should be handled manually, staged for preflight, or held for a bounded source-template spike before any broader automation.",
        "",
        "The audit does not change abstracts, labels, scope decisions, recovery packets, or final article files.",
        "",
        "## Automation Summary",
        "",
        df_to_markdown(summary, max_rows=30),
        "",
        "## Row Preview",
        "",
        df_to_markdown(preview, max_rows=40),
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def run_recovery_automation_audit(
    *,
    queue_path: Path,
    source_guide_path: Path,
    route_matrix_path: Path,
    detail_output: Path,
    summary_output: Path,
    report_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    detail, summary = recovery_automation_audit(
        read_csv_if_exists(queue_path),
        read_csv_if_exists(source_guide_path),
        read_csv_if_exists(route_matrix_path),
    )
    detail_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(detail_output, index=False)
    summary.to_csv(summary_output, index=False)
    write_audit_report(report_path, detail, summary)
    print(f"audit_rows={len(detail)}")
    print(f"summary_rows={len(summary)}")
    print(f"detail={detail_output}")
    print(f"summary={summary_output}")
    print(f"report={report_path}")
    return detail, summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", default="outputs/tables/enriched/recovery_batch_R001_review_queue.csv")
    parser.add_argument("--source-guide", default="outputs/tables/enriched/recovery_batch_R001_source_guide.csv")
    parser.add_argument("--route-matrix", default="outputs/tables/enriched/insufficient_text_source_route_matrix.csv")
    parser.add_argument("--detail-output", default="outputs/tables/enriched/recovery_automation_audit_detail.csv")
    parser.add_argument("--summary-output", default="outputs/tables/enriched/recovery_automation_audit_summary.csv")
    parser.add_argument("--report", default="docs/recovery_automation_audit.md")
    args = parser.parse_args()
    run_recovery_automation_audit(
        queue_path=Path(args.queue),
        source_guide_path=Path(args.source_guide),
        route_matrix_path=Path(args.route_matrix),
        detail_output=Path(args.detail_output),
        summary_output=Path(args.summary_output),
        report_path=Path(args.report),
    )


if __name__ == "__main__":
    main()
