from __future__ import annotations

import argparse
import html
import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "lib"))
sys.path.append(str(Path(__file__).resolve().parent))

from econqt_common import clean_text  # noqa: E402
from evidence_tier_policy import ACCEPTED_EVIDENCE_TIERS  # noqa: E402
from recovery_progress import df_to_markdown  # noqa: E402


DETAIL_COLUMNS = [
    "review_rank",
    "article_id",
    "action_group",
    "quick_win_tier",
    "cell_target_rank",
    "cell_target_level",
    "cell_recoveries_to_target_share",
    "cell_projected_share_after_ready_r001",
    "cell_ready_r001_target_coverage",
    "title",
    "export_row_count",
    "exported_files",
    "duplicate_export_rows",
    "exported_has_abstract",
    "exported_source_ready",
    "exported_importable_evidence_tier",
    "exported_ready_candidate",
    "staged",
    "stage_error_rows",
    "preflight_error_rows",
    "import_ready",
    "next_status",
    "next_step",
]

SUMMARY_COLUMNS = [
    "action_group",
    "rows_total",
    "priority_cell_rows",
    "critical_cell_rows",
    "top_cell_target_rank",
    "top_cell_target_level",
    "top_cell_recoveries_to_target_share",
    "exported_rows",
    "exported_ready_candidates",
    "staged_rows",
    "import_ready_rows",
    "stage_error_rows",
    "preflight_error_rows",
    "remaining_unexported_rows",
    "remaining_not_import_ready_rows",
    "first_review_rank",
    "next_status",
    "recommended_next_step",
]

OVERVIEW_COLUMNS = ["metric", "value"]


def numeric_value(value: Any, default: int = 0) -> int:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return default if pd.isna(parsed) else int(parsed)


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists() or not path.is_file():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def relative_href(from_path: Path, target: str) -> str:
    target_text = clean_text(target)
    if not target_text:
        return ""
    if target_text.startswith(("http://", "https://", "mailto:")):
        return target_text
    try:
        return os.path.relpath(target_text, start=str(from_path.parent))
    except ValueError:
        return target_text


def html_link(from_path: Path, label: str, target: str) -> str:
    target_text = clean_text(target)
    if not target_text:
        return ""
    return f'<a href="{html.escape(relative_href(from_path, target_text), quote=True)}">{html.escape(label)}</a>'


def reviewer_input_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(item for item in path.glob("*.csv") if item.is_file())
    return []


