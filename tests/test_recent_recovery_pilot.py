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

from recent_recovery_pilot import (  # noqa: E402
    recent_recovery_packet,
    recent_recovery_summary,
    recent_recovery_triage,
    run_recent_recovery_pilot,
)


class RecentRecoveryPilotTests(unittest.TestCase):
    def test_recent_recovery_triage_splits_scope_first_and_recover_text_rows(self) -> None:
        queue = pd.DataFrame(
            [
                {
                    "article_id": "scope-first",
                    "journal_short": "jpe",
                    "publication_year": "2023",
                    "title": "Back Cover",
                    "doi": "10.1086/724170",
                    "recovery_batch": "R035",
                    "recovery_rank": "3403",
                    "recovery_action": "recover_abstract_from_doi_or_publisher",
                    "text_enrichment_status": "not_found",
                },
                {
                    "article_id": "recover-text",
                    "journal_short": "jpe",
                    "publication_year": "2024",
                    "title": "Online Business Models, Digital Ads, and User Welfare",
                    "doi": "10.1086/742715",
                    "recovery_batch": "R035",
                    "recovery_rank": "3407",
                    "recovery_action": "recover_abstract_from_doi_or_publisher",
                    "text_enrichment_status": "not_found",
                },
                {
                    "article_id": "old-row",
                    "journal_short": "jpe",
                    "publication_year": "2022",
                    "title": "Old Row",
                    "doi": "10.1086/000000",
                },
            ]
        )
        scope_packet = pd.DataFrame([{"article_id": "scope-first"}])

        triage = recent_recovery_triage(queue, scope_packet, years=["2023", "2024", "2025"], journals=["jpe"])
        packet = recent_recovery_packet(triage)
        summary = recent_recovery_summary(triage, packet, years=["2023", "2024", "2025"], journals=["jpe"])
        lookup = dict(zip(summary["metric"], summary["value"]))

        self.assertEqual(triage["article_id"].tolist(), ["recover-text", "scope-first"])
        self.assertEqual(triage["recent_lane"].tolist(), ["recover_text", "scope_review_first"])
        self.assertEqual(packet["article_id"].tolist(), ["recover-text"])
        self.assertEqual(lookup["recent_queue_rows"], 2)
        self.assertEqual(lookup["recent_scope_review_first_rows"], 1)
        self.assertEqual(lookup["recent_recover_text_rows"], 1)
        self.assertIn("jpe_chicago_or_repec", set(triage["source_route_family"]))

    def test_run_recent_recovery_pilot_writes_packet_form_summary_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue_path = root / "queue.csv"
            scope_path = root / "scope.csv"
            triage_output = root / "outputs" / "triage.csv"
            packet_output = root / "outputs" / "packet.csv"
            summary_output = root / "outputs" / "summary.csv"
            form_output = root / "forms" / "recent.html"
            report = root / "docs" / "recent.md"
            export_path = root / "exports" / "recent.csv"

            pd.DataFrame(
                [
                    {
                        "article_id": "scope-first",
                        "journal_short": "jpe",
                        "publication_year": "2023",
                        "title": "Back Cover",
                        "doi": "10.1086/724170",
                        "recovery_batch": "R035",
                        "recovery_rank": "3403",
                        "recovery_action": "recover_abstract_from_doi_or_publisher",
                    },
                    {
                        "article_id": "recover-text",
                        "journal_short": "jpe",
                        "publication_year": "2024",
                        "title": "Online Business Models, Digital Ads, and User Welfare",
                        "doi": "10.1086/742715",
                        "recovery_batch": "R035",
                        "recovery_rank": "3407",
                        "recovery_action": "recover_abstract_from_doi_or_publisher",
                    },
                ]
            ).to_csv(queue_path, index=False)
            pd.DataFrame([{"article_id": "scope-first"}]).to_csv(scope_path, index=False)

            with contextlib.redirect_stdout(io.StringIO()):
                triage, packet, summary = run_recent_recovery_pilot(
                    recovery_queue_path=queue_path,
                    scope_packet_path=scope_path,
                    triage_output=triage_output,
                    packet_output=packet_output,
                    summary_output=summary_output,
                    form_output=form_output,
                    report_path=report,
                    export_path=export_path,
                    years=["2023", "2024", "2025"],
                    journals=["jpe"],
                )

            self.assertEqual(len(triage), 2)
            self.assertEqual(len(packet), 1)
            self.assertFalse(summary.empty)
            self.assertTrue(triage_output.exists())
            self.assertTrue(packet_output.exists())
            self.assertTrue(summary_output.exists())
            self.assertTrue(form_output.exists())
            self.assertTrue(report.exists())
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("Recent 2023-2025 Recovery Pilot", report_text)
            self.assertIn("scope_review_first", report_text)
            self.assertIn("run_import_abstract_backfill.py", report_text)
            self.assertIn("--dry-run --require-source-metadata", report_text)
            self.assertIn(
                "run_classification_pilot.py --input data/final/articles_enriched_pilot.csv --output data/final/articles_classified_enriched_pilot.csv",
                report_text,
            )
            self.assertIn("docs/classification_diagnostics_enriched.md", report_text)
            html = form_output.read_text(encoding="utf-8")
            self.assertIn("Recent 2023-2025 Insufficient Text Recovery", html)
            self.assertIn("Export CSV", html)


if __name__ == "__main__":
    unittest.main()
