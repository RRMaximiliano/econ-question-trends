from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "code" / "04_classify"))

from validation_sample import (  # noqa: E402
    assign_validation_strata,
    calibration_agreement_summary,
    calibration_disagreement_packet,
    completed_manual_label_count,
    filter_validation_scope,
    guard_against_overwriting_completed_labels,
    make_calibration_packet,
    make_label_template,
    make_overlap_packet,
    make_reviewer_batches,
    make_reviewer_packet,
    merge_manual_labels,
    manual_validation_readiness_summary,
    overlap_agreement_summary,
    overlap_disagreement_packet,
    reviewer_form_html,
    sample_validation_rows,
    validate_manual_label_values,
    validation_batch_completion_summary,
    validation_sample_drift,
    write_manual_validation_portal,
    write_reviewer_html_forms,
)


def fixture_df() -> pd.DataFrame:
    rows = []
    journals = ["aer", "qje", "jpe"]
    categories = ["causal", "predictive", "other", "insufficient_text"]
    for i in range(120):
        category = categories[i % len(categories)]
        rows.append(
            {
                "article_id": f"a{i:03d}",
                "title": f"Article {i}",
                "abstract": "" if category == "insufficient_text" else "Long enough abstract text " * 20,
                "journal_short": journals[i % len(journals)],
                "publication_year": str(1980 + (i % 40)),
                "causal_predictive_category": category,
                "classification_confidence": "low" if i % 5 == 0 else "medium",
                "causal_language_indicator": 1 if category == "causal" or i % 7 == 0 else 0,
                "predictive_language_indicator": 1 if category == "predictive" or i % 7 == 0 else 0,
            }
        )
    return pd.DataFrame(rows)