def reviewer_export_records(reviewer_input: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for source_file in reviewer_input_files(reviewer_input):
        try:
            submission = pd.read_csv(source_file, dtype=str).fillna("")
        except pd.errors.EmptyDataError:
            continue
        if "article_id" not in submission.columns:
            continue
        for idx, row in submission.iterrows():
            article_id = clean_text(row.get("article_id"))
            if not article_id:
                continue
            rows.append(
                {
                    "article_id": article_id,
                    "source_file": str(source_file),
                    "row_number": idx + 2,
                    "abstract": clean_text(row.get("abstract")),
                    "source": clean_text(row.get("source")),
                    "source_url": clean_text(row.get("source_url")),
                    "source_record_id": clean_text(row.get("source_record_id")),
                    "evidence_tier": clean_text(row.get("evidence_tier")),
                }
            )
    if not rows:
        return pd.DataFrame(columns=["article_id", "source_file", "row_number", "abstract", "source", "source_url", "source_record_id", "evidence_tier"])
    return pd.DataFrame(rows).fillna("")


def article_id_counts(frame: pd.DataFrame) -> dict[str, int]:
    if frame.empty or "article_id" not in frame.columns:
        return {}
    work = frame.copy().fillna("")
    work = work[work["article_id"].astype(str).str.strip().ne("")]
    if work.empty:
        return {}
    return work.groupby("article_id", dropna=False).size().astype(int).to_dict()


def export_status(records: pd.DataFrame) -> dict[str, dict[str, Any]]:
    if records.empty:
        return {}
    work = records.copy().fillna("")
    work["has_abstract"] = work["abstract"].astype(str).str.strip().ne("")
    work["source_ready"] = (
        work["source"].astype(str).str.strip().ne("")
        & (work["source_url"].astype(str).str.strip().ne("") | work["source_record_id"].astype(str).str.strip().ne(""))
    )
    work["importable_evidence_tier"] = work["evidence_tier"].isin(ACCEPTED_EVIDENCE_TIERS)
    work["ready_candidate"] = work["has_abstract"] & work["source_ready"] & work["importable_evidence_tier"]

    status: dict[str, dict[str, Any]] = {}
    for article_id, group in work.groupby("article_id", dropna=False):
        files = [clean_text(value) for value in group["source_file"].tolist() if clean_text(value)]
        status[str(article_id)] = {
            "export_row_count": len(group),
            "exported_files": "|".join(dict.fromkeys(files)),
            "duplicate_export_rows": max(0, len(group) - 1),
            "exported_has_abstract": bool(group["has_abstract"].any()),
            "exported_source_ready": bool(group["source_ready"].any()),
            "exported_importable_evidence_tier": bool(group["importable_evidence_tier"].any()),
            "exported_ready_candidate": bool(group["ready_candidate"].any()),
        }
    return status


def bool_text(value: bool) -> str:
    return "yes" if value else "no"


def unique_join(values: pd.Series | list[Any]) -> str:
    cleaned = [clean_text(value) for value in list(values) if clean_text(value)]
    return "|".join(dict.fromkeys(cleaned))


def target_rank_text(value: Any) -> str:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(parsed):
        return ""
    return str(int(parsed))


def row_status(
    *,
    export_row_count: int,
    exported_ready_candidate: bool,
    staged: bool,
    stage_error_rows: int,
    preflight_error_rows: int,
) -> tuple[str, str]:
    if stage_error_rows > 0:
        return "fix_stage_errors", "Open recovery_batch_R001_tiered_stage_errors.csv, fix the export row, then rerun staging."
    if preflight_error_rows > 0:
        return "fix_preflight_errors", "Open recovery_batch_R001_preflight_errors.csv, fix the staged row, then rerun preflight."
    if staged:
        return "ready_to_import", "Run the dry-run import for the staged split file before applying the import."
    if exported_ready_candidate:
        return "run_stage_and_preflight", "Run recovery tiered staging and split preflight."
    if export_row_count > 0:
        return "complete_export_fields", "Fill abstract, source provenance, and an importable evidence_tier in the export."
    return "not_started", "Work the action form and export completed rows to the R001 review exports directory."


def recovery_action_progress_detail(
    *,
    action_packet: pd.DataFrame,
    export_records: pd.DataFrame,
    stage_changes: pd.DataFrame,
    stage_errors: pd.DataFrame,
    preflight_errors: pd.DataFrame,
) -> pd.DataFrame:
    if action_packet.empty or "article_id" not in action_packet.columns:
        return pd.DataFrame(columns=DETAIL_COLUMNS)
    exports = export_status(export_records)
    staged_ids = set(stage_changes.get("article_id", pd.Series(dtype=str)).astype(str).str.strip()) if "article_id" in stage_changes.columns else set()
    stage_error_counts = article_id_counts(stage_errors)
    preflight_error_counts = article_id_counts(preflight_errors)

    rows: list[dict[str, Any]] = []
    work = action_packet.copy().fillna("")
    work["_review_rank"] = pd.to_numeric(work.get("review_rank", ""), errors="coerce").fillna(999999).astype(int)
    work = work.sort_values(["_review_rank", "article_id"]).drop(columns=["_review_rank"])
    for _, row in work.iterrows():
        article_id = clean_text(row.get("article_id"))
        export = exports.get(article_id, {})
        export_row_count = numeric_value(export.get("export_row_count"), 0)
        exported_ready_candidate = bool(export.get("exported_ready_candidate", False))
        stage_error_rows = stage_error_counts.get(article_id, 0)
        preflight_error_rows = preflight_error_counts.get(article_id, 0)
        staged = article_id in staged_ids
        status, next_step = row_status(
            export_row_count=export_row_count,
            exported_ready_candidate=exported_ready_candidate,
            staged=staged,
            stage_error_rows=stage_error_rows,
            preflight_error_rows=preflight_error_rows,
        )
        rows.append(
            {
                "review_rank": clean_text(row.get("review_rank")),
                "article_id": article_id,
                "action_group": clean_text(row.get("action_group")),
                "quick_win_tier": clean_text(row.get("quick_win_tier")),
                "cell_target_rank": clean_text(row.get("cell_target_rank")),
                "cell_target_level": clean_text(row.get("cell_target_level")),
                "cell_recoveries_to_target_share": clean_text(row.get("cell_recoveries_to_target_share")),
                "cell_projected_share_after_ready_r001": clean_text(row.get("cell_projected_share_after_ready_r001")),
                "cell_ready_r001_target_coverage": clean_text(row.get("cell_ready_r001_target_coverage")),
                "title": clean_text(row.get("title")),
                "export_row_count": export_row_count,
                "exported_files": clean_text(export.get("exported_files")),
                "duplicate_export_rows": numeric_value(export.get("duplicate_export_rows"), 0),
                "exported_has_abstract": bool_text(bool(export.get("exported_has_abstract", False))),
                "exported_source_ready": bool_text(bool(export.get("exported_source_ready", False))),
                "exported_importable_evidence_tier": bool_text(bool(export.get("exported_importable_evidence_tier", False))),
                "exported_ready_candidate": bool_text(exported_ready_candidate),
                "staged": bool_text(staged),
                "stage_error_rows": stage_error_rows,
                "preflight_error_rows": preflight_error_rows,
                "import_ready": bool_text(status == "ready_to_import"),
                "next_status": status,
                "next_step": next_step,
            }
        )
    return pd.DataFrame(rows, columns=DETAIL_COLUMNS)


def priority_status(statuses: list[str]) -> str:
    priority = [
        "fix_stage_errors",
        "fix_preflight_errors",
        "complete_export_fields",
        "run_stage_and_preflight",
        "not_started",
        "ready_to_import",
    ]
    present = set(statuses)
    for status in priority:
        if status in present:
            return status
    return ""


def recommended_next_step(status: str) -> str:
    return {
        "fix_stage_errors": "Fix stage errors before any imports.",
        "fix_preflight_errors": "Fix preflight errors before any imports.",
        "complete_export_fields": "Finish missing abstract/source/evidence-tier fields in exported rows.",
        "run_stage_and_preflight": "Run staging and split preflight for exported ready candidates.",
        "not_started": "Work the action forms and export completed rows.",
        "ready_to_import": "All rows in this action group are import-ready; run dry-run import before applying.",
    }.get(status, "")


def recovery_action_progress_summary(detail: pd.DataFrame) -> pd.DataFrame:
    if detail.empty:
        return pd.DataFrame(columns=SUMMARY_COLUMNS)
    work = detail.copy().fillna("")
    work["_review_rank"] = pd.to_numeric(work.get("review_rank", ""), errors="coerce").fillna(999999).astype(int)
    rows: list[dict[str, Any]] = []
    for action_group, group in work.groupby("action_group", sort=False, dropna=False):
        total = len(group)
        exported_rows = int(pd.to_numeric(group["export_row_count"], errors="coerce").fillna(0).gt(0).sum())
        import_ready_rows = int(group["import_ready"].astype(str).eq("yes").sum())
        target_needed = pd.to_numeric(group.get("cell_recoveries_to_target_share", pd.Series("", index=group.index)), errors="coerce").fillna(0)
        target_ranks = pd.to_numeric(group.get("cell_target_rank", pd.Series("", index=group.index)), errors="coerce")
        top_rank = int(target_ranks.min()) if target_ranks.notna().any() else ""
        top_group = group[target_ranks.eq(top_rank)] if top_rank != "" else pd.DataFrame()
        status = priority_status(group["next_status"].astype(str).tolist())
        rows.append(
            {
                "action_group": clean_text(action_group),
                "rows_total": total,
                "priority_cell_rows": int(target_needed.gt(0).sum()),
                "critical_cell_rows": int(group.get("cell_target_level", pd.Series("", index=group.index)).astype(str).eq("critical").sum()),
                "top_cell_target_rank": top_rank,
                "top_cell_target_level": unique_join(top_group.get("cell_target_level", pd.Series(dtype=str))) if not top_group.empty else "",
                "top_cell_recoveries_to_target_share": unique_join(top_group.get("cell_recoveries_to_target_share", pd.Series(dtype=str))) if not top_group.empty else "",
                "exported_rows": exported_rows,
                "exported_ready_candidates": int(group["exported_ready_candidate"].astype(str).eq("yes").sum()),
                "staged_rows": int(group["staged"].astype(str).eq("yes").sum()),
                "import_ready_rows": import_ready_rows,
                "stage_error_rows": int(pd.to_numeric(group["stage_error_rows"], errors="coerce").fillna(0).sum()),
                "preflight_error_rows": int(pd.to_numeric(group["preflight_error_rows"], errors="coerce").fillna(0).sum()),
                "remaining_unexported_rows": max(0, total - exported_rows),
                "remaining_not_import_ready_rows": max(0, total - import_ready_rows),
                "first_review_rank": int(group["_review_rank"].min()),
                "next_status": status,
                "recommended_next_step": recommended_next_step(status),
            }
        )
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS).sort_values(["first_review_rank", "action_group"]).reset_index(drop=True)


