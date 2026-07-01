from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "code" / "06_enrich"))

from pdf_text_extraction import (  # noqa: E402
    abstract_or_first_pages,
    extract_pdf_candidates,
    merge_pdf_text_into_enrichment,
    pdf_result_key,
    safe_pdf_filename,
)
import pdf_text_extraction  # noqa: E402


class PdfTextExtractionTests(unittest.TestCase):
    def test_safe_pdf_filename_is_stable_pdf_name(self) -> None:
        name = safe_pdf_filename("eqt_abc", "https://example.test/paper.pdf")
        self.assertTrue(name.startswith("eqt_abc_"))
        self.assertTrue(name.endswith(".pdf"))

    def test_pdf_result_key_is_stable(self) -> None:
        self.assertEqual(pdf_result_key("a1", "https://x.test/a.pdf"), pdf_result_key("a1", "https://x.test/a.pdf"))

    def test_abstract_or_first_pages_prefers_abstract_section(self) -> None:
        text = "Title\nAbstract\nThis is an abstract. " * 20 + "\n1 Introduction\nBody"
        selected = abstract_or_first_pages(text)
        self.assertIn("This is an abstract", selected)
        self.assertNotIn("Body", selected)

    def test_merge_pdf_text_into_enrichment_updates_non_enriched_rows(self) -> None:
        enrichment = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "title": "Title",
                    "enrichment_status": "pdf_candidate",
                    "enrichment_source": "openalex",
                    "enriched_abstract": "",
                    "enriched_text_chars": "0",
                    "enrichment_url": "",
                    "oa_pdf_url": "https://example.test/paper.pdf",
                    "attempted_sources": "openalex",
                    "enrichment_detail": "",
                }
            ]
        )
        pdf_text = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "pdf_text_status": "extracted",
                    "pdf_text": "This is extracted text. " * 20,
                    "pdf_text_chars": "480",
                    "oa_pdf_url": "https://example.test/paper.pdf",
                }
            ]
        )
        merged = merge_pdf_text_into_enrichment(enrichment, pdf_text)
        self.assertEqual(merged.iloc[0]["enrichment_status"], "enriched")
        self.assertEqual(merged.iloc[0]["enrichment_source"], "oa_pdf_first_pages")
        self.assertIn("oa_pdf_first_pages", merged.iloc[0]["attempted_sources"])

    def test_extract_pdf_candidates_reuses_existing_result(self) -> None:
        candidates = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "journal_short": "jpe",
                    "publication_year": "2020",
                    "title": "Title",
                    "oa_pdf_url": "https://example.invalid/paper.pdf",
                }
            ]
        )
        existing = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "oa_pdf_url": "https://example.invalid/paper.pdf",
                    "pdf_text_status": "download_error",
                    "pdf_text": "",
                    "pdf_text_chars": "0",
                    "pdf_detail": "http_status=403",
                }
            ]
        )
        out = extract_pdf_candidates(candidates, pdf_dir=Path("/tmp/unused"), pages=1, timeout=1, limit=None, existing_results=existing)
        self.assertEqual(out.iloc[0]["pdf_text_status"], "download_error")
        self.assertEqual(out.iloc[0]["pdf_detail"], "http_status=403")

    def test_extract_pdf_candidates_uses_ocr_fallback_when_text_layer_is_short(self) -> None:
        candidates = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "journal_short": "jpe",
                    "publication_year": "1980",
                    "title": "Title",
                    "oa_pdf_url": "https://example.test/paper.pdf",
                }
            ]
        )
        original_download_pdf = pdf_text_extraction.download_pdf
        original_extract_pdf_text = pdf_text_extraction.extract_pdf_text
        original_ocr_pdf_text = pdf_text_extraction.ocr_pdf_text

        def fake_download_pdf(url, path, timeout):  # type: ignore[no-untyped-def]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"%PDF fake")
            return True, url

        def fake_extract_pdf_text(pdf_path, pages, pdftotext_path="pdftotext"):  # type: ignore[no-untyped-def]
            return True, ""

        def fake_ocr_pdf_text(pdf_path, pages, *, dpi=200, pdftoppm_path="pdftoppm", tesseract_path="tesseract"):  # type: ignore[no-untyped-def]
            return True, "Recovered OCR abstract text. " * 20

        pdf_text_extraction.download_pdf = fake_download_pdf
        pdf_text_extraction.extract_pdf_text = fake_extract_pdf_text
        pdf_text_extraction.ocr_pdf_text = fake_ocr_pdf_text
        try:
            out = extract_pdf_candidates(
                candidates,
                pdf_dir=Path("/tmp/unused_pdf_ocr_test"),
                pages=1,
                timeout=1,
                limit=None,
                ocr_fallback=True,
            )
        finally:
            pdf_text_extraction.download_pdf = original_download_pdf
            pdf_text_extraction.extract_pdf_text = original_extract_pdf_text
            pdf_text_extraction.ocr_pdf_text = original_ocr_pdf_text

        self.assertEqual(out.iloc[0]["pdf_text_status"], "extracted")
        self.assertIn("Recovered OCR abstract", out.iloc[0]["pdf_text"])
        self.assertIn("ocr_fallback", out.iloc[0]["pdf_detail"])


if __name__ == "__main__":
    unittest.main()
