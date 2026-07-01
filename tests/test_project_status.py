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

from project_status import project_next_actions, project_status_summary, run_project_status  # noqa: E402


def metrics(rows: dict[str, object]) -> pd.DataFrame:
    return pd.DataFrame([{"metric": key, "value": value} for key, value in rows.items()])


class ProjectStatusTests(unittest.TestCase):
    def test_project_next_actions_prioritizes_calibration(self) -> None:
        gate = metrics(
            {
                "validation_gate": "blocked_calibration",
                "next_action": "Complete the calibration packet.",
                "completed_manual_labels": 0,
                "manual_validation_total_rows": 300,
                "remaining_manual_labels": 300,
            }
        )
        calibration = metrics({"calibration_rows": 20, "completed_calibration_labels": 0})
        readiness = metrics({"ready_for_blind_review": "yes", "drifted_articles": 0})
        recovery = metrics({"remaining_backfill_abstracts": 100, "next_recovery_batch": "R001"})
        route_matrix = pd.DataFrame()

        actions = project_next_actions(gate, recovery, calibration, readiness, route_matrix)

        self.assertEqual(actions.iloc[0]["action_id"], "complete_calibration_packet")
        self.assertEqual(actions.iloc[0]["status"], "blocking_human")
        self.assertIn("remaining-row calibration form", actions.iloc[0]["action"])
        self.assertIn("docs/manual_validation_calibration_kickoff.md", actions.iloc[0]["source_artifact"])
        self.assertEqual(
            actions.iloc[0]["next_artifact"],
            "data/intermediate/manual_validation_calibration_forms/manual_validation_calibration_remaining.html",
        )

    def test_project_status_summary_reads_route_matrix(self) -> None:
        gate = metrics({"validation_gate": "blocked_calibration", "first_blocking_check": "calibration", "next_action": "Calibrate."})
        recovery = metrics({"remaining_backfill_abstracts": 3912, "completed_backfill_abstracts": 13, "next_recovery_batch": "R001"})
        calibration = metrics({"calibration_rows": 20, "completed_calibration_labels": 0})
        readiness = metrics({"sample_rows": 300, "completed_manual_labels": 0, "remaining_manual_labels": 300})
        route_matrix = pd.DataFrame(
            [
                {
                    "route_unit": "10.1086",
                    "row_count": "810",
                    "current_route_status": "do_not_rerun_landing_pages",
                    "recommended_route_action": "Use the investigation packet; avoid broad DOI landing-page reruns.",
                }
            ]
        )

        summary = project_status_summary(gate, recovery, calibration, readiness, route_matrix)
        lookup = dict(zip(summary["metric"], summary["value"]))

        self.assertEqual(lookup["validation_gate"], "blocked_calibration")
        self.assertEqual(lookup["calibration_progress"], "0 / 20")
        self.assertIn("manual_validation_calibration_remaining.html", dict(zip(summary["metric"], summary["note"]))["calibration_progress"])
        self.assertEqual(lookup["top_route_status"], "do_not_rerun_landing_pages")

    def test_project_status_surfaces_scope_review_candidates_when_present(self) -> None:
        gate = metrics({"validation_gate": "blocked_calibration", "next_action": "Calibrate."})
        recovery = metrics({"remaining_backfill_abstracts": 100, "next_recovery_batch": "R001"})
        calibration = metrics({"calibration_rows": 20, "completed_calibration_labels": 0})
        readiness = metrics({"ready_for_blind_review": "yes", "drifted_articles": 0})
        route_matrix = pd.DataFrame()
        scope_candidates = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "recovery_batch": "R001",
                    "proposed_article_scope": "review_erratum_paratext",
                }
            ]
        )

        summary = project_status_summary(gate, recovery, calibration, readiness, route_matrix, scope_candidates)
        actions = project_next_actions(gate, recovery, calibration, readiness, route_matrix, scope_candidates)
        lookup = dict(zip(summary["metric"], summary["value"]))

        self.assertEqual(lookup["scope_review_candidates"], "1")
        self.assertIn("review_scope_candidates", set(actions["action_id"]))
        scope_action = actions[actions["action_id"].eq("review_scope_candidates")].iloc[0]
        self.assertEqual(scope_action["priority"], 7)
        self.assertEqual(scope_action["source_artifact"], "docs/scope_review_packet.md")
        self.assertEqual(scope_action["next_artifact"], "data/intermediate/scope_review_forms/scope_review_packet.html")

    def test_project_status_reads_scope_review_completion_progress(self) -> None:
        gate = metrics({"validation_gate": "blocked_calibration", "next_action": "Calibrate."})
        recovery = metrics({"remaining_backfill_abstracts": 100, "next_recovery_batch": "R001"})
        calibration = metrics({"calibration_rows": 20, "completed_calibration_labels": 0})
        readiness = metrics({"ready_for_blind_review": "yes", "drifted_articles": 0})
        route_matrix = pd.DataFrame()
        scope_candidates = pd.DataFrame([{"article_id": "a1", "recovery_batch": "R001"}])
        scope_completion = metrics(
            {
                "scope_review_rows": 2,
                "completed_scope_review_decisions": 1,
                "remaining_scope_review_decisions": 1,
            }
        )

        summary = project_status_summary(gate, recovery, calibration, readiness, route_matrix, scope_candidates, scope_completion)
        actions = project_next_actions(gate, recovery, calibration, readiness, route_matrix, scope_candidates, scope_completion)
        lookup = dict(zip(summary["metric"], summary["value"]))
        scope_action = actions[actions["action_id"].eq("review_scope_candidates")].iloc[0]

        self.assertEqual(lookup["scope_review_progress"], "1 / 2")
        self.assertIn("1 / 2", scope_action["action"])
        self.assertEqual(scope_action["next_artifact"], "data/intermediate/scope_review_forms/scope_review_packet.html")

    def test_project_status_marks_completed_scope_review_complete_when_no_split_rows_wait(self) -> None:
        gate = metrics({"validation_gate": "blocked_calibration", "next_action": "Calibrate."})
        recovery = metrics({"remaining_backfill_abstracts": 100, "next_recovery_batch": "R001"})
        calibration = metrics({"calibration_rows": 20, "completed_calibration_labels": 0})
        readiness = metrics({"ready_for_blind_review": "yes", "drifted_articles": 0})
        route_matrix = pd.DataFrame()
        scope_candidates = pd.DataFrame([{"article_id": "a1", "recovery_batch": "R001"}])
        scope_completion = metrics(
            {
                "scope_review_rows": 1,
                "completed_scope_review_decisions": 1,
                "remaining_scope_review_decisions": 0,
            }
        )
        recovery_split_summary = pd.DataFrame(
            [
                {"recovery_batch": "R001", "split_group": "waiting_scope_review", "rows": "0"},
                {"recovery_batch": "R001", "split_group": "excluded_nonresearch", "rows": "1"},
            ]
        )

        actions = project_next_actions(
            gate,
            recovery,
            calibration,
            readiness,
            route_matrix,
            scope_candidates,
            scope_completion,
            recovery_split_summary=recovery_split_summary,
        )
        scope_action = actions[actions["action_id"].eq("review_scope_candidates")].iloc[0]

        self.assertEqual(scope_action["status"], "complete")
        self.assertIn("no recovery rows remain paused", scope_action["action"])

    def test_project_status_splits_recent_scope_review_action_when_packet_available(self) -> None:
        gate = metrics({"validation_gate": "blocked_calibration", "next_action": "Calibrate."})
        recovery = metrics({"remaining_backfill_abstracts": 100, "next_recovery_batch": "R001"})
        calibration = metrics({"calibration_rows": 20, "completed_calibration_labels": 0})
        readiness = metrics({"ready_for_blind_review": "yes", "drifted_articles": 0})
        route_matrix = pd.DataFrame()
        scope_candidates = pd.DataFrame([{"article_id": "recent"}, {"article_id": "old"}])
        scope_completion = metrics(
            {
                "scope_review_rows": 2,
                "completed_scope_review_decisions": 0,
                "remaining_scope_review_decisions": 2,
            }
        )
        scope_packet = pd.DataFrame(
            [
                {
                    "scope_review_id": "SR0001",
                    "scope_review_priority": "P1_recent_2023_2025_top5",
                    "article_id": "recent",
                    "human_scope_decision": "",
                },
                {
                    "scope_review_id": "SR0002",
                    "scope_review_priority": "P2_scope_review_backlog",
                    "article_id": "old",
                    "human_scope_decision": "",
                },
            ]
        )

        actions = project_next_actions(
            gate,
            recovery,
            calibration,
            readiness,
            route_matrix,
            scope_candidates,
            scope_completion,
            scope_packet=scope_packet,
        )

        action_ids = set(actions["action_id"])
        recent_action = actions[actions["action_id"].eq("review_recent_2023_2025_scope_candidates")].iloc[0]
        backlog_action = actions[actions["action_id"].eq("review_scope_backlog_candidates")].iloc[0]

        self.assertIn("review_recent_2023_2025_scope_candidates", action_ids)
        self.assertIn("review_scope_backlog_candidates", action_ids)
        self.assertIn("priority filter", recent_action["action"])
        self.assertIn("P1_recent_2023_2025_top5", recent_action["action"])
        self.assertIn("0 / 1", recent_action["action"])
        self.assertIn("0 / 1", backlog_action["action"])
        self.assertEqual(recent_action["source_artifact"], "docs/scope_review_packet.md")

    def test_project_status_prefers_ready_recovery_splits_when_present(self) -> None:
        gate = metrics({"validation_gate": "blocked_calibration", "next_action": "Calibrate."})
        recovery = metrics({"remaining_backfill_abstracts": 100, "next_recovery_batch": "R001"})
        calibration = metrics({"calibration_rows": 20, "completed_calibration_labels": 0})
        readiness = metrics({"ready_for_blind_review": "yes", "drifted_articles": 0})
        route_matrix = pd.DataFrame()
        recovery_split_summary = pd.DataFrame(
            [
                {"recovery_batch": "R001", "split_group": "ready_partial_text_extension", "rows": "38", "source_incomplete_backfill_abstracts": "0"},
                {"recovery_batch": "R001", "split_group": "ready_manual_metadata", "rows": "55", "source_incomplete_backfill_abstracts": "2"},
                {"recovery_batch": "R001", "split_group": "waiting_scope_review", "rows": "7", "source_incomplete_backfill_abstracts": "0"},
            ]
        )

        summary = project_status_summary(
            gate,
            recovery,
            calibration,
            readiness,
            route_matrix,
            recovery_split_summary=recovery_split_summary,
        )
        actions = project_next_actions(
            gate,
            recovery,
            calibration,
            readiness,
            route_matrix,
            recovery_split_summary=recovery_split_summary,
        )
        lookup = dict(zip(summary["metric"], summary["value"]))
        recovery_action = actions[actions["action_id"].eq("work_ready_recovery_splits")].iloc[0]

        self.assertEqual(lookup["ready_recovery_split_rows"], "93")
        self.assertEqual(lookup["waiting_scope_review_recovery_rows"], "7")
        self.assertEqual(lookup["source_incomplete_recovery_split_rows"], "2")
        self.assertIn("dry-run", recovery_action["action"])
        self.assertIn("source metadata", recovery_action["action"])
        self.assertIn("atomically", recovery_action["action"])
        self.assertIn("docs/recovery_batch_R001_split.md", recovery_action["source_artifact"])
        self.assertEqual(recovery_action["next_artifact"], "data/intermediate/insufficient_text_recovery_split_forms/R001/")

    def test_project_status_surfaces_recovery_preflight_summary(self) -> None:
        gate = metrics({"validation_gate": "blocked_calibration", "next_action": "Calibrate."})
        recovery = metrics({"remaining_backfill_abstracts": 100, "next_recovery_batch": "R001"})
        calibration = metrics({"calibration_rows": 20, "completed_calibration_labels": 0})
        readiness = metrics({"ready_for_blind_review": "yes", "drifted_articles": 0})
        route_matrix = pd.DataFrame()
        recovery_preflight_summary = pd.DataFrame(
            [
                {"split_group": "ready_partial_text_extension", "import_ready_rows": "0", "error_rows": "0"},
                {"split_group": "ready_manual_metadata", "import_ready_rows": "2", "error_rows": "1"},
            ]
        )

        summary = project_status_summary(
            gate,
            recovery,
            calibration,
            readiness,
            route_matrix,
            recovery_preflight_summary=recovery_preflight_summary,
        )
        lookup = dict(zip(summary["metric"], summary["value"]))

        self.assertEqual(lookup["recovery_preflight_import_ready_rows"], "2")
        self.assertEqual(lookup["recovery_preflight_error_rows"], "1")

    def test_project_status_prefers_ranked_review_queue_when_present(self) -> None:
        gate = metrics({"validation_gate": "blocked_calibration", "next_action": "Calibrate."})
        recovery = metrics({"remaining_backfill_abstracts": 100, "next_recovery_batch": "R001"})
        calibration = metrics({"calibration_rows": 20, "completed_calibration_labels": 0})
        readiness = metrics({"ready_for_blind_review": "yes", "drifted_articles": 0})
        route_matrix = pd.DataFrame()
        recovery_split_summary = pd.DataFrame(
            [
                {"recovery_batch": "R001", "split_group": "ready_partial_text_extension", "rows": "38"},
                {"recovery_batch": "R001", "split_group": "ready_manual_metadata", "rows": "55"},
            ]
        )
        recovery_review_queue_summary = pd.DataFrame(
            [
                {
                    "recovery_batch": "R001",
                    "review_stage": "recover_abstract",
                    "quick_win_tier": "tier_1_partial_near_threshold",
                    "split_group": "ready_partial_text_extension",
                    "row_status": "manual_extend_partial_text",
                    "rows": "12",
                },
                {
                    "recovery_batch": "R001",
                    "review_stage": "recover_abstract",
                    "quick_win_tier": "tier_2_partial_extension",
                    "split_group": "ready_partial_text_extension",
                    "row_status": "manual_extend_partial_text",
                    "rows": "26",
                },
            ]
        )

        summary = project_status_summary(
            gate,
            recovery,
            calibration,
            readiness,
            route_matrix,
            recovery_split_summary=recovery_split_summary,
            recovery_review_queue_summary=recovery_review_queue_summary,
        )
        actions = project_next_actions(
            gate,
            recovery,
            calibration,
            readiness,
            route_matrix,
            recovery_split_summary=recovery_split_summary,
            recovery_review_queue_summary=recovery_review_queue_summary,
        )
        lookup = dict(zip(summary["metric"], summary["value"]))
        recovery_action = actions[actions["action_id"].eq("work_ready_recovery_splits")].iloc[0]

        self.assertEqual(lookup["recovery_review_queue_rows"], "38")
        self.assertEqual(lookup["recovery_review_queue_tier1_rows"], "12")
        self.assertIn("tiered recovery review packets", recovery_action["action"])
        self.assertIn("stage completed tiered exports", recovery_action["action"])
        self.assertIn("38 actionable review rows", recovery_action["why"])
        self.assertEqual(recovery_action["source_artifact"], "docs/recovery_batch_R001_tiered_packets.md")
        self.assertEqual(
            recovery_action["next_artifact"],
            "data/intermediate/insufficient_text_recovery_review_forms/R001/recovery_batch_R001_kickoff_packet.html",
        )

    def test_project_status_surfaces_recovery_source_experiments_when_present(self) -> None:
        gate = metrics({"validation_gate": "blocked_calibration", "next_action": "Calibrate."})
        recovery = metrics({"remaining_backfill_abstracts": 100, "next_recovery_batch": "R001"})
        calibration = metrics({"calibration_rows": 20, "completed_calibration_labels": 0})
        readiness = metrics({"ready_for_blind_review": "yes", "drifted_articles": 0})
        route_matrix = pd.DataFrame()
        experiments = pd.DataFrame(
            [
                {
                    "experiment_rank": "1",
                    "experiment_id": "R001_partial_extension",
                    "experiment_type": "manual_partial_extension",
                }
            ]
        )

        summary = project_status_summary(
            gate,
            recovery,
            calibration,
            readiness,
            route_matrix,
            recovery_source_experiments=experiments,
        )
        actions = project_next_actions(
            gate,
            recovery,
            calibration,
            readiness,
            route_matrix,
            recovery_source_experiments=experiments,
        )
        lookup = dict(zip(summary["metric"], summary["value"]))
        impact_action = actions[actions["action_id"].eq("review_recovery_impact_experiments")].iloc[0]

        self.assertEqual(lookup["recovery_source_experiments"], "1")
        self.assertEqual(impact_action["priority"], 9)
        self.assertEqual(impact_action["source_artifact"], "docs/recovery_impact_report.md")
        self.assertEqual(impact_action["next_artifact"], "docs/recovery_impact_report.md")
        self.assertIn("R001_partial_extension", impact_action["why"])

    def test_project_status_sets_next_artifact_for_route_actions(self) -> None:
        gate = metrics({"validation_gate": "blocked_calibration", "next_action": "Calibrate."})
        recovery = metrics({"remaining_backfill_abstracts": 100, "next_recovery_batch": "R001"})
        calibration = metrics({"calibration_rows": 20, "completed_calibration_labels": 0})
        readiness = metrics({"ready_for_blind_review": "yes", "drifted_articles": 0})
        route_matrix = pd.DataFrame(
            [
                {
                    "route_unit": "10.1086",
                    "row_count": "810",
                    "current_route_status": "do_not_rerun_landing_pages",
                    "recommended_route_action": "Use the investigation packet; avoid broad DOI landing-page reruns.",
                    "source_route_note": "Probe did not find usable abstracts.",
                    "next_artifact": "outputs/tables/enriched/insufficient_text_source_investigation_packet.csv",
                }
            ]
        )

        actions = project_next_actions(gate, recovery, calibration, readiness, route_matrix)
        route_action = actions[actions["action_id"].eq("source_route_10_1086")].iloc[0]

        self.assertEqual(route_action["source_artifact"], "outputs/tables/enriched/insufficient_text_source_investigation_packet.csv")
        self.assertEqual(route_action["next_artifact"], "outputs/tables/enriched/insufficient_text_source_investigation_packet.csv")

    def test_project_status_omits_scope_review_candidates_when_absent(self) -> None:
        gate = metrics({"validation_gate": "blocked_calibration", "next_action": "Calibrate."})
        recovery = metrics({"remaining_backfill_abstracts": 100, "next_recovery_batch": "R001"})
        calibration = metrics({"calibration_rows": 20, "completed_calibration_labels": 0})
        readiness = metrics({"ready_for_blind_review": "yes", "drifted_articles": 0})
        route_matrix = pd.DataFrame()

        summary = project_status_summary(gate, recovery, calibration, readiness, route_matrix, pd.DataFrame())
        actions = project_next_actions(gate, recovery, calibration, readiness, route_matrix, pd.DataFrame())

        self.assertNotIn("scope_review_candidates", set(summary["metric"]))
        self.assertNotIn("review_scope_candidates", set(actions["action_id"]))

    def test_run_project_status_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gate_path = root / "gate.csv"
            recovery_path = root / "recovery.csv"
            calibration_path = root / "calibration.csv"
            readiness_path = root / "readiness.csv"
            route_matrix_path = root / "route_matrix.csv"
            output_summary = root / "outputs" / "project_status_summary.csv"
            output_actions = root / "outputs" / "project_next_actions.csv"
            report = root / "docs" / "project_status.md"

            metrics({"validation_gate": "blocked_calibration", "next_action": "Complete calibration."}).to_csv(gate_path, index=False)
            metrics({"remaining_backfill_abstracts": 10, "next_recovery_batch": "R001"}).to_csv(recovery_path, index=False)
            metrics({"calibration_rows": 20, "completed_calibration_labels": 0}).to_csv(calibration_path, index=False)
            metrics({"ready_for_blind_review": "yes", "drifted_articles": 0}).to_csv(readiness_path, index=False)
            pd.DataFrame(
                [
                    {
                        "route_unit": "10.1086",
                        "row_count": "810",
                        "current_route_status": "do_not_rerun_landing_pages",
                        "recommended_route_action": "Avoid broad DOI landing-page reruns.",
                        "source_route_note": "Probe did not find abstracts.",
                        "next_artifact": "outputs/tables/enriched/insufficient_text_source_investigation_packet.csv",
                    }
                ]
            ).to_csv(route_matrix_path, index=False)

            with contextlib.redirect_stdout(io.StringIO()):
                summary, actions = run_project_status(
                    gate_path=gate_path,
                    recovery_path=recovery_path,
                    calibration_path=calibration_path,
                    readiness_path=readiness_path,
                    route_matrix_path=route_matrix_path,
                    scope_candidates_path=None,
                    output_summary=output_summary,
                    output_actions=output_actions,
                    report_path=report,
                )

            self.assertTrue(output_summary.exists())
            self.assertTrue(output_actions.exists())
            self.assertFalse(summary.empty)
            self.assertIn("complete_calibration_packet", set(actions["action_id"]))
            self.assertIn("Project Status", report.read_text(encoding="utf-8"))
            self.assertIn("Source Route Snapshot", report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
