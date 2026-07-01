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

from human_review_workboard import first_session_checklist, human_review_workboard, run_human_review_workboard  # noqa: E402


def metrics(rows: dict[str, object]) -> pd.DataFrame:
    return pd.DataFrame([{"metric": key, "value": value} for key, value in rows.items()])


class HumanReviewWorkboardTests(unittest.TestCase):
    def test_human_review_workboard_orders_blocking_and_parallel_tasks(self) -> None:
        workboard = human_review_workboard(
            calibration_summary=metrics({"calibration_rows": 20, "completed_calibration_labels": 0}),
            calibration_kickoff=pd.DataFrame(),
            calibration_guide_summary=pd.DataFrame(
                [
                    {"section": "review_difficulty", "value": "high", "rows": "7"},
                    {"section": "text_status", "value": "no_abstract", "rows": "5"},
                ]
            ),
            scope_completion=metrics(
                {
                    "scope_review_rows": 2,
                    "completed_scope_review_decisions": 0,
                    "remaining_scope_review_decisions": 2,
                }
            ),
            scope_packet=pd.DataFrame(
                [
                    {
                        "scope_review_id": "SR0001",
                        "scope_review_priority": "P1_recent_2023_2025_top5",
                        "title": "Retraction of Research Article",
                        "human_scope_decision": "",
                    },
                    {
                        "scope_review_id": "SR0002",
                        "scope_review_priority": "P2_scope_review_backlog",
                        "title": "A Correction",
                        "human_scope_decision": "",
                    }
                ]
            ),
            recovery_queue_summary=pd.DataFrame(
                [
                    {"quick_win_tier": "tier_1_partial_near_threshold", "rows": "19"},
                    {"quick_win_tier": "tier_2_partial_replace_suspect_text", "rows": "9"},
                    {"quick_win_tier": "tier_3_partial_extension", "rows": "10"},
                    {"quick_win_tier": "tier_4_manual_metadata_has_context", "rows": "41"},
                    {"quick_win_tier": "tier_5_manual_metadata_pdf_blocked", "rows": "14"},
                ]
            ),
            recovery_queue=pd.DataFrame(
                [
                    {
                        "review_rank": "1",
                        "title": "A Near Threshold Paper",
                        "chars_needed_to_threshold": "3",
                    }
                ]
            ),
            recovery_preflight_summary=pd.DataFrame([{"import_ready_rows": "0", "error_rows": "0"}]),
            recovery_automation_summary=pd.DataFrame(
                [
                    {"automation_status": "manual_near_threshold_extension", "rows": "19"},
                    {"automation_status": "manual_replace_boilerplate", "rows": "9"},
                    {"automation_status": "manual_partial_extension", "rows": "10"},
                    {"automation_status": "manual_index_or_template_spike_required", "rows": "41"},
                    {"automation_status": "manual_metadata_after_pdf_block", "rows": "14"},
                ]
            ),
            validation_gate=metrics(
                {
                    "manual_validation_total_rows": 300,
                    "completed_manual_labels": 0,
                    "remaining_manual_labels": 300,
                }
            ),
            recent_recovery_summary=metrics(
                {
                    "recent_queue_rows": 14,
                    "recent_scope_review_first_rows": 11,
                    "recent_recover_text_rows": 3,
                    "recent_recovery_packet_rows": 3,
                }
            ),
            recent_recovery_packet=pd.DataFrame(
                [
                    {
                        "article_id": "recent1",
                        "journal_short": "jpe",
                        "publication_year": "2024",
                        "title": "Online Business Models, Digital Ads, and User Welfare",
                    }
                ]
            ),
        )

        self.assertEqual(list(workboard["task_id"]), [
            "complete_calibration_packet",
            "complete_recent_2023_2025_scope_review",
            "work_recent_2023_2025_recovery_pilot",
            "complete_scope_review_backlog",
            "work_ranked_recovery_queue",
            "hold_main_validation_until_calibration",
        ])
        calibration = workboard[workboard["task_id"].eq("complete_calibration_packet")].iloc[0]
        recent_scope = workboard[workboard["task_id"].eq("complete_recent_2023_2025_scope_review")].iloc[0]
        scope_backlog = workboard[workboard["task_id"].eq("complete_scope_review_backlog")].iloc[0]
        recent = workboard[workboard["task_id"].eq("work_recent_2023_2025_recovery_pilot")].iloc[0]
        recovery = workboard[workboard["task_id"].eq("work_ranked_recovery_queue")].iloc[0]
        main_validation = workboard[workboard["task_id"].eq("hold_main_validation_until_calibration")].iloc[0]

        self.assertEqual(calibration["status"], "blocking")
        self.assertEqual(calibration["rows_remaining"], 20)
        self.assertIn("7 high-difficulty", calibration["first_item"])
        self.assertIn("blocks main validation", calibration["gate_rule"])
        self.assertIn("complete the remaining-row form", calibration["first_session_action"])
        self.assertIn("manual_validation_calibration_dashboard.html", calibration["form_or_queue"])
        self.assertIn("calibration dashboard", calibration["note"])
        self.assertEqual(recent_scope["status"], "ready_parallel")
        self.assertEqual(recent_scope["rows_total"], 1)
        self.assertIn("SR0001", recent_scope["first_item"])
        self.assertIn("unblocks recent 2023-2025", recent_scope["gate_rule"])
        self.assertIn("priority filter", recent_scope["first_session_action"])
        self.assertIn("P1_recent_2023_2025_top5", recent_scope["first_session_action"])
        self.assertIn("dry-run scope application", recent_scope["first_session_action"])
        self.assertIn("full canonical packet", recent_scope["note"])
        self.assertIn("recent top-5 denominator check", recent_scope["note"])
        self.assertIn("dry-run by default", recent_scope["note"])
        self.assertIn("--apply only after", recent_scope["note"])
        self.assertEqual(scope_backlog["status"], "ready_parallel")
        self.assertEqual(scope_backlog["rows_total"], 1)
        self.assertIn("SR0002", scope_backlog["first_item"])
        self.assertIn("remaining scope packet rows", scope_backlog["first_session_action"])
        self.assertIn("scope_review_guide.md", scope_backlog["note"])
        self.assertIn("bulk-fill", scope_backlog["note"])
        self.assertEqual(recent["status"], "ready_parallel")
        self.assertEqual(recent["rows_total"], 14)
        self.assertIn("recent 2023-2025 recovery form", recent["first_session_action"])
        self.assertIn("scope-review-first", recent["note"])
        self.assertIn("run_import_abstract_backfill.py", recent["next_command"])
        self.assertEqual(recovery["rows_total"], 93)
        self.assertIn("do not import recovered text", recovery["gate_rule"])
        self.assertIn("20-row R001 kickoff form", recovery["first_session_action"])
        self.assertIn("recovery_batch_R001_kickoff_packet.html", recovery["form_or_queue"])
        self.assertIn("recovery_batch_R001_kickoff_packet.md", recovery["recommended_artifact"])
        self.assertIn("run_recovery_tiered_stage.py", recovery["next_command"])
        self.assertIn("run_recovery_cached_evidence.py", recovery["next_command"])
        self.assertIn("run_recovery_action_progress.py", recovery["next_command"])
        self.assertIn("run_recovery_kickoff_packet.py", recovery["next_command"])
        self.assertIn("recovery_batch_R001_staged_split_summary.csv", recovery["next_command"])
        self.assertIn("recovery_batch_R001_kickoff_packet.html", recovery["note"])
        self.assertIn("20-row target-aware first session", recovery["note"])
        self.assertIn("action forms", recovery["note"])
        self.assertIn("recovery_batch_R001_action_dashboard.html", recovery["note"])
        self.assertIn("recovery_batch_R001_action_packet.md", recovery["note"])
        self.assertIn("recovery_batch_R001_action_packet_index.csv", recovery["note"])
        self.assertIn("full 93-row queue", recovery["note"])
        self.assertIn("insufficient_text_recovery_review_forms/R001/actions", recovery["note"])
        self.assertIn("recovery_batch_R001_source_guide.md", recovery["note"])
        self.assertIn("recovery_batch_R001_cached_evidence.md", recovery["note"])
        self.assertIn("recovery_batch_R001_action_progress.md", recovery["note"])
        self.assertIn("near-threshold", recovery["note"])
        self.assertIn("suspect replacement", recovery["note"])
        self.assertIn("deeper partial-extension", recovery["note"])
        self.assertIn("manual metadata", recovery["note"])
        self.assertIn("recovery_automation_audit.md", recovery["note"])
        self.assertIn("replace-boilerplate", recovery["note"])
        self.assertEqual(main_validation["status"], "waiting_on_calibration")
        self.assertIn("waits on calibration gate", main_validation["gate_rule"])
        self.assertIn("Hold the 300-row validation sample", main_validation["first_session_action"])

        checklist = first_session_checklist(workboard)
        self.assertEqual(len(checklist), 6)
        self.assertIn("calibration (blocking)", checklist[0])
        self.assertIn("blocks main validation", checklist[0])
        self.assertIn("recent_scope_review (ready_parallel)", checklist[1])
        self.assertIn("recent_recovery (ready_parallel)", checklist[2])
        self.assertIn("scope_review_backlog (ready_parallel)", checklist[3])
        self.assertIn("recovery (ready_parallel)", checklist[4])
        self.assertIn("manual_validation (waiting_on_calibration)", checklist[5])

    def test_human_review_workboard_marks_main_validation_ready_after_calibration(self) -> None:
        workboard = human_review_workboard(
            calibration_summary=metrics({"calibration_rows": 20, "completed_calibration_labels": 20}),
            calibration_kickoff=pd.DataFrame(),
            calibration_guide_summary=pd.DataFrame(),
            scope_completion=pd.DataFrame(),
            scope_packet=pd.DataFrame(),
            recovery_queue_summary=pd.DataFrame(),
            recovery_queue=pd.DataFrame(),
            recovery_preflight_summary=pd.DataFrame(),
            recovery_automation_summary=pd.DataFrame(),
            validation_gate=metrics(
                {
                    "manual_validation_total_rows": 300,
                    "completed_manual_labels": 0,
                    "remaining_manual_labels": 300,
                    "ready_for_blind_review": "yes",
                    "drifted_articles": 0,
                }
            ),
        )

        main_validation = workboard[workboard["task_id"].eq("hold_main_validation_until_calibration")].iloc[0]
        calibration = workboard[workboard["task_id"].eq("complete_calibration_packet")].iloc[0]

        self.assertEqual(calibration["status"], "complete")
        self.assertEqual(main_validation["status"], "ready")
        self.assertIn("Open B001", main_validation["first_session_action"])
        self.assertIn("sample is drift-free", main_validation["note"])

    def test_human_review_workboard_holds_main_validation_on_sample_drift(self) -> None:
        workboard = human_review_workboard(
            calibration_summary=metrics({"calibration_rows": 20, "completed_calibration_labels": 20}),
            calibration_kickoff=pd.DataFrame(),
            calibration_guide_summary=pd.DataFrame(),
            scope_completion=pd.DataFrame(),
            scope_packet=pd.DataFrame(),
            recovery_queue_summary=pd.DataFrame(),
            recovery_queue=pd.DataFrame(),
            recovery_preflight_summary=pd.DataFrame(),
            recovery_automation_summary=pd.DataFrame(),
            validation_gate=metrics(
                {
                    "manual_validation_total_rows": 300,
                    "completed_manual_labels": 0,
                    "remaining_manual_labels": 300,
                    "ready_for_blind_review": "no",
                    "drifted_articles": 2,
                }
            ),
        )

        main_validation = workboard[workboard["task_id"].eq("hold_main_validation_until_calibration")].iloc[0]

        self.assertEqual(main_validation["status"], "waiting_on_sample_readiness")
        self.assertIn("Resolve sample drift", main_validation["first_session_action"])

    def test_run_human_review_workboard_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "outputs" / "workboard.csv"
            report = root / "docs" / "workboard.md"
            calibration_summary = root / "calibration_summary.csv"
            calibration_kickoff = root / "calibration_kickoff.csv"
            calibration_guide_summary = root / "calibration_guide_summary.csv"
            scope_completion = root / "scope_completion.csv"
            scope_packet = root / "scope_packet.csv"
            recovery_queue_summary = root / "recovery_queue_summary.csv"
            recovery_queue = root / "recovery_queue.csv"
            recovery_preflight = root / "recovery_preflight.csv"
            recovery_automation = root / "recovery_automation.csv"
            validation_gate = root / "gate.csv"

            metrics({"calibration_rows": 20, "completed_calibration_labels": 0}).to_csv(calibration_summary, index=False)
            pd.DataFrame().to_csv(calibration_kickoff, index=False)
            pd.DataFrame([{"section": "review_difficulty", "value": "high", "rows": "1"}]).to_csv(calibration_guide_summary, index=False)
            metrics({"scope_review_rows": 1, "completed_scope_review_decisions": 0, "remaining_scope_review_decisions": 1}).to_csv(scope_completion, index=False)
            pd.DataFrame([{"scope_review_id": "SR0001", "title": "A Correction", "human_scope_decision": ""}]).to_csv(scope_packet, index=False)
            pd.DataFrame([{"quick_win_tier": "tier_1_partial_near_threshold", "rows": "2"}]).to_csv(recovery_queue_summary, index=False)
            pd.DataFrame([{"review_rank": "1", "title": "A Paper", "chars_needed_to_threshold": "5"}]).to_csv(recovery_queue, index=False)
            pd.DataFrame([{"import_ready_rows": "0", "error_rows": "0"}]).to_csv(recovery_preflight, index=False)
            pd.DataFrame([{"automation_status": "manual_near_threshold_extension", "rows": "2"}]).to_csv(recovery_automation, index=False)
            metrics({"manual_validation_total_rows": 300, "completed_manual_labels": 0, "remaining_manual_labels": 300}).to_csv(validation_gate, index=False)

            with contextlib.redirect_stdout(io.StringIO()):
                workboard = run_human_review_workboard(
                    calibration_summary_path=calibration_summary,
                    calibration_kickoff_path=calibration_kickoff,
                    calibration_guide_summary_path=calibration_guide_summary,
                    scope_completion_path=scope_completion,
                    scope_packet_path=scope_packet,
                    recovery_queue_summary_path=recovery_queue_summary,
                    recovery_queue_path=recovery_queue,
                    recovery_preflight_summary_path=recovery_preflight,
                    recovery_automation_summary_path=recovery_automation,
                    validation_gate_path=validation_gate,
                    output_path=output,
                    report_path=report,
                )

            self.assertFalse(workboard.empty)
            self.assertTrue(output.exists())
            self.assertTrue(report.exists())
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("Human Review Workboard", report_text)
            self.assertIn("First Session Checklist", report_text)
            self.assertIn("calibration (blocking)", report_text)
            self.assertIn("Gate:", report_text)


if __name__ == "__main__":
    unittest.main()
