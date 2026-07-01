from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "code" / "06_enrich"))

from recovery_progress import (  # noqa: E402
    batch_from_import_source,
    recovery_progress_by_batch,
    recovery_progress_overview,
    run_recovery_progress,
)


class RecoveryProgressTests(unittest.TestCase):
    def test_batch_from_import_source_extracts_recovery_batch(self) -> None:
        self.assertEqual(
            batch_from_import_source("data/intermediate/insufficient_text_recovery_batches/insufficient_text_recovery_batch_R012.csv"),
            "R012",
        )
        self.assertEqual(
            batch_from_import_source("data/intermediate/insufficient_text_recovery_splits/R001/insufficient_text_recovery_batch_R001_ready_manual_metadata.csv"),
            "R001",
        )
        self.assertEqual(batch_from_import_source("data/intermediate/abstract_backfill_template.csv"), "")

    def test_recovery_progress_by_batch_adds_history_counts_and_share(self) -> None:
        batch_summary = pd.DataFrame(
            [
                {"recovery_batch": "R001", "total_rows": "100", "completed_backfill_abstracts": "2", "remaining_backfill_abstracts": "98"},
                {"recovery_batch": "R002", "total_rows": "100", "completed_backfill_abstracts": "0", "remaining_backfill_abstracts": "100"},
            ]
        )
        imported_history = pd.DataFrame(
            [
                {"article_id": "a1", "import_source_file": "insufficient_text_recovery_batch_R001.csv"},
                {"article_id": "a2", "import_source_file": "insufficient_text_recovery_batch_R001.csv"},
            ]
        )
        error_history = pd.DataFrame([{"article_id": "bad", "import_source_file": "insufficient_text_recovery_batch_R002.csv"}])

        progress = recovery_progress_by_batch(batch_summary, imported_history, error_history).set_index("recovery_batch")

        self.assertEqual(int(progress.loc["R001", "history_imported_rows"]), 2)
        self.assertEqual(int(progress.loc["R001", "history_error_rows"]), 0)
        self.assertEqual(int(progress.loc["R002", "history_error_rows"]), 1)
        self.assertEqual(float(progress.loc["R001", "completed_backfill_share"]), 0.02)

    def test_recovery_progress_overview_combines_gate_metrics(self) -> None:
        batch_progress = pd.DataFrame(
            [
                {"recovery_batch": "R001", "total_rows": "100", "completed_backfill_abstracts": "2", "remaining_backfill_abstracts": "98"},
                {"recovery_batch": "R002", "total_rows": "100", "completed_backfill_abstracts": "0", "remaining_backfill_abstracts": "100"},
            ]
        )
        validation = pd.DataFrame(
            [
                {"metric": "total_rows", "value": "300"},
                {"metric": "completed_manual_labels", "value": "10"},
                {"metric": "remaining_manual_labels", "value": "290"},
            ]
        )
        recommendation = pd.DataFrame(
            [
                {
                    "recommendation": "pause_for_manual_validation",
                    "insufficient_text_share": "0.19",
                }
            ]
        )

        overview = recovery_progress_overview(batch_progress, pd.DataFrame([{"x": 1}]), pd.DataFrame(), validation, recommendation)
        lookup = dict(zip(overview["metric"], overview["value"]))

        self.assertEqual(lookup["recovery_batches"], 2)
        self.assertEqual(lookup["recovery_rows"], 200)
        self.assertEqual(lookup["current_recovery_queue_rows"], 200)
        self.assertEqual(lookup["completed_backfill_abstracts"], 2)
        self.assertEqual(lookup["current_packet_completed_backfill_abstracts"], 2)
        self.assertEqual(lookup["cumulative_imported_recovery_rows"], 1)
        self.assertEqual(lookup["remaining_backfill_abstracts"], 198)
        self.assertEqual(lookup["next_recovery_batch"], "R001")
        self.assertEqual(lookup["completed_manual_labels"], "10")
        self.assertEqual(lookup["classification_recommendation"], "pause_for_manual_validation")

    def test_recovery_progress_overview_uses_live_recovery_queue_when_available(self) -> None:
        batch_progress = pd.DataFrame(
            [
                {"recovery_batch": "R001", "total_rows": "100", "completed_backfill_abstracts": "0", "remaining_backfill_abstracts": "100"},
                {"recovery_batch": "R002", "total_rows": "100", "completed_backfill_abstracts": "0", "remaining_backfill_abstracts": "100"},
            ]
        )
        recovery_queue = pd.DataFrame(
            [
                {"article_id": "a1", "recovery_batch": "R001"},
                {"article_id": "a2", "recovery_batch": "R001"},
                {"article_id": "a3", "recovery_batch": "R002"},
            ]
        )

        overview = recovery_progress_overview(
            batch_progress,
            pd.DataFrame([{"article_id": "imported"}]),
            pd.DataFrame(),
            pd.DataFrame(),
            pd.DataFrame(),
            recovery_queue=recovery_queue,
        )
        lookup = dict(zip(overview["metric"], overview["value"]))

        self.assertEqual(lookup["current_recovery_queue_rows"], 3)
        self.assertEqual(lookup["remaining_backfill_abstracts"], 3)
        self.assertEqual(lookup["recovery_rows"], 4)
        self.assertEqual(lookup["next_recovery_batch"], "R001")
        self.assertEqual(lookup["next_recovery_batch_remaining"], "2")

    def test_run_recovery_progress_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch_summary = root / "batch_summary.csv"
            imported_history = root / "imported_history.csv"
            error_history = root / "error_history.csv"
            validation = root / "validation.csv"
            recommendation = root / "recommendation.csv"
            output_overview = root / "overview.csv"
            output_batches = root / "batches.csv"
            report = root / "report.md"
            pd.DataFrame([{"recovery_batch": "R001", "total_rows": "1", "completed_backfill_abstracts": "0", "remaining_backfill_abstracts": "1"}]).to_csv(batch_summary, index=False)
            pd.DataFrame(columns=["article_id", "import_source_file"]).to_csv(imported_history, index=False)
            pd.DataFrame(columns=["article_id", "import_source_file"]).to_csv(error_history, index=False)
            pd.DataFrame([{"metric": "completed_manual_labels", "value": "0"}, {"metric": "remaining_manual_labels", "value": "300"}]).to_csv(validation, index=False)
            pd.DataFrame([{"recommendation": "pause_for_manual_validation", "insufficient_text_share": "0.19"}]).to_csv(recommendation, index=False)

            with contextlib.redirect_stdout(io.StringIO()):
                run_recovery_progress(
                    batch_summary_path=batch_summary,
                    imported_history_path=imported_history,
                    error_history_path=error_history,
                    validation_completion_path=validation,
                    recommendation_path=recommendation,
                    output_overview=output_overview,
                    output_batches=output_batches,
                    report_path=report,
                )

            self.assertTrue(output_overview.exists())
            self.assertTrue(output_batches.exists())
            self.assertIn("Recovery Progress Status", report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
