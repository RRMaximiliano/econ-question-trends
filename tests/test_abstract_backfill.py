from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "code" / "06_enrich"))

from abstract_backfill import reapply_scope_review_decisions_to_articles  # noqa: E402


class AbstractBackfillTests(unittest.TestCase):
    def test_reapply_scope_review_decisions_to_rebuilt_articles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            packet_path = Path(tmp) / "scope_review_packet.csv"
            articles = pd.DataFrame(
                [
                    {
                        "article_id": "a1",
                        "title": "Research Correction",
                        "article_scope": "review_erratum_paratext",
                        "article_scope_reason": "title_pattern=correction",
                    }
                ]
            )
            pd.DataFrame(
                [
                    {
                        "scope_review_id": "SR0001",
                        "article_id": "a1",
                        "human_scope_decision": "exclude_nonresearch",
                        "proposed_article_scope": "nonresearch",
                        "proposed_scope_reason": "manual_scope_review",
                        "scope_review_notes": "Not a research article.",
                        "reviewer_id": "codex",
                        "review_date": "2026-06-29",
                    }
                ]
            ).to_csv(packet_path, index=False)

            updated = reapply_scope_review_decisions_to_articles(articles, packet_path)

            row = updated.iloc[0]
            self.assertEqual(row["article_scope"], "nonresearch")
            self.assertEqual(row["article_scope_reason"], "scope_review_decision=exclude_nonresearch;manual_scope_review")
            self.assertEqual(row["scope_review_decision"], "exclude_nonresearch")
            self.assertEqual(row["scope_review_notes"], "Not a research article.")
            self.assertEqual(row["scope_reviewer_id"], "codex")
            self.assertEqual(row["scope_review_date"], "2026-06-29")


if __name__ == "__main__":
    unittest.main()
