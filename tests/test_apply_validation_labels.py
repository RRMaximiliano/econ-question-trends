from __future__ import annotations

import sys
import subprocess
import tempfile
import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from run_apply_validation_labels import apply_validation_labels  # noqa: E402


def sample_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "validation_id": "VAL0001",
                "article_id": "a1",
                "title": "Article",
                "abstract": "Abstract text",
                "manual_label": "",
                "manual_confidence": "",
                "manual_notes": "",
                "reviewer_id": "",
                "review_date": "",
            }
        ]
    )


def reviewer_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "validation_id": "VAL0001",
                "article_id": "a1",
                "title": "Article",
                "abstract": "Abstract text",
                "manual_label": "causal",
                "manual_confidence": "high",
                "manual_notes": "Treatment effect",
                "reviewer_id": "r1",
                "review_date": "2026-06-29",
            }
        ]
    )


class ApplyValidationLabelsTests(unittest.TestCase):
    def test_dry_run_writes_reports_without_writing_output_sample(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sample = root / "sample.csv"
            reviewer = root / "reviewer.csv"
            output = root / "merged.csv"
            error_output = root / "errors.csv"
            summary_output = root / "summary.csv"
            batch_summary_output = root / "batch_summary.csv"
            report = root / "status.md"
            sample_frame().to_csv(sample, index=False)
            reviewer_frame().to_csv(reviewer, index=False)

            errors, summary = apply_validation_labels(
                sample_path=sample,
                reviewer_input=reviewer,
                output_path=output,
                error_output=error_output,
                summary_output=summary_output,
                batch_summary_output=batch_summary_output,
                report_path=report,
                dry_run=True,
            )

            self.assertTrue(errors.empty)
            self.assertFalse(output.exists())
            self.assertTrue(error_output.exists())
            self.assertTrue(summary_output.exists())
            self.assertTrue(batch_summary_output.exists())
            self.assertIn("Manual Validation Dry-Run Status", report.read_text(encoding="utf-8"))
            lookup = dict(zip(summary["metric"], summary["value"]))
            self.assertEqual(int(lookup["completed_manual_labels"]), 1)

    def test_apply_writes_output_sample_when_not_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sample = root / "sample.csv"
            reviewer = root / "reviewer.csv"
            output = root / "merged.csv"
            sample_frame().to_csv(sample, index=False)
            reviewer_frame().to_csv(reviewer, index=False)

            errors, _ = apply_validation_labels(
                sample_path=sample,
                reviewer_input=reviewer,
                output_path=output,
                error_output=root / "errors.csv",
                summary_output=root / "summary.csv",
                batch_summary_output=root / "batch_summary.csv",
                report_path=root / "status.md",
                dry_run=False,
            )

            self.assertTrue(errors.empty)
            merged = pd.read_csv(output, dtype=str).fillna("")
            self.assertEqual(merged.loc[0, "manual_label"], "causal")

    def test_cli_dry_run_uses_separate_default_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sample = root / "sample.csv"
            reviewer = root / "reviewer.csv"
            sample_frame().to_csv(sample, index=False)
            reviewer_frame().to_csv(reviewer, index=False)

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "run_apply_validation_labels.py"),
                    "--sample",
                    str(sample),
                    "--reviewer-input",
                    str(reviewer),
                    "--dry-run",
                ],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn("dry_run=true", result.stdout)
            self.assertIn("output=not_written_dry_run", result.stdout)
            self.assertTrue((root / "docs" / "manual_validation_dry_run_status.md").exists())
            self.assertTrue((root / "outputs" / "tables" / "enriched" / "manual_validation_dry_run_completion.csv").exists())
            self.assertFalse((root / "docs" / "manual_validation_status.md").exists())
            self.assertFalse((root / "data" / "intermediate" / "manual_validation_sample.csv").exists())


if __name__ == "__main__":
    unittest.main()
