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

from recovery_impact import (  # noqa: E402
    recovery_impact_changes,
    recovery_impact_summary,
    recovery_snapshot,
    recovery_source_experiments,
    run_recovery_impact_report,
)


def classified_row(
    article_id: str,
    *,
    category: str = "insufficient_text",
    text_chars: str = "120",
    title: str = "A Paper",
    doi: str = "10.2307/1910000",
    abstract_source: str = "",
    text_status: str = "not_found",
) -> dict[str, str]:
    return {
        "article_id": article_id,
        "journal_short": "ecta",
        "publication_year": "1980",
        "title": title,
        "doi": doi,
        "causal_predictive_category": category,
        "classification_text_chars": text_chars,
        "has_usable_classification_text": "yes" if category != "insufficient_text" else "no",
        "abstract_source": abstract_source,
        "text_enrichment_status": text_status,
    }


def queue_row(
    article_id: str,
    *,
    recovery_action: str = "recover_abstract_from_doi_or_publisher",
    recovery_rank: str = "1",
    doi: str = "10.2307/1910000",
    recovery_batch: str = "R001",
) -> dict[str, str]:
    return {
        "article_id": article_id,
        "journal_short": "ecta",
        "publication_year": "1980",
        "decade": "1980",
        "title": "A Paper",
        "doi": doi,
        "recovery_rank": recovery_rank,
        "recovery_batch": recovery_batch,
        "recovery_priority": "high",
        "recovery_action": recovery_action,
        "openalex_id": "W1",
    }


