from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT / "code" / "04_classify"))

from validation_sample import (  # noqa: E402
    manual_validation_readiness_summary,
    validation_batch_completion_summary,
    validation_sample_drift,
    write_manual_validation_portal,
    write_manual_validation_readiness_report,
)


def read_optional_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def read_reviewer_batches(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    if path.is_dir():
        frames = [pd.read_csv(file, dtype=str).fillna("") for file in sorted(path.glob("*.csv")) if file.is_file()]
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", default="data/intermediate/manual_validation_sample.csv")
    parser.add_argument("--classified", default="data/final/articles_classified_enriched_pilot.csv")
    parser.add_argument("--reviewer-input", default="data/intermediate/manual_validation_batches")
    parser.add_argument("--codebook", default="docs/manual_validation_codebook.md")
    parser.add_argument("--html-dir", default="data/intermediate/manual_validation_forms")
    parser.add_argument("--summary-output", default="outputs/tables/enriched/manual_validation_readiness.csv")
    parser.add_argument("--drift-output", default="outputs/tables/enriched/manual_validation_sample_drift.csv")
    parser.add_argument("--batch-summary-output", default="outputs/tables/enriched/manual_validation_batch_completion.csv")
    parser.add_argument("--report", default="docs/manual_validation_readiness.md")
    parser.add_argument("--status-report", default="docs/manual_validation_status.md")
    parser.add_argument("--overlap-report", default="docs/manual_validation_overlap.md")
    parser.add_argument("--human-review-workboard-report", default="docs/human_review_workboard.md")
    parser.add_argument("--overlap-html-dir", default="data/intermediate/manual_validation_overlap_forms")
    parser.add_argument("--overlap-summary", default="outputs/tables/enriched/manual_validation_overlap_summary.csv")
    parser.add_argument("--calibration-report", default="docs/manual_validation_calibration.md")
    parser.add_argument("--calibration-kickoff-report", default="docs/manual_validation_calibration_kickoff.md")
    parser.add_argument("--calibration-guide-report", default="docs/manual_validation_calibration_guide.md")
    parser.add_argument("--calibration-remaining-report", default="docs/manual_validation_calibration_remaining.md")
    parser.add_argument("--calibration-remaining-template", default="data/intermediate/manual_validation_calibration/manual_validation_calibration_remaining_submission_template.csv")
    parser.add_argument("--calibration-html-dir", default="data/intermediate/manual_validation_calibration_forms")
    parser.add_argument("--calibration-summary", default="outputs/tables/enriched/manual_validation_calibration_summary.csv")
    parser.add_argument("--adjudication-report", default="docs/manual_validation_adjudication_status.md")
    parser.add_argument("--adjudication-summary", default="outputs/tables/enriched/manual_validation_adjudication_completion.csv")
    parser.add_argument("--scope-review-report", default="docs/scope_review_packet.md")
    parser.add_argument("--scope-review-guide-report", default="docs/scope_review_guide.md")
    parser.add_argument("--scope-review-form", default="data/intermediate/scope_review_forms/scope_review_packet.html")
    parser.add_argument("--scope-review-apply-report", default="docs/scope_review_apply.md")
    parser.add_argument("--scope-review-completion", default="outputs/tables/enriched/scope_review_completion.csv")
    parser.add_argument("--portal", default="docs/manual_validation_portal.html")
    args = parser.parse_args()

    sample = pd.read_csv(args.sample, dtype=str).fillna("")
    classified = read_optional_csv(Path(args.classified))
    reviewer = read_reviewer_batches(Path(args.reviewer_input))

    batch_summary = validation_batch_completion_summary(reviewer)
    drift = validation_sample_drift(sample, classified) if not classified.empty else pd.DataFrame(columns=["validation_id", "article_id", "field", "sample_value", "current_value"])
    summary = manual_validation_readiness_summary(sample, batch_summary, drift)
    overlap_summary = read_optional_csv(Path(args.overlap_summary))
    calibration_summary = read_optional_csv(Path(args.calibration_summary))
    adjudication_summary = read_optional_csv(Path(args.adjudication_summary))
    scope_review_completion = read_optional_csv(Path(args.scope_review_completion))

    Path(args.summary_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.drift_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.batch_summary_output).parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.summary_output, index=False)
    drift.to_csv(args.drift_output, index=False)
    batch_summary.to_csv(args.batch_summary_output, index=False)
    write_manual_validation_readiness_report(
        Path(args.report),
        summary,
        batch_summary,
        drift,
        codebook_path=args.codebook,
        batch_dir=args.reviewer_input,
        html_dir=args.html_dir,
    )
    write_manual_validation_portal(
        Path(args.portal),
        summary,
        batch_summary,
        codebook_path=args.codebook,
        readiness_report=args.report,
        status_report=args.status_report,
        overlap_report=args.overlap_report,
        human_review_workboard_report=args.human_review_workboard_report,
        main_forms_dir=args.html_dir,
        overlap_forms_dir=args.overlap_html_dir,
        adjudication_report=args.adjudication_report,
        calibration_report=args.calibration_report,
        calibration_kickoff_report=args.calibration_kickoff_report,
        calibration_guide_report=args.calibration_guide_report,
        calibration_remaining_report=args.calibration_remaining_report,
        calibration_remaining_template=args.calibration_remaining_template,
        calibration_forms_dir=args.calibration_html_dir,
        calibration_summary=calibration_summary,
        overlap_summary=overlap_summary,
        adjudication_summary=adjudication_summary,
        scope_review_report=args.scope_review_report,
        scope_review_guide_report=args.scope_review_guide_report,
        scope_review_form=args.scope_review_form,
        scope_review_apply_report=args.scope_review_apply_report,
        scope_review_completion=scope_review_completion,
    )

    lookup = dict(zip(summary["metric"].astype(str), summary["value"]))
    print(f"ready_for_blind_review={lookup.get('ready_for_blind_review', '')}")
    print(f"completed_manual_labels={lookup.get('completed_manual_labels', '')}")
    print(f"remaining_manual_labels={lookup.get('remaining_manual_labels', '')}")
    print(f"drifted_articles={lookup.get('drifted_articles', '')}")
    print(f"next_incomplete_batch={lookup.get('next_incomplete_batch', '')}")
    print(f"report={args.report}")
    print(f"portal={args.portal}")


if __name__ == "__main__":
    main()
