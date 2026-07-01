from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "code" / "06_enrich"))

from recovery_cell_targets import (  # noqa: E402
    recoveries_needed_for_share,
    recovery_cell_target_queue,
    recovery_cell_targets,
    run_recovery_cell_targets,
    target_level,
)


class RecoveryCellTargetsTests(unittest.TestCase):
    def test_target_level_uses_count_or_share_thresholds(self) -> None:
        self.assertEqual(target_level(250, 0.1), "critical")
        self.assertEqual(target_level(20, 0.45), "critical")
        self.assertEqual(target_level(100, 0.1), "high")
        self.assertEqual(target_level(20, 0.25), "high")
        self.assertEqual(target_level(50, 0.1), "medium")
        self.assertEqual(target_level(10, 0.05), "low")

    def test_recoveries_needed_for_share_counts_rows_to_threshold(self) -> None:
        self.assertEqual(recoveries_needed_for_share(300, 1000, 0.2), 100)
        self.assertEqual(recoveries_needed_for_share(200, 1000, 0.2), 0)
        self.assertEqual(recoveries_needed_for_share(201, 1000, 0.2), 1)
        self.assertEqual(recoveries_needed_for_share(10, 0, 0.2), 0)

    def test_recovery_cell_targets_prioritizes_ready_weak_cells(self) -> None:
        profile = pd.DataFrame(
            [
                {
                    "journal_short": "aer",
                    "decade": "1980",
                    "rows": "1000",
                    "insufficient_rows": "300",
                    "insufficient_share": "0.30",
                    "partial_short_text_rows": "20",
                    "missing_abstract_rows": "280",
                    "has_oa_pdf_rows": "0",
                },
                {
                    "journal_short": "qje",
                    "decade": "1970",
                    "rows": "200",
                    "insufficient_rows": "90",
                    "insufficient_share": "0.45",
                    "partial_short_text_rows": "80",
                    "missing_abstract_rows": "10",
                    "has_oa_pdf_rows": "0",
                },
            ]
        )
        queue = pd.DataFrame(
            [
                {"article_id": "a1", "journal_short": "aer", "decade": "1980", "recovery_rank": "2", "title": "A", "publication_year": "1981"},
                {"article_id": "q1", "journal_short": "qje", "decade": "1970", "recovery_rank": "1", "title": "Q", "publication_year": "1978"},
            ]
        )
        ready = pd.DataFrame(
            [
                {"article_id": "a1", "journal_short": "aer", "decade": "1980", "review_rank": "3"},
                {"article_id": "a2", "journal_short": "aer", "decade": "1980", "review_rank": "4"},
            ]
        )

        targets = recovery_cell_targets(profile=profile, recovery_queue=queue, ready_queue=ready)
        indexed = targets.set_index(["journal_short", "decade"])

        self.assertEqual(indexed.loc[("aer", "1980"), "ready_r001_rows"], 2)
        self.assertEqual(indexed.loc[("aer", "1980"), "target_level"], "critical")
        self.assertEqual(indexed.loc[("aer", "1980"), "recoveries_to_target_share"], 100)
        self.assertEqual(indexed.loc[("aer", "1980"), "recoveries_to_stretch_share"], 200)
        self.assertEqual(indexed.loc[("aer", "1980"), "projected_share_after_ready_r001"], 0.298)
        self.assertEqual(indexed.loc[("aer", "1980"), "ready_r001_target_coverage"], 0.02)
        self.assertIn("ready R001", indexed.loc[("aer", "1980"), "recommended_next_step"])

    def test_recovery_cell_target_queue_selects_rows_per_target_cell(self) -> None:
        targets = pd.DataFrame(
            [
                {"target_rank": 1, "target_level": "critical", "journal_short": "aer", "decade": "1980", "recommended_next_step": "Work ready rows."},
            ]
        )
        queue = pd.DataFrame(
            [
                {"article_id": "a2", "journal_short": "aer", "decade": "1980", "recovery_rank": "2", "recovery_batch": "R001", "title": "Second", "doi_url": "https://doi.org/2"},
                {"article_id": "a1", "journal_short": "aer", "decade": "1980", "recovery_rank": "1", "recovery_batch": "R001", "title": "First", "doi_url": "https://doi.org/1"},
            ]
        )

        target_queue = recovery_cell_target_queue(targets=targets, recovery_queue=queue, rows_per_cell=1)

        self.assertEqual(len(target_queue), 1)
        self.assertEqual(target_queue.iloc[0]["article_id"], "a1")
        self.assertEqual(target_queue.iloc[0]["source_hint"], "https://doi.org/1")

    def test_run_recovery_cell_targets_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = root / "profile.csv"
            queue = root / "queue.csv"
            ready = root / "ready.csv"
            targets_out = root / "outputs" / "targets.csv"
            queue_out = root / "outputs" / "target_queue.csv"
            report = root / "docs" / "targets.md"
            pd.DataFrame(
                [
                    {
                        "journal_short": "ecta",
                        "decade": "1980",
                        "rows": "100",
                        "insufficient_rows": "60",
                        "insufficient_share": "0.60",
                        "partial_short_text_rows": "5",
                        "missing_abstract_rows": "55",
                        "has_oa_pdf_rows": "1",
                    }
                ]
            ).to_csv(profile, index=False)
            pd.DataFrame(
                [
                    {"article_id": "e1", "journal_short": "ecta", "decade": "1980", "recovery_rank": "1", "title": "Estimator", "publication_year": "1982"}
                ]
            ).to_csv(queue, index=False)
            pd.DataFrame().to_csv(ready, index=False)

            targets, target_queue = run_recovery_cell_targets(
                profile_path=profile,
                recovery_queue_path=queue,
                ready_queue_path=ready,
                output_targets=targets_out,
                output_queue=queue_out,
                report_path=report,
            )

            self.assertEqual(len(targets), 1)
            self.assertEqual(len(target_queue), 1)
            self.assertEqual(targets.iloc[0]["recoveries_to_target_share"], 40)
            self.assertTrue(targets_out.exists())
            self.assertTrue(queue_out.exists())
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("Recovery Cell Targets", report_text)
            self.assertIn("Recoveries needed across target cells", report_text)


if __name__ == "__main__":
    unittest.main()
