from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "lib"))
sys.path.append(str(Path(__file__).resolve().parent))

from econqt_common import clean_text  # noqa: E402
from recovery_batches import recovery_form_html  # noqa: E402
from recovery_progress import df_to_markdown  # noqa: E402


STATUS_ORDER = {
    "fix_stage_errors": 1,
    "fix_preflight_errors": 2,
    "complete_export_fields": 3,
    "run_stage_and_preflight": 4,
    "not_started": 5,
    "ready_to_import": 6,
}

TIER_ORDER = {
    "tier_1_partial_near_threshold": 1,
    "tier_2_partial_replace_suspect_text": 2,
    "tier_3_partial_extension": 3,
    "tier_4_manual_metadata_has_context": 4,
    "tier_5_manual_metadata_pdf_blocked": 5,
}

KICKOFF_SUMMARY_COLUMNS = [
    "metric",
    "value",
]

KICKOFF_PREVIEW_COLUMNS = [
    "kickoff_rank",
    "review_rank",
    "action_group",
    "quick_win_tier",
    "cell_target_rank",
    "cell_target_level",
    "cell_recoveries_to_target_share",
    "chars_needed_to_threshold",
    "title",
    "reviewer_action",
    "source_to_avoid",
]

KICKOFF_REVIEW_CHECKLIST = [
    "Open the browser form and work rows in kickoff_rank order.",
    "Complete a row only when the text is article-specific and source-confirmed.",
    "Fill abstract, source, and either source_url or source_record_id for every completed row.",
    "Set evidence_tier to tier_a_formal_abstract, tier_b_source_description, or tier_c_first_page_abstract_or_intro.",
    "Use notes when the evidence is a source description, first-page text, replacement for boilerplate, or otherwise not a formal abstract.",
    "Leave the row unresolved when the only evidence is title-only, citation-only, access-challenge, search-result snippet, blocked PDF, or provenance-free text.",
]

KICKOFF_AFTER_EXPORT_COMMANDS = [
    "PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_tiered_stage.py",
    "PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_split_preflight.py --split-summary outputs/tables/enriched/recovery_batch_R001_staged_split_summary.csv",
    "PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_action_progress.py",
    "PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_kickoff_packet.py",
]


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def numeric_series(frame: pd.DataFrame, column: str, default: int) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index)
    return pd.to_numeric(frame[column], errors="coerce").fillna(default).astype(int)


def read_action_packet_rows(packet_dir: Path) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    if not packet_dir.exists():
        return pd.DataFrame()
    for path in sorted(packet_dir.glob("*.csv")):
        try:
            frame = pd.read_csv(path, dtype=str).fillna("")
        except pd.errors.EmptyDataError:
            continue
        if "article_id" not in frame.columns:
            continue
        frame["action_packet_source"] = str(path)
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True).fillna("")
    return combined.drop_duplicates("article_id", keep="first").reset_index(drop=True)


def kickoff_article_ids(progress_detail: pd.DataFrame, *, limit: int) -> list[str]:
    if progress_detail.empty or "article_id" not in progress_detail.columns or limit <= 0:
        return []
    work = progress_detail.copy().fillna("")
    work["_status_order"] = work.get("next_status", pd.Series("", index=work.index)).map(STATUS_ORDER).fillna(99).astype(int)
    work["_tier_order"] = work.get("quick_win_tier", pd.Series("", index=work.index)).map(TIER_ORDER).fillna(99).astype(int)
    work["_target_needed"] = numeric_series(work, "cell_recoveries_to_target_share", 0)
    work["_target_needed_order"] = work["_target_needed"].le(0).astype(int)
    work["_target_rank"] = numeric_series(work, "cell_target_rank", 999999)
    work["_review_rank"] = numeric_series(work, "review_rank", 999999)
    work["_stage_errors"] = numeric_series(work, "stage_error_rows", 0)
    work["_preflight_errors"] = numeric_series(work, "preflight_error_rows", 0)
    work = work.sort_values(
        [
            "_status_order",
            "_stage_errors",
            "_preflight_errors",
            "_tier_order",
            "_target_needed_order",
            "_target_rank",
            "_review_rank",
            "article_id",
        ],
        ascending=[True, False, False, True, True, True, True, True],
    )
    return [clean_text(value) for value in work["article_id"].head(limit).tolist() if clean_text(value)]


def recovery_kickoff_packet(
    *,
    progress_detail: pd.DataFrame,
    action_packet_rows: pd.DataFrame,
    limit: int = 20,
) -> pd.DataFrame:
    if action_packet_rows.empty or "article_id" not in action_packet_rows.columns:
        return pd.DataFrame()
    article_ids = kickoff_article_ids(progress_detail, limit=limit)
    if not article_ids:
        return pd.DataFrame(columns=action_packet_rows.columns)
    order = {article_id: index for index, article_id in enumerate(article_ids, start=1)}
    packet = action_packet_rows[action_packet_rows["article_id"].astype(str).isin(order)].copy().fillna("")
    if packet.empty:
        return packet
    packet["_kickoff_rank"] = packet["article_id"].map(order).fillna(999999).astype(int)
    packet = packet.sort_values(["_kickoff_rank", "article_id"]).reset_index(drop=True)
    packet.insert(0, "kickoff_rank", packet["_kickoff_rank"].astype(str))
    return packet.drop(columns=["_kickoff_rank"])


