from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "code" / "06_enrich"))

from recovery_batch_autofill import autofill_recovery_batch  # noqa: E402


class RecoveryBatchAutofillTests(unittest.TestCase):
    def test_autofill_recovery_batch_copies_enriched_results_only_to_empty_rows(self) -> None:
        batch = pd.DataFrame(
            [
                {"article_id": "a1", "title": "A", "abstract": "", "source": "", "source_url": "", "source_record_id": "", "notes": "suggested_action=review"},
                {"article_id": "a2", "title": "B", "abstract": "Existing", "source": "manual", "source_url": "", "source_record_id": "", "notes": "checked"},
                {"article_id": "a3", "title": "C", "abstract": "", "source": "", "source_url": "", "source_record_id": "", "notes": ""},
            ]
        )
        enrichment = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "enrichment_status": "enriched",
                    "enrichment_source": "oa_pdf_first_pages",
                    "enriched_abstract": "Recovered first-page text " * 20,
                    "enrichment_url": "https://example.test/a1.pdf",
                    "source_record_id": "",
                    "enrichment_detail": "pdf_text_first_pages",
                },
                {
                    "article_id": "a2",
                    "enrichment_status": "enriched",
                    "enrichment_source": "crossref",
                    "enriched_abstract": "Should not overwrite",
                    "enrichment_url": "https://example.test/a2",
                    "source_record_id": "10.1/a2",
                    "enrichment_detail": "",
                },
                {
                    "article_id": "a3",
                    "enrichment_status": "partial_short_text",
                    "enrichment_source": "openalex",
                    "enriched_abstract": "Too short",
                    "enrichment_url": "",
                    "source_record_id": "",
                    "enrichment_detail": "",
                },
            ]
        )

        out, summary = autofill_recovery_batch(batch, enrichment)

        self.assertEqual(len(summary), 1)
        self.assertIn("Recovered first-page text", out.loc[out["article_id"].eq("a1"), "abstract"].iloc[0])
        self.assertEqual(out.loc[out["article_id"].eq("a1"), "source"].iloc[0], "oa_pdf_first_pages")
        self.assertEqual(out.loc[out["article_id"].eq("a1"), "evidence_tier"].iloc[0], "tier_c_first_page_abstract_or_intro")
        self.assertIn("source_text_type=first_pages", out.loc[out["article_id"].eq("a1"), "notes"].iloc[0])
        self.assertEqual(out.loc[out["article_id"].eq("a2"), "abstract"].iloc[0], "Existing")
        self.assertEqual(out.loc[out["article_id"].eq("a3"), "abstract"].iloc[0], "")


if __name__ == "__main__":
    unittest.main()
