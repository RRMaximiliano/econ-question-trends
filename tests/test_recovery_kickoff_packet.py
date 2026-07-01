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

from recovery_kickoff_packet import (  # noqa: E402
    kickoff_article_ids,
    kickoff_summary,
    recovery_kickoff_packet,
    run_recovery_kickoff_packet,
)


class RecoveryKickoffPacketTests(unittest.TestCase):
    def test_kickoff_article_ids_prioritizes_status_tier_and_target_cells(self) -> None:
        progress = pd.DataFrame(
            [
                {
                    "review_rank": "4",
                    "article_id": "manual_monitor",
                    "quick_win_tier": "tier_4_manual_metadata_has_context",
                    "next_status": "not_started",
                    "cell_target_rank": "1",
                    "cell_recoveries_to_target_share": "255",
                    "stage_error_rows": "0",
                    "preflight_error_rows": "0",
                },
                {
                    "review_rank": "2",
                    "article_id": "near_target_2",
                    "quick_win_tier": "tier_1_partial_near_threshold",
                    "next_status": "not_started",
                    "cell_target_rank": "2",
                    "cell_recoveries_to_target_share": "208",
                    "stage_error_rows": "0",
                    "preflight_error_rows": "0",
                },
                {
                    "review_rank": "1",
                    "article_id": "near_target_4",
                    "quick_win_tier": "tier_1_partial_near_threshold",
                    "next_status": "not_started",
                    "cell_target_rank": "4",
                    "cell_recoveries_to_target_share": "207",
                    "stage_error_rows": "0",
                    "preflight_error_rows": "0",
                },
                {
                    "review_rank": "3",
                    "article_id": "replace_target",
                    "quick_win_tier": "tier_2_partial_replace_suspect_text",
                    "next_status": "not_started",
                    "cell_target_rank": "2",
                    "cell_recoveries_to_target_share": "208",
                    "stage_error_rows": "0",
                    "preflight_error_rows": "0",
                },
            ]
        )

        self.assertEqual(
            kickoff_article_ids(progress, limit=3),
            ["near_target_2", "near_target_4", "replace_target"],
        )

    def test_recovery_kickoff_packet_selects_packet_rows_in_rank_order(self) -> None:
        progress = pd.DataFrame(
            [
                {"review_rank": "1", "article_id": "a1", "quick_win_tier": "tier_1_partial_near_threshold", "next_status": "not_started", "cell_target_rank": "2", "cell_recoveries_to_target_share": "208"},
                {"review_rank": "2", "article_id": "a2", "quick_win_tier": "tier_1_partial_near_threshold", "next_status": "not_started", "cell_target_rank": "4", "cell_recoveries_to_target_share": "207"},
            ]
        )
        packets = pd.DataFrame(
            [
                {"article_id": "a2", "title": "Second", "action_group": "find_external_extension", "quick_win_tier": "tier_1_partial_near_threshold", "cell_target_rank": "4", "cell_target_level": "critical", "cell_recoveries_to_target_share": "207"},
                {"article_id": "a1", "title": "First", "action_group": "find_external_extension", "quick_win_tier": "tier_1_partial_near_threshold", "cell_target_rank": "2", "cell_target_level": "critical", "cell_recoveries_to_target_share": "208"},
            ]
        )

        packet = recovery_kickoff_packet(progress_detail=progress, action_packet_rows=packets, limit=2)
        summary = kickoff_summary(packet).set_index("metric")

        self.assertEqual(packet["article_id"].tolist(), ["a1", "a2"])
        self.assertEqual(packet["kickoff_rank"].tolist(), ["1", "2"])
        self.assertEqual(int(summary.loc["kickoff_rows", "value"]), 2)
        self.assertEqual(int(summary.loc["priority_cell_rows", "value"]), 2)
        self.assertEqual(int(summary.loc["critical_cell_rows", "value"]), 2)

    def test_run_recovery_kickoff_packet_writes_csv_form_summary_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            progress_detail = root / "progress.csv"
            packet_dir = root / "packets"
            output_csv = root / "outputs" / "kickoff.csv"
            output_html = root / "forms" / "kickoff.html"
            summary_output = root / "outputs" / "summary.csv"
            report = root / "docs" / "kickoff.md"
            packet_dir.mkdir()

            pd.DataFrame(
                [
                    {"review_rank": "1", "article_id": "a1", "quick_win_tier": "tier_1_partial_near_threshold", "next_status": "not_started", "cell_target_rank": "2", "cell_recoveries_to_target_share": "208"},
                ]
            ).to_csv(progress_detail, index=False)
            pd.DataFrame(
                [
                    {
                        "review_rank": "1",
                        "article_id": "a1",
                        "recovery_batch": "R001",
                        "recovery_rank": "1",
                        "recovery_priority": "high",
                        "recovery_action": "extend_existing_short_abstract",
                        "recovery_reason": "partial_text",
                        "title": "A Paper",
                        "action_group": "find_external_extension",
                        "quick_win_tier": "tier_1_partial_near_threshold",
                        "cell_target_rank": "2",
                        "cell_target_level": "critical",
                        "cell_recoveries_to_target_share": "208",
                        "reviewer_action": "Find an extension.",
                        "source_to_avoid": "Do not rerun cached source.",
                        "suggested_evidence_tier": "tier_b_source_description",
                        "candidate_source": "OpenAlex",
                        "abstract": "",
                        "source": "",
                        "source_url": "",
                        "source_record_id": "",
                        "evidence_tier": "",
                        "notes": "",
                    }
                ]
            ).to_csv(packet_dir / "action.csv", index=False)

            with contextlib.redirect_stdout(io.StringIO()):
                packet, summary = run_recovery_kickoff_packet(
                    progress_detail_path=progress_detail,
                    action_packet_dir=packet_dir,
                    output_csv=output_csv,
                    output_html=output_html,
                    output_summary=summary_output,
                    report_path=report,
                    limit=20,
                )

            self.assertEqual(len(packet), 1)
            self.assertFalse(summary.empty)
            self.assertTrue(output_csv.exists())
            self.assertTrue(output_html.exists())
            self.assertTrue(summary_output.exists())
            self.assertTrue(report.exists())
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("Recovery Batch R001 Kickoff Packet", report_text)
            self.assertIn("## Review Checklist", report_text)
            self.assertIn("tier_a_formal_abstract", report_text)
            self.assertIn("run_recovery_split_preflight.py", report_text)
            html = output_html.read_text(encoding="utf-8")
            self.assertIn("Insufficient Text Recovery R001 Kickoff Top 20", html)
            self.assertIn("Export CSV", html)
            self.assertIn("data-name=\"abstract\"", html)
            summary_lookup = dict(zip(summary["metric"], summary["value"]))
            self.assertEqual(summary_lookup["suggested_evidence_tiers"], "tier_b_source_description")
            self.assertEqual(summary_lookup["candidate_sources"], "OpenAlex")


if __name__ == "__main__":
    unittest.main()
