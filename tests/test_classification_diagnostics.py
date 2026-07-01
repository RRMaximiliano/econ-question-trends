from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "code" / "05_analysis"))

from classification_diagnostics import (  # noqa: E402
    analysis_scope_filter,
    category_sensitivity_shares,
    category_shares,
    df_to_markdown,
    evidence_tier_category_shares,
    evidence_tier_sensitivity_shares,
    evidence_tier_sensitivity_summary,
    expansion_recommendation,
    insufficient_text_recovery_queue,
    remaining_insufficient_text_profile,
    resolved_category,
    title_only_triage_candidates,
    validation_metrics,
)


def classified_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "article_id": "a1",
                "journal_short": "aer",
                "publication_year": "2020",
                "article_type": "article",
                "abstract": "Abstract",
                "causal_predictive_category": "causal",
                "classification_confidence": "high",
            },
            {
                "article_id": "a2",
                "journal_short": "aer",
                "publication_year": "2020",
                "article_type": "article",
                "abstract": "",
                "causal_predictive_category": "insufficient_text",
                "classification_confidence": "low",
            },
            {
                "article_id": "a3",
                "journal_short": "qje",
                "publication_year": "2021",
                "article_type": "article",
                "abstract": "Abstract",
                "causal_predictive_category": "other",
                "classification_confidence": "medium",
                "llm_status": "ok",
                "llm_category": "predictive",
                "llm_confidence": "high",
            },
            {
                "article_id": "a4",
                "journal_short": "qje",
                "publication_year": "2021",
                "article_type": "article",
                "abstract": "Abstract",
                "causal_predictive_category": "other",
                "classification_confidence": "medium",
                "llm_status": "error",
                "llm_category": "causal",
                "llm_confidence": "high",
            },
        ]
    ).fillna("")


