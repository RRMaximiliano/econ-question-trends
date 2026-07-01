from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from run_apply_adjudication_labels import apply_adjudication_labels, merge_adjudication_labels  # noqa: E402


def sample_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "validation_id": "VAL0001",
                "article_id": "a1",
                "manual_label": "other",
                "manual_confidence": "high",
                "manual_notes": "Reviewer label",
            }
        ]
    )


def adjudication_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "validation_id": "VAL0001",
                "article_id": "a1",
                "manual_label": "other",
                "predicted_label": "causal",
                "adjudicated_label": "causal",
                "adjudication_notes": "Resolved as causal",
                "adjudicator_id": "lead",
                "adjudication_date": "2026-06-29",
            }
        ]
    )


class ApplyAdjudicationLabelsTests(unittest.TestCase):
    def test_merge_adjudication_labels_adds_fields_to_sample(self) -> None:
        merged, errors, summary = merge_adjudication_labels(sample_frame(), adjudication_frame())

        self.assertTrue(errors.empty)
        self.assertEqual(merged.loc[0, "manual_label"], "other")
        self.assertEqual(merged.loc[0, "adjudicated_label"], "causal")
        self.assertEqual(merged.loc[0, "adjudicator_id"], "lead")
        lookup = dict(zip(summary["metric"], summary["value"]))
        self.assertEqual(int(lookup["completed_adjudications"]), 1)

    def test_merge_adjudication_labels_rejects_invalid_label_and_missing_metadata(self) -> None:
        bad = adjudication_frame()
        bad.loc[0, "adjudicated_label"] = "maybe"
        bad.loc[0, "adjudicator_id"] = ""
        bad.loc[0, "adjudication_date"] = ""

        merged, errors, _ = merge_adjudication_labels(sample_frame(), bad)

        self.assertFalse(errors.empty)
        self.assertEqual(merged.loc[0].get("adjudicated_label", ""), "")
        self.assertEqual(
            set(errors["error"]),
            {"invalid_adjudicated_label", "missing_adjudicator_id", "missing_adjudication_date"},
        )

    def test_merge_adjudication_labels_rejects_missing_context_and_notes(self) -> None:
        bad = adjudication_frame().drop(columns=["manual_label", "predicted_label"])
        bad.loc[0, "adjudication_notes"] = ""

        merged, errors, _ = merge_adjudication_labels(sample_frame(), bad)

        self.assertFalse(errors.empty)
        self.assertEqual(merged.loc[0].get("adjudicated_label", ""), "")
        self.assertEqual(set(errors["error"]), {"missing_adjudication_context", "missing_adjudication_notes"})

    def test_merge_adjudication_labels_accepts_overlap_disagreement_context(self) -> None:
        overlap_context = adjudication_frame().drop(columns=["manual_label", "predicted_label"])
        overlap_context["primary_manual_label"] = "other"
        overlap_context["overlap_manual_label"] = "causal"

        merged, errors, _ = merge_adjudication_labels(sample_frame(), overlap_context)

        self.assertTrue(errors.empty)
        self.assertEqual(merged.loc[0, "adjudicated_label"], "causal")

    def test_dry_run_writes_reports_without_writing_output_sample(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sample = root / "sample.csv"
            adjudication = root / "adjudication.csv"
            output = root / "merged.csv"
            sample_frame().to_csv(sample, index=False)
            adjudication_frame().to_csv(adjudication, index=False)

            errors, summary = apply_adjudication_labels(
                sample_path=sample,
                adjudication_input=adjudication,
                output_path=output,
                error_output=root / "errors.csv",
                summary_output=root / "summary.csv",
                report_path=root / "status.md",
                dry_run=True,
            )

            self.assertTrue(errors.empty)
            self.assertFalse(output.exists())
            self.assertTrue((root / "errors.csv").exists())
            self.assertTrue((root / "summary.csv").exists())
            self.assertIn("Adjudication Dry-Run", (root / "status.md").read_text(encoding="utf-8"))
            lookup = dict(zip(summary["metric"], summary["value"]))
            self.assertEqual(int(lookup["completed_adjudications"]), 1)

    def test_apply_writes_output_sample_when_not_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sample = root / "sample.csv"
            adjudication = root / "adjudication.csv"
            output = root / "merged.csv"
            sample_frame().to_csv(sample, index=False)
            adjudication_frame().to_csv(adjudication, index=False)

            errors, _ = apply_adjudication_labels(
                sample_path=sample,
                adjudication_input=adjudication,
                output_path=output,
                error_output=root / "errors.csv",
                summary_output=root / "summary.csv",
                report_path=root / "status.md",
                dry_run=False,
            )

            self.assertTrue(errors.empty)
            merged = pd.read_csv(output, dtype=str).fillna("")
            self.assertEqual(merged.loc[0, "adjudicated_label"], "causal")

    def test_cli_dry_run_uses_separate_default_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sample = root / "sample.csv"
            adjudication = root / "adjudication.csv"
            sample_frame().to_csv(sample, index=False)
            adjudication_frame().to_csv(adjudication, index=False)

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "run_apply_adjudication_labels.py"),
                    "--sample",
                    str(sample),
                    "--adjudication-input",
                    str(adjudication),
                    "--dry-run",
                ],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn("dry_run=true", result.stdout)
            self.assertIn("output=not_written_dry_run", result.stdout)
            self.assertTrue((root / "docs" / "manual_validation_adjudication_dry_run_status.md").exists())
            self.assertTrue((root / "outputs" / "tables" / "enriched" / "manual_validation_adjudication_dry_run_completion.csv").exists())
            self.assertFalse((root / "docs" / "manual_validation_adjudication_status.md").exists())


if __name__ == "__main__":
    unittest.main()