class RecoveryImpactTests(unittest.TestCase):
    def test_recovery_snapshot_maps_queue_rows_to_route_status(self) -> None:
        classified = pd.DataFrame([classified_row("a1")])
        queue = pd.DataFrame([queue_row("a1")])
        route_matrix = pd.DataFrame(
            [
                {
                    "route_unit": "10.2307",
                    "current_route_status": "unsupported_existing_route",
                    "source_route_note": "No enabled public metadata template.",
                }
            ]
        )

        snapshot = recovery_snapshot(classified, queue, route_matrix, pd.DataFrame(), snapshot_label="before")

        self.assertEqual(len(snapshot), 1)
        row = snapshot.iloc[0]
        self.assertEqual(row["snapshot_label"], "before")
        self.assertEqual(row["route_unit"], "10.2307")
        self.assertEqual(row["current_route_status"], "unsupported_existing_route")
        self.assertEqual(row["expansion_lane"], "jstor_or_legacy_metadata_10_2307")
        self.assertEqual(row["classification_text_chars"], "120")

    def test_recovery_impact_changes_and_summary_detect_recovered_rows(self) -> None:
        before = pd.DataFrame(
            [
                {
                    **classified_row("recovered", category="insufficient_text", text_chars="120", title="Recovered Paper"),
                    "snapshot_label": "before",
                    "recovery_batch": "R001",
                    "recovery_action": "extend_existing_short_abstract",
                    "expansion_lane": "partial_short_text_extension",
                    "route_unit": "partial_short_text_extension",
                    "current_route_status": "manual_partial_abstract_extension",
                    "source_route_note": "",
                    "recovery_rank": "1",
                    "recovery_priority": "high",
                    "import_source_file": "",
                },
                {
                    **classified_row("unchanged", category="insufficient_text", text_chars="80", title="Still Missing"),
                    "snapshot_label": "before",
                    "recovery_batch": "R001",
                    "recovery_action": "recover_abstract_from_doi_or_publisher",
                    "expansion_lane": "jstor_or_legacy_metadata_10_2307",
                    "route_unit": "10.2307",
                    "current_route_status": "unsupported_existing_route",
                    "source_route_note": "",
                    "recovery_rank": "2",
                    "recovery_priority": "high",
                    "import_source_file": "",
                },
            ]
        )
        after = pd.DataFrame(
            [
                {
                    **classified_row(
                        "recovered",
                        category="causal",
                        text_chars="360",
                        title="Recovered Paper",
                        abstract_source="text_enrichment:curated_backfill",
                        text_status="enriched",
                    ),
                    "snapshot_label": "after",
                    "recovery_batch": "",
                    "recovery_action": "",
                    "expansion_lane": "",
                    "route_unit": "",
                    "current_route_status": "",
                    "source_route_note": "",
                    "recovery_rank": "",
                    "recovery_priority": "",
                    "import_source_file": "data/intermediate/insufficient_text_recovery_batch_R001_ready_partial_text_extension.csv",
                },
                {
                    **classified_row("unchanged", category="insufficient_text", text_chars="80", title="Still Missing"),
                    "snapshot_label": "after",
                    "recovery_batch": "R001",
                    "recovery_action": "recover_abstract_from_doi_or_publisher",
                    "expansion_lane": "jstor_or_legacy_metadata_10_2307",
                    "route_unit": "10.2307",
                    "current_route_status": "unsupported_existing_route",
                    "source_route_note": "",
                    "recovery_rank": "2",
                    "recovery_priority": "high",
                    "import_source_file": "",
                },
            ]
        )

        changes = recovery_impact_changes(before, after)
        summary = recovery_impact_summary(before, after)
        overall = summary[(summary["summary_group"].eq("overall")) & (summary["summary_value"].eq("all"))].iloc[0]

        self.assertEqual(len(changes), 1)
        self.assertEqual(changes.iloc[0]["article_id"], "recovered")
        self.assertEqual(changes.iloc[0]["recovered_from_insufficient"], "True")
        self.assertEqual(changes.iloc[0]["before_expansion_lane"], "partial_short_text_extension")
        self.assertEqual(int(overall["before_insufficient_rows"]), 2)
        self.assertEqual(int(overall["after_insufficient_rows"]), 1)
        self.assertEqual(int(overall["recovered_rows"]), 1)
        self.assertEqual(int(overall["net_insufficient_change"]), -1)

    def test_recovery_source_experiments_rank_manual_r001_work_first(self) -> None:
        recovery_queue = pd.DataFrame(
            [
                queue_row("a1", doi="10.2307/1910000"),
                queue_row("a2", doi="10.1086/260000", recovery_rank="2"),
            ]
        )
        route_matrix = pd.DataFrame(
            [
                {
                    "route_unit": "10.2307",
                    "row_count": "1048",
                    "current_route_status": "unsupported_existing_route",
                    "next_artifact": "data/intermediate/insufficient_text_recovery_batches/",
                },
                {
                    "route_unit": "10.1086",
                    "row_count": "810",
                    "current_route_status": "do_not_rerun_landing_pages",
                    "next_artifact": "outputs/tables/enriched/insufficient_text_source_investigation_packet.csv",
                },
            ]
        )
        review_queue = pd.DataFrame(
            [
                {"article_id": "p1", "split_group": "ready_partial_text_extension", "quick_win_tier": "tier_1_partial_near_threshold"},
                {"article_id": "p2", "split_group": "ready_partial_text_extension", "quick_win_tier": "tier_2_partial_replace_suspect_text"},
                {"article_id": "p3", "split_group": "ready_partial_text_extension", "quick_win_tier": "tier_3_partial_extension"},
                {"article_id": "m1", "split_group": "ready_manual_metadata", "quick_win_tier": "tier_4_manual_metadata_has_context"},
            ]
        )
        split_summary = pd.DataFrame([{"split_group": "waiting_scope_review", "rows": "7"}])
        profile = pd.DataFrame([{"journal_short": "aer", "decade": "1980", "insufficient_rows": "449"}])

        experiments = recovery_source_experiments(recovery_queue, route_matrix, review_queue, split_summary, profile)

        self.assertEqual(experiments.iloc[0]["experiment_id"], "R001_partial_extension")
        self.assertIn("suspect boilerplate", experiments.iloc[0]["expected_payoff"])
        self.assertEqual(experiments.iloc[1]["experiment_id"], "R001_manual_metadata")
        self.assertIn("access challenges", " ".join(experiments[experiments["experiment_type"].eq("source_template_spike")]["stop_rule"].tolist()))
        self.assertIn("credentialed_api_pass", set(experiments["experiment_type"]))

    def test_run_recovery_impact_report_writes_snapshot_and_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            classified_path = root / "classified.csv"
            queue_path = root / "queue.csv"
            route_path = root / "route.csv"
            history_path = root / "history.csv"
            profile_path = root / "profile.csv"
            review_queue_path = root / "review_queue.csv"
            split_summary_path = root / "split_summary.csv"
            snapshot_dir = root / "snapshots"
            output_summary = root / "outputs" / "summary.csv"
            output_changes = root / "outputs" / "changes.csv"
            output_experiments = root / "outputs" / "experiments.csv"
            report_path = root / "docs" / "impact.md"

            pd.DataFrame([classified_row("a1")]).to_csv(classified_path, index=False)
            pd.DataFrame([queue_row("a1")]).to_csv(queue_path, index=False)
            pd.DataFrame([{"route_unit": "10.2307", "row_count": "1", "current_route_status": "unsupported_existing_route"}]).to_csv(route_path, index=False)
            pd.DataFrame(columns=["article_id", "import_source_file"]).to_csv(history_path, index=False)
            pd.DataFrame([{"journal_short": "ecta", "decade": "1980", "insufficient_rows": "1"}]).to_csv(profile_path, index=False)
            pd.DataFrame([{"article_id": "p1", "split_group": "ready_partial_text_extension", "quick_win_tier": "tier_1_partial_near_threshold"}]).to_csv(review_queue_path, index=False)
            pd.DataFrame([{"split_group": "waiting_scope_review", "rows": "0"}]).to_csv(split_summary_path, index=False)

            with contextlib.redirect_stdout(io.StringIO()):
                snapshot, summary, changes, experiments = run_recovery_impact_report(
                    snapshot_label="before_R001",
                    write_snapshot=True,
                    compare_to="",
                    classified_path=classified_path,
                    recovery_queue_path=queue_path,
                    route_matrix_path=route_path,
                    import_history_path=history_path,
                    remaining_profile_path=profile_path,
                    review_queue_path=review_queue_path,
                    split_summary_path=split_summary_path,
                    snapshot_dir=snapshot_dir,
                    output_summary=output_summary,
                    output_changes=output_changes,
                    output_experiments=output_experiments,
                    report_path=report_path,
                )

            self.assertEqual(len(snapshot), 1)
            self.assertFalse(summary.empty)
            overall = summary[(summary["summary_group"].eq("overall")) & (summary["summary_value"].eq("all"))].iloc[0]
            self.assertEqual(int(overall["before_insufficient_rows"]), 1)
            self.assertEqual(int(overall["after_insufficient_rows"]), 1)
            self.assertEqual(int(overall["net_insufficient_change"]), 0)
            self.assertTrue(changes.empty)
            self.assertFalse(experiments.empty)
            self.assertTrue((snapshot_dir / "before_R001.csv").exists())
            self.assertTrue(output_summary.exists())
            self.assertTrue(output_changes.exists())
            self.assertTrue(output_experiments.exists())
            self.assertIn("Recovery Impact Report", report_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
