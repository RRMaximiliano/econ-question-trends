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

from recovery_split_preflight import run_recovery_split_preflight  # noqa: E402


def sample_articles() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "article_id": "a1",
                "journal_short": "aer",
                "publication_year": "1980",
                "title": "Partial Text",
                "doi": "10.1/a",
                "article_url": "https://doi.org/10.1/a",
                "abstract": "",
                "article_type": "research-article",
            },
            {
                "article_id": "a2",
                "journal_short": "jpe",
                "publication_year": "1981",
                "title": "Recovered Metadata",
                "doi": "10.2/b",
                "article_url": "https://doi.org/10.2/b",
                "abstract": "",
                "article_type": "research-article",
            },
            {
                "article_id": "a3",
                "journal_short": "ecta",
                "publication_year": "1982",
                "title": "Missing Source Locator",
                "doi": "10.3/c",
                "article_url": "https://doi.org/10.3/c",
                "abstract": "",
                "article_type": "research-article",
            },
            {
                "article_id": "a4",
                "journal_short": "qje",
                "publication_year": "1983",
                "title": "Waiting Scope",
                "doi": "10.4/d",
                "article_url": "https://doi.org/10.4/d",
                "abstract": "",
                "article_type": "research-article",
            },
        ]
    )


class RecoverySplitPreflightTests(unittest.TestCase):
    def test_run_recovery_split_preflight_writes_combined_summary_and_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            split_dir = root / "splits"
            output_dir = root / "outputs"
            docs_dir = root / "docs"
            split_dir.mkdir()

            ready_partial = split_dir / "ready_partial.csv"
            ready_manual = split_dir / "ready_manual.csv"
            ready_autofill = split_dir / "ready_autofill.csv"
            waiting_scope = split_dir / "waiting_scope.csv"
            articles_path = root / "articles.csv"
            config_path = root / "text_enrichment.yml"
            split_summary_path = root / "split_summary.csv"
            output_summary = output_dir / "preflight_summary.csv"
            output_errors = output_dir / "preflight_errors.csv"
            report_path = docs_dir / "preflight.md"

            sample_articles().to_csv(articles_path, index=False)
            config_path.write_text("minimum_usable_text_chars: 20\narticle_scope_patterns: {}\n", encoding="utf-8")
            pd.DataFrame([{"article_id": "a1", "title": "Partial Text", "publication_year": "1980", "abstract": "", "source": "", "source_url": "", "source_record_id": ""}]).to_csv(ready_partial, index=False)
            pd.DataFrame(
                [
                    {
                        "article_id": "a2",
                        "title": "Recovered Metadata",
                        "publication_year": "1981",
                        "abstract": "This recovered abstract has enough text for classification.",
                        "source": "econlit",
                        "source_url": "https://example.test/a2",
                        "source_record_id": "",
                        "evidence_tier": "tier_a_formal_abstract",
                    }
                ]
            ).to_csv(ready_manual, index=False)
            pd.DataFrame(
                [
                    {
                        "article_id": "a3",
                        "title": "Missing Source Locator",
                        "publication_year": "1982",
                        "abstract": "This abstract is filled but lacks a required source locator.",
                        "source": "econlit",
                        "source_url": "",
                        "source_record_id": "",
                        "evidence_tier": "tier_a_formal_abstract",
                    }
                ]
            ).to_csv(ready_autofill, index=False)
            pd.DataFrame(
                [
                    {
                        "article_id": "a4",
                        "title": "Waiting Scope",
                        "publication_year": "1983",
                        "abstract": "This waiting row should not be checked yet.",
                        "source": "econlit",
                        "source_url": "https://example.test/a4",
                        "source_record_id": "",
                        "evidence_tier": "tier_a_formal_abstract",
                    }
                ]
            ).to_csv(waiting_scope, index=False)
            pd.DataFrame(
                [
                    {"recovery_batch": "R001", "split_group": "ready_partial_text_extension", "rows": "1", "output_csv": str(ready_partial), "recommended_next_step": "Extend partial text."},
                    {"recovery_batch": "R001", "split_group": "ready_manual_metadata", "rows": "1", "output_csv": str(ready_manual), "recommended_next_step": "Recover metadata."},
                    {"recovery_batch": "R001", "split_group": "ready_autofill_or_completed", "rows": "1", "output_csv": str(ready_autofill), "recommended_next_step": "Autofill."},
                    {"recovery_batch": "R001", "split_group": "waiting_scope_review", "rows": "1", "output_csv": str(waiting_scope), "recommended_next_step": "Wait."},
                ]
            ).to_csv(split_summary_path, index=False)

            with contextlib.redirect_stdout(io.StringIO()):
                summary, errors = run_recovery_split_preflight(
                    split_summary_path=split_summary_path,
                    articles_input=articles_path,
                    config_path=config_path,
                    output_summary=output_summary,
                    output_errors=output_errors,
                    report_path=report_path,
                )

            indexed = summary.set_index("split_group")

            self.assertEqual(indexed.loc["ready_partial_text_extension", "preflight_status"], "pass_empty")
            self.assertEqual(int(indexed.loc["ready_partial_text_extension", "skipped_empty_abstract_rows"]), 1)
            self.assertEqual(indexed.loc["ready_manual_metadata", "preflight_status"], "pass_ready")
            self.assertEqual(int(indexed.loc["ready_manual_metadata", "import_ready_rows"]), 1)
            self.assertEqual(indexed.loc["ready_autofill_or_completed", "preflight_status"], "blocked_errors")
            self.assertNotIn("waiting_scope_review", set(summary["split_group"]))
            self.assertEqual(len(errors), 1)
            self.assertEqual(errors.iloc[0]["error"], "missing_source_locator")
            self.assertTrue(output_summary.exists())
            self.assertTrue(output_errors.exists())
            self.assertTrue(report_path.exists())
            self.assertIn("Recovery Batch R001 Split Preflight", report_path.read_text(encoding="utf-8"))

    def test_run_recovery_split_preflight_rejects_title_only_evidence_tier(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            split_dir = root / "splits"
            output_dir = root / "outputs"
            docs_dir = root / "docs"
            split_dir.mkdir()

            ready_manual = split_dir / "ready_manual.csv"
            articles_path = root / "articles.csv"
            config_path = root / "text_enrichment.yml"
            split_summary_path = root / "split_summary.csv"

            sample_articles().to_csv(articles_path, index=False)
            config_path.write_text("minimum_usable_text_chars: 20\narticle_scope_patterns: {}\n", encoding="utf-8")
            pd.DataFrame(
                [
                    {
                        "article_id": "a2",
                        "title": "Recovered Metadata",
                        "publication_year": "1981",
                        "abstract": "This recovered abstract has enough text for classification.",
                        "source": "econlit",
                        "source_url": "https://example.test/a2",
                        "source_record_id": "",
                        "evidence_tier": "tier_d_title_only_triage",
                    }
                ]
            ).to_csv(ready_manual, index=False)
            pd.DataFrame(
                [
                    {"recovery_batch": "R001", "split_group": "ready_manual_metadata", "rows": "1", "output_csv": str(ready_manual), "recommended_next_step": "Recover metadata."},
                ]
            ).to_csv(split_summary_path, index=False)

            with contextlib.redirect_stdout(io.StringIO()):
                summary, errors = run_recovery_split_preflight(
                    split_summary_path=split_summary_path,
                    articles_input=articles_path,
                    config_path=config_path,
                    output_summary=output_dir / "preflight_summary.csv",
                    output_errors=output_dir / "preflight_errors.csv",
                    report_path=docs_dir / "preflight.md",
                )

            self.assertEqual(summary.iloc[0]["preflight_status"], "blocked_errors")
            self.assertEqual(errors.iloc[0]["error"], "unimportable_evidence_tier")

    def test_run_recovery_split_preflight_reports_missing_split_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            articles_path = root / "articles.csv"
            config_path = root / "text_enrichment.yml"
            split_summary_path = root / "split_summary.csv"
            output_summary = root / "outputs" / "preflight_summary.csv"
            output_errors = root / "outputs" / "preflight_errors.csv"
            report_path = root / "docs" / "preflight.md"

            sample_articles().to_csv(articles_path, index=False)
            config_path.write_text("minimum_usable_text_chars: 20\narticle_scope_patterns: {}\n", encoding="utf-8")
            pd.DataFrame(
                [
                    {
                        "recovery_batch": "R001",
                        "split_group": "ready_manual_metadata",
                        "rows": "1",
                        "output_csv": str(root / "missing.csv"),
                        "recommended_next_step": "Recover metadata.",
                    }
                ]
            ).to_csv(split_summary_path, index=False)

            with contextlib.redirect_stdout(io.StringIO()):
                summary, errors = run_recovery_split_preflight(
                    split_summary_path=split_summary_path,
                    articles_input=articles_path,
                    config_path=config_path,
                    output_summary=output_summary,
                    output_errors=output_errors,
                    report_path=report_path,
                )

            self.assertEqual(summary.iloc[0]["preflight_status"], "missing_file")
            self.assertEqual(errors.iloc[0]["error"], "missing_split_file")


if __name__ == "__main__":
    unittest.main()
