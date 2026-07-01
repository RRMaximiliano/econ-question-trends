from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT / "code" / "04_classify"))

from validation_sample import (  # noqa: E402
    VALIDATION_ERROR_COLUMNS,
    completed_manual_label_count,
    make_overlap_packet,
    overlap_agreement_summary,
    overlap_disagreement_packet,
    validate_manual_label_values,
    write_reviewer_html_forms,
)


OVERLAP_KEY_COLUMNS = ["overlap_id", "validation_id", "article_id"]


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


def overlap_packet_key(df: pd.DataFrame) -> pd.Series:
    work = df.copy().fillna("")
    return work["validation_id"].astype(str).str.strip() + "|" + work["article_id"].astype(str).str.strip()


def overlap_packet_identity_errors(sample: pd.DataFrame, packet: pd.DataFrame, *, expected_rows: int) -> pd.DataFrame:
    sample_work = sample.copy().fillna("")
    packet_work = packet.copy().fillna("")
    errors: list[dict[str, object]] = []

    missing_packet_columns = [column for column in OVERLAP_KEY_COLUMNS if column not in packet_work.columns]
    for column in missing_packet_columns:
        errors.append(
            {
                "validation_id": "",
                "article_id": "",
                "row_number": 0,
                "field": column,
                "value": "",
                "error": "missing_overlap_packet_key_column",
            }
        )
    missing_sample_columns = [column for column in ["validation_id", "article_id"] if column not in sample_work.columns]
    for column in missing_sample_columns:
        errors.append(
            {
                "validation_id": "",
                "article_id": "",
                "row_number": 0,
                "field": column,
                "value": "",
                "error": "missing_sample_key_column",
            }
        )
    if missing_packet_columns or missing_sample_columns:
        return pd.DataFrame(errors, columns=VALIDATION_ERROR_COLUMNS)

    if len(packet_work) != expected_rows:
        errors.append(
            {
                "validation_id": "",
                "article_id": "",
                "row_number": 0,
                "field": "overlap_rows",
                "value": str(len(packet_work)),
                "error": "overlap_packet_row_count_mismatch",
            }
        )

    sample_keys = set(overlap_packet_key(sample_work))
    packet_keys = overlap_packet_key(packet_work)
    overlap_ids = packet_work["overlap_id"].astype(str).str.strip()

    duplicate_overlap_mask = overlap_ids.ne("") & overlap_ids.duplicated(keep=False)
    duplicate_key_mask = packet_keys.ne("|") & packet_keys.duplicated(keep=False)
    unknown_mask = ~packet_keys.isin(sample_keys)
    missing_overlap_id_mask = overlap_ids.eq("")

    for idx, row in packet_work.iterrows():
        validation_id = row.get("validation_id", "")
        article_id = row.get("article_id", "")
        row_number = idx + 2
        if missing_overlap_id_mask.loc[idx]:
            errors.append(
                {
                    "validation_id": validation_id,
                    "article_id": article_id,
                    "row_number": row_number,
                    "field": "overlap_id",
                    "value": "",
                    "error": "missing_overlap_id",
                }
            )
        if duplicate_overlap_mask.loc[idx]:
            errors.append(
                {
                    "validation_id": validation_id,
                    "article_id": article_id,
                    "row_number": row_number,
                    "field": "overlap_id",
                    "value": overlap_ids.loc[idx],
                    "error": "duplicate_overlap_id",
                }
            )
        if duplicate_key_mask.loc[idx]:
            errors.append(
                {
                    "validation_id": validation_id,
                    "article_id": article_id,
                    "row_number": row_number,
                    "field": "validation_id|article_id",
                    "value": packet_keys.loc[idx],
                    "error": "duplicate_overlap_sample_row",
                }
            )
        if unknown_mask.loc[idx]:
            errors.append(
                {
                    "validation_id": validation_id,
                    "article_id": article_id,
                    "row_number": row_number,
                    "field": "validation_id|article_id",
                    "value": packet_keys.loc[idx],
                    "error": "overlap_row_not_in_sample",
                }
            )

    return pd.DataFrame(errors, columns=VALIDATION_ERROR_COLUMNS)