def recovery_action_progress_overview(summary: pd.DataFrame, detail: pd.DataFrame) -> pd.DataFrame:
    rows_total = int(pd.to_numeric(summary.get("rows_total", pd.Series(dtype=str)), errors="coerce").fillna(0).sum()) if not summary.empty else 0
    exported_rows = int(pd.to_numeric(summary.get("exported_rows", pd.Series(dtype=str)), errors="coerce").fillna(0).sum()) if not summary.empty else 0
    import_ready_rows = int(pd.to_numeric(summary.get("import_ready_rows", pd.Series(dtype=str)), errors="coerce").fillna(0).sum()) if not summary.empty else 0
    priority_cell_rows = int(pd.to_numeric(summary.get("priority_cell_rows", pd.Series(dtype=str)), errors="coerce").fillna(0).sum()) if not summary.empty else 0
    critical_cell_rows = int(pd.to_numeric(summary.get("critical_cell_rows", pd.Series(dtype=str)), errors="coerce").fillna(0).sum()) if not summary.empty else 0
    stage_error_rows = int(pd.to_numeric(summary.get("stage_error_rows", pd.Series(dtype=str)), errors="coerce").fillna(0).sum()) if not summary.empty else 0
    preflight_error_rows = int(pd.to_numeric(summary.get("preflight_error_rows", pd.Series(dtype=str)), errors="coerce").fillna(0).sum()) if not summary.empty else 0
    duplicate_export_rows = int(pd.to_numeric(detail.get("duplicate_export_rows", pd.Series(dtype=str)), errors="coerce").fillna(0).sum()) if not detail.empty else 0
    next_status = priority_status(summary.get("next_status", pd.Series(dtype=str)).astype(str).tolist()) if not summary.empty else ""
    return pd.DataFrame(
        [
            {"metric": "action_groups", "value": len(summary)},
            {"metric": "rows_total", "value": rows_total},
            {"metric": "priority_cell_rows", "value": priority_cell_rows},
            {"metric": "critical_cell_rows", "value": critical_cell_rows},
            {"metric": "exported_rows", "value": exported_rows},
            {"metric": "import_ready_rows", "value": import_ready_rows},
            {"metric": "remaining_not_import_ready_rows", "value": max(0, rows_total - import_ready_rows)},
            {"metric": "stage_error_rows", "value": stage_error_rows},
            {"metric": "preflight_error_rows", "value": preflight_error_rows},
            {"metric": "duplicate_export_rows", "value": duplicate_export_rows},
            {"metric": "next_status", "value": next_status},
            {"metric": "recommended_next_step", "value": recommended_next_step(next_status)},
        ],
        columns=OVERVIEW_COLUMNS,
    )


