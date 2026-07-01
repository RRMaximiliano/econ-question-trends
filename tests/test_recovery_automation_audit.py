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

from recovery_automation_audit import recovery_automation_audit, run_recovery_automation_audit  # noqa: E402


class RecoveryAutomationAuditTests(unittest.TestCase):
    def test_recovery_automation_audit_classifies_safe_next_actions(self) -> None:
        queue = pd.DataFrame(
            [
                {
                    "review_rank": "1",
                    "article_id": "near",
                    "title": "Near Threshold",
                    "quick_win_tier": "tier_1_partial_near_threshold",
                    "row_status": "manual_extend_partial_text",
                    "completion_status": "needs_abstract_recovery",
                    "doi": "10.2307/1911932",
                    "current_text_chars": "247",
                    "chars_needed_to_threshold": "3",
                    "current_text_quality_flag": "",
                },
                {
                    "review_rank": "2",
                    "article_id": "boilerplate",
                    "title": "Boilerplate",
                    "quick_win_tier": "tier_2_partial_replace_suspect_text",
                    "row_status": "manual_extend_partial_text",
                    "completion_status": "needs_abstract_recovery",
                    "doi": "10.2307/1911412",
                    "current_text_quality_flag": "jstor_terms_boilerplate",
                },
                {
                    "review_rank": "3",
                    "article_id": "pdf",
                    "title": "PDF Blocked",
                    "quick_win_tier": "tier_5_manual_metadata_pdf_blocked",
                    "row_status": "pdf_route_blocked_use_manual_metadata",
                    "completion_status": "needs_abstract_recovery",
                    "doi": "10.1257/example",
                },
                {
                    "review_rank": "4",
                    "article_id": "template",
                    "title": "Template Needed",
                    "quick_win_tier": "tier_4_manual_metadata_has_context",
                    "row_status": "manual_index_or_new_template",
                    "completion_status": "needs_abstract_recovery",
                    "doi": "10.1111/example",
                },
            ]
        )
        source_guide = pd.DataFrame(
            [
                {"article_id": "near", "source_route_family": "partial_text_extension"},
                {"article_id": "boilerplate", "source_route_family": "partial_text_extension"},
                {"article_id": "pdf", "source_route_family": "pdf_blocker_metadata"},
                {"article_id": "template", "source_route_family": "wiley_or_society_metadata"},
            ]
        )
        route_matrix = pd.DataFrame(
            [
                {
                    "route_unit": "10.2307",
                    "decision": "new_source_template_or_manual_recovery",
                    "current_route_status": "unsupported_existing_route",
                    "source_route_note": "Probe found access challenges.",
                },
                {
                    "route_unit": "oa_pdf_review",
                    "decision": "inspect_pdf_blockers",
                    "current_route_status": "manual_pdf_blocker_review",
                    "source_route_note": "Use reachable PDFs only.",
                },
                {
                    "route_unit": "10.1111",
                    "decision": "new_source_template_or_manual_recovery",
                    "current_route_status": "unsupported_existing_route",
                    "source_route_note": "No public metadata template.",
                },
            ]
        )

        detail, summary = recovery_automation_audit(queue, source_guide, route_matrix)
        statuses = dict(zip(detail["article_id"], detail["automation_status"]))

        self.assertEqual(statuses["near"], "manual_near_threshold_extension")
        self.assertEqual(statuses["boilerplate"], "manual_replace_boilerplate")
        self.assertEqual(statuses["pdf"], "manual_metadata_after_pdf_block")
        self.assertEqual(statuses["template"], "manual_index_or_template_spike_required")
        self.assertIn("manual_replace_boilerplate", set(summary["automation_status"]))
        self.assertIn("access challenges", detail.loc[detail["article_id"].eq("near"), "source_route_note"].iloc[0])

    def test_run_recovery_automation_audit_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue_path = root / "queue.csv"
            guide_path = root / "guide.csv"
            route_path = root / "routes.csv"
            detail_output = root / "outputs" / "detail.csv"
            summary_output = root / "outputs" / "summary.csv"
            report_path = root / "docs" / "audit.md"
            pd.DataFrame(
                [
                    {
                        "review_rank": "1",
                        "article_id": "a1",
                        "title": "A",
                        "quick_win_tier": "tier_1_partial_near_threshold",
                        "completion_status": "needs_abstract_recovery",
                        "doi": "",
                    }
                ]
            ).to_csv(queue_path, index=False)
            pd.DataFrame([{"article_id": "a1", "source_route_family": "partial_text_extension"}]).to_csv(guide_path, index=False)
            pd.DataFrame([{"route_unit": "partial_short_text_extension", "current_route_status": "manual_partial_abstract_extension"}]).to_csv(route_path, index=False)

            with contextlib.redirect_stdout(io.StringIO()):
                detail, summary = run_recovery_automation_audit(
                    queue_path=queue_path,
                    source_guide_path=guide_path,
                    route_matrix_path=route_path,
                    detail_output=detail_output,
                    summary_output=summary_output,
                    report_path=report_path,
                )

            self.assertEqual(len(detail), 1)
            self.assertFalse(summary.empty)
            self.assertTrue(detail_output.exists())
            self.assertTrue(summary_output.exists())
            self.assertTrue(report_path.exists())
            self.assertIn("Recovery Automation Audit", report_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
