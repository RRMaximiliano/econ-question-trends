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

from scope_review_apply import (  # noqa: E402
    apply_scope_decisions_to_frame,
    run_apply_scope_review_decisions,
    validate_scope_review_packet,
)


class ScopeReviewApplyTests(unittest.TestCase):
    def test_validate_scope_review_packet_flags_bad_decision_and_missing_reviewer(self) -> None:
        packet = pd.DataFrame(
            [
                {
                    "scope_review_id": "SR0001",
                    "article_id": "a1",
                    "human_scope_decision": "drop_it",
                    "proposed_article_scope": "review_erratum_paratext",
                    "reviewer_id": "",
                    "review_date": "2026-06-29",
                }
            ]
        )

        errors = validate_scope_review_packet(packet, {"a1"})

        self.assertIn("invalid_scope_decision", set(errors["error"]))
        self.assertIn("missing_reviewer_id", set(errors["error"]))

    def test_validate_scope_review_packet_flags_duplicate_completed_identity_rows(self) -> None:
        packet = pd.DataFrame(
            [
                {
                    "scope_review_id": "SR0001",
                    "article_id": "a1",
                    "human_scope_decision": "keep_research",
                    "proposed_article_scope": "review_erratum_paratext",
                    "reviewer_id": "if",
                    "review_date": "2026-06-29",
                },
                {
                    "scope_review_id": "SR0001",
                    "article_id": "a1",
                    "human_scope_decision": "exclude_nonresearch",
                    "proposed_article_scope": "review_erratum_paratext",
                    "reviewer_id": "if",
                    "review_date": "2026-06-29",
                },
            ]
        )

        errors = validate_scope_review_packet(packet, {"a1"})

        self.assertIn("duplicate_scope_review_id", set(errors["error"]))
        self.assertIn("duplicate_scope_article_id", set(errors["error"]))

    def test_validate_scope_review_packet_flags_missing_scope_review_id(self) -> None:
        packet = pd.DataFrame(
            [
                {
                    "scope_review_id": "",
                    "article_id": "a1",
                    "human_scope_decision": "keep_research",
                    "proposed_article_scope": "review_erratum_paratext",
                    "reviewer_id": "if",
                    "review_date": "2026-06-29",
                }
            ]
        )

        errors = validate_scope_review_packet(packet, {"a1"})

        self.assertIn("missing_scope_review_id", set(errors["error"]))

    def test_apply_scope_decisions_updates_excluded_nonresearch_scope(self) -> None:
        articles = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "article_scope": "research_article",
                    "article_scope_reason": "",
                }
            ]
        )
        packet = pd.DataFrame(
            [
                {
                    "scope_review_id": "SR0001",
                    "article_id": "a1",
                    "human_scope_decision": "exclude_nonresearch",
                    "proposed_article_scope": "review_erratum_paratext",
                    "proposed_scope_reason": "title_pattern=: erratum$",
                    "scope_review_notes": "erratum",
                    "reviewer_id": "if",
                    "review_date": "2026-06-29",
                }
            ]
        )
        errors = validate_scope_review_packet(packet, {"a1"})

        updated, changes = apply_scope_decisions_to_frame(articles, packet, errors)

        self.assertTrue(errors.empty)
        self.assertEqual(updated.iloc[0]["article_scope"], "review_erratum_paratext")
        self.assertIn("scope_review_decision=exclude_nonresearch", updated.iloc[0]["article_scope_reason"])
        self.assertEqual(updated.iloc[0]["scope_review_decision"], "exclude_nonresearch")
        self.assertEqual(changes.iloc[0]["change_status"], "scope_updated")

    def test_apply_scope_decisions_keeps_unsure_as_metadata_only(self) -> None:
        articles = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "article_scope": "research_article",
                    "article_scope_reason": "",
                }
            ]
        )
        packet = pd.DataFrame(
            [
                {
                    "scope_review_id": "SR0001",
                    "article_id": "a1",
                    "human_scope_decision": "unsure",
                    "proposed_article_scope": "review_erratum_paratext",
                    "proposed_scope_reason": "title_pattern=: erratum$",
                    "scope_review_notes": "needs discussion",
                    "reviewer_id": "if",
                    "review_date": "2026-06-29",
                }
            ]
        )
        errors = validate_scope_review_packet(packet, {"a1"})

        updated, changes = apply_scope_decisions_to_frame(articles, packet, errors)

        self.assertEqual(updated.iloc[0]["article_scope"], "research_article")
        self.assertEqual(updated.iloc[0]["scope_review_decision"], "unsure")
        self.assertEqual(changes.iloc[0]["change_status"], "metadata_only")

    def test_run_apply_scope_review_decisions_dry_run_writes_reports_not_final_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packet_path = root / "packet.csv"
            articles_input = root / "articles.csv"
            classified_input = root / "classified.csv"
            output_articles = root / "out_articles.csv"
            output_classified = root / "out_classified.csv"
            summary = root / "outputs" / "summary.csv"
            errors = root / "outputs" / "errors.csv"
            changes = root / "outputs" / "changes.csv"
            report = root / "docs" / "scope_apply.md"
            pd.DataFrame(
                [
                    {
                        "scope_review_id": "SR0001",
                        "article_id": "a1",
                        "human_scope_decision": "exclude_nonresearch",
                        "proposed_article_scope": "review_erratum_paratext",
                        "proposed_scope_reason": "title_pattern=: erratum$",
                        "reviewer_id": "if",
                        "review_date": "2026-06-29",
                    }
                ]
            ).to_csv(packet_path, index=False)
            pd.DataFrame([{"article_id": "a1", "article_scope": "research_article", "article_scope_reason": ""}]).to_csv(
                articles_input, index=False
            )
            pd.DataFrame([{"article_id": "a1", "article_scope": "research_article", "article_scope_reason": ""}]).to_csv(
                classified_input, index=False
            )

            with contextlib.redirect_stdout(io.StringIO()):
                out_summary, out_errors, out_changes = run_apply_scope_review_decisions(
                    packet_path=packet_path,
                    articles_input=articles_input,
                    classified_input=classified_input,
                    output_articles=output_articles,
                    output_classified=output_classified,
                    output_summary=summary,
                    output_errors=errors,
                    output_changes=changes,
                    report_path=report,
                    apply=False,
                )

            self.assertTrue(summary.exists())
            self.assertTrue(changes.exists())
            self.assertTrue(report.exists())
            self.assertFalse(output_articles.exists())
            self.assertFalse(output_classified.exists())
            self.assertTrue(out_errors.empty)
            self.assertEqual(dict(zip(out_summary["metric"], out_summary["value"]))["applied"], "no")
            self.assertEqual(out_changes.iloc[0]["new_article_scope"], "review_erratum_paratext")


if __name__ == "__main__":
    unittest.main()