def write_action_progress_report(path: Path, *, overview: pd.DataFrame, summary: pd.DataFrame, detail: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lookup = {clean_text(row.get("metric")): clean_text(row.get("value")) for _, row in overview.iterrows()} if not overview.empty else {}
    lines = [
        "# Recovery Batch R001 Action Progress",
        "",
        "This report is non-mutating. It summarizes action-form exports, staged rows, stage errors, and preflight errors by reviewer action group. It does not import abstracts, update final article files, change labels, or call the network.",
        "",
        f"- Action groups: {lookup.get('action_groups', '0')}",
        f"- Total action rows: {lookup.get('rows_total', '0')}",
        f"- Rows in cells still above the target insufficient-text share: {lookup.get('priority_cell_rows', '0')}",
        f"- Rows in critical target cells: {lookup.get('critical_cell_rows', '0')}",
        f"- Exported rows: {lookup.get('exported_rows', '0')}",
        f"- Import-ready rows after staging/preflight: {lookup.get('import_ready_rows', '0')}",
        f"- Stage error rows: {lookup.get('stage_error_rows', '0')}",
        f"- Preflight error rows: {lookup.get('preflight_error_rows', '0')}",
        f"- Next status: `{lookup.get('next_status', '')}`",
        f"- Recommended next step: {lookup.get('recommended_next_step', '')}",
        "",
        "## Overview",
        "",
        df_to_markdown(overview, max_rows=20),
        "",
        "## Action Summary",
        "",
        df_to_markdown(summary, max_rows=40),
        "",
        "## Row Detail",
        "",
        df_to_markdown(detail, max_rows=60),
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_action_dashboard(
    path: Path,
    *,
    overview: pd.DataFrame,
    summary: pd.DataFrame,
    packet_index: pd.DataFrame,
    progress_report_path: str,
    action_report_path: str,
    cached_evidence_report_path: str,
    source_guide_report_path: str,
    workboard_report_path: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    overview_lookup = {clean_text(row.get("metric")): clean_text(row.get("value")) for _, row in overview.iterrows()} if not overview.empty else {}
    packets = packet_index.copy().fillna("") if not packet_index.empty else pd.DataFrame()
    progress = summary.copy().fillna("") if not summary.empty else pd.DataFrame(columns=SUMMARY_COLUMNS)
    if not packets.empty and "action_group" in packets.columns:
        progress = progress.merge(
            packets[[column for column in ["action_group", "html_path", "csv_path", "quick_win_tiers"] if column in packets.columns]].drop_duplicates("action_group", keep="first"),
            on="action_group",
            how="left",
        ).fillna("")
    else:
        for column in ["html_path", "csv_path", "quick_win_tiers"]:
            progress[column] = ""

    rows: list[str] = []
    for _, row in progress.iterrows():
        action_group = clean_text(row.get("action_group"))
        html_path = clean_text(row.get("html_path"))
        csv_path = clean_text(row.get("csv_path"))
        form_link = html_link(path, "Open form", html_path) if html_path else ""
        packet_link = html_link(path, "CSV", csv_path) if csv_path else ""
        rows.append(
            "<tr>"
            f"<td><strong>{html.escape(action_group)}</strong><br><span>{html.escape(clean_text(row.get('quick_win_tiers')))}</span></td>"
            f"<td>{html.escape(clean_text(row.get('rows_total')))}</td>"
            f"<td><strong>{html.escape(target_rank_text(row.get('top_cell_target_rank')) or '-')}</strong>"
            f"<span>{html.escape(clean_text(row.get('top_cell_target_level')))}"
            f"{' | need ' + html.escape(clean_text(row.get('top_cell_recoveries_to_target_share'))) if clean_text(row.get('top_cell_recoveries_to_target_share')) else ''}</span>"
            f"<span>{html.escape(clean_text(row.get('priority_cell_rows')))} target-share rows</span></td>"
            f"<td>{html.escape(clean_text(row.get('exported_rows')))}</td>"
            f"<td>{html.escape(clean_text(row.get('staged_rows')))}</td>"
            f"<td>{html.escape(clean_text(row.get('import_ready_rows')))}</td>"
            f"<td>{html.escape(clean_text(row.get('stage_error_rows')))} / {html.escape(clean_text(row.get('preflight_error_rows')))}</td>"
            f"<td><code>{html.escape(clean_text(row.get('next_status')))}</code><br><span>{html.escape(clean_text(row.get('recommended_next_step')))}</span></td>"
            f"<td>{form_link} {packet_link}</td>"
            "</tr>"
        )
    table_rows = "\n".join(rows) or '<tr><td colspan="9">No action groups found.</td></tr>'
    quick_links = [
        ("Action progress report", progress_report_path),
        ("Action packet report", action_report_path),
        ("Cached evidence report", cached_evidence_report_path),
        ("Source guide", source_guide_report_path),
        ("Human review workboard", workboard_report_path),
    ]
    quick_link_items = "\n".join(
        f"<li>{html_link(path, label, target)}</li>"
        for label, target in quick_links
        if clean_text(target)
    )
    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Recovery R001 Action Dashboard</title>
  <style>
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #1f2933;
      background: #ffffff;
    }}
    main {{
      max-width: 1120px;
      margin: 0 auto;
      padding: 28px 20px 48px;
    }}
    h1 {{
      margin: 0 0 16px;
      font-size: 26px;
    }}
    h2 {{
      margin-top: 28px;
      font-size: 18px;
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 10px;
      margin: 18px 0;
    }}
    .metric {{
      border: 1px solid #d7dce2;
      border-radius: 8px;
      padding: 12px;
      background: #f7f8fa;
    }}
    .metric span, td span {{
      display: block;
      color: #667085;
      font-size: 12px;
      margin-top: 4px;
    }}
    .metric strong {{
      font-size: 18px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 10px;
    }}
    th, td {{
      border-bottom: 1px solid #d7dce2;
      padding: 10px 8px;
      text-align: left;
      vertical-align: top;
      font-size: 14px;
    }}
    th {{
      color: #667085;
      font-weight: 650;
    }}
    a {{
      color: #215c5c;
      margin-right: 10px;
    }}
    code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 12px;
      background: #eef2f3;
      border-radius: 4px;
      padding: 2px 4px;
    }}
  </style>
