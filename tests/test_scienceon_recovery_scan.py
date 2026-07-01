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

from scienceon_recovery_scan import (  # noqa: E402
    SCIENCEON_DETAIL_URL,
    SCIENCEON_LIST_URL,
    nart_ids_from_html,
    parse_meta_tags,
    run_scienceon_recovery_scan,
    title_matches,
)


def scienceon_detail(*, title: str, doi: str, abstract: str = "") -> str:
    abstract_meta = f'<meta name="citation_abstract" content="{abstract}" />' if abstract else ""
    return f"""
    <html><head>
    <meta name="citation_title" content="[논문]{title}" />
    <meta name="citation_doi" content="{doi}" />
    {abstract_meta}
    </head><body></body></html>
    """


class ScienceOnRecoveryScanTests(unittest.TestCase):
    def test_parses_meta_and_nart_ids(self) -> None:
        html = '<meta name="citation_doi" content="10.2307/1912685"><a href="?cn=NART1">x</a><input value="NART2">'
        self.assertEqual(parse_meta_tags(html)["citation_doi"], "10.2307/1912685")
        self.assertEqual(nart_ids_from_html(html), ["NART1", "NART2"])

    def test_title_match_strips_scienceon_prefix(self) -> None:
        self.assertTrue(title_matches("A Paper: With Punctuation", "[논문]A Paper With Punctuation"))

    def test_run_scan_appends_only_threshold_passing_exact_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            action_packet = root / "action.csv"
            split_summary = root / "split_summary.csv"
            split_path = root / "ready_manual.csv"
            imported_history = root / "history.csv"
            confirmed_export = root / "confirmed.csv"
            output_candidates = root / "candidates.csv"
            output_skipped = root / "skipped.csv"
            report = root / "report.md"

            title = "Instrumental Variables Estimation of Differential Equations"
            pd.DataFrame(
                [
                    {"article_id": "a1", "title": title, "doi": "10.2307/1913442", "quick_win_tier": "tier_4_manual_metadata_has_context"},
                    {"article_id": "a2", "title": "Short Abstract Paper", "doi": "10.2307/short", "quick_win_tier": "tier_1_partial_near_threshold"},
                ]
            ).to_csv(action_packet, index=False)
            pd.DataFrame(
                [
                    {"article_id": "a1", "title": title, "doi": "10.2307/1913442", "quick_win_tier": "tier_4_manual_metadata_has_context"},
                    {"article_id": "a2", "title": "Short Abstract Paper", "doi": "10.2307/short", "quick_win_tier": "tier_1_partial_near_threshold"},
                ]
            ).to_csv(split_path, index=False)
            pd.DataFrame([{"split_group": "ready_manual_metadata", "output_csv": str(split_path)}]).to_csv(split_summary, index=False)
            pd.DataFrame(columns=["article_id"]).to_csv(imported_history, index=False)
            pd.DataFrame(columns=["article_id", "split_group", "quick_win_tier", "abstract", "source", "source_url", "source_record_id", "evidence_tier", "notes"]).to_csv(confirmed_export, index=False)

            long_abstract = " ".join(["This paper studies instrumental variables estimation in dynamic systems."] * 8)
            pages = {
                SCIENCEON_LIST_URL.format(query="10.2307/1913442"): "NART123",
                SCIENCEON_DETAIL_URL.format(nart_id="NART123"): scienceon_detail(title=title, doi="10.2307/1913442", abstract=long_abstract),
                SCIENCEON_LIST_URL.format(query="10.2307/short"): "NART999",
                SCIENCEON_DETAIL_URL.format(nart_id="NART999"): scienceon_detail(title="Short Abstract Paper", doi="10.2307/short", abstract="Too short."),
            }

            def fetch(url: str) -> str:
                return pages[url]

            with contextlib.redirect_stdout(io.StringIO()):
                candidates, skipped = run_scienceon_recovery_scan(
                    action_packet_path=action_packet,
                    split_summary_path=split_summary,
                    imported_history_path=imported_history,
                    confirmed_export_path=confirmed_export,
                    output_candidates=output_candidates,
                    output_skipped=output_skipped,
                    report_path=report,
                    doi_prefixes=["10.2307"],
                    minimum_chars=250,
                    max_detail_candidates=8,
                    append_export=True,
                    fetch_text=fetch,
                )

            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates.iloc[0]["article_id"], "a1")
            self.assertEqual(candidates.iloc[0]["split_group"], "ready_manual_metadata")
            self.assertIn("ScienceOn:NART123", candidates.iloc[0]["source_record_id"])
            self.assertEqual(set(skipped["status"]), {"accepted", "abstract_below_threshold"})
            exported = pd.read_csv(confirmed_export, dtype=str).fillna("")
            self.assertEqual(len(exported), 1)
            self.assertEqual(exported.iloc[0]["article_id"], "a1")
            self.assertTrue(report.exists())


if __name__ == "__main__":
    unittest.main()
