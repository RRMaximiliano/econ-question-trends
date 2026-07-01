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

from recovery_action_progress import (  # noqa: E402
    recovery_action_progress_detail,
    recovery_action_progress_summary,
    run_recovery_action_progress,
)


class RecoveryActionProgressTests(unittest.TestCase):
    def test_recovery_action_progress_detail_tracks_export_stage_and_preflight_status(self) -> None:
        action_packet = pd.DataFrame(
            [
                {"review_rank": "1", "article_id": "a1", "action_group": "find_external_extension", "quick_win_tier": "tier_1", "cell_target_rank": "2", "cell_target_level": "critical", "cell_recoveries_to_target_share": "208", "title": "Paper 1"},
                {"review_rank": "2", "article_id": "a2", "action_group": "find_external_extension", "quick_win_tier": "tier_1", "cell_target_rank": "2", "cell_target_level": "critical", "cell_recoveries_to_target_share": "208", "title": "Paper 2"},
                {"review_rank": "3", "article_id": "a3", "action_group": "manual_metadata_search", "quick_win_tier": "tier_4", "cell_target_rank": "8", "cell_target_level": "critical", "cell_recoveries_to_target_share": "138", "title": "Paper 3"},
                {"review_rank": "4", "article_id": "a4", "action_group": "manual_metadata_search", "quick_win_tier": "tier_4", "cell_target_rank": "11", "cell_target_level": "high", "cell_recoveries_to_target_share": "0", "title": "Paper 4"},
            ]
        )
        export_records = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "source_file": "exports/action.csv",
                    "abstract": "A recovered abstract.",
                    "source": "publisher",
                    "source_url": "https://example.test/a1",
                    "source_record_id": "",
                    "evidence_tier": "tier_a_formal_abstract",
                },
                {
                    "article_id": "a2",
                    "source_file": "exports/action.csv",
                    "abstract": "Incomplete abstract.",
                    "source": "",
                    "source_url": "",
                    "source_record_id": "",
                    "evidence_tier": "",
                },
                {
                    "article_id": "a4",
                    "source_file": "exports/action.csv",
                    "abstract": "Bad abstract.",
                    "source": "publisher",
                    "source_url": "https://example.test/a4",
                    "source_record_id": "",
                    "evidence_tier": "tier_a_formal_abstract",
                },
            ]
        )
        stage_changes = pd.DataFrame([{"article_id": "a1"}])
        stage_errors = pd.DataFrame([{"article_id": "a4", "error": "missing_staged_source_provenance"}])
        preflight_errors = pd.DataFrame([{"article_id": "a1", "error": "title_mismatch"}])

        detail = recovery_action_progress_detail(
            action_packet=action_packet,
            export_records=export_records,
            stage_changes=stage_changes,
            stage_errors=stage_errors,
            preflight_errors=preflight_errors,
        ).set_index("article_id")

        self.assertEqual(detail.loc["a1", "exported_ready_candidate"], "yes")
        self.assertEqual(detail.loc["a1", "staged"], "yes")
        self.assertEqual(detail.loc["a1", "cell_target_rank"], "2")
        self.assertEqual(detail.loc["a1", "cell_recoveries_to_target_share"], "208")
        self.assertEqual(detail.loc["a1", "next_status"], "fix_preflight_errors")
        self.assertEqual(detail.loc["a2", "next_status"], "complete_export_fields")
        self.assertEqual(detail.loc["a3", "next_status"], "not_started")
        self.assertEqual(detail.loc["a4", "next_status"], "fix_stage_errors")

    def test_recovery_action_progress_summary_counts_action_groups(self) -> None:
        detail = pd.DataFrame(
            [
                {"review_rank": "1", "action_group": "a", "cell_target_rank": "2", "cell_target_level": "critical", "cell_recoveries_to_target_share": "208", "export_row_count": 1, "exported_ready_candidate": "yes", "staged": "yes", "import_ready": "yes", "stage_error_rows": "0", "preflight_error_rows": "0", "next_status": "ready_to_import"},
                {"review_rank": "2", "action_group": "a", "cell_target_rank": "4", "cell_target_level": "critical", "cell_recoveries_to_target_share": "207", "export_row_count": 1, "exported_ready_candidate": "no", "staged": "no", "import_ready": "no", "stage_error_rows": "0", "preflight_error_rows": "0", "next_status": "complete_export_fields"},
                {"review_rank": "3", "action_group": "b", "cell_target_rank": "11", "cell_target_level": "high", "cell_recoveries_to_target_share": "0", "export_row_count": 0, "exported_ready_candidate": "no", "staged": "no", "import_ready": "no", "stage_error_rows": "1", "preflight_error_rows": "0", "next_status": "fix_stage_errors"},
            ]
        )

        summary = recovery_action_progress_summary(detail).set_index("action_group")

        self.assertEqual(int(summary.loc["a", "rows_total"]), 2)
        self.assertEqual(int(summary.loc["a", "priority_cell_rows"]), 2)
        self.assertEqual(int(summary.loc["a", "critical_cell_rows"]), 2)
        self.assertEqual(int(summary.loc["a", "top_cell_target_rank"]), 2)
        self.assertEqual(summary.loc["a", "top_cell_recoveries_to_target_share"], "208")
        self.assertEqual(int(summary.loc["a", "import_ready_rows"]), 1)
        self.assertEqual(summary.loc["a", "next_status"], "complete_export_fields")
        self.assertEqual(int(summary.loc["b", "priority_cell_rows"]), 0)
        self.assertEqual(int(summary.loc["b", "stage_error_rows"]), 1)
        self.assertEqual(summary.loc["b", "next_status"], "fix_stage_errors")

    def test_run_recovery_action_progress_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            action_packet = root / "action_packet.csv"
            action_packet_index = root / "action_packet_index.csv"
            reviewer_input = root / "exports"
            reviewer_input.mkdir()
            stage_changes = root / "stage_changes.csv"
            stage_errors = root / "stage_errors.csv"
            preflight_errors = root / "preflight_errors.csv"
            output_overview = root / "overview.csv"
            output_summary = root / "summary.csv"
            output_detail = root / "detail.csv"
            report = root / "report.md"
            dashboard = root / "forms" / "dashboard.html"

            pd.DataFrame(
                [
                    {"review_rank": "1", "article_id": "a1", "action_group": "find_external_extension", "quick_win_tier": "tier_1", "cell_target_rank": "2", "cell_target_level": "critical", "cell_recoveries_to_target_share": "208", "title": "Paper 1"}
                ]
            ).to_csv(action_packet, index=False)
            pd.DataFrame(
                [
                    {
                        "action_group": "find_external_extension",
                        "rows": "1",
                        "html_path": str(root / "forms" / "action.html"),
                        "csv_path": str(root / "packets" / "action.csv"),
                        "quick_win_tiers": "tier_1",
                    }
                ]
            ).to_csv(action_packet_index, index=False)
            pd.DataFrame(
                [
                    {
                        "article_id": "a1",
                        "abstract": "A recovered abstract.",
                        "source": "publisher",
                        "source_url": "https://example.test/a1",
                        "source_record_id": "",
                        "evidence_tier": "tier_a_formal_abstract",
                    }
                ]
            ).to_csv(reviewer_input / "export.csv", index=False)
            pd.DataFrame([{"article_id": "a1"}]).to_csv(stage_changes, index=False)
            pd.DataFrame(columns=["article_id", "error"]).to_csv(stage_errors, index=False)
            pd.DataFrame(columns=["article_id", "error"]).to_csv(preflight_errors, index=False)

            with contextlib.redirect_stdout(io.StringIO()):
                overview, summary, detail = run_recovery_action_progress(
                    action_packet_path=action_packet,
                    action_packet_index_path=action_packet_index,
                    reviewer_input=reviewer_input,
                    stage_changes_path=stage_changes,
                    stage_errors_path=stage_errors,
                    preflight_errors_path=preflight_errors,
                    output_overview=output_overview,
                    output_summary=output_summary,
                    output_detail=output_detail,
                    report_path=report,
                    dashboard_path=dashboard,
                )

            self.assertFalse(overview.empty)
            self.assertFalse(summary.empty)
            self.assertFalse(detail.empty)
            self.assertTrue(output_overview.exists())
            self.assertTrue(output_summary.exists())
            self.assertTrue(output_detail.exists())
            self.assertIn("Recovery Batch R001 Action Progress", report.read_text(encoding="utf-8"))
            dashboard_text = dashboard.read_text(encoding="utf-8")
            self.assertIn("Recovery R001 Action Dashboard", dashboard_text)
            self.assertIn("Target-share rows", dashboard_text)
            self.assertIn("find_external_extension", dashboard_text)
            self.assertIn("need 208", dashboard_text)
            self.assertIn("Open form", dashboard_text)


if __name__ == "__main__":
    unittest.main()
