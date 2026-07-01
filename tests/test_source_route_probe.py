from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "code" / "06_enrich"))

from source_route_probe import classify_probe_payload, looks_like_html_probe_url, source_route_probe_candidates  # noqa: E402


class SourceRouteProbeTests(unittest.TestCase):
    def test_looks_like_html_probe_url_skips_apis_and_pdfs(self) -> None:
        self.assertTrue(looks_like_html_probe_url("https://doi.org/10.1086/260334"))
        self.assertTrue(looks_like_html_probe_url("https://ideas.repec.org/a/ucp/jpolec/doi10.1086-260334.html"))
        self.assertFalse(looks_like_html_probe_url("https://api.openalex.org/works/W123"))
        self.assertFalse(looks_like_html_probe_url("https://example.test/article.pdf"))

    def test_source_route_probe_candidates_limits_urls_by_decision(self) -> None:
        packet = pd.DataFrame(
            [
                {
                    "investigation_rank": "1",
                    "decision_unit": "10.1086",
                    "doi_prefix": "10.1086",
                    "investigation_type": "failed_current_queue_attempt",
                    "article_id": "a1",
                    "article_url": "https://doi.org/10.1086/abc",
                    "attempt_url": "https://ideas.repec.org/a/ucp/jpolec/doi10.1086-abc.html",
                    "openalex_work_url": "https://api.openalex.org/works/W1",
                    "oa_pdf_url": "https://example.test/a.pdf",
                },
                {
                    "investigation_rank": "2",
                    "decision_unit": "10.1086",
                    "doi_prefix": "10.1086",
                    "investigation_type": "failed_current_queue_attempt",
                    "article_id": "a2",
                    "article_url": "https://doi.org/10.1086/def",
                    "attempt_url": "https://ideas.repec.org/a/ucp/jpolec/doi10.1086-def.html",
                },
            ]
        )

        candidates = source_route_probe_candidates(packet, max_urls_per_decision=2)

        self.assertEqual(len(candidates), 2)
        self.assertEqual(set(candidates["probe_source"]), {"doi_landing", "repec_landing"})
        self.assertFalse(candidates["probe_url"].str.contains("api.openalex").any())
        self.assertFalse(candidates["probe_url"].str.endswith(".pdf").any())

    def test_classify_probe_payload_detects_repec_abstract(self) -> None:
        html = '<html><head><meta name="citation_abstract" content="This is a useful abstract."></head></html>'

        result = classify_probe_payload(
            url="https://ideas.repec.org/a/ucp/jpolec/doi10.1086-abc.html",
            final_url="https://ideas.repec.org/a/ucp/jpolec/doi10.1086-abc.html",
            status_code=200,
            content_type="text/html",
            text=html,
            title="Article",
        )

        self.assertEqual(result["result_status"], "abstract_found")
        self.assertGreater(result["abstract_chars"], 0)
        self.assertEqual(result["parser_used"], "extract_econpapers_abstract")

    def test_classify_probe_payload_detects_pdf_candidate_access_and_not_found(self) -> None:
        pdf_result = classify_probe_payload(
            url="https://example.test/article",
            final_url="https://example.test/article",
            status_code=200,
            content_type="text/html",
            text='<html><head><meta name="citation_pdf_url" content="/paper.pdf"></head></html>',
            title="Article",
        )
        access_result = classify_probe_payload(
            url="https://example.test/article",
            final_url="https://example.test/article",
            status_code=403,
            content_type="text/html",
            text="<html>Access denied. Enable JavaScript.</html>",
            title="Article",
        )
        not_found_result = classify_probe_payload(
            url="https://example.test/article",
            final_url="https://example.test/article",
            status_code=404,
            content_type="text/html",
            text="<html>Page not found</html>",
            title="Article",
        )

        self.assertEqual(pdf_result["result_status"], "pdf_candidate")
        self.assertEqual(pdf_result["pdf_url"], "https://example.test/paper.pdf")
        self.assertEqual(access_result["result_status"], "access_challenge")
        self.assertEqual(not_found_result["result_status"], "not_found")


if __name__ == "__main__":
    unittest.main()
