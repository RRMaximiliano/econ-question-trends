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

from recovery_review_queue import (  # noqa: E402
    recovery_review_queue,
    recovery_source_guide,
    recovery_source_guide_summary,
    run_recovery_review_queue,
    queue_summary,
)


def split_row(
    article_id: str,
    *,
    split_group: str,
    row_status: str,
    current_text_chars: str,
    abstract: str = "",
    source: str = "",
    source_url: str = "",
    source_record_id: str = "",
    recovery_rank: str = "1",
    title: str = "A Paper",
    source_artifact: str = "https://doi.org/10.2307/example",
    current_abstract: str | None = None,
    text_enrichment_status: str = "partial_short_text",
    has_usable_classification_text: str = "",
) -> dict[str, str]:
    existing_abstract = current_abstract
    if existing_abstract is None:
        existing_abstract = abstract or ("Existing partial abstract text." if current_text_chars != "0" else "")
    return {
        "recovery_batch": "R001",
        "split_group": split_group,
        "row_status": row_status,
        "batch_row": recovery_rank.zfill(3),
        "recovery_rank": recovery_rank,
        "recovery_priority": "high",
        "article_id": article_id,
        "journal_short": "ecta",
        "publication_year": "1980",
        "title": title,
        "doi": "10.2307/example",
        "abstract": abstract,
        "source": source,
        "source_url": source_url,
        "source_record_id": source_record_id,
        "source_artifact": source_artifact,
        "current_text_chars": current_text_chars,
        "current_abstract": existing_abstract,
        "current_abstract_source": "openalex" if current_text_chars != "0" else "",
        "text_enrichment_status": text_enrichment_status,
        "has_usable_classification_text": has_usable_classification_text,
        "prior_attempt_summary": "openalex:found",
        "prior_attempt_detail_summary": "",
        "recommended_workflow": "Recover explicit abstract.",
        "notes": "",
    }


