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


CHECK_COLUMNS = ["check", "status", "observed", "required", "next_action"]
OVERVIEW_COLUMNS = ["metric", "value"]

GATE_SUFFIX = {
    "sample_readiness": "sample_readiness",
    "calibration": "calibration",
    "manual_validation": "manual_validation",
    "overlap_review": "overlap_review",
    "adjudication": "adjudication",
    "classification_recommendation": "classification_recommendation",
}


def metric_value(metrics_df: pd.DataFrame, metric: str, default: str = "") -> str:
    if metrics_df.empty or "metric" not in metrics_df.columns or "value" not in metrics_df.columns:
        return default
    matches = metrics_df[metrics_df["metric"].astype(str).eq(metric)]
    if matches.empty:
        return default
    value = clean_text(matches.iloc[0]["value"])
    return value if value != "" else default


def int_metric(metrics_df: pd.DataFrame, metric: str, default: int = 0) -> int:
    value = metric_value(metrics_df, metric, str(default))
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return default if pd.isna(parsed) else int(parsed)


def first_row_value(df: pd.DataFrame, column: str, default: str = "") -> str:
    if df.empty or column not in df.columns:
        return default
    value = clean_text(df.iloc[0].get(column, default))
    return value if value != "" else default


def completed_count(df: pd.DataFrame, column: str) -> int:
    if df.empty or column not in df.columns:
        return 0
    values = df[column].fillna("").astype(str).str.strip()
    return int(values.ne("").sum())


def gate_check(check: str, status: str, observed: Any, required: Any, next_action: str) -> dict[str, str]:
    return {
        "check": check,
        "status": status,
        "observed": clean_text(observed),
        "required": clean_text(required),
        "next_action": next_action,
    }


def sample_readiness_check(readiness: pd.DataFrame) -> dict[str, str]:
    if readiness.empty:
        return gate_check(
            "sample_readiness",
            "block",
            "missing readiness summary",
            "ready_for_blind_review=yes and drifted_articles=0",
            "Run python3 run_manual_validation_readiness.py and resolve sample drift before using validation outputs.",
        )
    ready = metric_value(readiness, "ready_for_blind_review", "no")
    drifted_articles = int_metric(readiness, "drifted_articles", 0)
    status = "pass" if ready == "yes" and drifted_articles == 0 else "block"
    action = (
        "No action needed."
        if status == "pass"
        else "Resolve sample drift or regenerate reviewer packets before assigning or importing labels."
    )
    return gate_check(
        "sample_readiness",
        status,
        f"ready_for_blind_review={ready}; drifted_articles={drifted_articles}",
        "ready_for_blind_review=yes; drifted_articles=0",
        action,
    )


def calibration_check(calibration_summary: pd.DataFrame) -> dict[str, str]:
    if calibration_summary.empty:
        return gate_check(
            "calibration",
            "block",
            "missing calibration summary",
            "calibration packet generated and completed before full-sample labeling",
            "Run python3 run_manual_validation_calibration.py, collect calibration submissions, and rerun the command.",
        )
    rows = int_metric(calibration_summary, "calibration_rows", 0)
    completed_labels = int_metric(calibration_summary, "completed_calibration_labels", 0)
    completed_rows = int_metric(calibration_summary, "completed_calibration_rows", completed_labels)
    if rows <= 0:
        return gate_check(
            "calibration",
            "block",
            f"calibration_rows={rows}; completed_calibration_rows={completed_rows}; completed_calibration_labels={completed_labels}",
            "calibration_rows>0",
            "Regenerate the calibration packet before assigning the full validation sample.",
        )
    status = "pass" if completed_rows >= rows else "block"
    action = (
        "No action needed."
        if status == "pass"
        else f"Complete the {rows}-row calibration packet before assigning the full validation sample."
    )
    return gate_check(
        "calibration",
        status,
        f"completed_calibration_rows={completed_rows}; completed_calibration_labels={completed_labels}; calibration_rows={rows}",
        f"completed_calibration_rows>={rows}",
        action,
    )


