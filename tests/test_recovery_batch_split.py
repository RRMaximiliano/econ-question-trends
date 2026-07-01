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

from recovery_batch_split import (  # noqa: E402
    merge_batch_with_workplan,
    split_group_for_status,
    split_recovery_batch,
    split_summary_rows,
    write_recovery_batch_splits,
)


def sample_batch() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "recovery_batch": "R001",
                "batch_row": "001",
                "recovery_rank": "1",
                "recovery_priority": "high",
                "recovery_priority_score": "10",
                "recovery_action": "extend_existing_short_abstract",
                "recovery_reason": "partial_text",
                "article_id": "a1",
                "journal_short": "aer",
                "publication_year": "1980",
                "decade": "1980",
                "title": "Partial Text",
                "doi": "10.1/a",
                "abstract": "",
                "source": "",
                "source_url": "",
                "source_record_id": "",
                "notes": "suggested_action=extend_existing_short_abstract",
            },
            {
                "recovery_batch": "R001",
                "batch_row": "002",
                "recovery_rank": "2",
                "recovery_priority": "high",
                "recovery_priority_score": "9",
                "recovery_action": "review_oa_pdf_or_first_pages",
                "recovery_reason": "pdf_available",
                "article_id": "a2",
                "journal_short": "jpe",
                "publication_year": "1978",
                "decade": "1970",
                "title": "Blocked PDF",
                "doi": "10.2/b",
                "abstract": "",
                "source": "",
                "source_url": "",
                "source_record_id": "",
                "notes": "suggested_action=review_oa_pdf_or_first_pages",
            },
            {
                "recovery_batch": "R001",
                "batch_row": "003",
                "recovery_rank": "3",
                "recovery_priority": "medium",
                "recovery_priority_score": "7",
                "recovery_action": "recover_abstract_from_doi_or_publisher",
                "recovery_reason": "missing_abstract",
                "article_id": "a3",
                "journal_short": "ecta",
                "publication_year": "1975",
                "decade": "1970",
                "title": "Erratum",
                "doi": "10.3/c",
                "abstract": "",
                "source": "",
                "source_url": "",
                "source_record_id": "",
                "notes": "suggested_action=recover_abstract_from_doi_or_publisher",
            },
        ]
    )


def sample_workplan() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "recovery_batch": "R001",
                "batch_row": "001",
                "recovery_rank": "1",
                "article_id": "a1",
                "row_status": "manual_extend_partial_text",
                "recommended_workflow": "Extend partial text.",
                "source_artifact": "publisher",
                "scope_review_decision": "",
                "article_scope": "research_article",
            },
            {
                "recovery_batch": "R001",
                "batch_row": "002",
                "recovery_rank": "2",
                "article_id": "a2",
                "row_status": "pdf_route_blocked_use_manual_metadata",
                "recommended_workflow": "Use manual metadata.",
                "source_artifact": "blockers.csv",
                "pdf_text_status": "download_error",
                "pdf_detail": "http_status=403",
                "scope_review_decision": "",
                "article_scope": "research_article",
            },
            {
                "recovery_batch": "R001",
                "batch_row": "003",
                "recovery_rank": "3",
                "article_id": "a3",
                "row_status": "scope_review_before_recovery",
                "recommended_workflow": "Review scope first.",
                "source_artifact": "docs/scope_review_packet.md",
                "scope_review_decision": "",
                "article_scope": "review_erratum_paratext",
            },
        ]
    )


def sample_articles() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "article_id": "a1",
                "abstract": "Short current abstract",
                "abstract_source": "openalex",
                "classification_text_chars": "41",
                "text_enrichment_status": "partial_short_text",
                "text_enrichment_source": "openalex",
                "text_enrichment_url": "https://example.test/a1",
                "article_type": "research-article",
                "primary_source": "crossref",
                "classification_confidence": "low",
                "classification_reason": "insufficient text",
                "has_usable_classification_text": "false",
            },
            {
                "article_id": "a2",
                "abstract": "",
                "abstract_source": "",
                "classification_text_chars": "32",
                "text_enrichment_status": "missing_abstract",
                "text_enrichment_source": "",
                "article_type": "research-article",
                "primary_source": "openalex",
                "classification_confidence": "low",
                "classification_reason": "insufficient text",
                "has_usable_classification_text": "false",
            },
        ]
    )


