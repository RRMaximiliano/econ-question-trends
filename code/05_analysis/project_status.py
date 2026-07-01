from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd

LIB_DIR = Path(__file__).resolve().parents[1] / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.append(str(LIB_DIR))

from econqt_common import clean_text  # noqa: E402


SUMMARY_COLUMNS = ["section", "metric", "value", "note"]
ACTION_COLUMNS = ["priority", "action_id", "status", "owner", "action", "why", "source_artifact", "next_artifact"]

CALIBRATION_DASHBOARD = "data/intermediate/manual_validation_calibration_forms/manual_validation_calibration_dashboard.html"
CALIBRATION_REMAINING_FORM = "data/intermediate/manual_validation_calibration_forms/manual_validation_calibration_remaining.html"
CALIBRATION_KICKOFF_REPORT = "docs/manual_validation_calibration_kickoff.md"
SCOPE_REVIEW_FORM = "data/intermediate/scope_review_forms/scope_review_packet.html"
RECENT_SCOPE_PRIORITY = "P1_recent_2023_2025_top5"
BACKLOG_SCOPE_PRIORITY = "P2_scope_review_backlog"
RECOVERY_KICKOFF_FORM_TEMPLATE = "data/intermediate/insufficient_text_recovery_review_forms/{batch}/recovery_batch_{batch}_kickoff_packet.html"
RECOVERY_BATCH_FORM_TEMPLATE = "data/intermediate/insufficient_text_recovery_forms/insufficient_text_recovery_batch_{batch}.html"
RECOVERY_IMPACT_REPORT = "docs/recovery_impact_report.md"


def metric_value(metrics_df: pd.DataFrame, metric: str, default: str = "") -> str:
    if metrics_df.empty or "metric" not in metrics_df.columns or "value" not in metrics_df.columns:
        return default
    matches = metrics_df[metrics_df["metric"].astype(str).eq(metric)]
    if matches.empty:
        return default
    value = clean_text(matches.iloc[0]["value"])
    return value if value != "" else default


def numeric_value(value: Any, default: int = 0) -> int:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return default if pd.isna(parsed) else int(parsed)


def numeric_metric(metrics_df: pd.DataFrame, metric: str, default: int = 0) -> int:
    return numeric_value(metric_value(metrics_df, metric, str(default)), default=default)


def first_row_value(df: pd.DataFrame, column: str, default: str = "") -> str:
    if df.empty or column not in df.columns:
        return default
    value = clean_text(df.iloc[0].get(column, default))
    return value if value != "" else default


def df_to_markdown(df: pd.DataFrame, max_rows: int = 30) -> str:
    if df.empty:
        return "_No rows._"
    shown = df.head(max_rows).fillna("")
    headers = [str(column).replace("|", "\\|") for column in shown.columns]
    rows = [headers] + [[str(value).replace("|", "\\|") for value in row] for row in shown.astype(str).values.tolist()]
    widths = [max(len(row[i]) for row in rows) for i in range(len(headers))]
    header = "| " + " | ".join(headers[i].ljust(widths[i]) for i in range(len(headers))) + " |"
    separator = "| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |"
    body = ["| " + " | ".join(row[i].ljust(widths[i]) for i in range(len(headers))) + " |" for row in rows[1:]]
    suffix = f"\n\n_Only first {max_rows} rows shown._" if len(df) > max_rows else ""
    return "\n".join([header, separator] + body) + suffix


