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

from recovery_tiered_stage import run_recovery_tiered_stage  # noqa: E402


def split_row(article_id: str, *, split_group: str, title: str, current_abstract: str = "") -> dict[str, str]:
    return {
        "recovery_batch": "R001",
        "split_group": split_group,
        "row_status": "manual_extend_partial_text" if split_group == "ready_partial_text_extension" else "manual_index_or_new_template",
        "batch_row": "001",
        "recovery_rank": "1",
        "recovery_priority": "high",
        "article_id": article_id,
        "journal_short": "aer",
        "publication_year": "1980",
        "title": title,
        "doi": "10.1/test",
        "abstract": "",
        "source": "",
        "source_url": "",
        "source_record_id": "",
        "evidence_tier": "",
        "notes": "",
        "current_abstract": current_abstract,
        "current_abstract_chars": str(len(current_abstract)),
        "current_text_chars": str(len(title) + len(current_abstract)),
    }


class RecoveryTieredStageTests(unittest.TestCase):
    def test_run_recovery_tiered_stage_writes_staged_split_packets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            split_dir = root / "splits"
            reviewer_dir = root / "exports"
            output_dir = root / "staged"
            outputs = root / "outputs"
            docs = root / "docs"
            split_dir.mkdir()
            reviewer_dir.mkdir()

            partial_path = split_dir / "ready_partial.csv"
            manual_path = split_dir / "ready_manual.csv"
            split_summary_path = root / "split_summary.csv"
            output_summary = outputs / "staged_summary.csv"
            output_changes = outputs / "stage_changes.csv"
            output_errors = outputs / "stage_errors.csv"
            report_path = docs / "stage.md"

            pd.DataFrame(
                [
                    split_row(
                        "p1",
                        split_group="ready_partial_text_extension",
                        title="Partial Text",
                        current_abstract="Existing short abstract.",
                    ),
                    split_row(
                        "p2",
                        split_group="ready_partial_text_extension",
                        title="Second Partial Text",
                        current_abstract="Another short abstract.",
                    ),
                ]
            ).to_csv(partial_path, index=False)
            pd.DataFrame([split_row("m1", split_group="ready_manual_metadata", title="Manual Metadata")]).to_csv(manual_path, index=False)
            pd.DataFrame(
                [
                    {"recovery_batch": "R001", "split_group": "ready_partial_text_extension", "rows": "1", "output_csv": str(partial_path), "recommended_next_step": "Extend."},
                    {"recovery_batch": "R001", "split_group": "ready_manual_metadata", "rows": "1", "output_csv": str(manual_path), "recommended_next_step": "Recover."},
                    {"recovery_batch": "R001", "split_group": "ready_autofill_or_completed", "rows": "0", "output_csv": "", "recommended_next_step": "None."},
                ]
            ).to_csv(split_summary_path, index=False)
            pd.DataFrame(
                [
                    {
                        "article_id": "p1",
                        "split_group": "ready_partial_text_extension",
                        "quick_win_tier": "tier_1_partial_near_threshold",
                        "abstract": "Existing short abstract. Extended with source-confirmed details.",
                        "source": "econlit",
                        "source_url": "https://example.test/p1",
                        "source_record_id": "",
                        "evidence_tier": "tier_b_source_description",
                        "notes": "extended",
                    },
                    {
                        "article_id": "m1",
                        "split_group": "ready_manual_metadata",
                        "quick_win_tier": "tier_3_manual_metadata_has_context",
                        "abstract": "A complete source-confirmed abstract for manual metadata.",
                        "source": "jstor",
                        "source_url": "",
                        "source_record_id": "stable/123",
                        "evidence_tier": "tier_a_formal_abstract",
                        "notes": "",
                    },
                ]
            ).to_csv(reviewer_dir / "reviewer_a.csv", index=False)

            with contextlib.redirect_stdout(io.StringIO()):
                summary, changes, errors = run_recovery_tiered_stage(
                    split_summary_path=split_summary_path,
                    reviewer_input=reviewer_dir,
                    imported_history_path=None,
                    output_dir=output_dir,
                    output_summary=output_summary,
                    output_changes=output_changes,
                    output_errors=output_errors,
                    report_path=report_path,
                )

            self.assertTrue(errors.empty)
            self.assertEqual(len(changes), 2)
            self.assertTrue(output_summary.exists())
            self.assertTrue(output_changes.exists())
            self.assertTrue(output_errors.exists())
            self.assertTrue(report_path.exists())
            staged_partial = pd.read_csv(output_dir / "insufficient_text_recovery_batch_R001_ready_partial_text_extension.csv", dtype=str).fillna("")
            staged_manual = pd.read_csv(output_dir / "insufficient_text_recovery_batch_R001_ready_manual_metadata.csv", dtype=str).fillna("")
            self.assertIn("Extended with source-confirmed", staged_partial.iloc[0]["abstract"])
            self.assertEqual(staged_partial.iloc[0]["source"], "econlit")
            self.assertEqual(staged_manual.iloc[0]["source_record_id"], "stable/123")
            self.assertEqual(staged_partial.iloc[0]["evidence_tier"], "tier_b_source_description")
            self.assertEqual(changes.loc[changes["article_id"].eq("p1"), "evidence_tier"].iloc[0], "tier_b_source_description")
            indexed = summary.set_index("split_group")
            self.assertEqual(int(indexed.loc["ready_partial_text_extension", "source_ready_backfill_abstracts"]), 1)
            self.assertEqual(int(indexed.loc["ready_manual_metadata", "source_ready_backfill_abstracts"]), 1)
            self.assertIn("Tiered Stage", report_path.read_text(encoding="utf-8"))

    def test_run_recovery_tiered_stage_reports_identity_and_completion_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            split_dir = root / "splits"
            reviewer_dir = root / "exports"
            split_dir.mkdir()
            reviewer_dir.mkdir()
            partial_path = split_dir / "ready_partial.csv"
            split_summary_path = root / "split_summary.csv"

            pd.DataFrame(
                [
                    split_row(
                        "p1",
                        split_group="ready_partial_text_extension",
                        title="Partial Text",
                        current_abstract="Existing short abstract.",
                    ),
                    split_row(
                        "p2",
                        split_group="ready_partial_text_extension",
                        title="Second Partial Text",
                        current_abstract="Another short abstract.",
                    ),
                    split_row(
                        "p3",
                        split_group="ready_partial_text_extension",
                        title="Already Imported Partial",
                        current_abstract="Current imported abstract that already matches the reviewer export.",
                    )
                ]
            ).to_csv(partial_path, index=False)
            pd.DataFrame(
                [
                    {"recovery_batch": "R001", "split_group": "ready_partial_text_extension", "rows": "2", "output_csv": str(partial_path), "recommended_next_step": "Extend."},
                ]
            ).to_csv(split_summary_path, index=False)
            pd.DataFrame(
                [
                    {
                        "article_id": "p1",
                        "split_group": "ready_partial_text_extension",
                        "quick_win_tier": "tier_1_partial_near_threshold",
                        "abstract": "Existing short abstract. A completed extension.",
                        "source": "econlit",
                        "source_url": "https://example.test/p1",
                        "source_record_id": "",
                        "evidence_tier": "tier_b_source_description",
                    },
                    {
                        "article_id": "p2",
                        "split_group": "ready_partial_text_extension",
                        "quick_win_tier": "tier_1_partial_near_threshold",
                        "abstract": "Short.",
                        "source": "econlit",
                        "source_url": "https://example.test/p2",
                        "source_record_id": "",
                        "evidence_tier": "tier_b_source_description",
                    },
                    {
                        "article_id": "p3",
                        "split_group": "ready_partial_text_extension",
                        "quick_win_tier": "tier_1_partial_near_threshold",
                        "abstract": "Current imported abstract that already matches the reviewer export.",
                        "source": "econlit",
                        "source_url": "https://example.test/p3",
                        "source_record_id": "",
                        "evidence_tier": "tier_b_source_description",
                    },
                    {
                        "article_id": "missing",
                        "split_group": "ready_partial_text_extension",
                        "abstract": "Recovered abstract.",
                        "source": "econlit",
                        "source_url": "https://example.test/missing",
                        "evidence_tier": "tier_a_formal_abstract",
                    },
                ]
            ).to_csv(reviewer_dir / "reviewer_a.csv", index=False)
            pd.DataFrame(
                [
                    {
                        "article_id": "p1",
                        "split_group": "ready_partial_text_extension",
                        "quick_win_tier": "tier_1_partial_near_threshold",
                        "abstract": "Existing short abstract. A different completed duplicate.",
                        "source": "econlit",
                        "source_url": "https://example.test/p1-duplicate",
                        "source_record_id": "",
                        "evidence_tier": "tier_b_source_description",
                    }
                ]
            ).to_csv(reviewer_dir / "reviewer_b.csv", index=False)

            with contextlib.redirect_stdout(io.StringIO()):
                _, changes, errors = run_recovery_tiered_stage(
                    split_summary_path=split_summary_path,
                    reviewer_input=reviewer_dir,
                    imported_history_path=None,
                    output_dir=root / "staged",
                    output_summary=root / "outputs" / "staged_summary.csv",
                    output_changes=root / "outputs" / "stage_changes.csv",
                    output_errors=root / "outputs" / "stage_errors.csv",
                    report_path=root / "docs" / "stage.md",
                )

            self.assertTrue(changes.empty)
            self.assertIn("partial_text_not_extended", set(errors["error"]))
            self.assertIn("tiered_row_not_in_ready_split", set(errors["error"]))
            self.assertIn("duplicate_completed_tiered_row", set(errors["error"]))
            self.assertNotIn("p3", set(errors["article_id"]))

    def test_run_recovery_tiered_stage_rejects_unimportable_evidence_tier(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            split_dir = root / "splits"
            reviewer_dir = root / "exports"
            split_dir.mkdir()
            reviewer_dir.mkdir()
            partial_path = split_dir / "ready_partial.csv"
            split_summary_path = root / "split_summary.csv"

            pd.DataFrame(
                [
                    split_row(
                        "p1",
                        split_group="ready_partial_text_extension",
                        title="Partial Text",
                        current_abstract="Existing short abstract.",
                    )
                ]
            ).to_csv(partial_path, index=False)
            pd.DataFrame(
                [{"recovery_batch": "R001", "split_group": "ready_partial_text_extension", "rows": "1", "output_csv": str(partial_path), "recommended_next_step": "Extend."}]
            ).to_csv(split_summary_path, index=False)
            pd.DataFrame(
                [
                    {
                        "article_id": "p1",
                        "split_group": "ready_partial_text_extension",
                        "abstract": "Existing short abstract. A completed extension.",
                        "source": "econlit",
                        "source_url": "https://example.test/p1",
                        "source_record_id": "",
                        "evidence_tier": "tier_d_title_only_triage",
                    }
                ]
            ).to_csv(reviewer_dir / "reviewer_a.csv", index=False)

            with contextlib.redirect_stdout(io.StringIO()):
                _, changes, errors = run_recovery_tiered_stage(
                    split_summary_path=split_summary_path,
                    reviewer_input=reviewer_dir,
                    imported_history_path=None,
                    output_dir=root / "staged",
                    output_summary=root / "outputs" / "staged_summary.csv",
                    output_changes=root / "outputs" / "stage_changes.csv",
                    output_errors=root / "outputs" / "stage_errors.csv",
                    report_path=root / "docs" / "stage.md",
                )

            self.assertTrue(changes.empty)
            self.assertEqual(errors.iloc[0]["error"], "unimportable_evidence_tier")

    def test_run_recovery_tiered_stage_skips_already_imported_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            split_dir = root / "splits"
            reviewer_dir = root / "exports"
            split_dir.mkdir()
            reviewer_dir.mkdir()
            partial_path = split_dir / "ready_partial.csv"
            split_summary_path = root / "split_summary.csv"
            imported_history_path = root / "import_history.csv"

            pd.DataFrame(
                [
                    split_row(
                        "already_imported",
                        split_group="ready_partial_text_extension",
                        title="Already Imported",
                        current_abstract="Existing short abstract.",
                    )
                ]
            ).to_csv(partial_path, index=False)
            pd.DataFrame(
                [
                    {
                        "recovery_batch": "R001",
                        "split_group": "ready_partial_text_extension",
                        "rows": "1",
                        "output_csv": str(partial_path),
                        "recommended_next_step": "Extend.",
                    }
                ]
            ).to_csv(split_summary_path, index=False)
            pd.DataFrame(
                [
                    {
                        "article_id": "already_imported",
                        "split_group": "ready_partial_text_extension",
                        "abstract": "Existing short abstract. A completed source-confirmed extension.",
                        "source": "institutional repository",
                        "source_url": "https://example.test/already-imported",
                        "source_record_id": "",
                        "evidence_tier": "tier_a_formal_abstract",
                    }
                ]
            ).to_csv(reviewer_dir / "reviewer_a.csv", index=False)
            pd.DataFrame([{"article_id": "already_imported"}]).to_csv(imported_history_path, index=False)

            with contextlib.redirect_stdout(io.StringIO()):
                summary, changes, errors = run_recovery_tiered_stage(
                    split_summary_path=split_summary_path,
                    reviewer_input=reviewer_dir,
                    imported_history_path=imported_history_path,
                    output_dir=root / "staged",
                    output_summary=root / "outputs" / "staged_summary.csv",
                    output_changes=root / "outputs" / "stage_changes.csv",
                    output_errors=root / "outputs" / "stage_errors.csv",
                    report_path=root / "docs" / "stage.md",
                )

            self.assertTrue(changes.empty)
            self.assertTrue(errors.empty)
            staged_partial = pd.read_csv(root / "staged" / "insufficient_text_recovery_batch_R001_ready_partial_text_extension.csv", dtype=str).fillna("")
            self.assertEqual(staged_partial.iloc[0]["abstract"], "")
            indexed = summary.set_index("split_group")
            self.assertEqual(int(indexed.loc["ready_partial_text_extension", "source_ready_backfill_abstracts"]), 0)


if __name__ == "__main__":
    unittest.main()