def sample_attempts() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "article_id": "a2",
                "attempt_source": "openalex",
                "attempt_status": "not_cached",
                "attempt_detail": "cached_only_no_response",
                "attempt_error": "",
            },
            {
                "article_id": "a2",
                "attempt_source": "crossref",
                "attempt_status": "not_found",
                "attempt_detail": "",
                "attempt_error": "404",
            },
        ]
    )


class RecoveryBatchSplitTests(unittest.TestCase):
    def test_split_group_for_status_maps_workplan_statuses(self) -> None:
        self.assertEqual(split_group_for_status("manual_extend_partial_text"), "ready_partial_text_extension")
        self.assertEqual(split_group_for_status("pdf_route_blocked_use_manual_metadata"), "ready_manual_metadata")
        self.assertEqual(split_group_for_status("scope_review_before_recovery"), "waiting_scope_review")
        self.assertEqual(split_group_for_status("scope_review_unsure_before_recovery"), "waiting_scope_review")
        self.assertEqual(split_group_for_status("scope_review_excluded_nonresearch"), "excluded_nonresearch")
        self.assertEqual(split_group_for_status("autofill_pdf_text"), "ready_autofill_or_completed")
        self.assertEqual(split_group_for_status("scienceon_bounded_recovery"), "ready_manual_metadata")
        self.assertEqual(split_group_for_status("unexpected"), "other_manual_review")

    def test_merge_preserves_importable_columns_and_adds_workplan_context(self) -> None:
        merged = merge_batch_with_workplan(sample_batch(), sample_workplan(), sample_articles(), sample_attempts())

        self.assertIn("abstract", merged.columns)
        self.assertIn("source", merged.columns)
        self.assertIn("source_url", merged.columns)
        self.assertIn("source_record_id", merged.columns)
        self.assertIn("notes", merged.columns)
        self.assertEqual(merged.loc[merged["article_id"].eq("a2"), "row_status"].iloc[0], "pdf_route_blocked_use_manual_metadata")
        self.assertEqual(merged.loc[merged["article_id"].eq("a3"), "split_group"].iloc[0], "waiting_scope_review")
        self.assertEqual(merged.loc[merged["article_id"].eq("a1"), "current_abstract"].iloc[0], "Short current abstract")
        self.assertIn("openalex:not_cached", merged.loc[merged["article_id"].eq("a2"), "prior_attempt_summary"].iloc[0])
        self.assertIn("crossref=404", merged.loc[merged["article_id"].eq("a2"), "prior_attempt_detail_summary"].iloc[0])

    def test_split_recovery_batch_separates_actionable_and_waiting_rows(self) -> None:
        splits = split_recovery_batch(sample_batch(), sample_workplan(), sample_articles(), sample_attempts())

        self.assertEqual(len(splits["ready_partial_text_extension"]), 1)
        self.assertEqual(len(splits["ready_manual_metadata"]), 1)
        self.assertEqual(len(splits["waiting_scope_review"]), 1)
        self.assertEqual(len(splits["excluded_nonresearch"]), 0)
        self.assertEqual(splits["ready_manual_metadata"].iloc[0]["article_id"], "a2")
        self.assertIn("row_status", splits["ready_manual_metadata"].columns)
        self.assertIn("current_text_chars", splits["ready_manual_metadata"].columns)
        self.assertIn("prior_attempt_summary", splits["ready_manual_metadata"].columns)

    def test_split_recovery_batch_keeps_excluded_nonresearch_out_of_waiting_scope(self) -> None:
        workplan = sample_workplan().copy()
        workplan.loc[workplan["article_id"].eq("a3"), "row_status"] = "scope_review_excluded_nonresearch"
        workplan.loc[workplan["article_id"].eq("a3"), "scope_review_decision"] = "exclude_nonresearch"

        splits = split_recovery_batch(sample_batch(), workplan, sample_articles(), sample_attempts())

        self.assertEqual(len(splits["waiting_scope_review"]), 0)
        self.assertEqual(len(splits["excluded_nonresearch"]), 1)
        self.assertEqual(splits["excluded_nonresearch"].iloc[0]["article_id"], "a3")

    def test_split_summary_counts_source_metadata_readiness_for_filled_rows(self) -> None:
        split_frames = {
            "ready_manual_metadata": pd.DataFrame(
                [
                    {
                        "article_id": "a1",
                        "abstract": "Recovered abstract",
                        "source": "econlit",
                        "source_url": "https://example.test/a1",
                        "source_record_id": "",
                    },
                    {
                        "article_id": "a2",
                        "abstract": "Recovered abstract",
                        "source": "econlit",
                        "source_url": "",
                        "source_record_id": "",
                    },
                    {
                        "article_id": "a3",
                        "abstract": "",
                        "source": "",
                        "source_url": "",
                        "source_record_id": "",
                    },
                ]
            )
        }

        summary = split_summary_rows(split_frames, batch_id="R001", output_dir=Path("splits"), html_dir=Path("forms"))
        row = summary[summary["split_group"].eq("ready_manual_metadata")].iloc[0]

        self.assertEqual(int(row["completed_backfill_abstracts"]), 2)
        self.assertEqual(int(row["source_ready_backfill_abstracts"]), 1)
        self.assertEqual(int(row["source_incomplete_backfill_abstracts"]), 1)
        self.assertEqual(int(row["remaining_backfill_abstracts"]), 1)

    def test_write_recovery_batch_splits_writes_csv_html_summary_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch_path = root / "batch.csv"
            workplan_path = root / "workplan.csv"
            articles_path = root / "articles.csv"
            attempts_path = root / "attempts.csv"
            output_dir = root / "splits"
            html_dir = root / "forms"
            summary_path = root / "outputs" / "summary.csv"
            report_path = root / "docs" / "split.md"
            sample_batch().to_csv(batch_path, index=False)
            sample_workplan().to_csv(workplan_path, index=False)
            sample_articles().to_csv(articles_path, index=False)
            sample_attempts().to_csv(attempts_path, index=False)

            with contextlib.redirect_stdout(io.StringIO()):
                splits, summary = write_recovery_batch_splits(
                    batch_path=batch_path,
                    workplan_path=workplan_path,
                    articles_path=articles_path,
                    attempts_path=attempts_path,
                    output_dir=output_dir,
                    html_dir=html_dir,
                    summary_output=summary_path,
                    report_path=report_path,
                )

            self.assertEqual(len(splits["ready_manual_metadata"]), 1)
            self.assertTrue((output_dir / "insufficient_text_recovery_batch_R001_ready_manual_metadata.csv").exists())
            self.assertTrue((html_dir / "insufficient_text_recovery_batch_R001_ready_manual_metadata.html").exists())
            self.assertTrue(summary_path.exists())
            self.assertTrue(report_path.exists())
            self.assertIn("ready_manual_metadata", set(summary["split_group"]))
            self.assertIn("Recovery Batch R001 Split Packets", report_path.read_text(encoding="utf-8"))
            written = pd.read_csv(output_dir / "insufficient_text_recovery_batch_R001_ready_manual_metadata.csv", dtype=str).fillna("")
            html = (html_dir / "insufficient_text_recovery_batch_R001_ready_manual_metadata.html").read_text(encoding="utf-8")
            self.assertIn("prior_attempt_summary", written.columns)
            self.assertIn("openalex:not_cached", written.iloc[0]["prior_attempt_summary"])
            self.assertIn("Prior attempts", html)


if __name__ == "__main__":
    unittest.main()
