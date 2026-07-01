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

from recovery_batch_workplan import recovery_batch_workplan, run_recovery_batch_workplan, suspect_pdf_url  # noqa: E402


class RecoveryBatchWorkplanTests(unittest.TestCase):
    def test_workplan_marks_prior_pdf_download_errors_as_blocked(self) -> None:
        batch = pd.DataFrame(
            [
                {
                    "recovery_batch": "R001",
                    "batch_row": "001",
                    "recovery_rank": "1",
                    "article_id": "a1",
                    "journal_short": "jpe",
                    "publication_year": "1980",
                    "title": "A Paper",
                    "doi": "10.1086/abc",
                    "recovery_action": "review_oa_pdf_or_first_pages",
                    "oa_pdf_url": "https://example.test/a.pdf",
                }
            ]
        )
        pdf_text = pd.DataFrame([{"article_id": "a1", "pdf_text_status": "download_error", "pdf_detail": "http_status=403"}])

        out = recovery_batch_workplan(batch, pdf_text, pd.DataFrame())

        self.assertEqual(out.iloc[0]["row_status"], "pdf_route_blocked_use_manual_metadata")
        self.assertIn("remaining_oa_pdf_download_blockers.csv", out.iloc[0]["source_artifact"])
        self.assertIn("http_status=403", out.iloc[0]["review_note"])

    def test_workplan_uses_route_matrix_for_scienceon_prefixes(self) -> None:
        batch = pd.DataFrame(
            [
                {
                    "recovery_batch": "R001",
                    "batch_row": "002",
                    "recovery_rank": "2",
                    "article_id": "a2",
                    "journal_short": "ecta",
                    "publication_year": "1980",
                    "title": "A JSTOR Paper",
                    "doi": "10.2307/123",
                    "recovery_action": "recover_abstract_from_doi_or_publisher",
                }
            ]
        )
        route_matrix = pd.DataFrame(
            [
                {
                    "route_unit": "10.2307",
                    "current_route_status": "scienceon_bounded_recovery",
                    "recommended_route_action": "Run ScienceOn in 25-row recovery-batch passes.",
                    "source_route_note": "ScienceOn is a tested public metadata route.",
                    "next_artifact": "run_scienceon_recovery_scan.py",
                }
            ]
        )

        out = recovery_batch_workplan(batch, pd.DataFrame(), route_matrix)

        self.assertEqual(out.iloc[0]["doi_prefix"], "10.2307")
        self.assertEqual(out.iloc[0]["route_status"], "scienceon_bounded_recovery")
        self.assertEqual(out.iloc[0]["row_status"], "scienceon_bounded_recovery")

    def test_workplan_rejects_suspect_non_article_pdf_url(self) -> None:
        self.assertTrue(suspect_pdf_url("https://example.test/Code of Professional Conduct Only.pdf"))
        batch = pd.DataFrame(
            [
                {
                    "recovery_batch": "R001",
                    "batch_row": "003",
                    "recovery_rank": "3",
                    "article_id": "a3",
                    "title": "An Article",
                    "doi": "10.3982/example",
                    "recovery_action": "review_oa_pdf_or_first_pages",
                    "article_url": "https://doi.org/10.3982/example",
                    "oa_pdf_url": "https://example.test/uploads/Code of Professional Conduct Only.pdf",
                }
            ]
        )

        out = recovery_batch_workplan(batch, pd.DataFrame(), pd.DataFrame())

        self.assertEqual(out.iloc[0]["row_status"], "suspect_pdf_url_use_manual_metadata")
        self.assertIn("non-article document", out.iloc[0]["review_note"])

    def test_workplan_flags_configured_nonresearch_scope_before_recovery(self) -> None:
        batch = pd.DataFrame(
            [
                {
                    "recovery_batch": "R001",
                    "batch_row": "004",
                    "recovery_rank": "4",
                    "article_id": "a4",
                    "title": "More on Prices vs. Quantities: Erratum",
                    "doi": "10.2307/example",
                    "recovery_action": "review_oa_pdf_or_first_pages",
                    "oa_pdf_url": "https://example.test/article.pdf",
                }
            ]
        )
        patterns = {"review_erratum_paratext": [r": erratum$"]}

        out = recovery_batch_workplan(batch, pd.DataFrame(), pd.DataFrame(), scope_patterns=patterns)

        self.assertEqual(out.iloc[0]["article_scope"], "review_erratum_paratext")
        self.assertEqual(out.iloc[0]["row_status"], "scope_review_before_recovery")

    def test_workplan_respects_keep_research_scope_review_decision(self) -> None:
        batch = pd.DataFrame(
            [
                {
                    "recovery_batch": "R001",
                    "batch_row": "004",
                    "recovery_rank": "4",
                    "article_id": "a4",
                    "title": "More on Prices vs. Quantities: Erratum",
                    "doi": "10.2307/example",
                    "recovery_action": "recover_abstract_from_doi_or_publisher",
                }
            ]
        )
        packet = pd.DataFrame(
            [
                {
                    "article_id": "a4",
                    "human_scope_decision": "keep_research",
                    "scope_review_notes": "substantive correction",
                }
            ]
        )
        patterns = {"review_erratum_paratext": [r": erratum$"]}

        out = recovery_batch_workplan(batch, pd.DataFrame(), pd.DataFrame(), scope_patterns=patterns, scope_packet=packet)

        self.assertEqual(out.iloc[0]["article_scope"], "research_article")
        self.assertEqual(out.iloc[0]["scope_review_decision"], "keep_research")
        self.assertNotEqual(out.iloc[0]["row_status"], "scope_review_before_recovery")

    def test_workplan_stops_excluded_scope_review_decision(self) -> None:
        batch = pd.DataFrame(
            [
                {
                    "recovery_batch": "R001",
                    "batch_row": "004",
                    "recovery_rank": "4",
                    "article_id": "a4",
                    "title": "More on Prices vs. Quantities: Erratum",
                    "doi": "10.2307/example",
                    "recovery_action": "recover_abstract_from_doi_or_publisher",
                }
            ]
        )
        packet = pd.DataFrame(
            [
                {
                    "article_id": "a4",
                    "human_scope_decision": "exclude_nonresearch",
                    "proposed_article_scope": "review_erratum_paratext",
                    "proposed_scope_reason": "title_pattern=: erratum$",
                    "scope_review_notes": "erratum only",
                }
            ]
        )

        out = recovery_batch_workplan(batch, pd.DataFrame(), pd.DataFrame(), scope_packet=packet)

        self.assertEqual(out.iloc[0]["row_status"], "scope_review_excluded_nonresearch")
        self.assertEqual(out.iloc[0]["article_scope"], "review_erratum_paratext")
        self.assertEqual(out.iloc[0]["source_artifact"], "docs/scope_review_packet.md")

    def test_workplan_pauses_unsure_scope_review_decision(self) -> None:
        batch = pd.DataFrame(
            [
                {
                    "recovery_batch": "R001",
                    "batch_row": "004",
                    "recovery_rank": "4",
                    "article_id": "a4",
                    "title": "A Correction",
                    "doi": "10.2307/example",
                    "recovery_action": "recover_abstract_from_doi_or_publisher",
                }
            ]
        )
        packet = pd.DataFrame([{"article_id": "a4", "human_scope_decision": "unsure", "scope_review_notes": "needs PI"}])

        out = recovery_batch_workplan(batch, pd.DataFrame(), pd.DataFrame(), scope_packet=packet)

        self.assertEqual(out.iloc[0]["row_status"], "scope_review_unsure_before_recovery")
        self.assertEqual(out.iloc[0]["scope_review_decision"], "unsure")

    def test_run_recovery_batch_workplan_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch_path = root / "batch.csv"
            pdf_text_path = root / "pdf_text.csv"
            route_matrix_path = root / "route_matrix.csv"
            config_path = root / "config.yml"
            output_path = root / "outputs" / "workplan.csv"
            report_path = root / "docs" / "workplan.md"
            pd.DataFrame(
                [
                    {
                        "recovery_batch": "R001",
                        "batch_row": "001",
                        "recovery_rank": "1",
                        "article_id": "a1",
                        "title": "A Paper",
                        "doi": "10.1086/abc",
                        "recovery_action": "extend_existing_short_abstract",
                    }
                ]
            ).to_csv(batch_path, index=False)
            pd.DataFrame(columns=["article_id", "pdf_text_status", "pdf_detail"]).to_csv(pdf_text_path, index=False)
            pd.DataFrame(columns=["route_unit", "current_route_status"]).to_csv(route_matrix_path, index=False)
            config_path.write_text("article_scope_patterns: {}\n", encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()):
                out = run_recovery_batch_workplan(
                    batch_path=batch_path,
                    pdf_text_path=pdf_text_path,
                    route_matrix_path=route_matrix_path,
                    scope_packet_path=None,
                    config_path=config_path,
                    output_path=output_path,
                    report_path=report_path,
                )

            self.assertEqual(len(out), 1)
            self.assertTrue(output_path.exists())
            self.assertTrue(report_path.exists())
            self.assertIn("Recovery Batch R001 Workplan", report_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