def project_status_summary(
    gate: pd.DataFrame,
    recovery: pd.DataFrame,
    calibration: pd.DataFrame,
    readiness: pd.DataFrame,
    route_matrix: pd.DataFrame,
    scope_candidates: pd.DataFrame | None = None,
    scope_completion: pd.DataFrame | None = None,
    recovery_split_summary: pd.DataFrame | None = None,
    recovery_preflight_summary: pd.DataFrame | None = None,
    recovery_review_queue_summary: pd.DataFrame | None = None,
    recovery_source_experiments: pd.DataFrame | None = None,
) -> pd.DataFrame:
    route_top = route_matrix.iloc[0].to_dict() if not route_matrix.empty else {}
    scope_candidates = scope_candidates if scope_candidates is not None else pd.DataFrame()
    scope_completion = scope_completion if scope_completion is not None else pd.DataFrame()
    recovery_split_summary = recovery_split_summary if recovery_split_summary is not None else pd.DataFrame()
    recovery_preflight_summary = recovery_preflight_summary if recovery_preflight_summary is not None else pd.DataFrame()
    recovery_review_queue_summary = recovery_review_queue_summary if recovery_review_queue_summary is not None else pd.DataFrame()
    recovery_source_experiments = recovery_source_experiments if recovery_source_experiments is not None else pd.DataFrame()
    rows = [
        {
            "section": "validation",
            "metric": "validation_gate",
            "value": metric_value(gate, "validation_gate", "missing"),
            "note": metric_value(gate, "next_action", ""),
        },
        {
            "section": "validation",
            "metric": "first_blocking_check",
            "value": metric_value(gate, "first_blocking_check", ""),
            "note": "Trend outputs are descriptive until validation_gate=proceed.",
        },
        {
            "section": "validation",
            "metric": "calibration_progress",
            "value": f"{metric_value(calibration, 'completed_calibration_rows', metric_value(calibration, 'completed_calibration_labels', '0'))} / {metric_value(calibration, 'calibration_rows', '0')}",
            "note": f"Use {CALIBRATION_REMAINING_FORM} before assigning the full validation sample.",
        },
        {
            "section": "validation",
            "metric": "manual_validation_progress",
            "value": f"{metric_value(gate, 'completed_manual_labels', metric_value(readiness, 'completed_manual_labels', '0'))} / {metric_value(gate, 'manual_validation_total_rows', metric_value(readiness, 'sample_rows', '0'))}",
            "note": f"Remaining labels: {metric_value(gate, 'remaining_manual_labels', metric_value(readiness, 'remaining_manual_labels', '0'))}",
        },
        {
            "section": "recovery",
            "metric": "remaining_backfill_abstracts",
            "value": metric_value(recovery, "remaining_backfill_abstracts", "0"),
            "note": f"Next batch: {metric_value(recovery, 'next_recovery_batch', '')}",
        },
        {
            "section": "recovery",
            "metric": "completed_backfill_abstracts",
            "value": metric_value(recovery, "completed_backfill_abstracts", "0"),
            "note": f"Current queue rows: {metric_value(recovery, 'current_recovery_queue_rows', '0')}",
        },
    ]
    if not scope_candidates.empty:
        batch_note = ""
        if "recovery_batch" in scope_candidates.columns:
            batches = [clean_text(value) for value in scope_candidates["recovery_batch"].tolist() if clean_text(value)]
            if batches:
                batch_note = f"First affected batch: {sorted(set(batches))[0]}"
        rows.append(
            {
                "section": "recovery",
                "metric": "scope_review_candidates",
                "value": str(len(scope_candidates)),
                "note": batch_note or "Review likely nonresearch/parataxt rows before abstract recovery.",
            }
        )
    scope_rows = numeric_metric(scope_completion, "scope_review_rows", 0)
    if scope_rows > 0:
        completed_scope = metric_value(scope_completion, "completed_scope_review_decisions", "0")
        remaining_scope = metric_value(scope_completion, "remaining_scope_review_decisions", "0")
        rows.append(
            {
                "section": "recovery",
                "metric": "scope_review_progress",
                "value": f"{completed_scope} / {scope_rows}",
                "note": f"Remaining scope decisions: {remaining_scope}",
            }
        )
    if not recovery_split_summary.empty and "split_group" in recovery_split_summary.columns:
        split_work = recovery_split_summary.copy().fillna("")
        split_work["_rows"] = pd.to_numeric(split_work.get("rows", ""), errors="coerce").fillna(0).astype(int)
        ready_groups = {"ready_partial_text_extension", "ready_manual_metadata", "ready_autofill_or_completed"}
        ready_rows = int(split_work[split_work["split_group"].isin(ready_groups)]["_rows"].sum())
        waiting_scope_rows = int(split_work[split_work["split_group"].eq("waiting_scope_review")]["_rows"].sum())
        if "source_incomplete_backfill_abstracts" in split_work.columns:
            split_work["_source_incomplete"] = pd.to_numeric(split_work["source_incomplete_backfill_abstracts"], errors="coerce").fillna(0).astype(int)
        else:
            split_work["_source_incomplete"] = pd.Series(0, index=split_work.index, dtype="int64")
        source_incomplete_rows = int(split_work["_source_incomplete"].sum())
        batch_id = first_row_value(split_work, "recovery_batch", "")
        rows.extend(
            [
                {
                    "section": "recovery",
                    "metric": "ready_recovery_split_rows",
                    "value": str(ready_rows),
                    "note": f"Batch {batch_id} split packets are ready for reviewer work.",
                },
                {
                    "section": "recovery",
                    "metric": "waiting_scope_review_recovery_rows",
                    "value": str(waiting_scope_rows),
                    "note": "These rows should stay paused until scope review is resolved.",
                },
                {
                    "section": "recovery",
                    "metric": "source_incomplete_recovery_split_rows",
                    "value": str(source_incomplete_rows),
                    "note": "Filled split rows missing source plus source_url or source_record_id.",
                },
            ]
        )
    if not recovery_preflight_summary.empty:
        preflight_work = recovery_preflight_summary.copy().fillna("")
        preflight_work["_import_ready_rows"] = pd.to_numeric(preflight_work.get("import_ready_rows", ""), errors="coerce").fillna(0).astype(int)
        preflight_work["_error_rows"] = pd.to_numeric(preflight_work.get("error_rows", ""), errors="coerce").fillna(0).astype(int)
        preflight_ready_rows = int(preflight_work["_import_ready_rows"].sum())
        preflight_error_rows = int(preflight_work["_error_rows"].sum())
        rows.extend(
            [
                {
                    "section": "recovery",
                    "metric": "recovery_preflight_import_ready_rows",
                    "value": str(preflight_ready_rows),
                    "note": f"Checked ready split groups: {len(preflight_work)}",
                },
                {
                    "section": "recovery",
                    "metric": "recovery_preflight_error_rows",
                    "value": str(preflight_error_rows),
                    "note": "Resolve these before applying completed split imports.",
                },
            ]
        )
    if not recovery_review_queue_summary.empty:
        queue_work = recovery_review_queue_summary.copy().fillna("")
        queue_work["_rows"] = pd.to_numeric(queue_work.get("rows", ""), errors="coerce").fillna(0).astype(int)
        queue_rows = int(queue_work["_rows"].sum())
        tier1_rows = int(queue_work[queue_work.get("quick_win_tier", "").astype(str).eq("tier_1_partial_near_threshold")]["_rows"].sum()) if "quick_win_tier" in queue_work.columns else 0
        source_fix_rows = int(queue_work[queue_work.get("review_stage", "").astype(str).eq("source_metadata_fix")]["_rows"].sum()) if "review_stage" in queue_work.columns else 0
        rows.extend(
            [
                {
                    "section": "recovery",
                    "metric": "recovery_review_queue_rows",
                    "value": str(queue_rows),
                    "note": "Ranked actionable rows for manual abstract recovery.",
                },
                {
                    "section": "recovery",
                    "metric": "recovery_review_queue_tier1_rows",
                    "value": str(tier1_rows),
                    "note": f"Source-metadata-only fixes: {source_fix_rows}",
                },
            ]
        )
    if not recovery_source_experiments.empty:
        first_experiment = first_row_value(recovery_source_experiments, "experiment_id", "")
        rows.append(
            {
                "section": "recovery",
                "metric": "recovery_source_experiments",
                "value": str(len(recovery_source_experiments)),
                "note": f"First experiment: {first_experiment}",
            }
        )
    rows.extend(
        [
            {
                "section": "source_routes",
                "metric": "route_matrix_rows",
                "value": str(len(route_matrix)),
                "note": f"Top route unit: {clean_text(route_top.get('route_unit', ''))}",
            },
            {
                "section": "source_routes",
                "metric": "top_route_status",
                "value": clean_text(route_top.get("current_route_status", "")),
                "note": clean_text(route_top.get("recommended_route_action", "")),
            },
        ]
    )
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