class ValidationSampleTests(unittest.TestCase):
    def test_same_seed_returns_same_order(self) -> None:
        data = fixture_df()
        first = sample_validation_rows(data, sample_size=30, seed=123)
        second = sample_validation_rows(data, sample_size=30, seed=123)
        self.assertEqual(first["article_id"].tolist(), second["article_id"].tolist())

    def test_different_seed_can_return_different_order(self) -> None:
        data = fixture_df()
        first = sample_validation_rows(data, sample_size=30, seed=123)
        second = sample_validation_rows(data, sample_size=30, seed=456)
        self.assertNotEqual(first["article_id"].tolist(), second["article_id"].tolist())

    def test_sample_includes_multiple_journals(self) -> None:
        sample = sample_validation_rows(fixture_df(), sample_size=30, seed=123)
        self.assertGreater(sample["journal_short"].nunique(), 1)

    def test_low_confidence_or_ambiguous_rows_are_included(self) -> None:
        sample = sample_validation_rows(fixture_df(), sample_size=30, seed=123)
        self.assertTrue(sample["validation_ambiguous"].any())

    def test_make_label_template_adds_empty_manual_columns(self) -> None:
        sample = sample_validation_rows(fixture_df(), sample_size=10, seed=123)
        template = make_label_template(sample)
        for column in ["validation_id", "manual_label", "manual_confidence", "manual_notes", "reviewer_id", "review_date"]:
            self.assertIn(column, template.columns)
        self.assertTrue((template["manual_label"] == "").all())

    def test_completed_manual_label_count_reads_existing_sample(self) -> None:
        sample = pd.DataFrame([{"manual_label": "causal"}, {"manual_label": ""}, {"manual_label": "other"}])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.csv"
            sample.to_csv(path, index=False)
            self.assertEqual(completed_manual_label_count(path), 2)

    def test_guard_against_overwriting_completed_labels_requires_override(self) -> None:
        sample = pd.DataFrame([{"manual_label": "causal"}])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.csv"
            sample.to_csv(path, index=False)
            with self.assertRaises(SystemExit):
                guard_against_overwriting_completed_labels(path)
            guard_against_overwriting_completed_labels(path, overwrite_labeled=True)

    def test_assign_validation_strata_prefers_ok_llm_labels(self) -> None:
        data = fixture_df().head(1).copy()
        data["llm_status"] = "ok"
        data["llm_category"] = "predictive"
        data["llm_confidence"] = "high"
        stratified = assign_validation_strata(data)
        self.assertEqual(stratified.iloc[0]["validation_category"], "predictive")
        self.assertEqual(stratified.iloc[0]["validation_confidence"], "high")

    def test_filter_validation_scope_excludes_nonresearch_scopes(self) -> None:
        data = fixture_df().head(3).copy()
        data["article_scope"] = ["research_article", "comment_reply", "review_erratum_paratext"]
        filtered = filter_validation_scope(data, ["comment_reply", "review_erratum_paratext"])
        self.assertEqual(filtered["article_id"].tolist(), ["a000"])

    def test_make_reviewer_packet_keeps_compact_labeling_columns(self) -> None:
        sample = sample_validation_rows(fixture_df(), sample_size=10, seed=123)
        template = make_label_template(sample)
        packet = make_reviewer_packet(template)
        self.assertIn("manual_label", packet.columns)
        self.assertIn("abstract", packet.columns)
        self.assertNotIn("validation_category", packet.columns)
        self.assertNotIn("classification_reason", packet.columns)
        self.assertLess(len(packet.columns), len(template.columns))

    def test_make_reviewer_packet_audit_mode_includes_model_context(self) -> None:
        sample = sample_validation_rows(fixture_df(), sample_size=10, seed=123)
        template = make_label_template(sample)
        packet = make_reviewer_packet(template, mode="audit")
        self.assertIn("validation_category", packet.columns)
        self.assertIn("classification_reason", packet.columns)

    def test_make_reviewer_batches_splits_packet_with_batch_columns(self) -> None:
        sample = make_label_template(sample_validation_rows(fixture_df(), sample_size=11, seed=123))
        packet = make_reviewer_packet(sample)
        batches = make_reviewer_batches(packet, batch_size=5)
        self.assertEqual([len(batch) for _, batch in batches], [5, 5, 1])
        self.assertEqual(batches[0][0], "manual_validation_review_packet_batch_001.csv")
        self.assertIn("batch_id", batches[0][1].columns)
        self.assertIn("batch_row", batches[0][1].columns)

    def test_merge_manual_labels_accepts_batched_packet_extra_columns(self) -> None:
        sample = make_label_template(sample_validation_rows(fixture_df(), sample_size=4, seed=123))
        packet = make_reviewer_packet(sample)
        _, batch = make_reviewer_batches(packet, batch_size=4)[0]
        batch.loc[0, "manual_label"] = "other"
        batch.loc[0, "manual_confidence"] = "medium"
        batch.loc[0, "reviewer_id"] = "r1"
        batch.loc[0, "review_date"] = "2026-06-29"
        merged, errors, summary = merge_manual_labels(sample, batch)
        self.assertTrue(errors.empty)
        self.assertEqual(merged.loc[0, "manual_label"], "other")
        self.assertEqual(int(summary.loc[summary["metric"].eq("completed_manual_labels"), "value"].iloc[0]), 1)

    def test_reviewer_form_html_uses_dropdowns_without_model_context(self) -> None:
        sample = make_label_template(sample_validation_rows(fixture_df(), sample_size=2, seed=123))
        packet = make_reviewer_packet(sample)
        _, batch = make_reviewer_batches(packet, batch_size=2)[0]
        html = reviewer_form_html(batch, title="Batch")
        self.assertIn("<select", html)
        self.assertIn("causal", html)
        self.assertIn("insufficient_text", html)
        self.assertIn("Primary focus rule", html)
        self.assertIn("Before export", html)
        self.assertIn("manual_notes for title-only judgments", html)
        self.assertIn("estimating, identifying, or interpreting causal effects", html)
        self.assertIn("prediction, forecasting, classification", html)
        self.assertIn("applyRowValues(DATA.rows)", html)
        self.assertIn("formIssues(rows)", html)
        self.assertIn("fillReviewer()", html)
        self.assertIn("fillToday()", html)
        self.assertIn("QA issues", html)
        self.assertIn("missing confidence, reviewer ID, or ISO review date", html)
        self.assertNotIn("classification_reason", html)
        self.assertNotIn("validation_category", html)
        columns_literal = html.split('"columns": ', 1)[1].split(", \"rows\"", 1)[0]
        self.assertNotIn("Primary focus rule", columns_literal)

    def test_write_reviewer_html_forms_writes_one_file_per_batch(self) -> None:
        sample = make_label_template(sample_validation_rows(fixture_df(), sample_size=6, seed=123))
        packet = make_reviewer_packet(sample)
        with tempfile.TemporaryDirectory() as tmp:
            written = write_reviewer_html_forms(packet, Path(tmp), batch_size=4)
            self.assertEqual(len(written), 2)
            self.assertTrue(written[0].read_text(encoding="utf-8").startswith("<!doctype html>"))

    def test_merge_manual_labels_updates_full_sample_from_reviewer_packet(self) -> None:
        sample = make_label_template(sample_validation_rows(fixture_df(), sample_size=10, seed=123))
        reviewer = make_reviewer_packet(sample)
        reviewer.loc[0, "manual_label"] = "causal"
        reviewer.loc[0, "manual_confidence"] = "high"
        reviewer.loc[0, "manual_notes"] = "clear treatment-effect language"
        reviewer.loc[0, "reviewer_id"] = "if"
        reviewer.loc[0, "review_date"] = "2026-06-28"
        merged, errors, summary = merge_manual_labels(sample, reviewer)
        self.assertTrue(errors.empty)
        self.assertEqual(merged.loc[0, "manual_label"], "causal")
        self.assertEqual(merged.loc[0, "manual_confidence"], "high")
        self.assertEqual(int(summary.loc[summary["metric"].eq("completed_manual_labels"), "value"].iloc[0]), 1)

    def test_validate_manual_label_values_rejects_invalid_values(self) -> None:
        reviewer = pd.DataFrame(
            [
                {
                    "validation_id": "VAL0001",
                    "article_id": "a1",
                    "manual_label": "maybe",
                    "manual_confidence": "certain",
                    "review_date": "06/28/2026",
                }
            ]
        )
        errors = validate_manual_label_values(reviewer)
        self.assertEqual(
            set(errors["error"]),
            {
                "invalid_manual_label",
                "invalid_manual_confidence",
                "missing_reviewer_id",
                "review_date_must_be_iso_yyyy_mm_dd",
            },
        )

    def test_validate_manual_label_values_requires_auditable_completed_labels(self) -> None:
        reviewer = pd.DataFrame(
            [
                {
                    "validation_id": "VAL0001",
                    "article_id": "a1",
                    "manual_label": "causal",
                    "manual_confidence": "high",
                    "reviewer_id": "",
                    "review_date": "",
                }
            ]
        )

        errors = validate_manual_label_values(reviewer)

        self.assertEqual(set(errors["error"]), {"missing_reviewer_id", "missing_review_date"})

    def test_merge_manual_labels_rejects_unknown_reviewer_row(self) -> None:
        sample = make_label_template(sample_validation_rows(fixture_df(), sample_size=2, seed=123))
        reviewer = make_reviewer_packet(sample)
        reviewer.loc[0, "article_id"] = "missing"
        merged, errors, _ = merge_manual_labels(sample, reviewer)
        self.assertFalse(errors.empty)
        self.assertEqual(merged.loc[0, "manual_label"], "")
        self.assertIn("reviewer_row_not_in_sample", set(errors["error"]))

    def test_validation_batch_completion_summary_counts_batch_progress(self) -> None:
        reviewer = pd.DataFrame(
            [
                {
                    "batch_id": "B001",
                    "manual_label": "causal",
                    "manual_confidence": "high",
                    "reviewer_id": "r1",
                    "review_date": "2026-06-28",
                },
                {
                    "batch_id": "B001",
                    "manual_label": "other",
                    "manual_confidence": "",
                    "reviewer_id": "r1",
                    "review_date": "2026-06-29",
                },
                {
                    "batch_id": "B002",
                    "manual_label": "",
                    "manual_confidence": "",
                    "reviewer_id": "",
                    "review_date": "",
                },
            ]
        )

        summary = validation_batch_completion_summary(reviewer).set_index("batch_id")

        self.assertEqual(int(summary.loc["B001", "total_rows"]), 2)
        self.assertEqual(int(summary.loc["B001", "completed_manual_labels"]), 2)
        self.assertEqual(int(summary.loc["B001", "missing_manual_confidence_rows"]), 1)
        self.assertEqual(summary.loc["B001", "reviewer_ids"], "r1")
        self.assertEqual(summary.loc["B001", "latest_review_date"], "2026-06-29")
        self.assertEqual(int(summary.loc["B002", "remaining_manual_labels"]), 1)

    def test_validation_batch_completion_summary_handles_unbatched_packet(self) -> None:
        reviewer = pd.DataFrame([{"manual_label": "predictive", "manual_confidence": "medium"}])

        summary = validation_batch_completion_summary(reviewer)

        self.assertEqual(summary.iloc[0]["batch_id"], "unbatched")
        self.assertEqual(int(summary.iloc[0]["manual_label_predictive"]), 1)

    def test_validation_sample_drift_reports_changed_current_values(self) -> None:
        sample = pd.DataFrame(
            [
                {
                    "validation_id": "VAL0001",
                    "article_id": "a1",
                    "abstract": "Old abstract",
                    "causal_predictive_category": "other",
                }
            ]
        )
        current = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "abstract": "New abstract",
                    "causal_predictive_category": "causal",
                }
            ]
        )

        drift = validation_sample_drift(sample, current, columns=["abstract", "causal_predictive_category"])

        self.assertEqual(set(drift["field"]), {"abstract", "causal_predictive_category"})
        self.assertEqual(drift.iloc[0]["validation_id"], "VAL0001")

    def test_manual_validation_readiness_summary_uses_drift_and_next_batch(self) -> None:
        sample = make_label_template(sample_validation_rows(fixture_df(), sample_size=5, seed=123))
        batch_summary = pd.DataFrame(
            [
                {"batch_id": "B001", "completed_manual_labels": "5", "remaining_manual_labels": "0"},
                {"batch_id": "B002", "completed_manual_labels": "1", "remaining_manual_labels": "4"},
            ]
        )
        drift = pd.DataFrame([{"article_id": sample.iloc[0]["article_id"], "field": "abstract"}])

        summary = manual_validation_readiness_summary(sample, batch_summary, drift)
        lookup = dict(zip(summary["metric"], summary["value"]))

        self.assertEqual(lookup["ready_for_blind_review"], "no")
        self.assertEqual(lookup["next_incomplete_batch"], "B002")
        self.assertEqual(lookup["drifted_articles"], 1)
        self.assertEqual(lookup["reviewer_batches"], 2)

    def test_make_overlap_packet_creates_blind_second_review_packet(self) -> None:
        sample = make_label_template(sample_validation_rows(fixture_df(), sample_size=40, seed=123))
        packet = make_overlap_packet(sample, sample_size=12, seed=456)

        self.assertEqual(len(packet), 12)
        self.assertIn("overlap_id", packet.columns)
        self.assertIn("manual_label", packet.columns)
        self.assertNotIn("validation_category", packet.columns)
        self.assertTrue(packet["manual_label"].astype(str).str.strip().eq("").all())

    def test_overlap_agreement_summary_counts_comparable_labels(self) -> None:
        sample = make_label_template(sample_validation_rows(fixture_df(), sample_size=3, seed=123))
        overlap = make_overlap_packet(sample, sample_size=3, seed=123)
        first_article = overlap.loc[0, "article_id"]
        second_article = overlap.loc[1, "article_id"]
        sample.loc[sample["article_id"].eq(first_article), "manual_label"] = "causal"
        sample.loc[sample["article_id"].eq(second_article), "manual_label"] = "other"
        overlap.loc[0, "manual_label"] = "causal"
        overlap.loc[0, "manual_confidence"] = "high"
        overlap.loc[1, "manual_label"] = "predictive"
        overlap.loc[1, "manual_confidence"] = "medium"

        summary = overlap_agreement_summary(sample, overlap)
        lookup = dict(zip(summary["metric"], summary["value"]))

        self.assertEqual(lookup["completed_overlap_labels"], 2)
        self.assertEqual(lookup["comparable_overlap_labels"], 2)
        self.assertEqual(lookup["overlap_agreements"], 1)
        self.assertEqual(lookup["overlap_disagreements"], 1)
        self.assertEqual(lookup["overlap_agreement_rate"], 0.5)

    def test_overlap_disagreement_packet_adds_adjudication_fields(self) -> None:
        sample = make_label_template(sample_validation_rows(fixture_df(), sample_size=2, seed=123))
        overlap = make_overlap_packet(sample, sample_size=2, seed=123)
        article_id = overlap.loc[0, "article_id"]
        sample.loc[sample["article_id"].eq(article_id), "manual_label"] = "causal"
        sample.loc[sample["article_id"].eq(article_id), "manual_confidence"] = "high"
        sample.loc[sample["article_id"].eq(article_id), "reviewer_id"] = "primary"
        overlap.loc[0, "manual_label"] = "other"
        overlap.loc[0, "manual_confidence"] = "low"
        overlap.loc[0, "reviewer_id"] = "secondary"

        disagreements = overlap_disagreement_packet(sample, overlap)

        self.assertEqual(len(disagreements), 1)
        self.assertEqual(disagreements.iloc[0]["primary_manual_label"], "causal")
        self.assertEqual(disagreements.iloc[0]["overlap_manual_label"], "other")
        self.assertIn("adjudicated_label", disagreements.columns)
        self.assertIn("adjudicator_id", disagreements.columns)

    def test_make_calibration_packet_balances_categories_and_stays_blind(self) -> None:
        sample = make_label_template(sample_validation_rows(fixture_df(), sample_size=60, seed=123))
        packet = make_calibration_packet(sample, sample_size=16, seed=456)

        self.assertEqual(len(packet), 16)
        self.assertIn("calibration_id", packet.columns)
        self.assertIn("manual_label", packet.columns)
        self.assertNotIn("validation_category", packet.columns)
        self.assertTrue(packet["manual_label"].astype(str).str.strip().eq("").all())

    def test_calibration_agreement_summary_counts_disagreements(self) -> None:
        submissions = pd.DataFrame(
            [
                {"calibration_id": "CAL0001", "validation_id": "VAL0001", "article_id": "a1", "manual_label": "causal", "manual_confidence": "high", "reviewer_id": "r1"},
                {"calibration_id": "CAL0001", "validation_id": "VAL0001", "article_id": "a1", "manual_label": "causal", "manual_confidence": "medium", "reviewer_id": "r2"},
                {"calibration_id": "CAL0002", "validation_id": "VAL0002", "article_id": "a2", "manual_label": "other", "manual_confidence": "high", "reviewer_id": "r1"},
                {"calibration_id": "CAL0002", "validation_id": "VAL0002", "article_id": "a2", "manual_label": "predictive", "manual_confidence": "low", "reviewer_id": "r2"},
            ]
        )

        summary = calibration_agreement_summary(submissions)
        lookup = dict(zip(summary["metric"], summary["value"]))

        self.assertEqual(lookup["completed_calibration_labels"], 4)
        self.assertEqual(lookup["completed_calibration_rows"], 2)
        self.assertEqual(lookup["remaining_calibration_rows"], 0)
        self.assertEqual(lookup["calibration_reviewers"], 2)
        self.assertEqual(lookup["rows_with_multiple_reviewers"], 2)
        self.assertEqual(lookup["unanimous_rows"], 1)
        self.assertEqual(lookup["disagreement_rows"], 1)
        self.assertEqual(lookup["agreement_rate"], 0.5)

    def test_calibration_disagreement_packet_collects_reviewer_labels(self) -> None:
        submissions = pd.DataFrame(
            [
                {"calibration_id": "CAL0001", "validation_id": "VAL0001", "article_id": "a1", "title": "Article", "manual_label": "other", "manual_confidence": "high", "manual_notes": "theory", "reviewer_id": "r1"},
                {"calibration_id": "CAL0001", "validation_id": "VAL0001", "article_id": "a1", "title": "Article", "manual_label": "causal", "manual_confidence": "medium", "manual_notes": "effect", "reviewer_id": "r2"},
            ]
        )

        disagreements = calibration_disagreement_packet(submissions)

        self.assertEqual(len(disagreements), 1)
        self.assertEqual(disagreements.iloc[0]["label_set"], "causal|other")
        self.assertIn("r1=other", disagreements.iloc[0]["reviewer_labels"])
        self.assertIn("adjudicated_label", disagreements.columns)

    def test_write_manual_validation_portal_links_forms_and_reports(self) -> None:
        summary = pd.DataFrame(
            [
                {"metric": "ready_for_blind_review", "value": "yes"},
                {"metric": "completed_manual_labels", "value": "10"},
                {"metric": "sample_rows", "value": "300"},
                {"metric": "remaining_manual_labels", "value": "290"},
                {"metric": "next_incomplete_batch", "value": "B002"},
                {"metric": "drifted_articles", "value": "0"},
            ]
        )
        batch_summary = pd.DataFrame(
            [
                {"batch_id": "B001", "completed_manual_labels": "50", "remaining_manual_labels": "0"},
                {"batch_id": "B002", "completed_manual_labels": "10", "remaining_manual_labels": "40"},
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            main_forms = root / "data" / "intermediate" / "manual_validation_forms"
            overlap_forms = root / "data" / "intermediate" / "manual_validation_overlap_forms"
            main_forms.mkdir(parents=True)
            overlap_forms.mkdir(parents=True)
            (main_forms / "manual_validation_review_packet_batch_001.html").write_text("batch 1", encoding="utf-8")
            (main_forms / "manual_validation_review_packet_batch_002.html").write_text("batch 2", encoding="utf-8")
            (overlap_forms / "manual_validation_review_packet_batch_001.html").write_text("overlap", encoding="utf-8")
            calibration_forms = root / "data" / "intermediate" / "manual_validation_calibration_forms"
            calibration_forms.mkdir(parents=True)
            (calibration_forms / "manual_validation_review_packet_batch_001.html").write_text("calibration", encoding="utf-8")
            calibration_remaining = root / "docs" / "manual_validation_calibration_remaining.md"
            calibration_remaining.parent.mkdir(parents=True, exist_ok=True)
            calibration_remaining.write_text("remaining", encoding="utf-8")
            calibration_template = root / "data" / "intermediate" / "manual_validation_calibration" / "manual_validation_calibration_remaining_submission_template.csv"
            calibration_template.parent.mkdir(parents=True)
            calibration_template.write_text("calibration_id,manual_label\n", encoding="utf-8")
            portal = root / "docs" / "manual_validation_portal.html"

            write_manual_validation_portal(
                portal,
                summary,
                batch_summary,
                codebook_path=str(root / "docs" / "manual_validation_codebook.md"),
                readiness_report=str(root / "docs" / "manual_validation_readiness.md"),
                status_report=str(root / "docs" / "manual_validation_status.md"),
                overlap_report=str(root / "docs" / "manual_validation_overlap.md"),
                main_forms_dir=str(main_forms),
                overlap_forms_dir=str(overlap_forms),
                adjudication_report=str(root / "docs" / "manual_validation_adjudication_status.md"),
                calibration_report=str(root / "docs" / "manual_validation_calibration.md"),
                calibration_kickoff_report=str(root / "docs" / "manual_validation_calibration_kickoff.md"),
                calibration_remaining_report=str(calibration_remaining),
                calibration_remaining_template=str(calibration_template),
                calibration_forms_dir=str(calibration_forms),
                calibration_summary=pd.DataFrame(
                    [{"metric": "calibration_rows", "value": "20"}, {"metric": "completed_calibration_labels", "value": "2"}]
                ),
                overlap_summary=pd.DataFrame(
                    [{"metric": "overlap_rows", "value": "30"}, {"metric": "completed_overlap_labels", "value": "3"}]
                ),
                adjudication_summary=pd.DataFrame([{"metric": "completed_adjudications", "value": "1"}]),
                scope_review_report=str(root / "docs" / "scope_review_packet.md"),
                scope_review_guide_report=str(root / "docs" / "scope_review_guide.md"),
                scope_review_form=str(root / "data" / "intermediate" / "scope_review_forms" / "scope_review_packet.html"),
                scope_review_apply_report=str(root / "docs" / "scope_review_apply.md"),
                scope_review_completion=pd.DataFrame(
                    [{"metric": "scope_review_rows", "value": "70"}, {"metric": "completed_scope_review_decisions", "value": "5"}]
                ),
            )

            html = portal.read_text(encoding="utf-8")
            self.assertIn("Manual Validation Portal", html)
            self.assertIn("10 / 300", html)
            self.assertIn("B002", html)
            self.assertIn("manual_validation_review_packet_batch_001.html", html)
            self.assertIn("manual_validation_overlap.md", html)
            self.assertIn("manual_validation_calibration_kickoff.md", html)
            self.assertIn("manual_validation_calibration_remaining.md", html)
            self.assertIn("manual_validation_calibration_remaining_submission_template.csv", html)
            self.assertIn("manual_validation_calibration.md", html)
            self.assertIn("2 / 20", html)
            self.assertIn("3 / 30", html)
            self.assertIn("manual_validation_adjudication_status.md", html)
            self.assertIn("5 / 70", html)
            self.assertIn("scope_review_packet.md", html)
            self.assertIn("scope_review_guide.md", html)
            self.assertIn("scope_review_packet.html", html)
            self.assertIn("scope_review_apply.md", html)


if __name__ == "__main__":
    unittest.main()
