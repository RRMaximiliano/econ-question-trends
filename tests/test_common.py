from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "code" / "lib"))

from econqt_common import (  # noqa: E402
    as_json_string,
    clean_text,
    normalize_doi,
    normalize_title,
    reconstruct_openalex_abstract,
    source_key,
)


class CommonHelperTests(unittest.TestCase):
    def test_clean_text_strips_markup_entities_and_whitespace(self) -> None:
        value = "<jats:p> A&nbsp;paper\n  about <i>effects</i>. </jats:p>"
        self.assertEqual(clean_text(value), "A paper about effects .")

    def test_normalize_doi_strips_common_prefixes(self) -> None:
        cases = {
            "https://doi.org/10.1257/AER.20200108": "10.1257/aer.20200108",
            "http://dx.doi.org/10.1093/qje/qjaf001": "10.1093/qje/qjaf001",
            "doi: 10.1086/739828": "10.1086/739828",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalize_doi(raw), expected)

    def test_normalize_title_lowercases_and_removes_punctuation(self) -> None:
        self.assertEqual(
            normalize_title("The Price of Housing in the United States, 1890-2006"),
            "the price of housing in the united states 1890 2006",
        )

    def test_source_key_prefers_doi_when_present(self) -> None:
        self.assertEqual(
            source_key("https://doi.org/10.1257/AER.20200108", "aer", 2025, "Title"),
            ("doi", "10.1257/aer.20200108"),
        )

    def test_source_key_uses_title_journal_year_without_doi(self) -> None:
        self.assertEqual(
            source_key("", "qje", 2025, "A Paper: With Punctuation!"),
            ("title_journal_year", "qje|2025|a paper with punctuation"),
        )

    def test_reconstruct_openalex_abstract_uses_position_order(self) -> None:
        inverted_index = {"causal": [1], "This": [0], "paper": [2]}
        self.assertEqual(reconstruct_openalex_abstract(inverted_index), "This causal paper")

    def test_as_json_string_treats_empty_containers_as_missing(self) -> None:
        self.assertEqual(as_json_string([]), "")
        self.assertEqual(as_json_string({}), "")
        self.assertEqual(json.loads(as_json_string({"a": 1})), {"a": 1})


if __name__ == "__main__":
    unittest.main()
