from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "lib"))

from econqt_common import clean_text  # noqa: E402
from project_status import df_to_markdown  # noqa: E402


WORKBOARD_COLUMNS = [
    "priority",
    "workstream",
    "task_id",
    "status",
    "owner",
    "rows_total",
    "rows_completed",
    "rows_remaining",
    "first_item",
    "gate_rule",
    "first_session_action",
    "recommended_artifact",
    "form_or_queue",
    "next_command",
    "note",
]
RECENT_SCOPE_PRIORITY = "P1_recent_2023_2025_top5"
BACKLOG_SCOPE_PRIORITY = "P2_scope_review_backlog"


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


def workboard_row(
    priority: int,
    workstream: str,
    task_id: str,
    status: str,
    owner: str,
    rows_total: int,
    rows_completed: int,
    rows_remaining: int,
    first_item: str,
    gate_rule: str,
    first_session_action: str,
    recommended_artifact: str,
    form_or_queue: str,
    next_command: str,
    note: str,
) -> dict[str, Any]:
    return {
        "priority": priority,
        "workstream": workstream,
        "task_id": task_id,
        "status": status,
        "owner": owner,
        "rows_total": rows_total,
        "rows_completed": rows_completed,
        "rows_remaining": rows_remaining,
        "first_item": first_item,
        "gate_rule": gate_rule,
        "first_session_action": first_session_action,
        "recommended_artifact": recommended_artifact,
        "form_or_queue": form_or_queue,
        "next_command": next_command,
        "note": note,
    }


def guide_count(guide_summary: pd.DataFrame, section: str, value: str) -> int:
    if guide_summary.empty or not {"section", "value", "rows"}.issubset(guide_summary.columns):
        return 0
    matches = guide_summary[
        guide_summary["section"].astype(str).eq(section)
        & guide_summary["value"].astype(str).eq(value)
    ]
    if matches.empty:
        return 0
    return numeric_value(matches.iloc[0].get("rows"), 0)


def recovery_tier_rows(recovery_queue_summary: pd.DataFrame, tier: str) -> int:
    if recovery_queue_summary.empty or "quick_win_tier" not in recovery_queue_summary.columns:
        return 0
    work = recovery_queue_summary.copy().fillna("")
    work["_rows"] = pd.to_numeric(work.get("rows", ""), errors="coerce").fillna(0).astype(int)
    return int(work[work["quick_win_tier"].astype(str).eq(tier)]["_rows"].sum())


def recovery_automation_note(audit_summary: pd.DataFrame) -> str:
    if audit_summary.empty or not {"automation_status", "rows"}.issubset(audit_summary.columns):
        return ""
    labels = {
        "manual_near_threshold_extension": "near-threshold",
        "manual_replace_boilerplate": "replace-boilerplate",
        "manual_partial_extension": "partial-extension",
        "manual_index_or_template_spike_required": "manual/template-spike",
        "manual_metadata_after_pdf_block": "PDF-blocked",
    }
    parts: list[str] = []
    for _, row in audit_summary.copy().fillna("").iterrows():
        status = clean_text(row.get("automation_status"))
        rows = numeric_value(row.get("rows"), 0)
        if not status or rows <= 0:
            continue
        parts.append(f"{rows} {labels.get(status, status)}")
    return "; ".join(parts)


def preflight_error_rows(preflight_summary: pd.DataFrame) -> int:
    if preflight_summary.empty:
        return 0
    return int(pd.to_numeric(preflight_summary.get("error_rows", ""), errors="coerce").fillna(0).sum())


def preflight_import_ready_rows(preflight_summary: pd.DataFrame) -> int:
    if preflight_summary.empty:
        return 0
    return int(pd.to_numeric(preflight_summary.get("import_ready_rows", ""), errors="coerce").fillna(0).sum())


def first_incomplete_scope(scope_packet: pd.DataFrame) -> str:
    if scope_packet.empty:
        return ""
    work = scope_packet.copy().fillna("")
    if "human_scope_decision" not in work.columns:
        return ""
    incomplete = work[work["human_scope_decision"].astype(str).str.strip().eq("")]
    if incomplete.empty:
        return ""
    row = incomplete.iloc[0]
    title = clean_text(row.get("title"))
    scope_id = clean_text(row.get("scope_review_id"))
    return f"{scope_id}: {title}" if title else scope_id


