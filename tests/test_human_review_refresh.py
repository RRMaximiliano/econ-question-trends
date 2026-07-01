from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "code" / "05_analysis"))

from human_review_refresh import refresh_steps, run_human_review_refresh  # noqa: E402


class HumanReviewRefreshTests(unittest.TestCase):
    def test_refresh_steps_are_in_dependency_order(self) -> None:
        steps = refresh_steps("python")
        step_ids = [step.step_id for step in steps]

        self.assertEqual(step_ids[0], "calibration")
        self.assertLess(step_ids.index("scope_review_audit"), step_ids.index("scope_review_packet"))
        self.assertLess(step_ids.index("scope_review_packet"), step_ids.index("project_status"))
        self.assertLess(step_ids.index("scope_review_packet"), step_ids.index("scope_review_apply_dry_run"))
        self.assertLess(step_ids.index("scope_review_apply_dry_run"), step_ids.index("project_status"))
        self.assertLess(step_ids.index("scope_review_apply_dry_run"), step_ids.index("recent_recovery_pilot"))
        self.assertLess(step_ids.index("recent_recovery_pilot"), step_ids.index("recovery_batch_workplan"))
        self.assertLess(step_ids.index("recovery_batch_workplan"), step_ids.index("recovery_batch_split"))
        self.assertLess(step_ids.index("recovery_batch_split"), step_ids.index("recovery_review_queue"))
        self.assertLess(step_ids.index("recovery_review_queue"), step_ids.index("recovery_cell_targets"))
        self.assertLess(step_ids.index("recovery_review_queue"), step_ids.index("recovery_cached_evidence"))
        self.assertLess(step_ids.index("recovery_cell_targets"), step_ids.index("recovery_cached_evidence"))
        self.assertLess(step_ids.index("recovery_automation_audit"), step_ids.index("recovery_cached_evidence"))
        self.assertLess(step_ids.index("recovery_cached_evidence"), step_ids.index("recovery_tiered_stage"))
        self.assertLess(step_ids.index("recovery_split_preflight"), step_ids.index("recovery_action_progress"))
        self.assertLess(step_ids.index("recovery_action_progress"), step_ids.index("recovery_kickoff_packet"))
        self.assertLess(step_ids.index("recovery_kickoff_packet"), step_ids.index("human_review_workboard"))
        self.assertLess(step_ids.index("manual_validation_readiness"), step_ids.index("validation_gate"))
        self.assertLess(step_ids.index("validation_gate"), step_ids.index("project_status"))
        self.assertEqual(step_ids[-1], "human_review_workboard")

    def test_run_human_review_refresh_writes_report_and_log(self) -> None:
        calls: list[tuple[str, ...]] = []

        def fake_executor(command, **kwargs):  # type: ignore[no-untyped-def]
            calls.append(tuple(command))
            return subprocess.CompletedProcess(command, 0, stdout=f"ran {' '.join(command)}\n")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "docs" / "refresh.md"
            log = root / "logs" / "refresh.log"
            with contextlib.redirect_stdout(io.StringIO()):
                results = run_human_review_refresh(
                    python_executable="python",
                    report_path=report,
                    log_path=log,
                    executor=fake_executor,
                )
            report_text = report.read_text(encoding="utf-8")
            log_text = log.read_text(encoding="utf-8")

            self.assertEqual(len(results), len(refresh_steps("python")))
            self.assertEqual(len(calls), len(results))
            self.assertEqual(calls[0], ("python", "run_manual_validation_calibration.py"))
            self.assertIn("run_human_review_refresh.py", report_text)
            self.assertIn("scope_review_audit", report_text)
            self.assertIn("scope_review_apply_dry_run", report_text)
            self.assertIn("recent_recovery_pilot", report_text)
            self.assertIn("recovery_batch_workplan", report_text)
            self.assertIn("recovery_batch_split", report_text)
            self.assertIn("recovery_cached_evidence", report_text)
            self.assertIn("human_review_workboard", report_text)
            self.assertIn("returncode=0", log_text)

    def test_run_human_review_refresh_stops_on_first_failure(self) -> None:
        calls = 0

        def fake_executor(command, **kwargs):  # type: ignore[no-untyped-def]
            nonlocal calls
            calls += 1
            returncode = 1 if calls == 2 else 0
            return subprocess.CompletedProcess(command, returncode, stdout=f"step {calls}\n")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit):
                    run_human_review_refresh(
                        python_executable="python",
                        report_path=root / "refresh.md",
                        log_path=root / "refresh.log",
                        executor=fake_executor,
                    )

        self.assertEqual(calls, 2)


if __name__ == "__main__":
    unittest.main()
