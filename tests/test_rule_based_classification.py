from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "code" / "04_classify"))

from rule_based import build_classification_text, classify_rule_based, load_rules, score_text  # noqa: E402


RULES = load_rules(PROJECT_ROOT / "config" / "classification_rules.yml")


class RuleBasedClassificationTests(unittest.TestCase):
    def test_causal_terms_score_causal(self) -> None:
        text = "This paper estimates treatment effects using a difference-in-differences design."
        scores = score_text(text, RULES)
        self.assertGreater(scores["causal"]["score"], 0)
        self.assertEqual(scores["predictive"]["score"], 0)

    def test_predictive_terms_score_predictive(self) -> None:
        text = "We evaluate out-of-sample forecast accuracy using cross-validation."
        scores = score_text(text, RULES)
        self.assertGreater(scores["predictive"]["score"], 0)
        self.assertEqual(scores["causal"]["score"], 0)

    def test_neutral_text_classifies_as_other(self) -> None:
        row = {
            "title": "A Theory of Exchange",
            "abstract": (
                "This paper studies a theoretical model of exchange with complete information "
                "and characterizes equilibrium allocations in a static environment. The analysis "
                "derives comparative statics and existence results for a broad class of economies, "
                "with emphasis on assumptions, proofs, and equilibrium structure rather than an "
                "empirical research design."
            ),
        }
        result = classify_rule_based(row, RULES)
        self.assertEqual(result["causal_predictive_category"], "other")

    def test_short_text_classifies_as_insufficient(self) -> None:
        row = {"title": "Forecasting Inflation", "abstract": ""}
        result = classify_rule_based(row, RULES)
        self.assertEqual(result["causal_predictive_category"], "insufficient_text")
        self.assertEqual(result["classification_confidence"], "low")

    def test_source_boilerplate_does_not_count_as_usable_text(self) -> None:
        row = {
            "title": "Forecasting Inflation",
            "abstract": (
                "Your use of the JSTOR archive indicates your acceptance of JSTOR&apos;s "
                "Terms and Conditions of Use, available at"
            ),
        }
        result = classify_rule_based(row, RULES)
        self.assertEqual(result["causal_predictive_category"], "insufficient_text")
        self.assertFalse(result["has_usable_classification_text"])
        self.assertIn("jstor_terms_boilerplate", result["classification_text_quality_flags"])
        self.assertLess(result["classification_text_chars"], 250)

    def test_mixed_first_page_text_is_stripped_but_retained(self) -> None:
        row = {
            "title": "Measuring Treatment Effects",
            "abstract": (
                "This paper estimates treatment effects in a randomized field experiment with "
                "administrative data and a pre-specified empirical design. This content downloaded "
                "from 157.55.39.186 on Tue, 12 Apr 2016 08:53:49 UTC All use subject to "
                "http://about.jstor.org/terms The analysis compares treated and control groups "
                "and interprets heterogeneous intervention effects across cohorts."
            ),
        }
        result = classify_rule_based(row, RULES)
        text = build_classification_text(row, RULES.get("text_fields", ["title", "abstract"]))
        self.assertEqual(result["causal_predictive_category"], "causal")
        self.assertIn("jstor_terms_boilerplate", result["classification_text_quality_flags"])
        self.assertNotIn("all use subject", text)

    def test_mixed_terms_are_not_high_confidence(self) -> None:
        row = {
            "title": "Prediction and Treatment Effects",
            "abstract": "This paper estimates treatment effects and also evaluates out-of-sample predictive accuracy across models in a long abstract with enough text for classification.",
        }
        result = classify_rule_based(row, RULES)
        self.assertIn(result["classification_confidence"], {"low", "medium"})
        self.assertNotEqual(result["classification_confidence"], "high")

    def test_matching_is_case_insensitive(self) -> None:
        row = {
            "title": "RANDOMIZED Evidence",
            "abstract": (
                "This paper reports a randomized controlled trial with enough additional title "
                "and abstract text to exceed the minimum threshold for usable text classification. "
                "The study compares treated and control groups, discusses implementation, and "
                "interprets the estimated intervention effects in an empirical setting."
            ),
        }
        result = classify_rule_based(row, RULES)
        self.assertEqual(result["causal_predictive_category"], "causal")


if __name__ == "__main__":
    unittest.main()
