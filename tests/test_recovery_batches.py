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

from recovery_batches import (  # noqa: E402
    apply_existing_recovery_edits,
    batch_summary,
    make_recovery_packets,
    read_existing_recovery_edits,
    recovery_form_html,
    write_recovery_batches,
)


class RecoveryBatchTests(unittest.TestCase):
    def test_make_recovery_packets_adds_importable_backfill_columns(self) -> None:
        queue = pd.DataFrame(
            [
                {
                    "recovery_batch": "R001",
                    "recovery_rank": "1",
                    "recovery_priority": "high",
                    "recovery_priority_score": "20",
                    "recovery_action": "recover_abstract_from_doi_or_publisher",
                    "recovery_reason": "doi_available|openalex_id_available",
                    "article_id": "a1",
                    "journal_short": "aer",
                    "publication_year": "1980",
                    "decade": "1980",
                    "title": "A Title",
                    "doi": "10.1/a",
                    "doi_url": "https://doi.org/10.1/a",
                    "backfill_abstract": "Recovered abstract",
                }
            ]
        )

        packets = make_recovery_packets(queue)

        self.assertEqual(len(packets), 1)
        batch_id, packet = packets[0]
        self.assertEqual(batch_id, "R001")
        self.assertEqual(packet.iloc[0]["batch_row"], "001")
        self.assertIn("abstract", packet.columns)
        self.assertEqual(packet.iloc[0]["abstract"], "Recovered abstract")
        self.assertIn("source_url", packet.columns)

    def test_batch_summary_counts_remaining_abstracts_and_actions(self) -> None:
        queue = pd.DataFrame(
            [
                {
                    "recovery_batch": "R001",
                    "article_id": "a1",
                    "recovery_priority": "high",
                    "recovery_action": "review_openalex_or_title_match",
                    "abstract": "Recovered",
                },
                {
                    "recovery_batch": "R001",
                    "article_id": "a2",
                    "recovery_priority": "medium",
                    "recovery_action": "review_openalex_or_title_match",
                    "abstract": "",
                },
            ]
        )
        packets = make_recovery_packets(queue)

        summary = batch_summary(packets)

        self.assertEqual(int(summary.iloc[0]["total_rows"]), 2)
        self.assertEqual(int(summary.iloc[0]["completed_backfill_abstracts"]), 1)
        self.assertEqual(int(summary.iloc[0]["remaining_backfill_abstracts"]), 1)
        self.assertEqual(int(summary.iloc[0]["action_review_openalex_or_title_match"]), 2)

    def test_recovery_form_html_contains_lookup_links_and_export_fields(self) -> None:
        queue = pd.DataFrame(
            [
                {
                    "recovery_batch": "R001",
                    "article_id": "a1",
                    "recovery_rank": "1",
                    "recovery_priority": "high",
                    "recovery_action": "manual_title_year_search",
                    "recovery_reason": "missing_abstract",
                    "title": "A Title",
                    "publication_year": "1980",
                    "journal_short": "aer",
                    "doi_url": "https://doi.org/10.1/a",
                }
            ]
        )
        _, packet = make_recovery_packets(queue)[0]

        html = recovery_form_html(packet, title="Recovery R001")

        self.assertIn("Recovery R001", html)
        self.assertIn("https://doi.org/10.1/a", html)
        self.assertIn('data-name="abstract"', html)
        self.assertIn("Export CSV", html)

    def test_recovery_form_html_shows_optional_source_guidance_without_exporting_it(self) -> None:
        packet = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "title": "A Guided Row",
                    "source_route_family": "partial_text_extension",
                    "first_source_to_check": "Start from current abstract source.",
                    "acceptable_evidence": "Recovered abstract text plus source metadata.",
                    "stop_rule": "Stop if provenance is missing.",
                }
            ]
        )

        html = recovery_form_html(packet, title="Guided Recovery")

        self.assertIn("Source route", html)
        self.assertIn("partial_text_extension", html)
        self.assertIn("First source to check", html)
        self.assertIn("Start from current abstract source.", html)
        self.assertIn("Acceptable evidence", html)
        self.assertIn("Stop rule", html)
        self.assertNotIn('"source_route_family"', html.split("const columns = ")[1].split(";")[0])

    def test_read_existing_recovery_edits_ignores_generated_notes_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            pd.DataFrame(
                [
                    {
                        "article_id": "a1",
                        "abstract": "",
                        "source": "",
                        "source_url": "",
                        "source_record_id": "",
                        "notes": "suggested_action=manual_title_year_search;recovery_reason=missing_abstract",
                    },
                    {
                        "article_id": "a2",
                        "abstract": "Recovered abstract",
                        "source": "manual",
                        "source_url": "https://example.test",
                        "source_record_id": "",
                        "notes": "Verified against source page",
                    },
                ]
            ).to_csv(output_dir / "insufficient_text_recovery_batch_R001.csv", index=False)

            edits = read_existing_recovery_edits(output_dir)

            self.assertEqual(edits["article_id"].tolist(), ["a2"])
            self.assertEqual(edits.iloc[0]["abstract"], "Recovered abstract")
            self.assertEqual(edits.iloc[0]["notes"], "Verified against source page")

    def test_apply_existing_recovery_edits_preserves_filled_backfill_fields(self) -> None:
        queue = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "abstract": "",
                    "source": "",
                    "source_url": "",
                    "source_record_id": "",
                    "notes": "suggested_action=old",
                }
            ]
        )
        edits = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "abstract": "Recovered abstract",
                    "source": "publisher_page",
                    "source_url": "https://example.test/source",
                    "source_record_id": "record-1",
                    "notes": "Human checked title match",
                }
            ]
        )

        out = apply_existing_recovery_edits(queue, edits)

        self.assertEqual(out.iloc[0]["abstract"], "Recovered abstract")
        self.assertEqual(out.iloc[0]["source"], "publisher_page")
        self.assertEqual(out.iloc[0]["source_url"], "https://example.test/source")
        self.assertEqual(out.iloc[0]["source_record_id"], "record-1")
        self.assertEqual(out.iloc[0]["notes"], "Human checked title match")

    def test_write_recovery_batches_preserves_existing_edits_by_default(self) -> None:
        queue = pd.DataFrame(
            [
                {
                    "recovery_batch": "R001",
                    "article_id": "a1",
                    "recovery_rank": "1",
                    "recovery_priority": "high",
                    "recovery_action": "manual_title_year_search",
                    "recovery_reason": "missing_abstract",
                    "title": "A Title",
                    "publication_year": "1980",
                }
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue_path = root / "queue.csv"
            output_dir = root / "batches"
            summary_path = root / "summary.csv"
            queue.to_csv(queue_path, index=False)
            output_dir.mkdir()
            pd.DataFrame(
                [
                    {
                        "article_id": "a1",
                        "abstract": "Recovered abstract",
                        "source": "manual",
                        "source_url": "https://example.test",
                        "source_record_id": "",
                        "notes": "Checked by reviewer",
                    }
                ]
            ).to_csv(output_dir / "insufficient_text_recovery_batch_R001.csv", index=False)

            with contextlib.redirect_stdout(io.StringIO()):
                write_recovery_batches(
                    queue_path=queue_path,
                    output_dir=output_dir,
                    html_dir=None,
                    summary_output=summary_path,
                    batch_size=100,
                )

            packet = pd.read_csv(output_dir / "insufficient_text_recovery_batch_R001.csv", dtype=str).fillna("")
            summary = pd.read_csv(summary_path, dtype=str).fillna("")
            self.assertEqual(packet.iloc[0]["abstract"], "Recovered abstract")
            self.assertEqual(packet.iloc[0]["source"], "manual")
            self.assertEqual(int(summary.iloc[0]["completed_backfill_abstracts"]), 1)


if __name__ == "__main__":
    unittest.main()