</head>
<body>
  <main>
    <h1>Recovery R001 Action Dashboard</h1>
    <div class="summary">
      <div class="metric"><span>Action groups</span><strong>{html.escape(overview_lookup.get("action_groups", "0"))}</strong></div>
      <div class="metric"><span>Total rows</span><strong>{html.escape(overview_lookup.get("rows_total", "0"))}</strong></div>
      <div class="metric"><span>Target-share rows</span><strong>{html.escape(overview_lookup.get("priority_cell_rows", "0"))}</strong></div>
      <div class="metric"><span>Critical-cell rows</span><strong>{html.escape(overview_lookup.get("critical_cell_rows", "0"))}</strong></div>
      <div class="metric"><span>Exported</span><strong>{html.escape(overview_lookup.get("exported_rows", "0"))}</strong></div>
      <div class="metric"><span>Import-ready</span><strong>{html.escape(overview_lookup.get("import_ready_rows", "0"))}</strong></div>
      <div class="metric"><span>Stage errors</span><strong>{html.escape(overview_lookup.get("stage_error_rows", "0"))}</strong></div>
      <div class="metric"><span>Preflight errors</span><strong>{html.escape(overview_lookup.get("preflight_error_rows", "0"))}</strong></div>
      <div class="metric"><span>Next status</span><strong>{html.escape(overview_lookup.get("next_status", ""))}</strong></div>
    </div>

    <h2>Action Groups</h2>
    <table>
      <thead>
        <tr><th>Action</th><th>Rows</th><th>Target</th><th>Exported</th><th>Staged</th><th>Ready</th><th>Errors</th><th>Status</th><th>Open</th></tr>
      </thead>
      <tbody>
        {table_rows}
      </tbody>
    </table>

    <h2>Reports</h2>
    <ul>
      {quick_link_items}
    </ul>
  </main>