class RecoveryReviewQueueTests(unittest.TestCase):
    def test_recovery_review_queue_prioritizes_source_fixes_and_partial_quick_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            partial_path = root / "partial.csv"
            manual_path = root / "manual.csv"
            pd.DataFrame(
                [
                    split_row(
                        "source-fix",
                        split_group="ready_partial_text_extension",
                        row_status="manual_extend_partial_text",
                        current_text_chars="210",
                        abstract="Recovered abstract text.",
                        source="econlit",
                        source_url="",
                        source_record_id="",
                        recovery_rank="3",
                        title="Needs Source Metadata",
                    ),
                    split_row(
                        "near-threshold",
                        split_group="ready_partial_text_extension",
                        row_status="manual_extend_partial_text",
                        current_text_chars="225",
                        recovery_rank="2",
                        title="Near Threshold",
                    ),
                    split_row(
                        "suspect-boilerplate",
                        split_group="ready_partial_text_extension",
                        row_status="manual_extend_partial_text",
                        current_text_chars="245",
                        recovery_rank="6",
                        title="Suspect Boilerplate",
                        current_abstract="Your use of the JSTOR archive indicates your acceptance of JSTOR's Terms and Conditions of Use, available at",
                    ),
                    split_row(
                        "already-enriched",
                        split_group="ready_partial_text_extension",
                        row_status="manual_extend_partial_text",
                        current_text_chars="300",
                        recovery_rank="7",
                        title="Already Enriched",
                        text_enrichment_status="enriched",
                        has_usable_classification_text="True",
                    ),
                    split_row(
                        "partial-longer",
                        split_group="ready_partial_text_extension",
                        row_status="manual_extend_partial_text",
                        current_text_chars="120",
                        recovery_rank="1",
                        title="Partial Longer",
                    ),
                ]
            ).to_csv(partial_path, index=False)
            pd.DataFrame(
                [
                    split_row(
                        "pdf-blocked",
                        split_group="ready_manual_metadata",
                        row_status="pdf_route_blocked_use_manual_metadata",
                        current_text_chars="80",
                        recovery_rank="4",
                        title="PDF Blocked",
                        source_artifact="outputs/tables/enriched/remaining_oa_pdf_download_blockers.csv",
                    ),
                    split_row(
                        "manual-context",
                        split_group="ready_manual_metadata",
                        row_status="manual_index_or_new_template",
                        current_text_chars="40",
                        recovery_rank="5",
                        title="Manual Context",
                    ),
                ]
            ).to_csv(manual_path, index=False)
            split_summary = pd.DataFrame(
                [
                    {"recovery_batch": "R001", "split_group": "ready_partial_text_extension", "rows": "5", "output_csv": str(partial_path)},
                    {"recovery_batch": "R001", "split_group": "ready_manual_metadata", "rows": "2", "output_csv": str(manual_path)},
                    {"recovery_batch": "R001", "split_group": "waiting_scope_review", "rows": "1", "output_csv": str(root / "waiting.csv")},
                ]
            )

            queue = recovery_review_queue(split_summary, minimum_chars=250)

            self.assertEqual(queue.iloc[0]["article_id"], "source-fix")
            self.assertEqual(queue.iloc[0]["quick_win_tier"], "source_metadata_fix")
            self.assertEqual(queue.iloc[1]["article_id"], "near-threshold")
            self.assertEqual(queue.iloc[1]["quick_win_tier"], "tier_1_partial_near_threshold")
            self.assertEqual(queue.iloc[1]["abstract"], "Existing partial abstract text.")
            self.assertEqual(queue.iloc[1]["current_abstract"], "Existing partial abstract text.")
            self.assertEqual(queue.iloc[2]["article_id"], "suspect-boilerplate")
            self.assertEqual(queue.iloc[2]["quick_win_tier"], "tier_2_partial_replace_suspect_text")
            self.assertEqual(queue.iloc[2]["abstract"], "")
            self.assertEqual(queue.iloc[2]["current_text_quality_flag"], "jstor_terms_boilerplate")
            self.assertEqual(queue.iloc[3]["article_id"], "partial-longer")
            self.assertEqual(queue.iloc[3]["quick_win_tier"], "tier_3_partial_extension")
            self.assertEqual(queue.iloc[4]["article_id"], "manual-context")
            self.assertEqual(queue.iloc[4]["quick_win_tier"], "tier_4_manual_metadata_has_context")
            self.assertEqual(queue.iloc[5]["article_id"], "pdf-blocked")
            self.assertEqual(queue.iloc[5]["quick_win_tier"], "tier_5_manual_metadata_pdf_blocked")
            self.assertEqual(list(queue["review_rank"]), ["1", "2", "3", "4", "5", "6"])
            self.assertNotIn("already-enriched", set(queue["article_id"]))
            self.assertNotIn("waiting_scope_review", set(queue["split_group"]))

    def test_queue_summary_counts_tiers(self) -> None:
        queue = pd.DataFrame(
            [
                {
                    "recovery_batch": "R001",
                    "review_stage": "recover_abstract",
                    "quick_win_tier": "tier_1_partial_near_threshold",
                    "split_group": "ready_partial_text_extension",
                    "row_status": "manual_extend_partial_text",
                    "article_id": "a1",
                    "chars_needed_to_threshold": "25",
                },
                {
                    "recovery_batch": "R001",
                    "review_stage": "recover_abstract",
                    "quick_win_tier": "tier_1_partial_near_threshold",
                    "split_group": "ready_partial_text_extension",
                    "row_status": "manual_extend_partial_text",
                    "article_id": "a2",
                    "chars_needed_to_threshold": "75",
                },
            ]
        )

        summary = queue_summary(queue)

        self.assertEqual(len(summary), 1)
        self.assertEqual(int(summary.iloc[0]["rows"]), 2)
        self.assertEqual(int(summary.iloc[0]["median_chars_needed_to_threshold"]), 50)
        self.assertIn("fastest", summary.iloc[0]["recommended_start"])

    def test_recovery_source_guide_groups_rows_by_evidence_route(self) -> None:
        queue = pd.DataFrame(
            [
                {
                    **split_row("partial", split_group="ready_partial_text_extension", row_status="manual_extend_partial_text", current_text_chars="230", recovery_rank="1"),
                    "review_rank": "1",
                    "quick_win_tier": "tier_1_partial_near_threshold",
                    "source_hint": "https://doi.org/10.2307/example",
                },
                {
                    **split_row(
                        "pdf-blocked",
                        split_group="ready_manual_metadata",
                        row_status="pdf_route_blocked_use_manual_metadata",
                        current_text_chars="0",
                        recovery_rank="2",
                        source_artifact="outputs/tables/enriched/remaining_oa_pdf_download_blockers.csv",
                    ),
                    "review_rank": "2",
                    "quick_win_tier": "tier_5_manual_metadata_pdf_blocked",
                    "source_hint": "outputs/tables/enriched/remaining_oa_pdf_download_blockers.csv",
                    "text_enrichment_status": "pdf_candidate",
                },
                {
                    **split_row("jstor", split_group="ready_manual_metadata", row_status="manual_index_or_new_template", current_text_chars="0", recovery_rank="3"),
                    "review_rank": "3",
                    "quick_win_tier": "tier_6_manual_metadata_sparse",
                    "source_hint": "https://doi.org/10.2307/example",
                },
            ]
        )

        guide = recovery_source_guide(queue)
        summary = recovery_source_guide_summary(guide)
        families = dict(zip(guide["article_id"], guide["source_route_family"]))

        self.assertEqual(families["partial"], "partial_text_extension")
        self.assertEqual(families["pdf-blocked"], "pdf_blocker_metadata")
        self.assertEqual(families["jstor"], "jstor_or_legacy_doi")
        self.assertIn("Title-only", guide.loc[guide["article_id"].eq("jstor"), "acceptable_evidence"].iloc[0])
        self.assertEqual(set(summary["source_route_family"]), {"partial_text_extension", "pdf_blocker_metadata", "jstor_or_legacy_doi"})

    def test_run_recovery_review_queue_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            split_path = root / "ready.csv"
            split_summary_path = root / "split_summary.csv"
            config_path = root / "config.yml"
            output_queue = root / "outputs" / "queue.csv"
            output_summary = root / "outputs" / "summary.csv"
            output_guide = root / "outputs" / "source_guide.csv"
            output_guide_summary = root / "outputs" / "source_guide_summary.csv"
            report_path = root / "docs" / "queue.md"
            guide_report_path = root / "docs" / "source_guide.md"
            guided_form = root / "forms" / "guided_queue.html"
            tiered_output_dir = root / "outputs" / "tiered"
            tiered_form_dir = root / "forms" / "tiered"
            tiered_index = root / "outputs" / "tiered_index.csv"
            tiered_report = root / "docs" / "tiered.md"
            tiered_output_dir.mkdir(parents=True)
            tiered_form_dir.mkdir(parents=True)
            stale_csv = tiered_output_dir / "recovery_batch_R001_tier_02_old_name.csv"
            stale_html = tiered_form_dir / "recovery_batch_R001_tier_02_old_name.html"
            unrelated_csv = tiered_output_dir / "keep_other_batch.csv"
            stale_csv.write_text("old\n", encoding="utf-8")
            stale_html.write_text("<html>old</html>\n", encoding="utf-8")
            unrelated_csv.write_text("keep\n", encoding="utf-8")
            pd.DataFrame(
                [
                    split_row(
                        "a1",
                        split_group="ready_partial_text_extension",
                        row_status="manual_extend_partial_text",
                        current_text_chars="225",
                    )
                ]
            ).to_csv(split_path, index=False)
            pd.DataFrame([{"recovery_batch": "R001", "split_group": "ready_partial_text_extension", "rows": "1", "output_csv": str(split_path)}]).to_csv(split_summary_path, index=False)
            config_path.write_text("minimum_usable_text_chars: 250\n", encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()):
                queue, summary = run_recovery_review_queue(
                    split_summary_path=split_summary_path,
                    config_path=config_path,
                    output_queue=output_queue,
                    output_summary=output_summary,
                    report_path=report_path,
                    output_guide=output_guide,
                    output_guide_summary=output_guide_summary,
                    guide_report_path=guide_report_path,
                    guided_form_path=guided_form,
                    tiered_output_dir=tiered_output_dir,
                    tiered_form_dir=tiered_form_dir,
                    tiered_index_output=tiered_index,
                    tiered_report_path=tiered_report,
                )

            self.assertEqual(len(queue), 1)
            self.assertFalse(summary.empty)
            self.assertTrue(output_queue.exists())
            self.assertTrue(output_summary.exists())
            self.assertTrue(output_guide.exists())
            self.assertTrue(output_guide_summary.exists())
            self.assertTrue(report_path.exists())
            self.assertTrue(guide_report_path.exists())
            self.assertTrue(guided_form.exists())
            self.assertTrue(tiered_index.exists())
            self.assertTrue(tiered_report.exists())
            self.assertIn("Recovery Batch R001 Review Queue", report_path.read_text(encoding="utf-8"))
            self.assertIn("Recovery Batch R001 Source Guide", guide_report_path.read_text(encoding="utf-8"))
            self.assertIn("Recovery Batch R001 Tiered Packets", tiered_report.read_text(encoding="utf-8"))
            guided_html = guided_form.read_text(encoding="utf-8")
            self.assertIn("Insufficient Text Recovery R001 Guided Queue", guided_html)
            self.assertIn("First source to check", guided_html)
            tiered = pd.read_csv(tiered_index, dtype=str).fillna("")
            self.assertEqual(tiered.iloc[0]["quick_win_tier"], "tier_1_partial_near_threshold")
            self.assertTrue(Path(tiered.iloc[0]["html_path"]).exists())
            self.assertFalse(stale_csv.exists())
            self.assertFalse(stale_html.exists())
            self.assertTrue(unrelated_csv.exists())


if __name__ == "__main__":
    unittest.main()
