from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "code" / "05_analysis"))

from trend_summary import filter_year_window, trend_changes  # noqa: E402


class TrendSummaryTests(unittest.TestCase):
    def test_filter_year_window_keeps_inclusive_bounds(self) -> None:
        data = pd.DataFrame(
            [
                {"article_id": "a1", "publication_year": "2022"},
                {"article_id": "a2", "publication_year": "2023"},
                {"article_id": "a3", "publication_year": "2025"},
                {"article_id": "a4", "publication_year": "2026"},
            ]
        )

        window = filter_year_window(data, 2023, 2025)

        self.assertEqual(window["article_id"].tolist(), ["a2", "a3"])

    def test_trend_changes_compute_start_end_share_change(self) -> None:
        trends = pd.DataFrame(
            [
                {"scenario": "baseline", "publication_year": "2023", "category": "causal", "article_count": 2, "group_total": 10, "category_share": 0.2},
                {"scenario": "baseline", "publication_year": "2025", "category": "causal", "article_count": 4, "group_total": 10, "category_share": 0.4},
                {"scenario": "baseline", "publication_year": "2025", "category": "other", "article_count": 6, "group_total": 10, "category_share": 0.6},
            ]
        )

        changes = trend_changes(trends, start_year=2023, end_year=2025).set_index(["scenario", "category"])

        self.assertEqual(float(changes.loc[("baseline", "causal"), "share_change"]), 0.2)
        self.assertEqual(float(changes.loc[("baseline", "other"), "start_share"]), 0.0)
        self.assertEqual(int(changes.loc[("baseline", "other"), "start_group_total"]), 10)
        self.assertEqual(int(changes.loc[("baseline", "causal"), "start_article_count"]), 2)

    def test_trend_changes_support_group_columns(self) -> None:
        trends = pd.DataFrame(
            [
                {
                    "scenario": "baseline",
                    "journal_short": "aer",
                    "publication_year": "2023",
                    "category": "predictive",
                    "article_count": 1,
                    "group_total": 5,
                    "category_share": 0.2,
                },
                {
                    "scenario": "baseline",
                    "journal_short": "aer",
                    "publication_year": "2025",
                    "category": "predictive",
                    "article_count": 2,
                    "group_total": 5,
                    "category_share": 0.4,
                },
            ]
        )

        changes = trend_changes(trends, start_year=2023, end_year=2025, group_cols=["journal_short"])

        self.assertEqual(changes.iloc[0]["journal_short"], "aer")
        self.assertEqual(float(changes.iloc[0]["share_change"]), 0.2)


if __name__ == "__main__":
    unittest.main()
