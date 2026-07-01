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

from insufficient_text_expansion import doi_prefix_family, doi_prefix_suggested_command, expansion_lane, insufficient_text_expansion_plan, recovery_decision_plan, run_expansion_plan, source_investigation_packet, source_route_matrix  # noqa: E402


class InsufficientTextExpansionTests(unittest.TestCase):
    def test_expansion_lane_maps_actions_and_doi_families(self) -> None:
        self.assertEqual(expansion_lane({"recovery_action": "review_oa_pdf_or_first_pages", "doi": ""}), "oa_pdf_review")
        self.assertEqual(expansion_lane({"recovery_action": "extend_existing_short_abstract", "doi": ""}), "partial_short_text_extension")
        self.assertEqual(
            expansion_lane({"recovery_action": "recover_abstract_from_doi_or_publisher", "doi": "https://doi.org/10.1086/123"}),
            "jpe_chicago_or_repec_10_1086",
        )
        self.assertEqual(
            expansion_lane({"recovery_action": "recover_abstract_from_doi_or_publisher", "doi": "10.3982/test"}),
            "econometric_society_10_3982",
        )
        self.assertEqual(expansion_lane({"recovery_action": "review_openalex_or_title_match", "doi": ""}), "openalex_or_title_search")

    def test_doi_prefix_family_keeps_useful_journal_prefixes(self) -> None:
        self.assertEqual(doi_prefix_family("https://doi.org/10.1093/qje/qjs001"), "10.1093/qje")
        self.assertEqual(doi_prefix_family("10.1093/restud/rdx001"), "10.1093/restud")
        self.assertEqual(doi_prefix_family("10.1111/j.1468-0262.2004.00500.x"), "10.1111")

    def test_doi_prefix_commands_use_supported_routes_when_available(self) -> None:
        self.assertIn("run_scienceon_recovery_scan.py", doi_prefix_suggested_command("10.2307", 100))
        self.assertIn("No automated publisher_metadata route", doi_prefix_suggested_command("10.1093/qje", 20))
        self.assertIn("No automated publisher_metadata route", doi_prefix_suggested_command("10.1108", 20))
        self.assertIn("--doi-prefixes 10.3982", doi_prefix_suggested_command("10.3982", 20))

    def test_insufficient_text_expansion_plan_summarizes_lanes(self) -> None:
        queue = pd.DataFrame(
            [
                {
                    "recovery_rank": "1",
                    "recovery_priority": "high",
                    "recovery_action": "recover_abstract_from_doi_or_publisher",
                    "article_id": "a1",
                    "journal_short": "jpe",
                    "decade": "1980",
                    "doi": "10.1086/abc",
                    "openalex_id": "W1",
                    "oa_pdf_url": "",
                    "text_enrichment_status": "not_found",
                },
                {
                    "recovery_rank": "2",
                    "recovery_priority": "high",
                    "recovery_action": "recover_abstract_from_doi_or_publisher",
                    "article_id": "a2",
                    "journal_short": "jpe",
                    "decade": "1980",
                    "doi": "10.1086/def",
                    "openalex_id": "W2",
                    "oa_pdf_url": "",
                    "text_enrichment_status": "not_found",
                },
                {
                    "recovery_rank": "3",
                    "recovery_priority": "medium",
                    "recovery_action": "review_openalex_or_title_match",
                    "article_id": "a3",
                    "journal_short": "aer",
                    "decade": "1970",
                    "doi": "",
                    "openalex_id": "W3",
                    "oa_pdf_url": "",
                    "text_enrichment_status": "not_found",
                },
            ]
        )

        overview, detail, doi_prefixes, attempt_summary = insufficient_text_expansion_plan(queue)
        indexed = overview.set_index("expansion_lane")

        self.assertTrue(attempt_summary.empty)
        self.assertEqual(int(indexed.loc["jpe_chicago_or_repec_10_1086", "row_count"]), 2)
        self.assertEqual(int(indexed.loc["jpe_chicago_or_repec_10_1086", "high_priority_rows"]), 2)
        self.assertIn("--doi-prefixes 10.1086", indexed.loc["jpe_chicago_or_repec_10_1086", "suggested_command"])
        self.assertIn("jpe 1980 (2)", indexed.loc["jpe_chicago_or_repec_10_1086", "top_journal_decades"])
        self.assertEqual(detail.iloc[0]["expansion_lane"], "jpe_chicago_or_repec_10_1086")
        prefix_indexed = doi_prefixes.set_index("doi_prefix")
        self.assertEqual(int(prefix_indexed.loc["10.1086", "row_count"]), 2)
        self.assertIn("--doi-prefixes 10.1086", prefix_indexed.loc["10.1086", "suggested_command"])

    def test_insufficient_text_expansion_plan_summarizes_prior_attempts(self) -> None:
        queue = pd.DataFrame(
            [
                {
                    "recovery_rank": "1",
                    "recovery_priority": "high",
                    "recovery_action": "recover_abstract_from_doi_or_publisher",
                    "article_id": "a1",
                    "journal_short": "jpe",
                    "decade": "1980",
                    "doi": "10.1086/abc",
                    "openalex_id": "W1",
                    "oa_pdf_url": "",
                    "text_enrichment_status": "not_found",
                },
                {
                    "recovery_rank": "2",
                    "recovery_priority": "high",
                    "recovery_action": "recover_abstract_from_doi_or_publisher",
                    "article_id": "a2",
                    "journal_short": "jpe",
                    "decade": "1980",
                    "doi": "10.1086/def",
                    "openalex_id": "W2",
                    "oa_pdf_url": "",
                    "text_enrichment_status": "not_found",
                },
            ]
        )
        attempts = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "doi": "10.1086/abc",
                    "attempt_source": "econpapers",
                    "attempt_status": "found",
                    "attempt_error": "",
                },
                {
                    "article_id": "a2",
                    "doi": "10.1086/def",
                    "attempt_source": "econpapers",
                    "attempt_status": "error",
                    "attempt_error": "Not Found",
                },
                {
                    "article_id": "a3",
                    "doi": "10.1086/ghi",
                    "attempt_source": "econpapers",
                    "attempt_status": "not_found",
                    "attempt_error": "",
                },
            ]
        )

        _, _, doi_prefixes, attempt_summary = insufficient_text_expansion_plan(queue, attempts)

        prefix = doi_prefixes.set_index("doi_prefix").loc["10.1086"]
        self.assertEqual(int(prefix["prior_attempted_articles"]), 3)
        self.assertEqual(int(prefix["prior_found_articles"]), 1)
        self.assertEqual(int(prefix["prior_error_attempts"]), 1)
        self.assertEqual(int(prefix["prior_not_found_attempts"]), 1)
        self.assertIn("mostly failed", prefix["prior_attempt_note"])
        attempt = attempt_summary.set_index(["doi_prefix", "attempt_source"]).loc[("10.1086", "econpapers")]
        self.assertEqual(int(attempt["found_attempts"]), 1)
        self.assertIn("Not Found (1)", attempt["top_errors"])

    def test_recovery_decision_plan_flags_failed_prefix_reruns(self) -> None:
        queue = pd.DataFrame(
            [
                {
                    "recovery_rank": "1",
                    "recovery_priority": "high",
                    "recovery_action": "recover_abstract_from_doi_or_publisher",
                    "article_id": "a1",
                    "journal_short": "jpe",
                    "decade": "1980",
                    "doi": "10.1086/abc",
                    "openalex_id": "W1",
                    "oa_pdf_url": "",
                    "text_enrichment_status": "not_found",
                },
                {
                    "recovery_rank": "2",
                    "recovery_priority": "high",
                    "recovery_action": "recover_abstract_from_doi_or_publisher",
                    "article_id": "a2",
                    "journal_short": "jpe",
                    "decade": "1980",
                    "doi": "10.1086/def",
                    "openalex_id": "W2",
                    "oa_pdf_url": "",
                    "text_enrichment_status": "not_found",
                },
            ]
        )
        attempts = pd.DataFrame(
            [
                {"article_id": "a1", "doi": "10.1086/abc", "attempt_source": "econpapers", "attempt_status": "found", "attempt_error": ""},
                {"article_id": "a2", "doi": "10.1086/def", "attempt_source": "econpapers", "attempt_status": "error", "attempt_error": "Not Found"},
                {"article_id": "a3", "doi": "10.1086/ghi", "attempt_source": "econpapers", "attempt_status": "not_found", "attempt_error": ""},
                {"article_id": "a4", "doi": "10.1086/jkl", "attempt_source": "econpapers", "attempt_status": "skipped", "attempt_error": ""},
                {"article_id": "a5", "doi": "10.1086/mno", "attempt_source": "econpapers", "attempt_status": "not_cached", "attempt_error": ""},
                {"article_id": "a6", "doi": "10.1086/pqr", "attempt_source": "econpapers", "attempt_status": "rate_limited", "attempt_error": ""},
                {"article_id": "a7", "doi": "10.1086/stu", "attempt_source": "econpapers", "attempt_status": "error", "attempt_error": "Not Found"},
                {"article_id": "a8", "doi": "10.1086/vwx", "attempt_source": "econpapers", "attempt_status": "error", "attempt_error": "Not Found"},
                {"article_id": "a9", "doi": "10.1086/yz1", "attempt_source": "econpapers", "attempt_status": "error", "attempt_error": "Not Found"},
                {"article_id": "a10", "doi": "10.1086/yz2", "attempt_source": "econpapers", "attempt_status": "error", "attempt_error": "Not Found"},
                {"article_id": "a11", "doi": "10.1086/yz3", "attempt_source": "econpapers", "attempt_status": "error", "attempt_error": "Not Found"},
                {"article_id": "a12", "doi": "10.1086/yz4", "attempt_source": "econpapers", "attempt_status": "error", "attempt_error": "Not Found"},
                {"article_id": "a13", "doi": "10.1086/yz5", "attempt_source": "econpapers", "attempt_status": "error", "attempt_error": "Not Found"},
                {"article_id": "a14", "doi": "10.1086/yz6", "attempt_source": "econpapers", "attempt_status": "error", "attempt_error": "Not Found"},
                {"article_id": "a15", "doi": "10.1086/yz7", "attempt_source": "econpapers", "attempt_status": "error", "attempt_error": "Not Found"},
                {"article_id": "a16", "doi": "10.1086/yz8", "attempt_source": "econpapers", "attempt_status": "error", "attempt_error": "Not Found"},
                {"article_id": "a17", "doi": "10.1086/yz9", "attempt_source": "econpapers", "attempt_status": "error", "attempt_error": "Not Found"},
                {"article_id": "a18", "doi": "10.1086/za1", "attempt_source": "econpapers", "attempt_status": "error", "attempt_error": "Not Found"},
                {"article_id": "a19", "doi": "10.1086/za2", "attempt_source": "econpapers", "attempt_status": "error", "attempt_error": "Not Found"},
                {"article_id": "a20", "doi": "10.1086/za3", "attempt_source": "econpapers", "attempt_status": "error", "attempt_error": "Not Found"},
                {"article_id": "a21", "doi": "10.1086/za4", "attempt_source": "econpapers", "attempt_status": "error", "attempt_error": "Not Found"},
                {"article_id": "a22", "doi": "10.1086/za5", "attempt_source": "econpapers", "attempt_status": "error", "attempt_error": "Not Found"},
                {"article_id": "a23", "doi": "10.1086/za6", "attempt_source": "econpapers", "attempt_status": "error", "attempt_error": "Not Found"},
                {"article_id": "a24", "doi": "10.1086/za7", "attempt_source": "econpapers", "attempt_status": "error", "attempt_error": "Not Found"},
                {"article_id": "a25", "doi": "10.1086/za8", "attempt_source": "econpapers", "attempt_status": "error", "attempt_error": "Not Found"},
                {"article_id": "a26", "doi": "10.1086/za9", "attempt_source": "econpapers", "attempt_status": "error", "attempt_error": "Not Found"},
                {"article_id": "a27", "doi": "10.1086/zb1", "attempt_source": "econpapers", "attempt_status": "error", "attempt_error": "Not Found"},
            ]
        )

        overview, _, doi_prefixes, attempt_summary = insufficient_text_expansion_plan(queue, attempts)
        decisions = recovery_decision_plan(overview, doi_prefixes, attempt_summary).set_index("decision_unit")

        self.assertEqual(decisions.loc["10.1086", "decision"], "source_specific_investigation_before_rerun")
        self.assertEqual(decisions.loc["10.1086", "best_prior_source"], "econpapers")
        self.assertIn("unchanged full-prefix rerun", decisions.loc["10.1086", "rationale"])

    def test_source_investigation_packet_combines_queue_and_attempt_samples(self) -> None:
        queue = pd.DataFrame(
            [
                {
                    "recovery_rank": "1",
                    "recovery_batch": "R001",
                    "recovery_priority": "high",
                    "recovery_action": "recover_abstract_from_doi_or_publisher",
                    "article_id": "a1",
                    "journal_short": "jpe",
                    "publication_year": "1980",
                    "decade": "1980",
                    "title": "A JPE Article",
                    "doi": "10.1086/abc",
                    "openalex_id": "W1",
                    "article_url": "https://doi.org/10.1086/abc",
                    "doi_url": "https://doi.org/10.1086/abc",
                    "crossref_work_url": "https://api.crossref.org/works/10.1086%2Fabc",
                    "openalex_work_url": "https://openalex.org/W1",
                    "oa_pdf_url": "",
                    "text_enrichment_status": "not_found",
                }
            ]
        )
        attempts = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "journal_short": "jpe",
                    "publication_year": "1980",
                    "title": "A JPE Article",
                    "doi": "10.1086/abc",
                    "attempt_source": "econpapers",
                    "attempt_status": "error",
                    "attempt_url": "https://ideas.repec.org/a/ucp/jpolec/doi10.1086-abc.html",
                    "attempt_error": "Not Found",
                    "attempt_detail": "",
                },
                {
                    "article_id": "a2",
                    "journal_short": "jpe",
                    "publication_year": "1979",
                    "title": "Recovered JPE Article",
                    "doi": "10.1086/def",
                    "attempt_source": "econpapers",
                    "attempt_status": "found",
                    "attempt_url": "https://ideas.repec.org/a/ucp/jpolec/doi10.1086-def.html",
                    "attempt_error": "",
                    "attempt_detail": "citation meta abstract",
                },
            ]
        )
        decisions = pd.DataFrame(
            [
                {
                    "decision_unit": "10.1086",
                    "unit_type": "doi_prefix",
                    "decision": "source_specific_investigation_before_rerun",
                    "best_prior_source": "econpapers",
                    "top_failure_source": "econpapers",
                }
            ]
        )

        packet = source_investigation_packet(queue, attempts, decisions, max_rows_per_group=2)

        self.assertIn("failed_current_queue_attempt", set(packet["investigation_type"]))
        self.assertIn("found_reference_attempt", set(packet["investigation_type"]))
        failed = packet[packet["investigation_type"].eq("failed_current_queue_attempt")].iloc[0]
        self.assertEqual(failed["recovery_batch"], "R001")
        self.assertEqual(failed["attempt_error"], "Not Found")
        self.assertIn("ideas.repec.org", failed["attempt_url"])

    def test_source_route_matrix_uses_probe_evidence_to_block_landing_reruns(self) -> None:
        decisions = pd.DataFrame(
            [
                {
                    "decision_unit": "10.1086",
                    "unit_type": "doi_prefix",
                    "row_count": "10",
                    "high_priority_rows": "8",
                    "decision": "source_specific_investigation_before_rerun",
                    "prior_found_articles": "2",
                    "prior_failed_attempts": "40",
                    "best_prior_source": "econpapers",
                    "supporting_command_or_artifact": "python3 run_text_enrichment.py --doi-prefixes 10.1086",
                },
                {
                    "decision_unit": "10.1111",
                    "unit_type": "doi_prefix",
                    "row_count": "12",
                    "high_priority_rows": "12",
                    "decision": "new_source_template_or_manual_recovery",
                    "prior_found_articles": "3",
                    "prior_failed_attempts": "50",
                    "best_prior_source": "openalex",
                    "supporting_command_or_artifact": "No automated publisher_metadata route",
                },
            ]
        )
        probes = pd.DataFrame(
            [
                {"decision_unit": "10.1086", "result_status": "access_challenge"},
                {"decision_unit": "10.1086", "result_status": "not_found"},
            ]
        )

        matrix = source_route_matrix(decisions, probes).set_index("route_unit")

        self.assertEqual(matrix.loc["10.1086", "current_route_status"], "do_not_rerun_landing_pages")
        self.assertEqual(int(matrix.loc["10.1086", "probe_access_challenge_rows"]), 1)
        self.assertIn("avoid broad DOI landing-page reruns", matrix.loc["10.1086", "recommended_route_action"])
        self.assertEqual(matrix.loc["10.1111", "current_route_status"], "unsupported_existing_route")

    def test_run_expansion_plan_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue_path = root / "queue.csv"
            attempts_path = root / "attempts.csv"
            probe_results_path = root / "probe_results.csv"
            output_overview = root / "outputs" / "overview.csv"
            output_detail = root / "outputs" / "detail.csv"
            output_doi_prefixes = root / "outputs" / "doi_prefixes.csv"
            output_attempt_summary = root / "outputs" / "attempt_summary.csv"
            output_decisions = root / "outputs" / "decisions.csv"
            output_investigation_packet = root / "outputs" / "investigation_packet.csv"
            output_route_matrix = root / "outputs" / "route_matrix.csv"
            report = root / "docs" / "report.md"
            pd.DataFrame(
                [
                    {
                        "recovery_rank": "1",
                        "recovery_priority": "high",
                        "recovery_action": "review_oa_pdf_or_first_pages",
                        "article_id": "a1",
                        "journal_short": "ecta",
                        "decade": "1970",
                        "doi": "10.2307/abc",
                        "openalex_id": "W1",
                        "oa_pdf_url": "https://example.test/a.pdf",
                        "text_enrichment_status": "not_found",
                    }
                ]
            ).to_csv(queue_path, index=False)
            pd.DataFrame(
                [
                    {
                        "article_id": "a1",
                        "doi": "10.2307/abc",
                        "attempt_source": "publisher_metadata",
                        "attempt_status": "skipped",
                        "attempt_error": "",
                    }
                ]
            ).to_csv(attempts_path, index=False)
            pd.DataFrame([{"decision_unit": "10.2307", "result_status": "access_challenge"}]).to_csv(probe_results_path, index=False)

            with contextlib.redirect_stdout(io.StringIO()):
                run_expansion_plan(
                    queue_path=queue_path,
                    attempts_path=attempts_path,
                    output_overview=output_overview,
                    output_detail=output_detail,
                    output_doi_prefixes=output_doi_prefixes,
                    output_attempt_summary=output_attempt_summary,
                    output_decisions=output_decisions,
                    output_investigation_packet=output_investigation_packet,
                    output_route_matrix=output_route_matrix,
                    probe_results_path=probe_results_path,
                    report_path=report,
                )

            self.assertTrue(output_overview.exists())
            self.assertTrue(output_detail.exists())
            self.assertTrue(output_doi_prefixes.exists())
            self.assertTrue(output_attempt_summary.exists())
            self.assertTrue(output_decisions.exists())
            self.assertTrue(output_investigation_packet.exists())
            self.assertTrue(output_route_matrix.exists())
            self.assertIn("Insufficient Text Expansion Plan", report.read_text(encoding="utf-8"))
            self.assertIn("Recommended Decisions", report.read_text(encoding="utf-8"))
            self.assertIn("Source Route Matrix", report.read_text(encoding="utf-8"))
            self.assertIn("Source Investigation Packet", report.read_text(encoding="utf-8"))
            self.assertIn("DOI Prefixes", report.read_text(encoding="utf-8"))
            self.assertIn("Prior Source Attempts", report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