def manual_validation_check(manual_completion: pd.DataFrame, readiness: pd.DataFrame) -> dict[str, str]:
    total_rows = int_metric(manual_completion, "total_rows", int_metric(readiness, "sample_rows", 0))
    completed = int_metric(manual_completion, "completed_manual_labels", int_metric(readiness, "completed_manual_labels", 0))
    remaining = int_metric(manual_completion, "remaining_manual_labels", max(total_rows - completed, 0))
    if total_rows <= 0:
        return gate_check(
            "manual_validation",
            "block",
            "missing manual validation completion summary",
            "completed_manual_labels equals total_rows",
            "Run python3 run_apply_validation_labels.py --reviewer-input data/intermediate/manual_validation_batches --dry-run, then run the real import after errors are clear.",
        )
    status = "pass" if completed >= total_rows and remaining == 0 else "block"
    action = (
        "No action needed."
        if status == "pass"
        else "Complete and import all manual validation labels with a dry-run import before the real import."
    )
    return gate_check(
        "manual_validation",
        status,
        f"completed_manual_labels={completed}; total_rows={total_rows}; remaining_manual_labels={remaining}",
        f"completed_manual_labels={total_rows}; remaining_manual_labels=0",
        action,
    )


def overlap_check(overlap_summary: pd.DataFrame) -> dict[str, str]:
    if overlap_summary.empty:
        return gate_check(
            "overlap_review",
            "block",
            "missing overlap summary",
            "overlap packet generated and completed",
            "Run python3 run_manual_validation_overlap.py, complete the second-review packet, and rerun the command.",
        )
    rows = int_metric(overlap_summary, "overlap_rows", 0)
    completed = int_metric(overlap_summary, "completed_overlap_labels", 0)
    if rows <= 0:
        return gate_check(
            "overlap_review",
            "not_applicable",
            "overlap_rows=0",
            "overlap rows only if an overlap packet is configured",
            "No overlap packet is configured.",
        )
    status = "pass" if completed >= rows else "block"
    action = (
        "No action needed."
        if status == "pass"
        else f"Complete the {rows}-row overlap review packet and rerun python3 run_manual_validation_overlap.py."
    )
    return gate_check(
        "overlap_review",
        status,
        f"completed_overlap_labels={completed}; overlap_rows={rows}",
        f"completed_overlap_labels>={rows}",
        action,
    )


def adjudication_check(adjudication_packet: pd.DataFrame) -> dict[str, str]:
    if adjudication_packet.empty:
        return gate_check(
            "adjudication",
            "not_applicable",
            "pending_adjudication_rows=0",
            "all diagnostics disagreement rows adjudicated when present",
            "No adjudication rows are currently pending.",
        )
    rows = len(adjudication_packet)
    completed = completed_count(adjudication_packet, "adjudicated_label")
    status = "pass" if completed >= rows else "block"
    action = (
        "No action needed."
        if status == "pass"
        else "Fill adjudicated_label, adjudicator_id, and adjudication_date for pending rows, then run the adjudication dry-run and real import."
    )
    return gate_check(
        "adjudication",
        status,
        f"completed_adjudications={completed}; pending_adjudication_rows={rows}",
        f"completed_adjudications={rows}",
        action,
    )


def classification_recommendation_check(classification_recommendation: pd.DataFrame) -> dict[str, str]:
    recommendation = first_row_value(classification_recommendation, "recommendation", "missing")
    if recommendation == "proceed":
        return gate_check(
            "classification_recommendation",
            "pass",
            "recommendation=proceed",
            "recommendation=proceed",
            "No action needed.",
        )
    action = (
        "Run classification diagnostics after completing upstream validation/enrichment work and resolve any remaining pause recommendation."
        if recommendation != "missing"
        else "Run python3 run_classification_diagnostics.py to write classification_recommendation.csv."
    )
    return gate_check(
        "classification_recommendation",
        "block",
        f"recommendation={recommendation}",
        "recommendation=proceed",
        action,
    )