def scope_progress(scope_packet: pd.DataFrame, priority: str | None = None) -> tuple[int, int, int, str]:
    if scope_packet.empty:
        return 0, 0, 0, ""
    work = scope_packet.copy().fillna("")
    if priority is not None:
        if "scope_review_priority" not in work.columns:
            return 0, 0, 0, ""
        work = work[work["scope_review_priority"].astype(str).eq(priority)].copy()
    if work.empty:
        return 0, 0, 0, ""
    decision = work["human_scope_decision"].astype(str).str.strip() if "human_scope_decision" in work.columns else pd.Series("", index=work.index)
    completed = int(decision.ne("").sum())
    total = len(work)
    remaining = max(0, total - completed)
    return total, completed, remaining, first_incomplete_scope(work)


def first_recovery_queue_item(recovery_queue: pd.DataFrame) -> str:
    if recovery_queue.empty:
        return ""
    row = recovery_queue.iloc[0].fillna("")
    rank = clean_text(row.get("review_rank"))
    title = clean_text(row.get("title"))
    chars_needed = clean_text(row.get("chars_needed_to_threshold"))
    prefix = f"rank {rank}" if rank else "first row"
    suffix = f" ({chars_needed} chars needed)" if chars_needed else ""
    return f"{prefix}: {title}{suffix}" if title else prefix


def first_recent_recovery_item(recent_packet: pd.DataFrame) -> str:
    if recent_packet is None or recent_packet.empty:
        return ""
    row = recent_packet.iloc[0].fillna("")
    title = clean_text(row.get("title"))
    journal = clean_text(row.get("journal_short"))
    year = clean_text(row.get("publication_year"))
    prefix = "first recover-text row"
    context = " · ".join(part for part in [journal, year] if part)
    return f"{prefix}: {title} ({context})" if title and context else f"{prefix}: {title}" if title else prefix