class ClassificationDiagnosticsTests(unittest.TestCase):
    def test_category_shares_sum_to_one_within_group(self) -> None:
        shares = category_shares(classified_fixture(), ["journal_short"])
        totals = shares.groupby("journal_short")["category_share"].sum().round(6)
        self.assertTrue((totals == 1.0).all())

    def test_resolved_category_prefers_ok_llm_label(self) -> None:
        labels = resolved_category(classified_fixture()).tolist()
        self.assertEqual(labels[2], "predictive")

    def test_resolved_category_falls_back_when_llm_not_ok(self) -> None:
        labels = resolved_category(classified_fixture()).tolist()
        self.assertEqual(labels[3], "other")

    def test_validation_confusion_matrix_when_labels_exist(self) -> None:
        validation = pd.DataFrame(
            [
                {"article_id": "a1", "manual_label": "causal"},
                {"article_id": "a3", "manual_label": "predictive"},
            ]
        )
        metrics = validation_metrics(classified_fixture(), validation)
        self.assertIn("confusion", metrics)
        self.assertEqual(metrics["metrics"].iloc[0]["validation_status"], "available")

    def test_validation_category_metrics_when_labels_exist(self) -> None:
        validation = pd.DataFrame(
            [
                {"article_id": "a1", "manual_label": "causal"},
                {"article_id": "a2", "manual_label": "other"},
                {"article_id": "a3", "manual_label": "predictive"},
            ]
        )
        metrics = validation_metrics(classified_fixture(), validation)
        category_metrics = metrics["category_metrics"].set_index("label")

        self.assertEqual(float(category_metrics.loc["causal", "precision"]), 1.0)
        self.assertEqual(float(category_metrics.loc["predictive", "recall"]), 1.0)
        self.assertEqual(int(category_metrics.loc["insufficient_text", "predicted_count"]), 1)
        self.assertEqual(int(category_metrics.loc["other", "manual_count"]), 1)

    def test_validation_disagreements_include_review_context(self) -> None:
        validation = pd.DataFrame(
            [
                {
                    "validation_id": "VAL0001",
                    "article_id": "a1",
                    "title": "A title",
                    "journal_short": "aer",
                    "publication_year": "2020",
                    "manual_label": "other",
                    "manual_confidence": "high",
                    "manual_notes": "Not actually causal",
                },
                {
                    "validation_id": "VAL0002",
                    "article_id": "a3",
                    "title": "Another title",
                    "journal_short": "qje",
                    "publication_year": "2021",
                    "manual_label": "predictive",
                    "manual_confidence": "medium",
                    "manual_notes": "",
                },
            ]
        )
        classified = classified_fixture()
        classified["classification_reason"] = ["causal reason", "short", "llm", "fallback"]

        metrics = validation_metrics(classified, validation)
        disagreements = metrics["disagreements"]

        self.assertEqual(disagreements["article_id"].tolist(), ["a1"])
        self.assertEqual(disagreements.iloc[0]["predicted_label"], "causal")
        self.assertEqual(disagreements.iloc[0]["manual_label"], "other")
        self.assertEqual(disagreements.iloc[0]["classification_reason"], "causal reason")

    def test_validation_adjudication_packet_adds_empty_adjudication_fields(self) -> None:
        validation = pd.DataFrame(
            [
                {
                    "validation_id": "VAL0001",
                    "article_id": "a1",
                    "title": "A title",
                    "journal_short": "aer",
                    "publication_year": "2020",
                    "manual_label": "other",
                    "manual_confidence": "high",
                    "manual_notes": "Needs adjudication",
                }
            ]
        )
        classified = classified_fixture()
        classified["classification_reason"] = ["causal reason", "short", "llm", "fallback"]

        metrics = validation_metrics(classified, validation)
        packet = metrics["adjudication_packet"]

        self.assertEqual(packet["article_id"].tolist(), ["a1"])
        self.assertIn("adjudicated_label", packet.columns)
        self.assertIn("adjudication_notes", packet.columns)
        self.assertEqual(packet.iloc[0]["adjudicated_label"], "")
        self.assertEqual(packet.iloc[0]["manual_label"], "other")
        self.assertEqual(packet.iloc[0]["predicted_label"], "causal")

    def test_validation_adjudication_packet_preserves_existing_adjudication_fields(self) -> None:
        validation = pd.DataFrame(
            [
                {
                    "validation_id": "VAL0001",
                    "article_id": "a1",
                    "title": "A title",
                    "journal_short": "aer",
                    "publication_year": "2020",
                    "manual_label": "other",
                    "manual_confidence": "high",
                    "manual_notes": "Already adjudicated",
                    "adjudicated_label": "other",
                    "adjudication_notes": "Confirmed reviewer label.",
                    "adjudicator_id": "arbiter",
                    "adjudication_date": "2026-06-30",
                }
            ]
        )
        classified = classified_fixture()
        classified["classification_reason"] = ["causal reason", "short", "llm", "fallback"]

        metrics = validation_metrics(classified, validation)
        packet = metrics["adjudication_packet"]

        self.assertEqual(packet["article_id"].tolist(), ["a1"])
        self.assertEqual(packet.iloc[0]["adjudicated_label"], "other")
        self.assertEqual(packet.iloc[0]["adjudication_notes"], "Confirmed reviewer label.")
        self.assertEqual(packet.iloc[0]["adjudicator_id"], "arbiter")
        self.assertEqual(packet.iloc[0]["adjudication_date"], "2026-06-30")

    def test_validation_metrics_prefers_adjudicated_label_when_available(self) -> None:
        validation = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "manual_label": "other",
                    "adjudicated_label": "causal",
                }
            ]
        )

        metrics = validation_metrics(classified_fixture(), validation)
        labeled = metrics["labeled"]

        self.assertEqual(labeled.iloc[0]["manual_label"], "causal")
        self.assertTrue(labeled.iloc[0]["agreement"])
        self.assertEqual(float(metrics["metrics"].iloc[0]["agreement_rate"]), 1.0)

    def test_recommendation_pauses_when_insufficient_share_high(self) -> None:
        config = {
            "minimum_overall_abstract_share": 0.0,
            "minimum_journal_abstract_share": 0.0,
            "maximum_insufficient_text_share": 0.1,
            "minimum_high_confidence_validation_agreement": 0.85,
        }
        validation = {"status": pd.DataFrame([{"validation_status": "unavailable"}])}
        recommendation = expansion_recommendation(classified_fixture(), validation, config)
        self.assertEqual(recommendation["recommendation"], "pause_for_metadata_enrichment")

    def test_recommendation_pauses_for_manual_validation_when_metadata_gate_passes(self) -> None:
        config = {
            "minimum_overall_abstract_share": 0.0,
            "minimum_journal_abstract_share": 0.0,
            "maximum_insufficient_text_share": 1.0,
            "minimum_high_confidence_validation_agreement": 0.85,
        }
        validation = {"status": pd.DataFrame([{"validation_status": "unavailable"}])}
        recommendation = expansion_recommendation(classified_fixture(), validation, config)
        self.assertEqual(recommendation["recommendation"], "pause_for_manual_validation")

    def test_validation_unavailable_status_without_labels(self) -> None:
        metrics = validation_metrics(classified_fixture(), pd.DataFrame({"article_id": ["a1"], "manual_label": [""]}))
        self.assertEqual(metrics["status"].iloc[0]["validation_status"], "unavailable")

    def test_analysis_scope_filter_excludes_configured_nonresearch_scopes(self) -> None:
        data = classified_fixture()
        data["article_scope"] = ["research_article", "comment_reply", "research_article", "review_erratum_paratext"]
        filtered, summary = analysis_scope_filter(
            data,
            {
                "analysis_scope_column": "article_scope",
                "excluded_analysis_scopes": ["comment_reply", "review_erratum_paratext"],
            },
        )
        self.assertEqual(filtered["article_id"].tolist(), ["a1", "a3"])
        self.assertEqual(int(summary.loc[summary["included_in_analysis"].eq(False), "rows"].sum()), 2)

    def test_remaining_insufficient_text_profile_counts_recovery_handles(self) -> None:
        data = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "journal_short": "aer",
                    "publication_year": "1975",
                    "abstract": "",
                    "doi": "10.1/a",
                    "openalex_id": "W1",
                    "oa_pdf_url": "https://example.test/a.pdf",
                    "text_enrichment_status": "not_found",
                    "causal_predictive_category": "insufficient_text",
                    "classification_confidence": "low",
                },
                {
                    "article_id": "a2",
                    "journal_short": "aer",
                    "publication_year": "1976",
                    "abstract": "Short abstract",
                    "doi": "",
                    "openalex_id": "W2",
                    "oa_pdf_url": "",
                    "text_enrichment_status": "partial_short_text",
                    "causal_predictive_category": "insufficient_text",
                    "classification_confidence": "low",
                },
                {
                    "article_id": "a3",
                    "journal_short": "aer",
                    "publication_year": "1977",
                    "abstract": "Long abstract",
                    "doi": "10.1/c",
                    "openalex_id": "W3",
                    "oa_pdf_url": "",
                    "text_enrichment_status": "not_needed",
                    "causal_predictive_category": "other",
                    "classification_confidence": "medium",
                },
                {
                    "article_id": "a4",
                    "journal_short": "qje",
                    "publication_year": "1981",
                    "abstract": "",
                    "doi": "10.1/d",
                    "openalex_id": "",
                    "oa_pdf_url": "",
                    "text_enrichment_status": "not_found",
                    "causal_predictive_category": "insufficient_text",
                    "classification_confidence": "low",
                },
            ]
        ).fillna("")

        profile = remaining_insufficient_text_profile(data)
        aer_1970s = profile[(profile["journal_short"] == "aer") & (profile["decade"] == "1970")].iloc[0]

        self.assertEqual(int(aer_1970s["rows"]), 3)
        self.assertEqual(int(aer_1970s["insufficient_rows"]), 2)
        self.assertEqual(float(aer_1970s["insufficient_share"]), 0.666667)
        self.assertEqual(int(aer_1970s["has_doi_rows"]), 1)
        self.assertEqual(int(aer_1970s["has_openalex_rows"]), 2)
        self.assertEqual(int(aer_1970s["has_oa_pdf_rows"]), 1)
        self.assertEqual(int(aer_1970s["missing_abstract_rows"]), 1)
        self.assertEqual(int(aer_1970s["partial_short_text_rows"]), 1)

    def test_title_only_triage_candidates_do_not_change_final_labels(self) -> None:
        rules = {
            "scoring": {"strong_weight": 2, "moderate_weight": 1, "dominance_margin": 2},
            "causal": {"strong_phrases": ["treatment effects"], "moderate_phrases": ["effect of"]},
            "predictive": {"strong_phrases": ["forecast accuracy"], "moderate_phrases": ["forecasting"]},
        }
        data = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "journal_short": "aer",
                    "publication_year": "1980",
                    "title": "Forecasting Inflation",
                    "abstract": "",
                    "classification_text_chars": "21",
                    "causal_predictive_category": "insufficient_text",
                    "classification_confidence": "low",
                },
                {
                    "article_id": "a2",
                    "journal_short": "aer",
                    "publication_year": "1980",
                    "title": "A Theory of Exchange",
                    "abstract": "Long abstract",
                    "classification_text_chars": "500",
                    "causal_predictive_category": "other",
                    "classification_confidence": "medium",
                },
            ]
        ).fillna("")

        triage = title_only_triage_candidates(data, rules)

        self.assertEqual(triage["article_id"].tolist(), ["a1"])
        self.assertEqual(triage.iloc[0]["current_category"], "insufficient_text")
        self.assertEqual(triage.iloc[0]["title_only_suggested_category"], "predictive")
        self.assertEqual(triage.iloc[0]["title_only_confidence"], "medium")
        self.assertTrue(bool(triage.iloc[0]["needs_manual_review"]))
        self.assertEqual(data.loc[data["article_id"] == "a1", "causal_predictive_category"].iloc[0], "insufficient_text")

    def test_insufficient_text_recovery_queue_prioritizes_old_rows_with_recovery_handles(self) -> None:
        data = pd.DataFrame(
            [
                {
                    "article_id": "old_pdf",
                    "journal_short": "ecta",
                    "publication_year": "1978",
                    "title": "Instrumental Variables and Demand",
                    "doi": "10.1111/example",
                    "openalex_id": "W123",
                    "article_url": "https://example.test/article",
                    "oa_pdf_url": "https://example.test/article.pdf",
                    "text_enrichment_status": "not_found",
                    "abstract_source": "",
                    "classification_text_chars": "80",
                    "causal_predictive_category": "insufficient_text",
                    "classification_confidence": "low",
                },
                {
                    "article_id": "recent_no_handle",
                    "journal_short": "restud",
                    "publication_year": "2022",
                    "title": "A Recent Theory",
                    "doi": "",
                    "openalex_id": "",
                    "article_url": "",
                    "oa_pdf_url": "",
                    "text_enrichment_status": "not_found",
                    "abstract_source": "",
                    "classification_text_chars": "20",
                    "causal_predictive_category": "insufficient_text",
                    "classification_confidence": "low",
                },
                {
                    "article_id": "already_classified",
                    "journal_short": "aer",
                    "publication_year": "1980",
                    "title": "Known Effects",
                    "doi": "10.1257/example",
                    "openalex_id": "W456",
                    "article_url": "",
                    "oa_pdf_url": "",
                    "text_enrichment_status": "not_needed",
                    "abstract_source": "openalex",
                    "classification_text_chars": "500",
                    "causal_predictive_category": "causal",
                    "classification_confidence": "high",
                },
            ]
        ).fillna("")
        triage = pd.DataFrame(
            [
                {
                    "article_id": "old_pdf",
                    "title_only_suggested_category": "causal",
                    "title_only_confidence": "high",
                    "title_only_reason": "Title matched causal language.",
                }
            ]
        )

        queue = insufficient_text_recovery_queue(data, triage)

        self.assertEqual(queue["article_id"].tolist(), ["old_pdf", "recent_no_handle"])
        self.assertEqual(queue.iloc[0]["recovery_rank"], 1)
        self.assertEqual(queue.iloc[0]["recovery_batch"], "R001")
        self.assertEqual(queue.iloc[0]["recovery_priority"], "high")
        self.assertEqual(queue.iloc[0]["recovery_action"], "review_oa_pdf_or_first_pages")
        self.assertIn("pre_1990_high_missingness", queue.iloc[0]["recovery_reason"])
        self.assertIn("title_triage_causal", queue.iloc[0]["recovery_reason"])
        self.assertEqual(queue.iloc[0]["doi_url"], "https://doi.org/10.1111/example")
        self.assertEqual(queue.iloc[0]["openalex_work_url"], "https://openalex.org/W123")
        self.assertIn("query.title=Instrumental%20Variables", queue.iloc[0]["crossref_title_search_url"])
        self.assertEqual(queue.iloc[0]["backfill_abstract"], "")
        self.assertEqual(queue.iloc[1]["recovery_action"], "manual_title_year_search")

    def test_insufficient_text_recovery_queue_has_stable_empty_schema(self) -> None:
        queue = insufficient_text_recovery_queue(pd.DataFrame())

        self.assertTrue(queue.empty)
        self.assertIn("recovery_rank", queue.columns)
        self.assertIn("backfill_abstract", queue.columns)

    def test_df_to_markdown_escapes_pipe_delimited_cells(self) -> None:
        markdown = df_to_markdown(pd.DataFrame([{"reason": "doi_available|openalex_id_available"}]))

        self.assertIn("doi_available\\|openalex_id_available", markdown)

    def test_category_sensitivity_shares_apply_missing_text_scenarios(self) -> None:
        data = pd.DataFrame(
            [
                {"article_id": "a1", "journal_short": "aer", "causal_predictive_category": "causal", "classification_confidence": "high"},
                {"article_id": "a2", "journal_short": "aer", "causal_predictive_category": "insufficient_text", "classification_confidence": "low"},
                {"article_id": "a3", "journal_short": "aer", "causal_predictive_category": "insufficient_text", "classification_confidence": "low"},
                {"article_id": "a4", "journal_short": "aer", "causal_predictive_category": "other", "classification_confidence": "medium"},
            ]
        ).fillna("")
        title_triage = pd.DataFrame(
            [
                {"article_id": "a2", "title_only_suggested_category": "predictive"},
                {"article_id": "a3", "title_only_suggested_category": "other"},
            ]
        )

        shares = category_sensitivity_shares(data, ["journal_short"], title_triage)
        indexed = shares.set_index(["scenario", "journal_short", "category"])

        self.assertEqual(int(indexed.loc[("baseline", "aer", "insufficient_text"), "article_count"]), 2)
        self.assertEqual(int(indexed.loc[("exclude_insufficient_text", "aer", "causal"), "group_total"]), 2)
        self.assertEqual(int(indexed.loc[("insufficient_text_as_other", "aer", "other"), "article_count"]), 3)
        self.assertEqual(int(indexed.loc[("title_triage_non_other", "aer", "predictive"), "article_count"]), 1)
        self.assertEqual(int(indexed.loc[("title_triage_non_other", "aer", "insufficient_text"), "article_count"]), 1)
        self.assertEqual(int(indexed.loc[("title_triage_all_suggestions", "aer", "other"), "article_count"]), 2)

    def test_evidence_tier_category_shares_count_recovered_tiers_separately(self) -> None:
        data = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "causal_predictive_category": "causal",
                    "classification_confidence": "high",
                    "text_enrichment_status": "enriched",
                    "text_enrichment_evidence_tier": "tier_a_formal_abstract",
                },
                {
                    "article_id": "a2",
                    "causal_predictive_category": "predictive",
                    "classification_confidence": "high",
                    "text_enrichment_status": "enriched",
                    "text_enrichment_evidence_tier": "tier_c_first_page_abstract_or_intro",
                },
                {
                    "article_id": "a3",
                    "causal_predictive_category": "other",
                    "classification_confidence": "medium",
                    "text_enrichment_status": "not_needed",
                    "text_enrichment_evidence_tier": "",
                },
                {
                    "article_id": "a4",
                    "causal_predictive_category": "causal",
                    "classification_confidence": "medium",
                    "text_enrichment_status": "enriched",
                    "text_enrichment_evidence_tier": "",
                },
            ]
        ).fillna("")

        shares = evidence_tier_category_shares(data)
        indexed = shares.set_index(["evidence_tier", "category"])

        self.assertEqual(int(indexed.loc[("tier_a_formal_abstract", "causal"), "article_count"]), 1)
        self.assertEqual(int(indexed.loc[("tier_c_first_page_abstract_or_intro", "predictive"), "article_count"]), 1)
        self.assertEqual(int(indexed.loc[("no_recovered_text_tier", "other"), "article_count"]), 1)
        self.assertEqual(int(indexed.loc[("missing_recovered_text_tier", "causal"), "article_count"]), 1)

    def test_evidence_tier_sensitivity_demotes_non_formal_recovered_text(self) -> None:
        data = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "journal_short": "aer",
                    "causal_predictive_category": "causal",
                    "classification_confidence": "high",
                    "text_enrichment_evidence_tier": "tier_a_formal_abstract",
                },
                {
                    "article_id": "a2",
                    "journal_short": "aer",
                    "causal_predictive_category": "predictive",
                    "classification_confidence": "high",
                    "text_enrichment_evidence_tier": "tier_c_first_page_abstract_or_intro",
                },
                {
                    "article_id": "a3",
                    "journal_short": "aer",
                    "causal_predictive_category": "other",
                    "classification_confidence": "medium",
                    "text_enrichment_evidence_tier": "",
                },
            ]
        ).fillna("")

        summary = evidence_tier_sensitivity_summary(data).set_index("scenario")
        shares = evidence_tier_sensitivity_shares(data, ["journal_short"]).set_index(["scenario", "journal_short", "category"])

        self.assertEqual(int(summary.loc["baseline_current_labels", "rows_demoted_to_insufficient_text"]), 0)
        self.assertEqual(int(summary.loc["formal_abstract_only", "rows_demoted_to_insufficient_text"]), 1)
        self.assertEqual(int(summary.loc["formal_abstract_only", "insufficient_text_count"]), 1)
        self.assertEqual(int(summary.loc["no_recovered_text", "rows_demoted_to_insufficient_text"]), 2)
        self.assertEqual(int(shares.loc[("formal_abstract_only", "aer", "insufficient_text"), "article_count"]), 1)
        self.assertEqual(data.loc[data["article_id"] == "a2", "causal_predictive_category"].iloc[0], "predictive")


if __name__ == "__main__":
    unittest.main()
