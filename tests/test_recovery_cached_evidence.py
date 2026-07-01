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

from recovery_cached_evidence import (  # noqa: E402
    cached_evidence_summary,
    evidence_status,
    recovery_action_packet,
    recovery_action_summary,
    recovery_cached_evidence,
    run_recovery_cached_evidence,
    write_action_reviewer_packets,
)


def queue_row(
    article_id: str = "a1",
    *,
    title: str = "A Paper",
    doi: str = "10.2307/example",
    current_text_chars: str = "20",
    quick_win_tier: str = "tier_1_partial_near_threshold",
) -> dict[str, str]:
    return {
        "review_rank": "1",
        "article_id": article_id,
        "quick_win_tier": quick_win_tier,
        "journal_short": "ecta",
        "publication_year": "1980",
        "title": title,
        "doi": doi,
        "current_text_chars": current_text_chars,
    }


class RecoveryCachedEvidenceTests(unittest.TestCase):
    def test_recovery_cached_evidence_marks_source_record_import_candidate(self) -> None:
        queue = pd.DataFrame([queue_row(current_text_chars="20")])
        source_records = pd.DataFrame(
            [
                {
                    "source": "openalex",
                    "source_record_id": "https://openalex.org/W1",
                    "journal_short": "ecta",
                    "publication_year": "1980",
                    "title": "A Paper",
                    "doi": "10.2307/example",
                    "abstract": "This paper studies a long enough source-confirmed abstract with enough detail to cross the configured threshold.",
                    "article_url": "https://openalex.org/W1",
                }
            ]
        )

        detail = recovery_cached_evidence(
            queue,
            config={"minimum_usable_text_chars": 80, "source_timeout_seconds": 1, "source_sleep_seconds": {}},
            cache_dir=Path("does-not-matter"),
            sources=[],
            source_records=source_records,
        )

        self.assertEqual(detail.iloc[0]["cached_evidence_status"], "cached_import_candidate")
        self.assertEqual(detail.iloc[0]["candidate_source"], "source_records:openalex")
        self.assertEqual(detail.iloc[0]["evidence_tier_suggestion"], "review_required_tier_a_or_b")

    def test_recovery_cached_evidence_marks_current_text_only(self) -> None:
        abstract = (
            "This is source-confirmed context that remains below the configured threshold and only repeats the existing local text."
        )
        queue = pd.DataFrame([queue_row(current_text_chars="200")])
        source_records = pd.DataFrame(
            [
                {
                    "source": "openalex",
                    "source_record_id": "https://openalex.org/W1",
                    "journal_short": "ecta",
                    "publication_year": "1980",
                    "title": "A Paper",
                    "doi": "10.2307/example",
                    "abstract": abstract,
                    "article_url": "https://openalex.org/W1",
                }
            ]
        )

        detail = recovery_cached_evidence(
            queue,
            config={"minimum_usable_text_chars": 250, "source_timeout_seconds": 1, "source_sleep_seconds": {}},
            cache_dir=Path("does-not-matter"),
            sources=[],
            source_records=source_records,
        )

        self.assertEqual(detail.iloc[0]["cached_evidence_status"], "cached_current_text_only")
        self.assertIn("only repeats", detail.iloc[0]["recommended_action"])

    def test_evidence_status_rejects_suspect_text_before_import_candidate(self) -> None:
        status = evidence_status(
            candidate={"abstract": "boilerplate"},
            candidate_text_chars=500,
            candidate_abstract_chars=450,
            current_text_chars=10,
            minimum_chars=250,
            quality_flags="jstor_terms_boilerplate",
            fallback_status="found",
            candidate_oa_pdf_url="",
        )

        self.assertEqual(status, "cached_suspect_text_only")

    def test_run_recovery_cached_evidence_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue_path = root / "queue.csv"
            source_records_path = root / "source_records.csv"
            source_guide_path = root / "source_guide.csv"
            automation_detail_path = root / "automation.csv"
            config_path = root / "config.yml"
            detail_path = root / "outputs" / "detail.csv"
            summary_path = root / "outputs" / "summary.csv"
            action_packet_path = root / "outputs" / "action.csv"
            action_summary_path = root / "outputs" / "action_summary.csv"
            action_packet_dir = root / "outputs" / "action_packets"
            action_form_dir = root / "forms" / "actions"
            action_packet_index = root / "outputs" / "action_index.csv"
            report_path = root / "docs" / "cached.md"
            action_report_path = root / "docs" / "action.md"
            pd.DataFrame([queue_row(current_text_chars="20")]).to_csv(queue_path, index=False)
            pd.DataFrame(
                [
                    {
                        "source": "openalex",
                        "source_record_id": "https://openalex.org/W1",
                        "journal_short": "ecta",
                        "publication_year": "1980",
                        "title": "A Paper",
                        "doi": "10.2307/example",
                        "abstract": "This paper studies a long enough source-confirmed abstract with enough detail to cross the configured threshold.",
                        "article_url": "https://openalex.org/W1",
                    }
                ]
            ).to_csv(source_records_path, index=False)
            pd.DataFrame(
                [
                    {
                        "article_id": "a1",
                        "source_route_family": "partial_text_extension",
                        "first_source_to_check": "Check DOI metadata.",
                        "stop_rule": "Stop without provenance.",
                        "source_links": "doi=https://doi.org/10.2307/example",
                    }
                ]
            ).to_csv(source_guide_path, index=False)
            pd.DataFrame(
                [
                    {
                        "article_id": "a1",
                        "automation_status": "manual_near_threshold_extension",
                        "safe_next_action": "Extend only from explicit source metadata.",
                    }
                ]
            ).to_csv(automation_detail_path, index=False)
            config_path.write_text("minimum_usable_text_chars: 80\nsource_sleep_seconds: {}\nsource_timeout_seconds: 1\n", encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()):
                detail, summary = run_recovery_cached_evidence(
                    queue_path=queue_path,
                    config_path=config_path,
                    cache_dir=root / "cache",
                    source_records_path=source_records_path,
                    sources_value="",
                    output_detail=detail_path,
                    output_summary=summary_path,
                    report_path=report_path,
                    source_guide_path=source_guide_path,
                    automation_detail_path=automation_detail_path,
                    output_action_packet=action_packet_path,
                    output_action_summary=action_summary_path,
                    action_report_path=action_report_path,
                    action_packet_dir=action_packet_dir,
                    action_form_dir=action_form_dir,
                    action_packet_index_output=action_packet_index,
                )

            self.assertEqual(len(detail), 1)
            self.assertFalse(summary.empty)
            self.assertTrue(detail_path.exists())
            self.assertTrue(summary_path.exists())
            self.assertTrue(report_path.exists())
            self.assertTrue(action_packet_path.exists())
            self.assertTrue(action_summary_path.exists())
            self.assertTrue(action_packet_index.exists())
            self.assertTrue(action_report_path.exists())
            action_index = pd.read_csv(action_packet_index, dtype=str).fillna("")
            self.assertEqual(len(action_index), 1)
            self.assertTrue(Path(action_index.iloc[0]["html_path"]).exists())
            self.assertIn("Cached Evidence Audit", report_path.read_text(encoding="utf-8"))
            self.assertIn("Action Packet", action_report_path.read_text(encoding="utf-8"))

    def test_cached_evidence_summary_groups_status_and_tier(self) -> None:
        detail = pd.DataFrame(
            [
                {
                    "cached_evidence_status": "cached_import_candidate",
                    "quick_win_tier": "tier_1_partial_near_threshold",
                    "review_rank": "2",
                    "candidate_source": "source_records:openalex",
                },
                {
                    "cached_evidence_status": "cached_import_candidate",
                    "quick_win_tier": "tier_1_partial_near_threshold",
                    "review_rank": "1",
                    "candidate_source": "openalex",
                },
            ]
        )

        summary = cached_evidence_summary(detail)

        self.assertEqual(int(summary.iloc[0]["rows"]), 2)
        self.assertEqual(int(summary.iloc[0]["first_review_rank"]), 1)
        self.assertIn("openalex", summary.iloc[0]["candidate_sources"])

    def test_recovery_action_packet_turns_cache_status_into_reviewer_action(self) -> None:
        detail = pd.DataFrame(
            [
                {
                    "review_rank": "1",
                    "article_id": "a1",
                    "quick_win_tier": "tier_1_partial_near_threshold",
                    "journal_short": "ecta",
                    "publication_year": "1980",
                    "title": "Near Threshold",
                    "doi": "10.2307/example",
                    "cached_evidence_status": "cached_current_text_only",
                    "candidate_source": "openalex",
                    "candidate_text_chars": "247",
                    "current_text_chars": "247",
                    "chars_needed_to_threshold": "3",
                    "candidate_quality_flags": "",
                    "candidate_url": "https://api.openalex.org/works/W1",
                    "candidate_source_record_id": "https://openalex.org/W1",
                    "review_note": "",
                },
                {
                    "review_rank": "2",
                    "article_id": "a2",
                    "quick_win_tier": "tier_2_partial_replace_suspect_text",
                    "journal_short": "ecta",
                    "publication_year": "1980",
                    "title": "Boilerplate",
                    "doi": "10.2307/example2",
                    "cached_evidence_status": "cached_suspect_text_only",
                    "candidate_source": "openalex",
                    "candidate_text_chars": "0",
                    "current_text_chars": "80",
                    "chars_needed_to_threshold": "170",
                    "candidate_quality_flags": "jstor_terms_boilerplate",
                    "candidate_url": "https://api.openalex.org/works/W2",
                    "candidate_source_record_id": "https://openalex.org/W2",
                    "review_note": "",
                },
            ]
        )
        queue = pd.DataFrame(
            [
                {"article_id": "a1", "decade": "1980", "current_abstract": "Short current text.", "source_hint": "https://doi.org/10.2307/example"},
                {"article_id": "a2", "decade": "1980", "current_abstract": "JSTOR terms text.", "source_hint": "https://doi.org/10.2307/example2"},
            ]
        )
        source_guide = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "source_route_family": "partial_text_extension",
                    "first_source_to_check": "Check DOI metadata.",
                    "stop_rule": "Stop without provenance.",
                    "source_links": "doi=https://doi.org/10.2307/example",
                },
                {
                    "article_id": "a2",
                    "source_route_family": "partial_text_extension",
                    "first_source_to_check": "Check index metadata.",
                    "stop_rule": "Stop on boilerplate.",
                    "source_links": "doi=https://doi.org/10.2307/example2",
                },
            ]
        )
        automation = pd.DataFrame(
            [
                {"article_id": "a1", "automation_status": "manual_near_threshold_extension", "safe_next_action": "Extend only from explicit metadata."},
                {"article_id": "a2", "automation_status": "manual_replace_boilerplate", "safe_next_action": "Replace boilerplate."},
            ]
        )
        cell_targets = pd.DataFrame(
            [
                {
                    "journal_short": "ecta",
                    "decade": "1980",
                    "target_rank": "2",
                    "target_level": "core",
                    "recoveries_to_target_share": "208",
                    "projected_share_after_ready_r001": "0.4161",
                    "ready_r001_target_coverage": "0.1827",
                    "recommended_next_step": "Use R001 before expanding broader queue.",
                }
            ]
        )

        packet = recovery_action_packet(detail, queue=queue, source_guide=source_guide, automation_detail=automation, cell_targets=cell_targets)
        summary = recovery_action_summary(packet)
        groups = dict(zip(packet["article_id"], packet["action_group"]))

        self.assertEqual(groups["a1"], "find_external_extension")
        self.assertEqual(groups["a2"], "replace_boilerplate_from_new_source")
        self.assertIn("Do not rerun openalex", packet.loc[packet["article_id"].eq("a1"), "source_to_avoid"].iloc[0])
        self.assertIn("boilerplate", packet.loc[packet["article_id"].eq("a2"), "source_to_avoid"].iloc[0])
        self.assertEqual(packet.loc[packet["article_id"].eq("a1"), "cell_target_rank"].iloc[0], "2")
        self.assertEqual(packet.loc[packet["article_id"].eq("a2"), "cell_recoveries_to_target_share"].iloc[0], "208")
        self.assertIn("R001", packet.loc[packet["article_id"].eq("a1"), "cell_recommended_next_step"].iloc[0])
        self.assertEqual(int(summary["rows"].astype(int).sum()), 2)

    def test_write_action_reviewer_packets_groups_forms_by_action(self) -> None:
        queue = pd.DataFrame(
            [
                {
                    **queue_row("a1", title="Near Threshold", current_text_chars="247"),
                    "recovery_batch": "R001",
                    "split_group": "ready_partial_text_extension",
                    "recovery_rank": "1",
                    "recovery_priority": "high",
                    "recovery_action": "extend_existing_short_abstract",
                    "recovery_reason": "partial_text",
                    "abstract": "Short current text.",
                    "source": "",
                    "source_url": "",
                    "source_record_id": "",
                    "evidence_tier": "",
                    "notes": "",
                    "doi_url": "https://doi.org/10.2307/example",
                },
                {
                    **queue_row("a2", title="Boilerplate", current_text_chars="80", quick_win_tier="tier_2_partial_replace_suspect_text"),
                    "recovery_batch": "R001",
                    "split_group": "ready_partial_text_extension",
                    "recovery_rank": "2",
                    "recovery_priority": "high",
                    "recovery_action": "extend_existing_short_abstract",
                    "recovery_reason": "partial_text",
                    "abstract": "",
                    "source": "",
                    "source_url": "",
                    "source_record_id": "",
                    "evidence_tier": "",
                    "notes": "",
                    "doi_url": "https://doi.org/10.2307/example2",
                },
            ]
        )
        action_packet = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "action_group": "find_external_extension",
                    "reviewer_action": "Find an extension.",
                    "source_to_avoid": "Do not rerun openalex unchanged.",
                    "suggested_evidence_tier": "tier_a_formal_abstract or tier_b_source_description",
                    "cached_evidence_status": "cached_current_text_only",
                    "cell_target_rank": "2",
                    "cell_target_level": "core",
                    "cell_recoveries_to_target_share": "208",
                    "cell_projected_share_after_ready_r001": "0.4161",
                    "cell_ready_r001_target_coverage": "0.1827",
                    "cell_recommended_next_step": "Use R001 before expanding broader queue.",
                    "candidate_source": "openalex",
                    "candidate_text_chars": "247",
                },
                {
                    "article_id": "a2",
                    "action_group": "replace_boilerplate_from_new_source",
                    "reviewer_action": "Replace boilerplate.",
                    "source_to_avoid": "Do not reuse boilerplate.",
                    "suggested_evidence_tier": "tier_a_formal_abstract or tier_b_source_description",
                    "cached_evidence_status": "cached_suspect_text_only",
                    "candidate_source": "openalex",
                    "candidate_text_chars": "0",
                },
            ]
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = write_action_reviewer_packets(
                queue=queue,
                action_packet=action_packet,
                output_dir=root / "csv",
                html_dir=root / "html",
                index_output=root / "index.csv",
            )

            self.assertEqual(len(index), 2)
            self.assertEqual(index.iloc[0]["action_group"], "find_external_extension")
            first_csv = Path(index.iloc[0]["csv_path"])
            first_html = Path(index.iloc[0]["html_path"])
            self.assertTrue(first_csv.exists())
            self.assertTrue(first_html.exists())
            html = first_html.read_text(encoding="utf-8")
            self.assertIn("Reviewer action", html)
            self.assertIn("Do not rerun openalex unchanged.", html)
            exported = pd.read_csv(first_csv, dtype=str).fillna("")
            exported_columns = exported.columns
            self.assertIn("abstract", exported_columns)
            self.assertIn("action_group", exported_columns)
            self.assertIn("cell_target_rank", exported_columns)
            self.assertEqual(exported.iloc[0]["cell_target_rank"], "2")


if __name__ == "__main__":
    unittest.main()