def write_overlap_report(
    path: Path,
    summary: pd.DataFrame,
    disagreements: pd.DataFrame,
    errors: pd.DataFrame,
    *,
    packet_path: str,
    html_dir: str,
) -> None:
    lookup = dict(zip(summary["metric"].astype(str), summary["value"])) if not summary.empty else {}
    lines = [
        "# Manual Validation Overlap QA",
        "",
        f"- Overlap packet: `{packet_path}`",
        f"- Browser forms: `{html_dir}`",
        f"- Overlap rows: {lookup.get('overlap_rows', 0)}",
        f"- Completed overlap labels: {lookup.get('completed_overlap_labels', 0)}",
        f"- Comparable overlap labels: {lookup.get('comparable_overlap_labels', 0)}",
        f"- Overlap disagreements: {lookup.get('overlap_disagreements', 0)}",
        f"- Agreement rate: `{lookup.get('overlap_agreement_rate', '')}`",
        "",
        "The overlap packet is validated against the current manual validation sample. Stale rows, duplicate overlap IDs, duplicate sample rows, and row-count drift are reported as import errors before agreement metrics are trusted.",
        "",
        "## Summary",
        "",
        markdown_table(summary),
        "",
        "## Import Errors",
        "",
        markdown_table(errors),
        "",
        "## Disagreements For Adjudication",
        "",
        markdown_table(disagreements),
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", default="data/intermediate/manual_validation_sample.csv")
    parser.add_argument("--packet-output", default="data/intermediate/manual_validation_overlap/manual_validation_overlap_packet.csv")
    parser.add_argument("--html-dir", default="data/intermediate/manual_validation_overlap_forms")
    parser.add_argument("--sample-size", type=int, default=30)
    parser.add_argument("--seed", type=int, default=20260629)
    parser.add_argument("--regenerate", action="store_true")
    parser.add_argument("--overwrite-labeled", action="store_true")
    parser.add_argument("--summary-output", default="outputs/tables/enriched/manual_validation_overlap_summary.csv")
    parser.add_argument("--disagreement-output", default="outputs/tables/enriched/manual_validation_overlap_disagreements.csv")
    parser.add_argument("--error-output", default="outputs/tables/enriched/manual_validation_overlap_errors.csv")
    parser.add_argument("--report", default="docs/manual_validation_overlap.md")
    args = parser.parse_args()

    sample = pd.read_csv(args.sample, dtype=str).fillna("")
    packet_path = Path(args.packet_output)
    should_create_packet = args.regenerate or not packet_path.exists()
    if should_create_packet:
        completed_existing = completed_manual_label_count(packet_path)
        if completed_existing and not args.overwrite_labeled:
            raise SystemExit(
                f"Refusing to overwrite {packet_path}: {completed_existing} completed overlap labels found. "
                "Use --overwrite-labeled only after exporting/backing up existing labels."
            )
        packet = make_overlap_packet(sample, args.sample_size, args.seed)
        packet_path.parent.mkdir(parents=True, exist_ok=True)
        packet.to_csv(packet_path, index=False)
    else:
        packet = pd.read_csv(packet_path, dtype=str).fillna("")

    write_reviewer_html_forms(packet, Path(args.html_dir), batch_size=args.sample_size)
    errors = pd.concat(
        [
            validate_manual_label_values(packet),
            overlap_packet_identity_errors(sample, packet, expected_rows=args.sample_size),
        ],
        ignore_index=True,
    ).reindex(columns=VALIDATION_ERROR_COLUMNS)
    summary = overlap_agreement_summary(sample, packet)
    disagreements = overlap_disagreement_packet(sample, packet)

    Path(args.summary_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.disagreement_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.error_output).parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.summary_output, index=False)
    disagreements.to_csv(args.disagreement_output, index=False)
    errors.to_csv(args.error_output, index=False)
    write_overlap_report(
        Path(args.report),
        summary,
        disagreements,
        errors,
        packet_path=args.packet_output,
        html_dir=args.html_dir,
    )

    lookup = dict(zip(summary["metric"].astype(str), summary["value"]))
    print(f"overlap_rows={lookup.get('overlap_rows', 0)}")
    print(f"completed_overlap_labels={lookup.get('completed_overlap_labels', 0)}")
    print(f"comparable_overlap_labels={lookup.get('comparable_overlap_labels', 0)}")
    print(f"overlap_disagreements={lookup.get('overlap_disagreements', 0)}")
    print(f"report={args.report}")

    if not errors.empty:
        print(f"overlap_import_errors={len(errors)}")
        print(f"error_output={args.error_output}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
