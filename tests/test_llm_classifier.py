from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "code" / "04_classify"))

from llm_classifier import (  # noqa: E402
    build_openai_request,
    build_prompt_input,
    classify_row,
    parse_llm_response,
    stable_cache_key,
    validate_llm_json,
)


class LlmClassifierTests(unittest.TestCase):
    def test_valid_json_passes_validation(self) -> None:
        result = validate_llm_json(
            {
                "category": "causal",
                "confidence": "high",
                "reason": "The abstract says it estimates treatment effects.",
            }
        )
        self.assertEqual(result["category"], "causal")

    def test_invalid_category_fails_validation(self) -> None:
        with self.assertRaises(ValueError):
            validate_llm_json({"category": "descriptive", "confidence": "low", "reason": "x"})

    def test_missing_reason_fails_validation(self) -> None:
        with self.assertRaises(ValueError):
            validate_llm_json({"category": "other", "confidence": "low"})

    def test_prompt_input_excludes_metadata_fields(self) -> None:
        row = {
            "title": "A Causal Paper",
            "abstract": "This abstract estimates treatment effects.",
            "journal": "American Economic Review",
            "publication_year": "2025",
            "doi": "10.1257/example",
            "author_names": "A. Author",
        }
        prompt_input = build_prompt_input(row, ["title", "abstract"])
        self.assertIn("TITLE:", prompt_input)
        self.assertIn("ABSTRACT:", prompt_input)
        self.assertNotIn("American Economic Review", prompt_input)
        self.assertNotIn("10.1257/example", prompt_input)
        self.assertNotIn("A. Author", prompt_input)

    def test_prompt_input_strips_source_boilerplate(self) -> None:
        row = {
            "title": "A Causal Paper",
            "abstract": (
                "This abstract estimates treatment effects. This content downloaded from "
                "157.55.39.186 on Tue, 12 Apr 2016 08:53:49 UTC All use subject to "
                "http://about.jstor.org/terms"
            ),
        }
        prompt_input = build_prompt_input(row, ["title", "abstract"])
        self.assertIn("estimates treatment effects", prompt_input)
        self.assertNotIn("All use subject", prompt_input)

    def test_cache_key_changes_when_prompt_version_changes(self) -> None:
        key1 = stable_cache_key("a1", "v1", "model", "title", "abstract")
        key2 = stable_cache_key("a1", "v2", "model", "title", "abstract")
        self.assertNotEqual(key1, key2)

    def test_short_text_skips_without_api_call(self) -> None:
        config = {
            "prompt_version": "test_prompt",
            "input_fields": ["title", "abstract"],
            "minimum_usable_text_chars": 250,
            "cache_dir": "cache",
        }
        row = {
            "article_id": "a1",
            "title": "Short title",
            "abstract": "",
            "classification_method": "rule_based",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            result = classify_row(
                row,
                prompt="prompt",
                config=config,
                model="model",
                api_key=None,
                dry_run=False,
                resume=False,
                force=False,
                project_root=Path(temp_dir),
            )
        self.assertEqual(result["llm_status"], "skipped_insufficient_text")
        self.assertEqual(result["llm_category"], "insufficient_text")

    def test_boilerplate_only_text_skips_without_api_call(self) -> None:
        config = {
            "prompt_version": "test_prompt",
            "input_fields": ["title", "abstract"],
            "minimum_usable_text_chars": 250,
            "cache_dir": "cache",
        }
        row = {
            "article_id": "a1",
            "title": "Forecasting Inflation",
            "abstract": (
                "Your use of the JSTOR archive indicates your acceptance of JSTOR&apos;s "
                "Terms and Conditions of Use, available at"
            ),
            "classification_method": "rule_based",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            result = classify_row(
                row,
                prompt="prompt",
                config=config,
                model="model",
                api_key=None,
                dry_run=False,
                resume=False,
                force=False,
                project_root=Path(temp_dir),
            )
        self.assertEqual(result["llm_status"], "skipped_insufficient_text")
        self.assertEqual(result["llm_category"], "insufficient_text")

    def test_parse_response_from_output_text(self) -> None:
        payload = {
            "output_text": '{"category":"predictive","confidence":"medium","reason":"It evaluates forecast accuracy."}'
        }
        result = parse_llm_response(payload)
        self.assertEqual(result["category"], "predictive")

    def test_openai_request_uses_json_schema_format(self) -> None:
        request = build_openai_request("prompt", "input", "model", {"max_output_tokens": 100, "temperature": 0})
        text_format = request["text"]["format"]
        self.assertEqual(text_format["type"], "json_schema")
        self.assertTrue(text_format["strict"])
        self.assertEqual(text_format["schema"]["required"], ["category", "confidence", "reason"])


if __name__ == "__main__":
    unittest.main()