def human_review_workboard(
    *,
    calibration_summary: pd.DataFrame,
    calibration_kickoff: pd.DataFrame,
    calibration_guide_summary: pd.DataFrame,
    scope_completion: pd.DataFrame,
    scope_packet: pd.DataFrame,
    recovery_queue_summary: pd.DataFrame,
    recovery_queue: pd.DataFrame,
    recovery_preflight_summary: pd.DataFrame,
    recovery_automation_summary: pd.DataFrame,
    validation_gate: pd.DataFrame,
    recent_recovery_summary: pd.DataFrame | None = None,
    recent_recovery_packet: pd.DataFrame | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    recent_recovery_summary = recent_recovery_summary if recent_recovery_summary is not None else pd.DataFrame()
    recent_recovery_packet = recent_recovery_packet if recent_recovery_packet is not None else pd.DataFrame()

    calibration_rows = numeric_metric(calibration_summary, "calibration_rows", 0)
    calibration_completed = numeric_metric(
        calibration_summary,
        "completed_calibration_rows",
        numeric_metric(calibration_summary, "completed_calibration_labels", 0),
    )
    calibration_remaining = max(0, calibration_rows - calibration_completed)
    high_difficulty = guide_count(calibration_guide_summary, "review_difficulty", "high")
    no_abstract = guide_count(calibration_guide_summary, "text_status", "no_abstract")
    calibration_status = "blocking" if calibration_remaining else "complete"
    rows.append(
        workboard_row(
            1,
            "calibration",
            "complete_calibration_packet",
            calibration_status,
            "reviewer",
            calibration_rows,
            calibration_completed,
            calibration_remaining,
            f"{high_difficulty} high-difficulty rows; {no_abstract} no-abstract rows",
            "blocks main validation until calibration is complete and disagreements are resolved",
            "Open the calibration dashboard, complete the remaining-row form, export reviewer labels, then rerun calibration and gate checks.",
            "docs/manual_validation_calibration_kickoff.md",
            "data/intermediate/manual_validation_calibration_forms/manual_validation_calibration_dashboard.html",
            "/usr/bin/python3 run_manual_validation_calibration.py && /usr/bin/python3 run_validation_gate.py",
            "Start from the calibration dashboard and use the remaining-row form first; finish calibration before assigning the full 300-row validation sample.",
        )
    )

    scope_rows = numeric_metric(scope_completion, "scope_review_rows", 0)
    scope_completed = numeric_metric(scope_completion, "completed_scope_review_decisions", 0)
    scope_remaining = numeric_metric(scope_completion, "remaining_scope_review_decisions", max(0, scope_rows - scope_completed))
    if scope_rows:
        recent_scope_total, recent_scope_completed, recent_scope_remaining, recent_scope_first = scope_progress(scope_packet, RECENT_SCOPE_PRIORITY)
        if recent_scope_total:
            rows.append(
                workboard_row(
                    2,
                    "recent_scope_review",
                    "complete_recent_2023_2025_scope_review",
                    "ready_parallel" if recent_scope_remaining else "complete",
                    "researcher",
                    recent_scope_total,
                    recent_scope_completed,
                    recent_scope_remaining,
                    recent_scope_first,
                    "unblocks recent 2023-2025 scope-first rows; can run in parallel with calibration",
                    f"Open the scope form, set the priority filter to {RECENT_SCOPE_PRIORITY}, complete those rows first, then run the dry-run scope application before using --apply.",
                    "docs/scope_review_packet.md",
                    "data/intermediate/scope_review_forms/scope_review_packet.html",
                    "/usr/bin/python3 run_apply_scope_review_decisions.py",
                    f"The scope form still exports the full canonical packet even when filtered. These priority rows are the recent top-5 denominator check before spending recovery effort on likely paratext. The listed command is a dry-run by default; add --apply only after docs/scope_review_apply.md reports zero errors and the proposed scope changes are reviewed.",
                )
            )

            backlog_total, backlog_completed, backlog_remaining, backlog_first = scope_progress(scope_packet, BACKLOG_SCOPE_PRIORITY)
            if backlog_total:
                rows.append(
                    workboard_row(
                        4,
                        "scope_review_backlog",
                        "complete_scope_review_backlog",
                        "ready_parallel" if backlog_remaining else "complete",
                        "researcher",
                        backlog_total,
                        backlog_completed,
                        backlog_remaining,
                        backlog_first,
                        "can run in parallel after or alongside the recent priority rows",
                        "Continue the remaining scope packet rows after the recent priority group, preserving the same reviewer/date and dry-run-before-apply checks.",
                        "docs/scope_review_packet.md",
                        "data/intermediate/scope_review_forms/scope_review_packet.html",
                        "/usr/bin/python3 run_apply_scope_review_decisions.py",
                        "Use docs/scope_review_guide.md to group repeated patterns; the scope form can bulk-fill blank decisions by pattern family after reviewer confirmation. Resolve likely nonresearch/parataxt rows before broad recovery work. The listed command is a dry-run by default; add --apply only after docs/scope_review_apply.md reports zero errors and the proposed scope changes are reviewed.",
                    )
                )
        else:
            rows.append(
                workboard_row(
                    2,
                    "scope_review",
                    "complete_scope_review_packet",
                    "ready_parallel" if scope_remaining else "complete",
                    "researcher",
                    scope_rows,
                    scope_completed,
                    scope_remaining,
                    first_incomplete_scope(scope_packet),
                    "can run in parallel with calibration; resolve likely nonresearch rows before spending recovery effort on them",
                    "Open the scope packet, decide exclude_nonresearch/keep_research/unsure with reviewer/date fields, then run the dry-run scope application before using --apply.",
                    "docs/scope_review_packet.md",
                    "data/intermediate/scope_review_forms/scope_review_packet.html",
                    "/usr/bin/python3 run_apply_scope_review_decisions.py",
                    "Use docs/scope_review_guide.md to group repeated patterns; the scope form can bulk-fill blank decisions by pattern family after reviewer confirmation. Resolve likely nonresearch/parataxt rows before spending recovery effort on them. The listed command is a dry-run by default; add --apply only after docs/scope_review_apply.md reports zero errors and the proposed scope changes are reviewed.",
                )
            )

    recent_queue_rows = numeric_metric(recent_recovery_summary, "recent_queue_rows", 0)
    recent_scope_first = numeric_metric(recent_recovery_summary, "recent_scope_review_first_rows", 0)
    recent_recover_text = numeric_metric(recent_recovery_summary, "recent_recover_text_rows", 0)
    if recent_queue_rows:
        rows.append(
            workboard_row(
                3,
                "recent_recovery",
                "work_recent_2023_2025_recovery_pilot",
                "ready_parallel" if recent_recover_text else "waiting_on_scope_review",
                "researcher",
                recent_queue_rows,
                0,
                recent_queue_rows,
                first_recent_recovery_item(recent_recovery_packet) or f"{recent_recover_text} recover-text rows; {recent_scope_first} scope-first rows",
                "scope-first rows wait on scope review; recover-text rows can run before broad R001 backfill",
                "Open the recent 2023-2025 recovery form first, work only recover_text rows, and keep scope_review_first rows in the scope packet.",
                "docs/recent_2023_2025_recovery_pilot.md",
                "data/intermediate/insufficient_text_recovery_review_forms/recent_2023_2025/recent_2023_2025_recovery_packet.html",
                "/usr/bin/python3 run_import_abstract_backfill.py --input data/intermediate/insufficient_text_recovery_review_exports/recent_2023_2025/recent_2023_2025_recovery_packet.csv --skip-empty-abstracts --dry-run --require-source-metadata",
                f"Recent top-5 pilot has {recent_queue_rows} recovery-queue rows: {recent_recover_text} immediate recover-text rows and {recent_scope_first} scope-review-first rows. Use docs/recent_2023_2025_recovery_pilot.md before broad R001 packets; apply imports only after the dry-run has zero errors.",
            )
        )

    queue_rows = int(pd.to_numeric(recovery_queue_summary.get("rows", pd.Series(dtype=str)), errors="coerce").fillna(0).sum()) if not recovery_queue_summary.empty else 0
    tier1_rows = recovery_tier_rows(recovery_queue_summary, "tier_1_partial_near_threshold")
    tier2_replace_rows = recovery_tier_rows(recovery_queue_summary, "tier_2_partial_replace_suspect_text")
    tier3_partial_rows = recovery_tier_rows(recovery_queue_summary, "tier_3_partial_extension")
    tier4_metadata_rows = recovery_tier_rows(recovery_queue_summary, "tier_4_manual_metadata_has_context")
    tier5_blocked_rows = recovery_tier_rows(recovery_queue_summary, "tier_5_manual_metadata_pdf_blocked")
    preflight_errors = preflight_error_rows(recovery_preflight_summary)
    import_ready = preflight_import_ready_rows(recovery_preflight_summary)
    automation_note = recovery_automation_note(recovery_automation_summary)
    automation_suffix = f" See docs/recovery_automation_audit.md for blocker groups: {automation_note}." if automation_note else ""
    if queue_rows:
        rows.append(
            workboard_row(
                5,
                "recovery",
                "work_ranked_recovery_queue",
                "ready_parallel",
                "researcher",
                queue_rows,
                import_ready,
                queue_rows - import_ready,
                first_recovery_queue_item(recovery_queue),
                "can run in parallel with calibration; do not import recovered text until staging and split preflight pass",
                "Open the 20-row R001 kickoff form, recover only importable evidence-tier text, then rerun tiered staging and split preflight.",
                "docs/recovery_batch_R001_kickoff_packet.md",
                "data/intermediate/insufficient_text_recovery_review_forms/R001/recovery_batch_R001_kickoff_packet.html",
                "/usr/bin/python3 run_recovery_review_queue.py && /usr/bin/python3 run_recovery_cached_evidence.py && /usr/bin/python3 run_recovery_tiered_stage.py && /usr/bin/python3 run_recovery_split_preflight.py --split-summary outputs/tables/enriched/recovery_batch_R001_staged_split_summary.csv && /usr/bin/python3 run_recovery_action_progress.py && /usr/bin/python3 run_recovery_kickoff_packet.py && /usr/bin/python3 run_recovery_cell_targets.py",
                f"Start from data/intermediate/insufficient_text_recovery_review_forms/R001/recovery_batch_R001_kickoff_packet.html and docs/recovery_batch_R001_kickoff_packet.md for a 20-row target-aware first session. Use data/intermediate/insufficient_text_recovery_review_forms/R001/recovery_batch_R001_action_dashboard.html, docs/recovery_batch_R001_action_packet.md, and outputs/tables/enriched/recovery_batch_R001_action_packet_index.csv for the full {queue_rows}-row queue, then use the action forms under data/intermediate/insufficient_text_recovery_review_forms/R001/actions/ plus docs/recovery_batch_R001_source_guide.md, docs/recovery_batch_R001_cached_evidence.md, docs/recovery_batch_R001_action_progress.md, and docs/recovery_cell_targets.md for row-level source routes, local-cache evidence, action-group completion status, and balanced journal-decade targeting; start with {tier1_rows} near-threshold rows, then {tier2_replace_rows} suspect replacement rows, {tier3_partial_rows} deeper partial-extension rows, {tier4_metadata_rows} manual metadata rows, and {tier5_blocked_rows} blocked-PDF metadata rows; current preflight errors: {preflight_errors}.{automation_suffix}",
            )
        )

    manual_total = numeric_metric(validation_gate, "manual_validation_total_rows", 0)
    manual_completed = numeric_metric(validation_gate, "completed_manual_labels", 0)
    manual_remaining = numeric_metric(validation_gate, "remaining_manual_labels", max(0, manual_total - manual_completed))
    if manual_total:
        ready_for_blind_review = metric_value(validation_gate, "ready_for_blind_review", "no")
        drifted_articles = numeric_metric(validation_gate, "drifted_articles", 0)
        if calibration_remaining:
            manual_status = "waiting_on_calibration"
            manual_gate_rule = "waits on calibration gate; do not assign blind main-validation batches yet"
            manual_action = "Hold the 300-row validation sample until calibration is complete and the validation gate says proceed."
            manual_note = "Do not assign main reviewer batches until calibration is complete and disagreements are resolved."
        elif ready_for_blind_review != "yes" or drifted_articles:
            manual_status = "waiting_on_sample_readiness"
            manual_gate_rule = "waits on drift-free sample readiness before assigning blind main-validation batches"
            manual_action = "Resolve sample drift or regenerate reviewer packets, then rerun readiness and gate checks."
            manual_note = "Do not assign main reviewer batches until ready_for_blind_review=yes and drifted_articles=0."
        elif manual_remaining:
            manual_status = "ready"
            manual_gate_rule = "main validation is open; complete all blind reviewer batches before using validation outputs"
            manual_action = "Open B001 from the manual validation portal, complete labels, export the batch CSV, then dry-run the label import."
            manual_note = "Calibration is complete and the sample is drift-free; start with B001 and keep exported reviewer CSVs under data/intermediate/manual_validation_batches/."
        else:
            manual_status = "complete"
            manual_gate_rule = "main validation labels are complete; rerun diagnostics and adjudication/overlap checks as needed"
            manual_action = "Rerun validation diagnostics and gate checks before using validation outputs."
            manual_note = "All main manual validation rows have labels."
        rows.append(
            workboard_row(
                6,
                "manual_validation",
                "hold_main_validation_until_calibration",
                manual_status,
                "reviewer",
                manual_total,
                manual_completed,
                manual_remaining,
                "B001",
                manual_gate_rule,
                manual_action,
                "docs/manual_validation_portal.html",
                "data/intermediate/manual_validation_forms/",
                "/usr/bin/python3 run_apply_validation_labels.py --reviewer-input data/intermediate/manual_validation_batches --dry-run",
                manual_note,
            )
        )

    if not rows:
        return pd.DataFrame(columns=WORKBOARD_COLUMNS)
    return pd.DataFrame(rows, columns=WORKBOARD_COLUMNS).sort_values(["priority", "task_id"], ascending=[True, True]).reset_index(drop=True)


def first_session_checklist(workboard: pd.DataFrame) -> list[str]:
    if workboard.empty or "first_session_action" not in workboard.columns:
        return []
    checklist: list[str] = []
    for _, row in workboard.sort_values(["priority", "task_id"]).iterrows():
        workstream = clean_text(row.get("workstream"))
        status = clean_text(row.get("status"))
        action = clean_text(row.get("first_session_action"))
        gate_rule = clean_text(row.get("gate_rule"))
        if not action:
            continue
        prefix = f"{workstream} ({status})" if status else workstream
        suffix = f" Gate: {gate_rule}." if gate_rule else ""
        checklist.append(f"- {prefix}: {action}{suffix}")
    return checklist


def write_workboard_report(path: Path, workboard: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    blocking = workboard[workboard["status"].astype(str).eq("blocking")] if not workboard.empty else pd.DataFrame()
    ready = workboard[workboard["status"].astype(str).str.contains("ready", na=False)] if not workboard.empty else pd.DataFrame()
    checklist = first_session_checklist(workboard)
    lines = [
        "# Human Review Workboard",
        "",
        "This is a generated handoff across the human-review bottlenecks. It does not change labels, scope decisions, abstracts, or final article files.",
        "",
        f"- Blocking tasks: {len(blocking)}",
        f"- Ready parallel tasks: {len(ready)}",
        "",
        "## First Session Checklist",
        "",
        "\n".join(checklist) if checklist else "- No review tasks are currently queued.",
        "",
        "## Workboard",
        "",
        df_to_markdown(workboard, max_rows=30),
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def run_human_review_workboard(
    *,
    calibration_summary_path: Path,
    calibration_kickoff_path: Path,
    calibration_guide_summary_path: Path,
    scope_completion_path: Path,
    scope_packet_path: Path,
    recovery_queue_summary_path: Path,
    recovery_queue_path: Path,
    recovery_preflight_summary_path: Path,
    recovery_automation_summary_path: Path,
    validation_gate_path: Path,
    output_path: Path,
    report_path: Path,
    recent_recovery_summary_path: Path | None = None,
    recent_recovery_packet_path: Path | None = None,
) -> pd.DataFrame:
    workboard = human_review_workboard(
        calibration_summary=read_csv_if_exists(calibration_summary_path),
        calibration_kickoff=read_csv_if_exists(calibration_kickoff_path),
        calibration_guide_summary=read_csv_if_exists(calibration_guide_summary_path),
        scope_completion=read_csv_if_exists(scope_completion_path),
        scope_packet=read_csv_if_exists(scope_packet_path),
        recovery_queue_summary=read_csv_if_exists(recovery_queue_summary_path),
        recovery_queue=read_csv_if_exists(recovery_queue_path),
        recovery_preflight_summary=read_csv_if_exists(recovery_preflight_summary_path),
        recovery_automation_summary=read_csv_if_exists(recovery_automation_summary_path),
        validation_gate=read_csv_if_exists(validation_gate_path),
        recent_recovery_summary=read_csv_if_exists(recent_recovery_summary_path) if recent_recovery_summary_path is not None else pd.DataFrame(),
        recent_recovery_packet=read_csv_if_exists(recent_recovery_packet_path) if recent_recovery_packet_path is not None else pd.DataFrame(),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    workboard.to_csv(output_path, index=False)
    write_workboard_report(report_path, workboard)
    print(f"workboard_rows={len(workboard)}")
    print(f"output={output_path}")
    print(f"report={report_path}")
    return workboard


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--calibration-summary", default="outputs/tables/enriched/manual_validation_calibration_summary.csv")
    parser.add_argument("--calibration-kickoff", default="outputs/tables/enriched/manual_validation_calibration_kickoff.csv")
    parser.add_argument("--calibration-guide-summary", default="outputs/tables/enriched/manual_validation_calibration_guide_summary.csv")
    parser.add_argument("--scope-completion", default="outputs/tables/enriched/scope_review_completion.csv")
    parser.add_argument("--scope-packet", default="data/intermediate/scope_review/scope_review_packet.csv")
    parser.add_argument("--recovery-queue-summary", default="outputs/tables/enriched/recovery_batch_R001_review_queue_summary.csv")
    parser.add_argument("--recovery-queue", default="outputs/tables/enriched/recovery_batch_R001_review_queue.csv")
    parser.add_argument("--recovery-preflight-summary", default="outputs/tables/enriched/recovery_batch_R001_preflight_summary.csv")
    parser.add_argument("--recovery-automation-summary", default="outputs/tables/enriched/recovery_automation_audit_summary.csv")
    parser.add_argument("--validation-gate", default="outputs/tables/enriched/manual_validation_gate.csv")
    parser.add_argument("--recent-recovery-summary", default="outputs/tables/enriched/recent_2023_2025_recovery_summary.csv")
    parser.add_argument("--recent-recovery-packet", default="outputs/tables/enriched/recent_2023_2025_recovery_packet.csv")
    parser.add_argument("--output", default="outputs/tables/enriched/human_review_workboard.csv")
    parser.add_argument("--report", default="docs/human_review_workboard.md")
    args = parser.parse_args()
    run_human_review_workboard(
        calibration_summary_path=Path(args.calibration_summary),
        calibration_kickoff_path=Path(args.calibration_kickoff),
        calibration_guide_summary_path=Path(args.calibration_guide_summary),
        scope_completion_path=Path(args.scope_completion),
        scope_packet_path=Path(args.scope_packet),
        recovery_queue_summary_path=Path(args.recovery_queue_summary),
        recovery_queue_path=Path(args.recovery_queue),
        recovery_preflight_summary_path=Path(args.recovery_preflight_summary),
        recovery_automation_summary_path=Path(args.recovery_automation_summary),
        validation_gate_path=Path(args.validation_gate),
        output_path=Path(args.output),
        report_path=Path(args.report),
        recent_recovery_summary_path=Path(args.recent_recovery_summary) if args.recent_recovery_summary else None,
        recent_recovery_packet_path=Path(args.recent_recovery_packet) if args.recent_recovery_packet else None,
    )


if __name__ == "__main__":
    main()
