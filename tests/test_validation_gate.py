from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "code" / "05_analysis"))

from validation_gate import run_validation_gate, validation_gate_status  # noqa: E402


def metrics(rows: dict[str, object]) -> pd.DataFrame:
    return pd.DataFrame([{"metric": key, "value": value} for key, value in rows.items()])


def complete_inputs() -> dict[str, pd.DataFrame]:
    return {
        "readiness": metrics(
            {
                "ready_for_blind_review": "yes",
                "drifted_articles": 0,
                "sample_rows": 300,
                "completed_manual_labels": 300,
                "remaining_manual_labels": 0,
            }
        ),
        "manual_completion": metrics({"total_rows": 300, "completed_manual_labels": 300, "remaining_manual_labels": 0}),
        "calibration_summary": metrics({"calibration_rows": 20, "completed_calibration_rows": 20, "completed_calibration_labels": 20}),
        "overlap_summary": metrics({"overlap_rows": 30, "completed_overlap_labels": 30}),
        "adjudication_summary": metrics({"completed_adjudications": 0}),
        "adjudication_packet": pd.DataFrame(
            columns=[
                "validation_id",
                "article_id",
                "manual_label",
                "predicted_label",
                "adjudicated_label",
                "adjudicator_id",
                "adjudication_date",
            ]
        ),
        "classification_recommendation": pd.DataFrame([{"recommendation": "proceed"}]),
        "validation_metrics": pd.DataFrame([{"validation_status": "available", "agreement_rate": "0.9"}]),
    }


def gate_lookup(overview: pd.DataFrame) -> dict[str, object]:
    return dict(zip(overview["metric"], overview["value"]))


def check_lookup(checks: pd.DataFrame) -> dict[str, str]:
    return dict(zip(checks["check"], checks["status"]))


class ValidationGateTests(unittest.TestCase):
    def test_gate_blocks_on_calibration_before_main_labels(self) -> None:
        inputs = complete_inputs()
        inputs["calibration_summary"] = metrics({"calibration_rows": 20, "completed_calibration_rows": 0, "completed_calibration_labels": 0})
        inputs["manual_completion"] = metrics({"total_rows": 300, "completed_manual_labels": 0, "remaining_manual_labels": 300})
        inputs["overlap_summary"] = metrics({"overlap_rows": 30, "completed_overlap_labels": 0})
        inputs["classification_recommendation"] = pd.DataFrame([{"recommendation": "pause_for_manual_validation"}])

        overview, checks = validation_gate_status(**inputs)
        lookup = gate_lookup(overview)

        self.assertEqual(lookup["validation_gate"], "blocked_calibration")
        self.assertEqual(lookup["first_blocking_check"], "calibration")
        self.assertEqual(check_lookup(checks)["manual_validation"], "block")

    def test_gate_blocks_when_duplicate_labels_do_not_cover_all_calibration_rows(self) -> None:
        inputs = complete_inputs()
        inputs["calibration_summary"] = metrics({"calibration_rows": 2, "completed_calibration_rows": 1, "completed_calibration_labels": 2})

        overview, checks = validation_gate_status(**inputs)

        self.assertEqual(gate_lookup(overview)["validation_gate"], "blocked_calibration")
        self.assertEqual(check_lookup(checks)["calibration"], "block")

    def test_gate_blocks_on_manual_validation_after_calibration_passes(self) -> None:
        inputs = complete_inputs()
        inputs["manual_completion"] = metrics({"total_rows": 300, "completed_manual_labels": 20, "remaining_manual_labels": 280})
        inputs["overlap_summary"] = metrics({"overlap_rows": 30, "completed_overlap_labels": 0})
        inputs["classification_recommendation"] = pd.DataFrame([{"recommendation": "pause_for_manual_validation"}])

        overview, _ = validation_gate_status(**inputs)

        self.assertEqual(gate_lookup(overview)["validation_gate"], "blocked_manual_validation")

    def test_gate_blocks_on_overlap_after_main_labels_pass(self) -> None:
        inputs = complete_inputs()
        inputs["overlap_summary"] = metrics({"overlap_rows": 30, "completed_overlap_labels": 5})
        inputs["classification_recommendation"] = pd.DataFrame([{"recommendation": "pause_for_manual_validation"}])

        overview, _ = validation_gate_status(**inputs)

        self.assertEqual(gate_lookup(overview)["validation_gate"], "blocked_overlap_review")

    def test_gate_blocks_on_pending_adjudication_rows(self) -> None:
        inputs = complete_inputs()
        inputs["adjudication_packet"] = pd.DataFrame(
            [
                {
                    "validation_id": "VAL0001",
                    "article_id": "a1",
                    "manual_label": "causal",
                    "predicted_label": "other",
                    "adjudicated_label": "",
                    "adjudicator_id": "",
                    "adjudication_date": "",
                }
            ]
        )

        overview, checks = validation_gate_status(**inputs)

        self.assertEqual(gate_lookup(overview)["validation_gate"], "blocked_adjudication")
        self.assertEqual(check_lookup(checks)["adjudication"], "block")

    def test_gate_proceeds_when_all_checks_pass(self) -> None:
        overview, checks = validation_gate_status(**complete_inputs())

        self.assertEqual(gate_lookup(overview)["validation_gate"], "proceed")
        self.assertFalse((checks["status"] == "block").any())

    def test_run_validation_gate_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs = complete_inputs()
            paths: dict[str, Path] = {}
            for key, frame in inputs.items():
                path = root / f"{key}.csv"
                frame.to_csv(path, index=False)
                paths[key] = path

            output_overview = root / "outputs" / "manual_validation_gate.csv"
            output_checks = root / "outputs" / "manual_validation_gate_checks.csv"
            report = root / "docs" / "manual_validation_gate.md"

            with contextlib.redirect_stdout(io.StringIO()):
                run_validation_gate(
                    readiness_path=paths["readiness"],
                    manual_completion_path=paths["manual_completion"],
                    calibration_summary_path=paths["calibration_summary"],
                    overlap_summary_path=paths["overlap_summary"],
                    adjudication_summary_path=paths["adjudication_summary"],
                    adjudication_packet_path=paths["adjudication_packet"],
                    classification_recommendation_path=paths["classification_recommendation"],
                    validation_metrics_path=paths["validation_metrics"],
                    output_overview=output_overview,
                    output_checks=output_checks,
                    report_path=report,
                )

            self.assertTrue(output_overview.exists())
            self.assertTrue(output_checks.exists())
            self.assertIn("Manual Validation Gate", report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