def action_row(
    priority: int,
    action_id: str,
    status: str,
    owner: str,
    action: str,
    why: str,
    source_artifact: str,
    next_artifact: str = "",
) -> dict[str, Any]:
    return {
        "priority": priority,
        "action_id": action_id,
        "status": status,
        "owner": owner,
        "action": action,
        "why": why,
        "source_artifact": source_artifact,
        "next_artifact": next_artifact,
    }


def validation_actions(gate: pd.DataFrame, calibration: pd.DataFrame, readiness: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    gate_status = metric_value(gate, "validation_gate", "missing")
    next_action = metric_value(gate, "next_action", "")
    calibration_rows = numeric_metric(calibration, "calibration_rows", numeric_metric(gate, "calibration_rows", 0))
    completed_calibration = numeric_metric(
        calibration,
        "completed_calibration_rows",
        numeric_metric(gate, "completed_calibration_rows", numeric_metric(calibration, "completed_calibration_labels", numeric_metric(gate, "completed_calibration_labels", 0))),
    )
    if gate_status == "blocked_calibration" or completed_calibration < calibration_rows:
        rows.append(
            action_row(
                1,
                "complete_calibration_packet",
                "blocking_human",
                "reviewer",
                f"Open {CALIBRATION_DASHBOARD}, complete the remaining-row calibration form, export reviewer CSVs, then rerun run_manual_validation_calibration.py and run_validation_gate.py.",
                next_action or "Calibration labels are required before assigning the full 300-row validation sample.",
                CALIBRATION_KICKOFF_REPORT,
                CALIBRATION_REMAINING_FORM,
            )
        )
    ready = metric_value(readiness, "ready_for_blind_review", metric_value(gate, "ready_for_blind_review", "no"))
    drifted = numeric_metric(readiness, "drifted_articles", numeric_metric(gate, "drifted_articles", 0))
    if ready == "yes" and drifted == 0:
        rows.append(
            action_row(
                2,
                "hold_main_validation_until_calibration",
                "ready_after_calibration",
                "reviewer",
                "Use the six 50-row reviewer batches only after calibration is complete and any calibration disagreements are resolved.",
                "The sample is ready and has zero drift, but the gate still blocks full assignment until calibration passes.",
                "docs/manual_validation_portal.html",
            )
        )
    return rows


def route_actions(route_matrix: pd.DataFrame, *, max_routes: int = 5) -> list[dict[str, Any]]:
    if route_matrix.empty:
        return []
    rows: list[dict[str, Any]] = []
    work = route_matrix.copy().fillna("")
    work["_row_count"] = pd.to_numeric(work.get("row_count", ""), errors="coerce").fillna(0).astype(int)
    if "current_route_status" in work.columns:
        work = work[~work["current_route_status"].astype(str).eq("lane_decision_reference")].copy()
    work = work.sort_values(["_row_count", "route_unit"], ascending=[False, True])
    for _, route in work.head(max_routes).iterrows():
        route_unit = clean_text(route.get("route_unit", ""))
        status = clean_text(route.get("current_route_status", ""))
        action = clean_text(route.get("recommended_route_action", ""))
        if not route_unit or not action:
            continue
        rows.append(
            action_row(
                10 + len(rows),
                f"source_route_{route_unit.replace('/', '_').replace('.', '_')}",
                status or "inspect",
                "researcher",
                action,
                clean_text(route.get("source_route_note", "")),
                clean_text(route.get("next_artifact", "")),
                clean_text(route.get("next_artifact", "")),
            )
        )
    return rows


def recovery_actions(
    recovery: pd.DataFrame,
    recovery_split_summary: pd.DataFrame | None = None,
    recovery_review_queue_summary: pd.DataFrame | None = None,
) -> list[dict[str, Any]]:
    remaining = numeric_metric(recovery, "remaining_backfill_abstracts", 0)
    next_batch = metric_value(recovery, "next_recovery_batch", "")
    if remaining <= 0 or not next_batch:
        return []
    split_summary = recovery_split_summary if recovery_split_summary is not None else pd.DataFrame()
    if not split_summary.empty and "split_group" in split_summary.columns:
        split_work = split_summary.copy().fillna("")
        split_work["_rows"] = pd.to_numeric(split_work.get("rows", ""), errors="coerce").fillna(0).astype(int)
        ready_groups = {"ready_partial_text_extension", "ready_manual_metadata", "ready_autofill_or_completed"}
        ready_rows = int(split_work[split_work["split_group"].isin(ready_groups)]["_rows"].sum())
        waiting_scope_rows = int(split_work[split_work["split_group"].eq("waiting_scope_review")]["_rows"].sum())
        split_batch = first_row_value(split_work, "recovery_batch", next_batch)
        if ready_rows > 0:
            has_review_queue = recovery_review_queue_summary is not None and not recovery_review_queue_summary.empty
            review_queue_rows = 0
            if has_review_queue:
                queue_work = recovery_review_queue_summary.copy().fillna("")
                queue_work["_rows"] = pd.to_numeric(queue_work.get("rows", ""), errors="coerce").fillna(0).astype(int)
                review_queue_rows = int(queue_work["_rows"].sum())
            action_text = (
                f"Work the tiered recovery review packets for batch {split_batch}, stage completed tiered exports, run the combined preflight on the staged split summary, dry-run completed split CSVs with source metadata required, then import them atomically with --skip-empty-abstracts."
                if has_review_queue
                else f"Work the ready split packets for recovery batch {split_batch}, run the combined preflight, dry-run completed split CSVs with source metadata required, then import them atomically with --skip-empty-abstracts."
            )
            source_artifact = f"docs/recovery_batch_{split_batch}_tiered_packets.md" if has_review_queue else f"docs/recovery_batch_{split_batch}_split.md"
            next_artifact = (
                RECOVERY_KICKOFF_FORM_TEMPLATE.format(batch=split_batch)
                if has_review_queue
                else f"data/intermediate/insufficient_text_recovery_split_forms/{split_batch}/"
            )
            ready_note = (
                f"{review_queue_rows} actionable review rows are ready now"
                if has_review_queue
                else f"{ready_rows} split rows are ready now"
            )
            return [
                action_row(
                    8,
                    "work_ready_recovery_splits",
                    "ready_parallel",
                    "researcher",
                    action_text,
                    f"{ready_note}; {waiting_scope_rows} rows are paused for scope review.",
                    source_artifact,
                    next_artifact,
                )
            ]
    return [
        action_row(
            8,
            "work_next_recovery_batch",
            "ready_parallel",
            "researcher",
            f"Work recovery batch {next_batch} using its workplan for explicit abstracts only, then import completed rows with --skip-empty-abstracts.",
            f"{remaining} recovery rows still need enough text before classification can improve.",
            f"docs/recovery_batch_{next_batch}_workplan.md",
            RECOVERY_BATCH_FORM_TEMPLATE.format(batch=next_batch),
        )
    ]


def scope_packet_progress(scope_packet: pd.DataFrame, priority: str) -> tuple[int, int, int]:
    if scope_packet.empty or "scope_review_priority" not in scope_packet.columns:
        return 0, 0, 0
    work = scope_packet.copy().fillna("")
    work = work[work["scope_review_priority"].astype(str).eq(priority)].copy()
    if work.empty:
        return 0, 0, 0
    decision = work["human_scope_decision"].astype(str).str.strip() if "human_scope_decision" in work.columns else pd.Series("", index=work.index)
    completed = int(decision.ne("").sum())
    total = len(work)
    return total, completed, max(0, total - completed)


def scope_review_actions(
    scope_candidates: pd.DataFrame | None,
    scope_completion: pd.DataFrame | None = None,
    scope_packet: pd.DataFrame | None = None,
    recovery_split_summary: pd.DataFrame | None = None,
) -> list[dict[str, Any]]:
    if scope_candidates is None or scope_candidates.empty:
        return []
    scope_completion = scope_completion if scope_completion is not None else pd.DataFrame()
    scope_packet = scope_packet if scope_packet is not None else pd.DataFrame()
    recovery_split_summary = recovery_split_summary if recovery_split_summary is not None else pd.DataFrame()
    scope_rows = numeric_metric(scope_completion, "scope_review_rows", 0)
    completed = numeric_metric(scope_completion, "completed_scope_review_decisions", 0)
    remaining = numeric_metric(scope_completion, "remaining_scope_review_decisions", scope_rows or len(scope_candidates))
    waiting_scope_rows = 0
    if not recovery_split_summary.empty and "split_group" in recovery_split_summary.columns:
        split_work = recovery_split_summary.copy().fillna("")
        split_work["_rows"] = pd.to_numeric(split_work.get("rows", ""), errors="coerce").fillna(0).astype(int)
        waiting_scope_rows = int(split_work[split_work["split_group"].eq("waiting_scope_review")]["_rows"].sum())
    complete_status = "complete" if waiting_scope_rows == 0 else "completed_pending_application"
    recent_total, recent_completed, recent_remaining = scope_packet_progress(scope_packet, RECENT_SCOPE_PRIORITY)
    if recent_total:
        backlog_total, backlog_completed, backlog_remaining = scope_packet_progress(scope_packet, BACKLOG_SCOPE_PRIORITY)
        rows = [
            action_row(
                7,
                "review_recent_2023_2025_scope_candidates",
                "ready_parallel" if recent_remaining else complete_status,
                "researcher",
                f"Use the scope form priority filter for {RECENT_SCOPE_PRIORITY} and complete those rows first; current progress is {recent_completed} / {recent_total}.",
                "This recent top-5 denominator check unblocks the scope-first rows in the 2023-2025 recovery pilot.",
                "docs/scope_review_packet.md",
                SCOPE_REVIEW_FORM,
            )
        ]
        if backlog_total:
            rows.append(
                action_row(
                    7,
                    "review_scope_backlog_candidates",
                    "ready_parallel" if backlog_remaining else complete_status,
                    "researcher",
                    f"Continue the scope-review backlog after the recent priority rows; current progress is {backlog_completed} / {backlog_total}.",
                    "Likely nonresearch/parataxt rows should not consume broad abstract-recovery effort or enter trend denominators without review.",
                    "docs/scope_review_packet.md",
                    SCOPE_REVIEW_FORM,
                )
            )
        return rows
    if scope_rows > 0 and remaining <= 0:
        if waiting_scope_rows == 0:
            action = "Scope decisions are complete and no recovery rows remain paused for scope review."
            why = "Resolved nonresearch/parataxt rows are separated from ready recovery work."
        else:
            action = "Scope decisions are complete; review the packet before applying any denominator changes."
            why = "The audit is still non-mutating, so completed decisions need an explicit application step before trend denominators change."
        return [
            action_row(
                7,
                "review_scope_candidates",
                complete_status,
                "researcher",
                action,
                why,
                "docs/scope_review_packet.md",
                SCOPE_REVIEW_FORM,
            )
        ]
    progress = f"{completed} / {scope_rows}" if scope_rows else f"0 / {len(scope_candidates)}"
    return [
        action_row(
            7,
            "review_scope_candidates",
            "ready_parallel",
            "researcher",
            f"Complete the scope-review packet before recovering abstracts for those rows; current progress is {progress}.",
            "Likely nonresearch/parataxt rows should not consume abstract-recovery effort or enter trend denominators without review.",
            "docs/scope_review_packet.md",
            SCOPE_REVIEW_FORM,
        )
    ]


def project_next_actions(
    gate: pd.DataFrame,
    recovery: pd.DataFrame,
    calibration: pd.DataFrame,
    readiness: pd.DataFrame,
    route_matrix: pd.DataFrame,
    scope_candidates: pd.DataFrame | None = None,
    scope_completion: pd.DataFrame | None = None,
    recovery_split_summary: pd.DataFrame | None = None,
    recovery_review_queue_summary: pd.DataFrame | None = None,
    recovery_source_experiments: pd.DataFrame | None = None,
    scope_packet: pd.DataFrame | None = None,
) -> pd.DataFrame:
    rows = validation_actions(gate, calibration, readiness)
    rows.extend(scope_review_actions(scope_candidates, scope_completion, scope_packet, recovery_split_summary))
    rows.extend(recovery_actions(recovery, recovery_split_summary, recovery_review_queue_summary))
    if recovery_source_experiments is not None and not recovery_source_experiments.empty:
        first_experiment = first_row_value(recovery_source_experiments, "experiment_id", "")
        rows.append(
            action_row(
                9,
                "review_recovery_impact_experiments",
                "ready_parallel",
                "researcher",
                "Use the recovery impact report to snapshot before/after R001 imports and rank the next insufficient-text expansion experiments.",
                f"The first ranked experiment is `{first_experiment}`; use measured yield before scaling source routes.",
                RECOVERY_IMPACT_REPORT,
                RECOVERY_IMPACT_REPORT,
            )
        )
    rows.extend(route_actions(route_matrix))
    if not rows:
        return pd.DataFrame(columns=ACTION_COLUMNS)
    return pd.DataFrame(rows, columns=ACTION_COLUMNS).sort_values(["priority", "action_id"], ascending=[True, True]).reset_index(drop=True)


def write_project_status_report(path: Path, summary: pd.DataFrame, actions: pd.DataFrame, route_matrix: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary_lookup = dict(zip(summary["metric"], summary["value"])) if not summary.empty else {}
    lines = [
        "# Project Status",
        "",
        f"- Validation gate: `{summary_lookup.get('validation_gate', 'missing')}`",
        f"- Calibration progress: {summary_lookup.get('calibration_progress', '0 / 0')}",
        f"- Manual validation progress: {summary_lookup.get('manual_validation_progress', '0 / 0')}",
        f"- Remaining recovery abstracts: {summary_lookup.get('remaining_backfill_abstracts', '0')}",
        f"- Ready recovery split rows: {summary_lookup.get('ready_recovery_split_rows', '0')}",
        f"- Waiting scope-review recovery rows: {summary_lookup.get('waiting_scope_review_recovery_rows', '0')}",
        f"- Source-incomplete completed split rows: {summary_lookup.get('source_incomplete_recovery_split_rows', '0')}",
        f"- Recovery review queue rows: {summary_lookup.get('recovery_review_queue_rows', '0')}",
        f"- Recovery preflight errors: {summary_lookup.get('recovery_preflight_error_rows', '0')}",
        f"- Recovery source experiments: {summary_lookup.get('recovery_source_experiments', '0')}",
        f"- Scope review candidates: {summary_lookup.get('scope_review_candidates', '0')}",
        f"- Scope review progress: {summary_lookup.get('scope_review_progress', '0 / 0')}",
        "",
        "Treat recent trend outputs as descriptive until `validation_gate=proceed`.",
        "",
        "## Next Actions",
        "",
        df_to_markdown(actions, max_rows=20),
        "",
        "## Status Summary",
        "",
        df_to_markdown(summary, max_rows=30),
        "",
        "## Source Route Snapshot",
        "",
        df_to_markdown(
            route_matrix[
                [
                    column
                    for column in [
                        "route_unit",
                        "row_count",
                        "decision",
                        "current_route_status",
                        "probe_rows",
                        "recommended_route_action",
                        "next_artifact",
                    ]
                    if column in route_matrix.columns
                ]
            ],
            max_rows=12,
        ),
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("") if path.exists() else pd.DataFrame()


def run_project_status(
    *,
    gate_path: Path,
    recovery_path: Path,
    calibration_path: Path,
    readiness_path: Path,
    route_matrix_path: Path,
    scope_candidates_path: Path | None = None,
    scope_completion_path: Path | None = None,
    recovery_split_summary_path: Path | None = None,
    recovery_preflight_summary_path: Path | None = None,
    recovery_review_queue_summary_path: Path | None = None,
    recovery_source_experiments_path: Path | None = None,
    scope_packet_path: Path | None = None,
    output_summary: Path,
    output_actions: Path,
    report_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    gate = read_csv_if_exists(gate_path)
    recovery = read_csv_if_exists(recovery_path)
    calibration = read_csv_if_exists(calibration_path)
    readiness = read_csv_if_exists(readiness_path)
    route_matrix = read_csv_if_exists(route_matrix_path)
    scope_candidates = read_csv_if_exists(scope_candidates_path) if scope_candidates_path is not None else pd.DataFrame()
    scope_completion = read_csv_if_exists(scope_completion_path) if scope_completion_path is not None else pd.DataFrame()
    scope_packet = read_csv_if_exists(scope_packet_path) if scope_packet_path is not None else pd.DataFrame()
    recovery_split_summary = read_csv_if_exists(recovery_split_summary_path) if recovery_split_summary_path is not None else pd.DataFrame()
    recovery_preflight_summary = read_csv_if_exists(recovery_preflight_summary_path) if recovery_preflight_summary_path is not None else pd.DataFrame()
    recovery_review_queue_summary = read_csv_if_exists(recovery_review_queue_summary_path) if recovery_review_queue_summary_path is not None else pd.DataFrame()
    recovery_source_experiments = read_csv_if_exists(recovery_source_experiments_path) if recovery_source_experiments_path is not None else pd.DataFrame()
    summary = project_status_summary(gate, recovery, calibration, readiness, route_matrix, scope_candidates, scope_completion, recovery_split_summary, recovery_preflight_summary, recovery_review_queue_summary, recovery_source_experiments)
    actions = project_next_actions(gate, recovery, calibration, readiness, route_matrix, scope_candidates, scope_completion, recovery_split_summary, recovery_review_queue_summary, recovery_source_experiments, scope_packet)
    output_summary.parent.mkdir(parents=True, exist_ok=True)
    output_actions.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output_summary, index=False)
    actions.to_csv(output_actions, index=False)
    write_project_status_report(report_path, summary, actions, route_matrix)
    print(f"status_summary={output_summary}")
    print(f"next_actions={output_actions}")
    print(f"report={report_path}")
    return summary, actions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gate", default="outputs/tables/enriched/manual_validation_gate.csv")
    parser.add_argument("--recovery-progress", default="outputs/tables/enriched/recovery_progress_overview.csv")
    parser.add_argument("--calibration-summary", default="outputs/tables/enriched/manual_validation_calibration_summary.csv")
    parser.add_argument("--readiness", default="outputs/tables/enriched/manual_validation_readiness.csv")
    parser.add_argument("--route-matrix", default="outputs/tables/enriched/insufficient_text_source_route_matrix.csv")
    parser.add_argument("--scope-candidates", default="outputs/tables/enriched/scope_review_candidates.csv")
    parser.add_argument("--scope-completion", default="outputs/tables/enriched/scope_review_completion.csv")
    parser.add_argument("--scope-packet", default="data/intermediate/scope_review/scope_review_packet.csv")
    parser.add_argument("--recovery-split-summary", default="outputs/tables/enriched/recovery_batch_R001_split_summary.csv")
    parser.add_argument("--recovery-preflight-summary", default="outputs/tables/enriched/recovery_batch_R001_preflight_summary.csv")
    parser.add_argument("--recovery-review-queue-summary", default="outputs/tables/enriched/recovery_batch_R001_review_queue_summary.csv")
    parser.add_argument("--recovery-source-experiments", default="outputs/tables/enriched/recovery_source_experiments.csv")
    parser.add_argument("--output-summary", default="outputs/tables/enriched/project_status_summary.csv")
    parser.add_argument("--output-actions", default="outputs/tables/enriched/project_next_actions.csv")
    parser.add_argument("--report", default="docs/project_status.md")
    args = parser.parse_args()
    run_project_status(
        gate_path=Path(args.gate),
        recovery_path=Path(args.recovery_progress),
        calibration_path=Path(args.calibration_summary),
        readiness_path=Path(args.readiness),
        route_matrix_path=Path(args.route_matrix),
        scope_candidates_path=Path(args.scope_candidates),
        scope_completion_path=Path(args.scope_completion),
        scope_packet_path=Path(args.scope_packet),
        recovery_split_summary_path=Path(args.recovery_split_summary),
        recovery_preflight_summary_path=Path(args.recovery_preflight_summary),
        recovery_review_queue_summary_path=Path(args.recovery_review_queue_summary),
        recovery_source_experiments_path=Path(args.recovery_source_experiments),
        output_summary=Path(args.output_summary),
        output_actions=Path(args.output_actions),
        report_path=Path(args.report),
    )


if __name__ == "__main__":
    main()
