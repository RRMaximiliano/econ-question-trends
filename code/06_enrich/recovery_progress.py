from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "lib"))

from econqt_common import clean_text  # noqa: E402


OVERVIEW_COLUMNS = ["metric", "value"]


def numeric_column(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(0, index=df.index, dtype="int64")
    return pd.to_numeric(df[column], errors="coerce").fillna(0).astype(int)


def metric_value(metrics_df: pd.DataFrame, metric: str, default: str = "0") -> str:
    if metrics_df.empty or "metric" not in metrics_df.columns or "value" not in metrics_df.columns:
        return default
    matches = metrics_df[metrics_df["metric"].astype(str).eq(metric)]
    if matches.empty:
        return default
    return clean_text(matches.iloc[0]["value"]) or default


def batch_from_import_source(value: Any) -> str:
    text = clean_text(value)
    match = re.search(r"insufficient_text_recovery_batch_(R\d{3})(?:_[A-Za-z0-9_]+)?\.csv", text)
    return match.group(1) if match else ""


def history_counts_by_batch(history_df: pd.DataFrame, count_column: str) -> pd.DataFrame:
    if history_df.empty or "import_source_file" not in history_df.columns:
        return pd.DataFrame(columns=["recovery_batch", count_column])
    work = history_df.copy().fillna("")
    work["recovery_batch"] = work["import_source_file"].map(batch_from_import_source)
    work = work[work["recovery_batch"].astype(str).str.strip().ne("")]
    if work.empty:
        return pd.DataFrame(columns=["recovery_batch", count_column])
    return work.groupby("recovery_batch", dropna=False).size().reset_index(name=count_column)


def recovery_progress_by_batch(
    batch_summary: pd.DataFrame,
    imported_history: pd.DataFrame,
    error_history: pd.DataFrame,
) -> pd.DataFrame:
    if batch_summary.empty:
        return pd.DataFrame()
    out = batch_summary.copy().fillna("")
    imported_counts = history_counts_by_batch(imported_history, "history_imported_rows")
    error_counts = history_counts_by_batch(error_history, "history_error_rows")
    out = out.merge(imported_counts, on="recovery_batch", how="left").merge(error_counts, on="recovery_batch", how="left")
    out["history_imported_rows"] = numeric_column(out, "history_imported_rows")
    out["history_error_rows"] = numeric_column(out, "history_error_rows")
    total = numeric_column(out, "total_rows")
    completed = numeric_column(out, "completed_backfill_abstracts")
    out["completed_backfill_share"] = [
        round(done / rows, 6) if rows else 0.0
        for done, rows in zip(completed.tolist(), total.tolist())
    ]
    return out


def recovery_progress_overview(
    batch_progress: pd.DataFrame,
    imported_history: pd.DataFrame,
    error_history: pd.DataFrame,
    validation_completion: pd.DataFrame,
    recommendation: pd.DataFrame,
    recovery_queue: pd.DataFrame | None = None,
) -> pd.DataFrame:
    live_queue = recovery_queue.copy().fillna("") if recovery_queue is not None and not recovery_queue.empty else pd.DataFrame()
    current_packet_completed = int(numeric_column(batch_progress, "completed_backfill_abstracts").sum()) if not batch_progress.empty else 0
    cumulative_imported = len(imported_history)
    completed_backfills = max(current_packet_completed, cumulative_imported)
    if not live_queue.empty:
        current_queue_rows = len(live_queue)
        remaining_backfills = current_queue_rows
        if "recovery_batch" in live_queue.columns:
            recovery_batches = int(live_queue["recovery_batch"].astype(str).str.strip().replace("", pd.NA).dropna().nunique())
            open_batches = live_queue[live_queue["recovery_batch"].astype(str).str.strip().ne("")]
            next_batch = clean_text(open_batches.iloc[0]["recovery_batch"]) if not open_batches.empty else ""
            next_batch_remaining = str(int((live_queue["recovery_batch"].astype(str) == next_batch).sum())) if next_batch else "0"
        else:
            recovery_batches = int(len(batch_progress))
            next_batch = ""
            next_batch_remaining = "0"
    else:
        current_queue_rows = int(numeric_column(batch_progress, "total_rows").sum()) if not batch_progress.empty else 0
        remaining_backfills = int(numeric_column(batch_progress, "remaining_backfill_abstracts").sum()) if not batch_progress.empty else 0
        recovery_batches = int(len(batch_progress))
        open_batches = batch_progress[numeric_column(batch_progress, "remaining_backfill_abstracts") > 0] if not batch_progress.empty else pd.DataFrame()
        next_batch = clean_text(open_batches.iloc[0]["recovery_batch"]) if not open_batches.empty and "recovery_batch" in open_batches.columns else ""
        next_batch_remaining = (
            clean_text(open_batches.iloc[0]["remaining_backfill_abstracts"])
            if not open_batches.empty and "remaining_backfill_abstracts" in open_batches.columns
            else "0"
        )
    total_rows = remaining_backfills + completed_backfills
    recommendation_row = recommendation.iloc[0].to_dict() if not recommendation.empty else {}
    rows = [
        {"metric": "recovery_batches", "value": recovery_batches},
        {"metric": "recovery_rows", "value": total_rows},
        {"metric": "current_recovery_queue_rows", "value": current_queue_rows},
        {"metric": "completed_backfill_abstracts", "value": completed_backfills},
        {"metric": "current_packet_completed_backfill_abstracts", "value": current_packet_completed},
        {"metric": "cumulative_imported_recovery_rows", "value": cumulative_imported},
        {"metric": "remaining_backfill_abstracts", "value": remaining_backfills},
        {"metric": "next_recovery_batch", "value": next_batch},
        {"metric": "next_recovery_batch_remaining", "value": next_batch_remaining},
        {"metric": "import_history_rows", "value": len(imported_history)},
        {"metric": "import_error_history_rows", "value": len(error_history)},
        {"metric": "manual_validation_total_rows", "value": metric_value(validation_completion, "total_rows")},
        {"metric": "completed_manual_labels", "value": metric_value(validation_completion, "completed_manual_labels")},
        {"metric": "remaining_manual_labels", "value": metric_value(validation_completion, "remaining_manual_labels")},
        {"metric": "classification_recommendation", "value": clean_text(recommendation_row.get("recommendation", ""))},
        {"metric": "insufficient_text_share", "value": clean_text(recommendation_row.get("insufficient_text_share", ""))},
    ]
    return pd.DataFrame(rows, columns=OVERVIEW_COLUMNS)


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


def write_recovery_progress_report(
    path: Path,
    *,
    overview: pd.DataFrame,
    batch_progress: pd.DataFrame,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    overview_lookup = {row["metric"]: row["value"] for _, row in overview.iterrows()}
    lines = [
        "# Recovery Progress Status",
        "",
        f"- Classification recommendation: `{overview_lookup.get('classification_recommendation', '')}`",
        f"- Remaining insufficient-text recovery rows: {overview_lookup.get('remaining_backfill_abstracts', '0')}",
        f"- Completed recovery abstracts: {overview_lookup.get('completed_backfill_abstracts', '0')}",
        f"- Completed manual validation labels: {overview_lookup.get('completed_manual_labels', '0')}",
        f"- Remaining manual validation labels: {overview_lookup.get('remaining_manual_labels', '0')}",
        f"- Next recovery batch: `{overview_lookup.get('next_recovery_batch', '')}`",
        "",
        "## Overview",
        "",
        df_to_markdown(overview),
        "",
        "## Recovery Batches",
        "",
        df_to_markdown(batch_progress, max_rows=40),
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("") if path.exists() else pd.DataFrame()


def run_recovery_progress(
    *,
    batch_summary_path: Path,
    imported_history_path: Path,
    error_history_path: Path,
    validation_completion_path: Path,
    recommendation_path: Path,
    recovery_queue_path: Path | None = None,
    output_overview: Path,
    output_batches: Path,
    report_path: Path,
) -> None:
    batch_summary = read_csv_if_exists(batch_summary_path)
    imported_history = read_csv_if_exists(imported_history_path)
    error_history = read_csv_if_exists(error_history_path)
    validation_completion = read_csv_if_exists(validation_completion_path)
    recommendation = read_csv_if_exists(recommendation_path)
    recovery_queue = read_csv_if_exists(recovery_queue_path) if recovery_queue_path is not None else pd.DataFrame()
    batch_progress = recovery_progress_by_batch(batch_summary, imported_history, error_history)
    overview = recovery_progress_overview(
        batch_progress,
        imported_history,
        error_history,
        validation_completion,
        recommendation,
        recovery_queue=recovery_queue,
    )

    for path, frame in [(output_overview, overview), (output_batches, batch_progress)]:
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)
    write_recovery_progress_report(report_path, overview=overview, batch_progress=batch_progress)
    print(f"overview={output_overview}")
    print(f"batches={output_batches}")
    print(f"report={report_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-summary", default="outputs/tables/enriched/insufficient_text_recovery_batch_summary.csv")
    parser.add_argument("--imported-history", default="data/intermediate/abstract_backfill_import_history.csv")
    parser.add_argument("--error-history", default="data/intermediate/abstract_backfill_import_error_history.csv")
    parser.add_argument("--validation-completion", default="outputs/tables/enriched/manual_validation_completion.csv")
    parser.add_argument("--recommendation", default="outputs/tables/enriched/classification_recommendation.csv")
    parser.add_argument("--recovery-queue", default="outputs/tables/enriched/insufficient_text_recovery_queue.csv")
    parser.add_argument("--output-overview", default="outputs/tables/enriched/recovery_progress_overview.csv")
    parser.add_argument("--output-batches", default="outputs/tables/enriched/recovery_progress_by_batch.csv")
    parser.add_argument("--report", default="docs/recovery_progress_status.md")
    args = parser.parse_args()
    run_recovery_progress(
        batch_summary_path=Path(args.batch_summary),
        imported_history_path=Path(args.imported_history),
        error_history_path=Path(args.error_history),
        validation_completion_path=Path(args.validation_completion),
        recommendation_path=Path(args.recommendation),
        recovery_queue_path=Path(args.recovery_queue),
        output_overview=Path(args.output_overview),
        output_batches=Path(args.output_batches),
        report_path=Path(args.report),
    )


if __name__ == "__main__":
    main()