def kickoff_summary(packet: pd.DataFrame) -> pd.DataFrame:
    if packet.empty:
        rows = [
            {"metric": "kickoff_rows", "value": 0},
            {"metric": "priority_cell_rows", "value": 0},
            {"metric": "critical_cell_rows", "value": 0},
        ]
        return pd.DataFrame(rows, columns=KICKOFF_SUMMARY_COLUMNS)
    target_needed = pd.to_numeric(packet.get("cell_recoveries_to_target_share", pd.Series(dtype=str)), errors="coerce").fillna(0)
    review_ranks = pd.to_numeric(packet.get("review_rank", pd.Series(dtype=str)), errors="coerce")
    first_review_rank = int(review_ranks.min()) if review_ranks.notna().any() else ""
    last_review_rank = int(review_ranks.max()) if review_ranks.notna().any() else ""
    rows: list[dict[str, Any]] = [
        {"metric": "kickoff_rows", "value": len(packet)},
        {"metric": "priority_cell_rows", "value": int(target_needed.gt(0).sum())},
        {"metric": "critical_cell_rows", "value": int(packet.get("cell_target_level", pd.Series(dtype=str)).astype(str).eq("critical").sum())},
        {"metric": "action_groups", "value": "|".join(dict.fromkeys(clean_text(value) for value in packet.get("action_group", pd.Series(dtype=str)).tolist() if clean_text(value)))},
        {"metric": "quick_win_tiers", "value": "|".join(dict.fromkeys(clean_text(value) for value in packet.get("quick_win_tier", pd.Series(dtype=str)).tolist() if clean_text(value)))},
        {"metric": "suggested_evidence_tiers", "value": "|".join(dict.fromkeys(clean_text(value) for value in packet.get("suggested_evidence_tier", pd.Series(dtype=str)).tolist() if clean_text(value)))},
        {"metric": "candidate_sources", "value": "|".join(dict.fromkeys(clean_text(value) for value in packet.get("candidate_source", pd.Series(dtype=str)).tolist() if clean_text(value)))},
        {"metric": "first_review_rank", "value": first_review_rank},
        {"metric": "last_review_rank", "value": last_review_rank},
    ]
    return pd.DataFrame(rows, columns=KICKOFF_SUMMARY_COLUMNS)


def write_kickoff_report(path: Path, *, packet: pd.DataFrame, summary: pd.DataFrame, output_csv: Path, output_html: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    preview = packet[[column for column in KICKOFF_PREVIEW_COLUMNS if column in packet.columns]].copy() if not packet.empty else pd.DataFrame(columns=KICKOFF_PREVIEW_COLUMNS)
    lines = [
        "# Recovery Batch R001 Kickoff Packet",
        "",
        "This generated packet is a smaller first-session handoff for R001. It is non-mutating and selects rows from the existing action packets using action-progress status, evidence tier, and journal-decade target priority.",
        "",
        f"- Packet CSV: `{output_csv}`",
        f"- Browser form: `{output_html}`",
        "",
        "Export completed rows from the browser form into `data/intermediate/insufficient_text_recovery_review_exports/R001/`, then run the normal staging and preflight commands. Do not import title-only, citation-only, blocked, or provenance-free text.",
        "",
        "## Review Checklist",
        "",
        *[f"- {item}" for item in KICKOFF_REVIEW_CHECKLIST],
        "",
        "## After Export Commands",
        "",
        "Run these after exporting reviewer CSVs. They are non-importing checks; empty exports are allowed and should remain no-ops.",
        "",
        "```bash",
        *KICKOFF_AFTER_EXPORT_COMMANDS,
        "```",
        "",
        "Only after preflight reports import-ready completed rows should imports use `run_import_abstract_backfill.py --require-source-metadata --fail-on-errors`.",
        "",
        "## Summary",
        "",
        df_to_markdown(summary, max_rows=20),
        "",
        "## Rows",
        "",
        df_to_markdown(preview, max_rows=40),
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def run_recovery_kickoff_packet(
    *,
    progress_detail_path: Path,
    action_packet_dir: Path,
    output_csv: Path,
    output_html: Path,
    output_summary: Path,
    report_path: Path,
    limit: int = 20,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    progress_detail = read_csv_if_exists(progress_detail_path)
    action_rows = read_action_packet_rows(action_packet_dir)
    packet = recovery_kickoff_packet(progress_detail=progress_detail, action_packet_rows=action_rows, limit=limit)
    summary = kickoff_summary(packet)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_html.parent.mkdir(parents=True, exist_ok=True)
    output_summary.parent.mkdir(parents=True, exist_ok=True)
    packet.to_csv(output_csv, index=False)
    output_html.write_text(recovery_form_html(packet, title=f"Insufficient Text Recovery R001 Kickoff Top {limit}"), encoding="utf-8")
    summary.to_csv(output_summary, index=False)
    write_kickoff_report(report_path, packet=packet, summary=summary, output_csv=output_csv, output_html=output_html)
    print(f"kickoff_rows={len(packet)}")
    print(f"output={output_csv}")
    print(f"form={output_html}")
    print(f"summary={output_summary}")
    print(f"report={report_path}")
    return packet, summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--progress-detail", default="outputs/tables/enriched/recovery_batch_R001_action_progress_detail.csv")
    parser.add_argument("--action-packet-dir", default="outputs/tables/enriched/recovery_batch_R001_action_packets")
    parser.add_argument("--output", default="outputs/tables/enriched/recovery_batch_R001_kickoff_packet.csv")
    parser.add_argument("--form", default="data/intermediate/insufficient_text_recovery_review_forms/R001/recovery_batch_R001_kickoff_packet.html")
    parser.add_argument("--summary-output", default="outputs/tables/enriched/recovery_batch_R001_kickoff_summary.csv")
    parser.add_argument("--report", default="docs/recovery_batch_R001_kickoff_packet.md")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    run_recovery_kickoff_packet(
        progress_detail_path=Path(args.progress_detail),
        action_packet_dir=Path(args.action_packet_dir),
        output_csv=Path(args.output),
        output_html=Path(args.form),
        output_summary=Path(args.summary_output),
        report_path=Path(args.report),
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
