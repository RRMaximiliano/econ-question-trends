from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT / "code" / "04_classify"))

from validation_sample import merge_manual_labels, validation_batch_completion_summary, write_validation_status_report  # noqa: E402


def read_reviewer_input(path: Path) -> pd.DataFrame:
    if path.is_dir():
        files = sorted(item for item in path.glob("*.csv") if item.is_file())
        if not files:
            raise SystemExit(f"No CSV reviewer batch files found in {path}")
        frames = [pd.read_csv(file, dtype=str).fillna("") for file in files]
        return pd.concat(frames, ignore_index=True)
    return pd.read_csv(path, dtype=str).fillna("")


def apply_validation_labels(
    *,
    sample_path: Path,
    reviewer_input: Path,
    output_path: Path,
    error_output: Path,
    summary_output: Path,
    batch_summary_output: Path,
    report_path: Path,
    dry_run: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    sample = pd.read_csv(sample_path, dtype=str).fillna("")
    reviewer = read_reviewer_input(reviewer_input)
    merged, errors, summary = merge_manual_labels(sample, reviewer)
    batch_summary = validation_batch_completion_summary(reviewer)

    error_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    batch_summary_output.parent.mkdir(parents=True, exist_ok=True)
    errors.to_csv(error_output, index=False)
    summary.to_csv(summary_output, index=False)
    batch_summary.to_csv(batch_summary_output, index=False)
    report_title = "Manual Validation Dry-Run Status" if dry_run else "Manual Validation Status"
    write_validation_status_report(report_path, summary, errors, batch_summary, title=report_title)

    if errors.empty and not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        merged.to_csv(output_path, index=False)
    return errors, summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", default="data/intermediate/manual_validation_sample.csv")
    parser.add_argument("--reviewer-input", default="data/intermediate/manual_validation_review_packet.csv")
    parser.add_argument("--output", default="data/intermediate/manual_validation_sample.csv")
    parser.add_argument("--error-output", default="outputs/tables/enriched/manual_validation_import_errors.csv")
    parser.add_argument("--summary-output", default="outputs/tables/enriched/manual_validation_completion.csv")
    parser.add_argument("--batch-summary-output", default="outputs/tables/enriched/manual_validation_batch_completion.csv")
    parser.add_argument("--report", default="docs/manual_validation_status.md")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        if args.error_output == parser.get_default("error_output"):
            args.error_output = "outputs/tables/enriched/manual_validation_dry_run_errors.csv"
        if args.summary_output == parser.get_default("summary_output"):
            args.summary_output = "outputs/tables/enriched/manual_validation_dry_run_completion.csv"
        if args.batch_summary_output == parser.get_default("batch_summary_output"):
            args.batch_summary_output = "outputs/tables/enriched/manual_validation_dry_run_batch_completion.csv"
        if args.report == parser.get_default("report"):
            args.report = "docs/manual_validation_dry_run_status.md"

    errors, summary = apply_validation_labels(
        sample_path=Path(args.sample),
        reviewer_input=Path(args.reviewer_input),
        output_path=Path(args.output),
        error_output=Path(args.error_output),
        summary_output=Path(args.summary_output),
        batch_summary_output=Path(args.batch_summary_output),
        report_path=Path(args.report),
        dry_run=args.dry_run,
    )

    if not errors.empty:
        print(f"validation_import_errors={len(errors)}")
        print(f"error_output={args.error_output}")
        raise SystemExit(1)

    labeled = int(summary.loc[summary["metric"].eq("completed_manual_labels"), "value"].iloc[0])
    remaining = int(summary.loc[summary["metric"].eq("remaining_manual_labels"), "value"].iloc[0])
    print(f"completed_manual_labels={labeled}")
    print(f"remaining_manual_labels={remaining}")
    print(f"dry_run={str(args.dry_run).lower()}")
    print(f"output={'not_written_dry_run' if args.dry_run else args.output}")
    print(f"batch_summary_output={args.batch_summary_output}")
    print(f"report={args.report}")


if __name__ == "__main__":
    main()
