from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT / "code" / "04_classify"))

from validation_sample import ALLOWED_MANUAL_LABELS, VALIDATION_ERROR_COLUMNS, validation_row_key  # noqa: E402


ADJUDICATION_COLUMNS = ["adjudicated_label", "adjudication_notes", "adjudicator_id", "adjudication_date"]
ADJUDICATION_CONTEXT_COLUMN_SETS = [
    ("manual_label", "predicted_label"),
    ("primary_manual_label", "overlap_manual_label"),
]


def adjudication_completion_summary(sample_df: pd.DataFrame) -> pd.DataFrame:
    work = sample_df.copy().fillna("")
    if "adjudicated_label" not in work.columns:
        work["adjudicated_label"] = ""
    completed = work["adjudicated_label"].astype(str).str.strip().ne("")
    rows: list[dict[str, Any]] = [
        {"metric": "total_rows", "value": len(work)},
        {"metric": "completed_adjudications", "value": int(completed.sum())},
        {"metric": "remaining_unadjudicated_rows", "value": int((~completed).sum())},
    ]
    for label in ALLOWED_MANUAL_LABELS:
        rows.append({"metric": f"adjudicated_label_{label}", "value": int(work.loc[completed, "adjudicated_label"].astype(str).eq(label).sum())})
    return pd.DataFrame(rows, columns=["metric", "value"])


def validate_adjudication_values(adjudication_df: pd.DataFrame, sample_df: pd.DataFrame) -> pd.DataFrame:
    packet = adjudication_df.copy().fillna("")
    sample = sample_df.copy().fillna("")
    output_columns = VALIDATION_ERROR_COLUMNS
    if packet.empty:
        return pd.DataFrame(columns=output_columns)
    for column in ["validation_id", "article_id", *ADJUDICATION_COLUMNS]:
        if column not in packet.columns:
            packet[column] = ""
    errors: list[dict[str, Any]] = []
    sample_keys = set(validation_row_key(sample))
    packet_keys = validation_row_key(packet)
    duplicate_mask = packet_keys.duplicated(keep=False) & packet["adjudicated_label"].astype(str).str.strip().ne("")
    unknown_mask = ~packet_keys.isin(sample_keys)

    for idx, row in packet.iterrows():
        label = str(row.get("adjudicated_label", "")).strip()
        notes = str(row.get("adjudication_notes", "")).strip()
        date = str(row.get("adjudication_date", "")).strip()
        adjudicator = str(row.get("adjudicator_id", "")).strip()
        base = {
            "validation_id": row.get("validation_id", ""),
            "article_id": row.get("article_id", ""),
            "row_number": idx + 2,
        }
        if not label:
            continue
        if duplicate_mask.loc[idx]:
            errors.append({**base, "field": "validation_id|article_id", "value": packet_keys.loc[idx], "error": "duplicate_adjudication_row"})
        if unknown_mask.loc[idx]:
            errors.append({**base, "field": "validation_id|article_id", "value": packet_keys.loc[idx], "error": "adjudication_row_not_in_sample"})
        if label not in ALLOWED_MANUAL_LABELS:
            errors.append({**base, "field": "adjudicated_label", "value": label, "error": "invalid_adjudicated_label"})
        has_context = any(all(str(row.get(column, "")).strip() for column in columns) for columns in ADJUDICATION_CONTEXT_COLUMN_SETS)
        if not has_context:
            errors.append({**base, "field": "manual_label|predicted_label", "value": "", "error": "missing_adjudication_context"})
        if not notes:
            errors.append({**base, "field": "adjudication_notes", "value": notes, "error": "missing_adjudication_notes"})
        if not adjudicator:
            errors.append({**base, "field": "adjudicator_id", "value": adjudicator, "error": "missing_adjudicator_id"})
        if not date:
            errors.append({**base, "field": "adjudication_date", "value": date, "error": "missing_adjudication_date"})
        elif re.match(r"^\d{4}-\d{2}-\d{2}$", date) is None:
            errors.append({**base, "field": "adjudication_date", "value": date, "error": "adjudication_date_must_be_iso_yyyy_mm_dd"})
    return pd.DataFrame(errors, columns=output_columns)