def validation_gate_status(
    *,
    readiness: pd.DataFrame,
    manual_completion: pd.DataFrame,
    calibration_summary: pd.DataFrame,
    overlap_summary: pd.DataFrame,
    adjudication_summary: pd.DataFrame,
    adjudication_packet: pd.DataFrame,
    classification_recommendation: pd.DataFrame,
    validation_metrics: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    checks = pd.DataFrame(
        [
            sample_readiness_check(readiness),
            calibration_check(calibration_summary),
            manual_validation_check(manual_completion, readiness),
            overlap_check(overlap_summary),
            adjudication_check(adjudication_packet),
            classification_recommendation_check(classification_recommendation),
        ],
        columns=CHECK_COLUMNS,
    )
    blockers = checks[checks["status"].eq("block")].copy()
    if blockers.empty:
        gate = "proceed"
        first_blocking_check = ""
        next_action = "Validation gate passed. Trend outputs can be used with documented caveats."
    else:
        first_blocking_check = clean_text(blockers.iloc[0]["check"])
        gate = f"blocked_{GATE_SUFFIX.get(first_blocking_check, first_blocking_check)}"
        next_action = clean_text(blockers.iloc[0]["next_action"])

    recommendation = first_row_value(classification_recommendation, "recommendation", "missing")
    validation_status = first_row_value(validation_metrics, "validation_status", "missing")
    pending_adjudication_rows = len(adjudication_packet)
    completed_adjudications = completed_count(adjudication_packet, "adjudicated_label")
    overview = pd.DataFrame(
        [
            {"metric": "validation_gate", "value": gate},
            {"metric": "first_blocking_check", "value": first_blocking_check},
            {"metric": "blocking_checks", "value": len(blockers)},
            {"metric": "next_action", "value": next_action},
            {"metric": "ready_for_blind_review", "value": metric_value(readiness, "ready_for_blind_review", "")},
            {"metric": "drifted_articles", "value": int_metric(readiness, "drifted_articles", 0)},
            {"metric": "calibration_rows", "value": int_metric(calibration_summary, "calibration_rows", 0)},
            {"metric": "completed_calibration_labels", "value": int_metric(calibration_summary, "completed_calibration_labels", 0)},
            {"metric": "completed_calibration_rows", "value": int_metric(calibration_summary, "completed_calibration_rows", int_metric(calibration_summary, "completed_calibration_labels", 0))},
            {"metric": "manual_validation_total_rows", "value": int_metric(manual_completion, "total_rows", int_metric(readiness, "sample_rows", 0))},
            {"metric": "completed_manual_labels", "value": int_metric(manual_completion, "completed_manual_labels", int_metric(readiness, "completed_manual_labels", 0))},
            {"metric": "remaining_manual_labels", "value": int_metric(manual_completion, "remaining_manual_labels", int_metric(readiness, "remaining_manual_labels", 0))},
            {"metric": "overlap_rows", "value": int_metric(overlap_summary, "overlap_rows", 0)},
            {"metric": "completed_overlap_labels", "value": int_metric(overlap_summary, "completed_overlap_labels", 0)},
            {"metric": "pending_adjudication_rows", "value": pending_adjudication_rows},
            {"metric": "completed_adjudications", "value": completed_adjudications},
            {"metric": "classification_recommendation", "value": recommendation},
            {"metric": "validation_status", "value": validation_status},
        ],
        columns=OVERVIEW_COLUMNS,
    )
    return overview, checks


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


def write_validation_gate_report(path: Path, overview: pd.DataFrame, checks: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lookup = dict(zip(overview["metric"].astype(str), overview["value"]))
    lines = [
        "# Manual Validation Gate",
        "",
        f"- Gate: `{lookup.get('validation_gate', '')}`",
        f"- First blocking check: `{lookup.get('first_blocking_check', '')}`",
        f"- Blocking checks: {lookup.get('blocking_checks', 0)}",
        f"- Next action: {lookup.get('next_action', '')}",
        "",
        "This gate is the project stoplight for using classification trend outputs as evidence. A descriptive trend report can exist while this gate is blocked, but it should not be treated as final analysis.",
        "",
        "## Overview",
        "",
        df_to_markdown(overview),
        "",
        "## Checks",
        "",
        df_to_markdown(checks),
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("") if path.exists() else pd.DataFrame()


def run_validation_gate(
    *,
    readiness_path: Path,
    manual_completion_path: Path,
    calibration_summary_path: Path,
    overlap_summary_path: Path,
    adjudication_summary_path: Path,
    adjudication_packet_path: Path,
    classification_recommendation_path: Path,
    validation_metrics_path: Path,
    output_overview: Path,
    output_checks: Path,
    report_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    overview, checks = validation_gate_status(
        readiness=read_csv_if_exists(readiness_path),
        manual_completion=read_csv_if_exists(manual_completion_path),
        calibration_summary=read_csv_if_exists(calibration_summary_path),
        overlap_summary=read_csv_if_exists(overlap_summary_path),
        adjudication_summary=read_csv_if_exists(adjudication_summary_path),
        adjudication_packet=read_csv_if_exists(adjudication_packet_path),
        classification_recommendation=read_csv_if_exists(classification_recommendation_path),
        validation_metrics=read_csv_if_exists(validation_metrics_path),
    )
    output_overview.parent.mkdir(parents=True, exist_ok=True)
    output_checks.parent.mkdir(parents=True, exist_ok=True)
    overview.to_csv(output_overview, index=False)
    checks.to_csv(output_checks, index=False)
    write_validation_gate_report(report_path, overview, checks)
    lookup = dict(zip(overview["metric"].astype(str), overview["value"]))
    print(f"validation_gate={lookup.get('validation_gate', '')}")
    print(f"first_blocking_check={lookup.get('first_blocking_check', '')}")
    print(f"next_action={lookup.get('next_action', '')}")
    print(f"report={report_path}")
    return overview, checks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--readiness", default="outputs/tables/enriched/manual_validation_readiness.csv")
    parser.add_argument("--manual-completion", default="outputs/tables/enriched/manual_validation_completion.csv")
    parser.add_argument("--calibration-summary", default="outputs/tables/enriched/manual_validation_calibration_summary.csv")
    parser.add_argument("--overlap-summary", default="outputs/tables/enriched/manual_validation_overlap_summary.csv")
    parser.add_argument("--adjudication-summary", default="outputs/tables/enriched/manual_validation_adjudication_completion.csv")
    parser.add_argument("--adjudication-packet", default="outputs/tables/enriched/validation_adjudication_packet.csv")
    parser.add_argument("--classification-recommendation", default="outputs/tables/enriched/classification_recommendation.csv")
    parser.add_argument("--validation-metrics", default="outputs/tables/enriched/validation_metrics.csv")
    parser.add_argument("--output-overview", default="outputs/tables/enriched/manual_validation_gate.csv")
    parser.add_argument("--output-checks", default="outputs/tables/enriched/manual_validation_gate_checks.csv")
    parser.add_argument("--report", default="docs/manual_validation_gate.md")
    args = parser.parse_args()
    run_validation_gate(
        readiness_path=Path(args.readiness),
        manual_completion_path=Path(args.manual_completion),
        calibration_summary_path=Path(args.calibration_summary),
        overlap_summary_path=Path(args.overlap_summary),
        adjudication_summary_path=Path(args.adjudication_summary),
        adjudication_packet_path=Path(args.adjudication_packet),
        classification_recommendation_path=Path(args.classification_recommendation),
        validation_metrics_path=Path(args.validation_metrics),
        output_overview=Path(args.output_overview),
        output_checks=Path(args.output_checks),
        report_path=Path(args.report),
    )


if __name__ == "__main__":
    main()
