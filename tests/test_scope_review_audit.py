from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "code" / "05_analysis"))

from scope_review_audit import (  # noqa: E402
    CANDIDATE_COLUMNS,
    PACKET_COLUMNS,
    SUMMARY_COLUMNS,
    scope_review_completion_summary,
    scope_review_form_html,
    scope_review_guide,
    scope_review_candidates,
    scope_review_candidates_for_dataset,
    scope_review_packet,
    scope_review_summary,
    write_scope_review_packet_report,
    write_scope_review_guide_report,
    write_scope_review_report,
)


class ScopeReviewAuditTests(unittest.TestCase):
    def test_scope_review_candidates_flags_new_nonresearch_scope(self) -> None:
        data = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "journal_short": "restud",
                    "publication_year": "1978",
                    "title": "Money in a Sequence Economy: A Correction",
                    "doi": "10.2307/2297356",
                    "causal_predictive_category": "insufficient_text",
                    "article_scope": "research_article",
                    "recovery_batch": "R001",
                    "recovery_rank": "6",
                }
            ]
        )

        out = scope_review_candidates_for_dataset(
            "classified_file",
            data,
            scope_patterns={"review_erratum_paratext": [r"\ba correction$"]},
        )

        self.assertEqual(list(out.columns), CANDIDATE_COLUMNS)
        self.assertEqual(len(out), 1)
        self.assertEqual(out.iloc[0]["proposed_article_scope"], "review_erratum_paratext")
        self.assertEqual(out.iloc[0]["recommended_action"], "review_scope_before_recovery")
        self.assertEqual(out.iloc[0]["human_scope_decision"], "")

    def test_scope_review_candidates_skips_already_excluded_and_research_rows(self) -> None:
        data = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "title": "More on Prices vs. Quantities: Erratum",
                    "article_scope": "review_erratum_paratext",
                },
                {
                    "article_id": "a2",
                    "title": "A Normal Research Article",
                    "article_scope": "research_article",
                },
            ]
        )

        out = scope_review_candidates_for_dataset(
            "classified_file",
            data,
            scope_patterns={"review_erratum_paratext": [r": erratum$"]},
        )

        self.assertEqual(list(out.columns), CANDIDATE_COLUMNS)
        self.assertTrue(out.empty)

    def test_scope_review_candidates_combines_datasets_with_stable_empty_schema(self) -> None:
        out = scope_review_candidates(
            {
                "classified_file": pd.DataFrame(),
                "recovery_queue": pd.DataFrame(),
            },
            scope_patterns={"review_erratum_paratext": [r": erratum$"]},
        )

        self.assertEqual(list(out.columns), CANDIDATE_COLUMNS)
        self.assertTrue(out.empty)

    def test_scope_review_summary_has_stable_schema(self) -> None:
        empty = scope_review_summary(pd.DataFrame(columns=CANDIDATE_COLUMNS))
        self.assertEqual(list(empty.columns), SUMMARY_COLUMNS)
        self.assertTrue(empty.empty)

        candidates = pd.DataFrame(
            [
                {
                    "dataset": "recovery_queue",
                    "proposed_article_scope": "review_erratum_paratext",
                    "proposed_scope_reason": "title_pattern=: erratum$",
                    "journal_short": "restud",
                    "decade": "1970",
                    "recovery_batch": "R001",
                }
            ]
        )
        summary = scope_review_summary(candidates)
        self.assertEqual(list(summary.columns), SUMMARY_COLUMNS)
        self.assertEqual(summary.iloc[0]["candidate_rows"], 1)

    def test_write_scope_review_report_marks_audit_non_mutating(self) -> None:
        candidates = pd.DataFrame(
            [
                {
                    "dataset": "active_batch",
                    "article_id": "a1",
                    "journal_short": "ecta",
                    "publication_year": "2009",
                    "title": "Econometrica Referees 2007-2008",
                    "doi": "10.3982/ecta771ref",
                    "current_article_scope": "",
                    "proposed_article_scope": "review_erratum_paratext",
                    "proposed_scope_reason": r"title_pattern=\breferees? [0-9]{4}",
                    "recovery_batch": "R001",
                    "recovery_rank": "38",
                }
            ]
        )
        summary = scope_review_summary(candidates)
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "scope_review_audit.md"
            write_scope_review_report(report, candidates, summary)
            text = report.read_text(encoding="utf-8")

        self.assertIn("non-mutating audit", text)
        self.assertIn("does not change `causal_predictive_category`", text)
        self.assertIn("run_project_status.py", text)

    def test_scope_review_packet_deduplicates_articles_and_preserves_decisions(self) -> None:
        candidates = pd.DataFrame(
            [
                {
                    "dataset": "classified_file",
                    "article_id": "a1",
                    "journal_short": "ecta",
                    "publication_year": "2009",
                    "decade": "2000",
                    "title": "2008 Election of Fellows to the Econometric Society",
                    "doi": "10.3982/ecta772fes",
                    "causal_predictive_category": "insufficient_text",
                    "current_article_scope": "research_article",
                    "proposed_article_scope": "review_erratum_paratext",
                    "proposed_scope_reason": "title_pattern=election",
                    "recovery_batch": "",
                    "recovery_rank": "",
                },
                {
                    "dataset": "recovery_queue",
                    "article_id": "a1",
                    "journal_short": "ecta",
                    "publication_year": "2009",
                    "decade": "2000",
                    "title": "2008 Election of Fellows to the Econometric Society",
                    "doi": "10.3982/ecta772fes",
                    "causal_predictive_category": "insufficient_text",
                    "current_article_scope": "",
                    "proposed_article_scope": "review_erratum_paratext",
                    "proposed_scope_reason": "title_pattern=election",
                    "recovery_batch": "R001",
                    "recovery_rank": "36",
                },
            ]
        )
        existing = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "human_scope_decision": "exclude_nonresearch",
                    "scope_review_notes": "parataxt",
                    "reviewer_id": "if",
                    "review_date": "2026-06-29",
                }
            ]
        )

        packet = scope_review_packet(candidates, existing_packet=existing)

        self.assertEqual(list(packet.columns), PACKET_COLUMNS)
        self.assertEqual(len(packet), 1)
        self.assertEqual(packet.iloc[0]["scope_review_id"], "SR0001")
        self.assertEqual(packet.iloc[0]["appears_in_datasets"], "classified_file|recovery_queue")
        self.assertEqual(packet.iloc[0]["recovery_batches"], "R001")
        self.assertEqual(packet.iloc[0]["human_scope_decision"], "exclude_nonresearch")
        self.assertEqual(packet.iloc[0]["scope_review_notes"], "parataxt")

    def test_scope_review_packet_prioritizes_recent_top5_scope_rows(self) -> None:
        candidates = pd.DataFrame(
            [
                {
                    "dataset": "active_batch",
                    "article_id": "old_rank_1",
                    "journal_short": "restud",
                    "publication_year": "1978",
                    "decade": "1970",
                    "title": "Money in a Sequence Economy: A Correction",
                    "causal_predictive_category": "insufficient_text",
                    "current_article_scope": "research_article",
                    "proposed_article_scope": "review_erratum_paratext",
                    "proposed_scope_reason": "title_pattern=correction",
                    "recovery_batch": "R001",
                    "recovery_rank": "1",
                },
                {
                    "dataset": "recovery_queue",
                    "article_id": "recent_jpe",
                    "journal_short": "jpe",
                    "publication_year": "2024",
                    "decade": "2020",
                    "title": "Back Cover",
                    "causal_predictive_category": "insufficient_text",
                    "current_article_scope": "research_article",
                    "proposed_article_scope": "review_erratum_paratext",
                    "proposed_scope_reason": "title_pattern=back cover",
                    "recovery_batch": "R035",
                    "recovery_rank": "3404",
                },
                {
                    "dataset": "recovery_queue",
                    "article_id": "recent_aer",
                    "journal_short": "aer",
                    "publication_year": "2023",
                    "decade": "2020",
                    "title": "Retraction of Research Article",
                    "causal_predictive_category": "insufficient_text",
                    "current_article_scope": "research_article",
                    "proposed_article_scope": "review_erratum_paratext",
                    "proposed_scope_reason": "title_pattern=retraction",
                    "recovery_batch": "R033",
                    "recovery_rank": "3288",
                },
            ]
        )

        packet = scope_review_packet(candidates)

        self.assertEqual(list(packet["article_id"]), ["recent_aer", "recent_jpe", "old_rank_1"])
        self.assertEqual(packet.iloc[0]["scope_review_priority"], "P1_recent_2023_2025_top5")
        self.assertEqual(packet.iloc[1]["scope_review_priority"], "P1_recent_2023_2025_top5")
        self.assertEqual(packet.iloc[2]["scope_review_priority"], "P2_scope_review_backlog")
        self.assertEqual(list(packet["scope_review_id"]), ["SR0001", "SR0002", "SR0003"])

    def test_scope_review_completion_summary_counts_decisions(self) -> None:
        packet = pd.DataFrame(
            [
                {"scope_review_id": "SR0001", "human_scope_decision": "exclude_nonresearch"},
                {"scope_review_id": "SR0002", "human_scope_decision": ""},
            ]
        )

        summary = scope_review_completion_summary(packet)
        lookup = dict(zip(summary["metric"], summary["value"]))

        self.assertEqual(lookup["scope_review_rows"], "2")
        self.assertEqual(lookup["completed_scope_review_decisions"], "1")
        self.assertEqual(lookup["remaining_scope_review_decisions"], "1")
        self.assertEqual(lookup["first_incomplete_scope_review_id"], "SR0002")
        self.assertEqual(lookup["decision_exclude_nonresearch"], "1")

    def test_scope_review_guide_groups_repeated_patterns_without_decisions(self) -> None:
        packet = pd.DataFrame(
            [
                {
                    "scope_review_id": "SR0001",
                    "article_id": "a1",
                    "title": "2008 Election of Fellows to the Econometric Society",
                    "proposed_article_scope": "review_erratum_paratext",
                    "proposed_scope_reason": r"title_pattern=\belection of fellows\b",
                    "human_scope_decision": "",
                },
                {
                    "scope_review_id": "SR0002",
                    "article_id": "a2",
                    "title": "2009 Election of Fellows to the Econometric Society",
                    "proposed_article_scope": "review_erratum_paratext",
                    "proposed_scope_reason": r"title_pattern=\belection of fellows\b",
                    "human_scope_decision": "",
                },
            ]
        )

        guide, summary = scope_review_guide(packet)

        self.assertEqual(set(guide["scope_pattern_family"]), {"society_election"})
        self.assertEqual(set(guide["pattern_group_rows"]), {2})
        self.assertIn("society paratext", guide.iloc[0]["review_lens"])
        self.assertEqual(int(summary.iloc[0]["pattern_group_rows"]), 2)
        self.assertEqual(int(summary.iloc[0]["remaining_decisions"]), 2)

    def test_scope_review_form_html_exports_scope_fields(self) -> None:
        packet = pd.DataFrame(
            [
                {
                    "scope_review_id": "SR0001",
                    "scope_review_priority": "P1_recent_2023_2025_top5",
                    "article_id": "a1",
                    "title": "Erratum",
                    "human_scope_decision": "",
                    "scope_review_notes": "",
                    "reviewer_id": "",
                    "review_date": "",
                    "scope_pattern_family": "correction_erratum",
                    "review_lens": "Usually exclude if it only corrects a prior article.",
                    "review_focus": "Confirm whether this row is only a correction.",
                    "pattern_group_rows": "1",
                }
            ],
        )

        html = scope_review_form_html(packet, title="Scope Review")

        self.assertIn("Scope Review", html)
        self.assertIn("Scope decision rule", html)
        self.assertIn("keep_research", html)
        self.assertIn("completed decisions need reviewer_id", html)
        self.assertIn("After export", html)
        self.assertIn("run_apply_scope_review_decisions.py", html)
        self.assertIn("--apply", html)
        self.assertIn("Review priority", html)
        self.assertIn("P1_recent_2023_2025_top5", html)
        self.assertIn("priority_filter", html)
        self.assertIn("applyFilters", html)
        self.assertIn("all priorities", html)
        self.assertIn("shown", html)
        self.assertIn("exclude_nonresearch", html)
        self.assertIn("human_scope_decision", html)
        self.assertIn("correction_erratum", html)
        self.assertIn("Usually exclude", html)
        self.assertIn("Export CSV", html)
        self.assertIn("bulk_family", html)
        self.assertIn("bulk_decision", html)
        self.assertIn("Fill Pattern Blanks", html)
        self.assertIn("fillFamilyDecision", html)

    def test_write_scope_review_guide_report_marks_guide_non_mutating(self) -> None:
        packet = pd.DataFrame(
            [
                {
                    "scope_review_id": "SR0001",
                    "article_id": "a1",
                    "title": "Erratum",
                    "proposed_article_scope": "review_erratum_paratext",
                    "proposed_scope_reason": "title_pattern=erratum",
                    "human_scope_decision": "",
                }
            ]
        )
        guide, summary = scope_review_guide(packet)
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "scope_review_guide.md"
            write_scope_review_guide_report(report, guide, summary)
            text = report.read_text(encoding="utf-8")

        self.assertIn("non-mutating", text)
        self.assertIn("correction_erratum", text)
        self.assertIn("does not make or apply scope decisions", text)

    def test_write_scope_review_packet_report_includes_progress_and_paths(self) -> None:
        packet = pd.DataFrame(
            [
                {
                    "scope_review_id": "SR0001",
                    "scope_review_priority": "P1_recent_2023_2025_top5",
                    "article_id": "a1",
                    "journal_short": "ecta",
                    "publication_year": "2009",
                    "title": "Election of Fellows",
                    "proposed_article_scope": "review_erratum_paratext",
                    "proposed_scope_reason": "title_pattern=election",
                    "recovery_batches": "R001",
                    "human_scope_decision": "",
                }
            ]
        )
        completion = scope_review_completion_summary(packet)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "scope_review_packet.md"
            write_scope_review_packet_report(
                report,
                packet,
                completion,
                packet_path=root / "scope_review_packet.csv",
                form_path=root / "scope_review_packet.html",
            )
            text = report.read_text(encoding="utf-8")

        self.assertIn("Scope Review Packet", text)
        self.assertIn("Decision Rubric", text)
        self.assertIn("Review Priority", text)
        self.assertIn("P1_recent_2023_2025_top5", text)
        self.assertIn("After Export Commands", text)
        self.assertIn("standalone research", text)
        self.assertIn("run_apply_scope_review_decisions.py", text)
        self.assertIn("--apply", text)
        self.assertIn("error_rows=0", text)
        self.assertIn("0 / 1", text)
        self.assertIn("scope_review_packet.html", text)


if __name__ == "__main__":
    unittest.main()