</body>
</html>
"""
    path.write_text(html_text, encoding="utf-8")


def run_recovery_action_progress(
    *,
    action_packet_path: Path,
    action_packet_index_path: Path,
    reviewer_input: Path,
    stage_changes_path: Path,
    stage_errors_path: Path,
    preflight_errors_path: Path,
    output_overview: Path,
    output_summary: Path,
    output_detail: Path,
    report_path: Path,
    dashboard_path: Path,
    action_report_path: Path = Path("docs/recovery_batch_R001_action_packet.md"),
    cached_evidence_report_path: Path = Path("docs/recovery_batch_R001_cached_evidence.md"),
    source_guide_report_path: Path = Path("docs/recovery_batch_R001_source_guide.md"),
    workboard_report_path: Path = Path("docs/human_review_workboard.md"),
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    action_packet = read_csv_if_exists(action_packet_path)
    action_packet_index = read_csv_if_exists(action_packet_index_path)
    export_records = reviewer_export_records(reviewer_input)
    stage_changes = read_csv_if_exists(stage_changes_path)
    stage_errors = read_csv_if_exists(stage_errors_path)
    preflight_errors = read_csv_if_exists(preflight_errors_path)
    detail = recovery_action_progress_detail(
        action_packet=action_packet,
        export_records=export_records,
        stage_changes=stage_changes,
        stage_errors=stage_errors,
        preflight_errors=preflight_errors,
    )
    summary = recovery_action_progress_summary(detail)
    overview = recovery_action_progress_overview(summary, detail)
    for path, frame in [(output_overview, overview), (output_summary, summary), (output_detail, detail)]:
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)
    write_action_progress_report(report_path, overview=overview, summary=summary, detail=detail)
    write_action_dashboard(
        dashboard_path,
        overview=overview,
        summary=summary,
        packet_index=action_packet_index,
        progress_report_path=str(report_path),
        action_report_path=str(action_report_path),
        cached_evidence_report_path=str(cached_evidence_report_path),
        source_guide_report_path=str(source_guide_report_path),
        workboard_report_path=str(workboard_report_path),
    )
    print(f"action_progress_rows={len(detail)}")
    print(f"action_progress_groups={len(summary)}")
    print(f"overview={output_overview}")
    print(f"summary={output_summary}")
    print(f"detail={output_detail}")
    print(f"report={report_path}")
    print(f"dashboard={dashboard_path}")
    return overview, summary, detail


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--action-packet", default="outputs/tables/enriched/recovery_batch_R001_action_packet.csv")
    parser.add_argument("--action-packet-index", default="outputs/tables/enriched/recovery_batch_R001_action_packet_index.csv")
    parser.add_argument("--reviewer-input", default="data/intermediate/insufficient_text_recovery_review_exports/R001")
    parser.add_argument("--stage-changes", default="outputs/tables/enriched/recovery_batch_R001_tiered_stage_changes.csv")
    parser.add_argument("--stage-errors", default="outputs/tables/enriched/recovery_batch_R001_tiered_stage_errors.csv")
    parser.add_argument("--preflight-errors", default="outputs/tables/enriched/recovery_batch_R001_preflight_errors.csv")
    parser.add_argument("--output-overview", default="outputs/tables/enriched/recovery_batch_R001_action_progress_overview.csv")
    parser.add_argument("--output-summary", default="outputs/tables/enriched/recovery_batch_R001_action_progress_summary.csv")
    parser.add_argument("--output-detail", default="outputs/tables/enriched/recovery_batch_R001_action_progress_detail.csv")
    parser.add_argument("--report", default="docs/recovery_batch_R001_action_progress.md")
    parser.add_argument("--dashboard", default="data/intermediate/insufficient_text_recovery_review_forms/R001/recovery_batch_R001_action_dashboard.html")
    args = parser.parse_args()
    run_recovery_action_progress(
        action_packet_path=Path(args.action_packet),
        action_packet_index_path=Path(args.action_packet_index),
        reviewer_input=Path(args.reviewer_input),
        stage_changes_path=Path(args.stage_changes),
        stage_errors_path=Path(args.stage_errors),
        preflight_errors_path=Path(args.preflight_errors),
        output_overview=Path(args.output_overview),
        output_summary=Path(args.output_summary),
        output_detail=Path(args.output_detail),
        report_path=Path(args.report),
        dashboard_path=Path(args.dashboard),
    )


if __name__ == "__main__":
    main()
