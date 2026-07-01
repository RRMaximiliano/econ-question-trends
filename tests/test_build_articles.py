from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "code" / "lib"))
sys.path.append(str(PROJECT_ROOT / "code" / "02_clean"))

from build_articles_pilot import build_articles  # noqa: E402


def make_project_root() -> tempfile.TemporaryDirectory[str]:
    temp_dir = tempfile.TemporaryDirectory()
    project_root = Path(temp_dir.name)
    (project_root / "config").mkdir(parents=True)
    (project_root / "config" / "journals.yml").write_text(
        "\n".join(
            [
                "journals:",
                "  - journal_short: aer",
                "    journal: American Economic Review",
                "  - journal_short: qje",
                "    journal: Quarterly Journal of Economics",
            ]
        ),
        encoding="utf-8",
    )
    return temp_dir


def base_record(source: str, doi: str, title: str, **overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "source": source,
        "source_record_id": f"{source}:{doi or title}",
        "source_file": "",
        "source_query_url": "",
        "journal_short": "aer",
        "journal": "American Economic Review",
        "title": title,
        "abstract": "",
        "publication_year": 2025,
        "publication_date": "2025-01-01",
        "doi": doi,
        "volume": "115",
        "issue": "1",
        "first_page": "1",
        "last_page": "20",
        "pages_raw": "1-20",
        "article_type": "journal-article" if source == "crossref" else "article",
        "article_url": "",
        "authors_raw": "",
        "author_names": "",
        "author_affiliations_raw": "",
        "num_authors": "",
        "jel_codes": "",
        "keywords": "",
        "field_jel_primary": "",
        "field_jel_broad": "",
        "openalex_id": "",
        "crossref_id": doi,
        "jstor_id": "",
        "repec_handle": "",
        "publisher_record_id": "",
    }
    record.update(overrides)
    return record


class BuildArticlesTests(unittest.TestCase):
    def test_build_articles_prefers_openalex_abstract_for_matched_doi(self) -> None:
        with make_project_root() as temp_path:
            project_root = Path(temp_path)
            rows = [
                base_record(
                    "crossref",
                    "10.1257/aer.20250001",
                    "A Matched Article",
                    abstract="Crossref abstract",
                ),
                base_record(
                    "openalex",
                    "10.1257/aer.20250001",
                    "A Matched Article",
                    abstract="OpenAlex abstract",
                    openalex_id="https://openalex.org/W1",
                ),
            ]
            articles = build_articles(rows, project_root)

        self.assertEqual(len(articles), 1)
        row = articles.iloc[0]
        self.assertEqual(row["abstract"], "OpenAlex abstract")
        self.assertEqual(row["abstract_source"], "openalex")
        self.assertEqual(row["source_record_count"], 2)
        self.assertEqual(row["duplicate_resolution_rule"], "doi")

    def test_build_articles_groups_missing_doi_by_title_journal_year(self) -> None:
        with make_project_root() as temp_path:
            project_root = Path(temp_path)
            rows = [
                base_record("crossref", "", "No DOI Paper"),
                base_record("openalex", "", "No DOI Paper", abstract="OpenAlex text"),
            ]
            articles = build_articles(rows, project_root)

        self.assertEqual(len(articles), 1)
        self.assertEqual(articles.iloc[0]["duplicate_resolution_rule"], "title_journal_year")
        self.assertIn("missing_doi", articles.iloc[0]["metadata_warning"])

    def test_build_articles_flags_nonstandard_article_type(self) -> None:
        with make_project_root() as temp_path:
            project_root = Path(temp_path)
            rows = [
                base_record(
                    "openalex",
                    "10.1257/aer.20250002",
                    "Report-Labeled Journal Record",
                    article_type="report",
                )
            ]
            articles = build_articles(rows, project_root)

        self.assertIn("nonstandard_article_type", articles.iloc[0]["metadata_warning"])

    def test_build_articles_flags_missing_jel_codes(self) -> None:
        with make_project_root() as temp_path:
            project_root = Path(temp_path)
            rows = [base_record("crossref", "10.1257/aer.20250003", "No JEL Paper")]
            articles = build_articles(rows, project_root)

        self.assertIn("missing_jel_codes", articles.iloc[0]["metadata_warning"])


if __name__ == "__main__":
    unittest.main()