def merge_adjudication_labels(sample_df: pd.DataFrame, adjudication_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    sample = sample_df.copy().fillna("")
    packet = adjudication_df.copy().fillna("")
    for column in ADJUDICATION_COLUMNS:
        if column not in sample.columns:
            sample[column] = ""
        if column not in packet.columns:
            packet[column] = ""
    if packet.empty:
        return sample, pd.DataFrame(columns=VALIDATION_ERROR_COLUMNS), adjudication_completion_summary(sample)

    errors = validate_adjudication_values(packet, sample)
    if not errors.empty:
        return sample, errors.reset_index(drop=True), adjudication_completion_summary(sample)

    sample_keys = validation_row_key(sample)
    packet = packet[packet["adjudicated_label"].astype(str).str.strip().ne("")].copy()
    packet_lookup = packet.assign(_validation_key=validation_row_key(packet)).set_index("_validation_key", drop=False)
    merged = sample.copy()
    for idx, key in sample_keys.items():
        if key not in packet_lookup.index:
            continue
        row = packet_lookup.loc[key]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        for column in ADJUDICATION_COLUMNS:
            merged.at[idx, column] = str(row.get(column, "")).strip()
    return merged, pd.DataFrame(columns=VALIDATION_ERROR_COLUMNS), adjudication_completion_summary(merged)


def markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No rows._"
    shown = df.fillna("").astype(str)
    headers = list(shown.columns)
    rows = [headers] + shown.values.tolist()
    widths = [max(len(row[i]) for row in rows) for i in range(len(headers))]
    header = "| " + " | ".join(headers[i].ljust(widths[i]) for i in range(len(headers))) + " |"
    sep = "| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |"
    body = ["| " + " | ".join(row[i].ljust(widths[i]) for i in range(len(headers))) + " |" for row in rows[1:]]
    return "\n".join([header, sep] + body)


def write_adjudication_status_report(path: Path, summary: pd.DataFrame, errors: pd.DataFrame, *, dry_run: bool = False) -> None:
    title = "Manual Validation Adjudication Dry-Run Status" if dry_run else "Manual Validation Adjudication Status"
    lines = [
        f"# {title}",
        "",
        "Completed adjudication rows must include a valid `adjudicated_label`, adjudication notes, adjudicator ID, ISO adjudication date, and disagreement context from either diagnostics (`manual_label` plus `predicted_label`) or overlap QA (`primary_manual_label` plus `overlap_manual_label`).",
        "",
        "## Completion",
        "",
        markdown_table(summary),
        "",
        "## Import Errors",
        "",
        markdown_table(errors),
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def apply_adjudication_labels(
    *,
    sample_path: Path,
    adjudication_input: Path,
    output_path: Path,
    error_output: Path,
    summary_output: Path,
    report_path: Path,
    dry_run: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    sample = pd.read_csv(sample_path, dtype=str).fillna("")
    adjudication = pd.read_csv(adjudication_input, dtype=str).fillna("") if adjudication_input.exists() else pd.DataFrame()
    merged, errors, summary = merge_adjudication_labels(sample, adjudication)
    error_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    errors.to_csv(error_output, index=False)
    summary.to_csv(summary_output, index=False)
    write_adjudication_status_report(report_path, summary, errors, dry_run=dry_run)
    if errors.empty and not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        merged.to_csv(output_path, index=False)
    return errors, summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", default="data/intermediate/manual_validation_sample.csv")
    parser.add_argument("--adjudication-input", default="outputs/tables/enriched/validation_adjudication_packet.csv")
    parser.add_argument("--output", default="data/intermediate/manual_validation_sample.csv")
    parser.add_argument("--error-output", default="outputs/tables/enriched/manual_validation_adjudication_errors.csv")
    parser.add_argument("--summary-output", default="outputs/tables/enriched/manual_validation_adjudication_completion.csv")
    parser.add_argument("--report", default="docs/manual_validation_adjudication_status.md")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        if args.error_output == parser.get_default("error_output"):
            args.error_output = "outputs/tables/enriched/manual_validation_adjudication_dry_run_errors.csv"
        if args.summary_output == parser.get_default("summary_output"):
            args.summary_output = "outputs/tables/enriched/manual_validation_adjudication_dry_run_completion.csv"
        if args.report == parser.get_default("report"):
            args.report = "docs/manual_validation_adjudication_dry_run_status.md"

    errors, summary = apply_adjudication_labels(
        sample_path=Path(args.sample),
        adjudication_input=Path(args.adjudication_input),
        output_path=Path(args.output),
        error_output=Path(args.error_output),
        summary_output=Path(args.summary_output),
        report_path=Path(args.report),
        dry_run=args.dry_run,
    )

    if not errors.empty:
        print(f"adjudication_import_errors={len(errors)}")
        print(f"error_output={args.error_output}")
        raise SystemExit(1)

    lookup = dict(zip(summary["metric"].astype(str), summary["value"]))
    print(f"completed_adjudications={lookup.get('completed_adjudications', 0)}")
    print(f"dry_run={str(args.dry_run).lower()}")
    print(f"output={'not_written_dry_run' if args.dry_run else args.output}")
    print(f"report={args.report}")


if __name__ == "__main__":
    main()
