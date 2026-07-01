from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Mapping

import pandas as pd
import yaml

sys.path.append(str(Path(__file__).resolve().parents[1] / "lib"))

from econqt_common import source_text_quality_flags, strip_source_boilerplate  # noqa: E402


CATEGORY_VALUES = {"causal", "predictive", "other", "insufficient_text"}
CONFIDENCE_VALUES = {"high", "medium", "low"}


def load_rules(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def clean_for_matching(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).lower()
    text = text.replace("‐", "-").replace("‑", "-").replace("‒", "-").replace("–", "-").replace("—", "-")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def build_classification_text(row: Mapping[str, Any], fields: list[str] | None = None) -> str:
    selected_fields = fields or ["title", "abstract"]
    pieces = [clean_for_matching(strip_source_boilerplate(row.get(field, ""))) for field in selected_fields]
    return " ".join(piece for piece in pieces if piece).strip()


def classification_text_quality_flags(row: Mapping[str, Any], fields: list[str] | None = None) -> str:
    selected_fields = fields or ["title", "abstract"]
    flags: list[str] = []
    for field in selected_fields:
        for flag in source_text_quality_flags(row.get(field, "")):
            if flag not in flags:
                flags.append(flag)
    return "|".join(flags)


def phrase_pattern(phrase: str) -> re.Pattern[str]:
    normalized = clean_for_matching(phrase)
    escaped = re.escape(normalized)
    escaped = escaped.replace(r"\ ", r"\s+")
    escaped = escaped.replace(r"\-", r"[-\s]")
    return re.compile(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", re.IGNORECASE)


def matched_phrases(text: str, phrases: list[str]) -> list[str]:
    matches = []
    for phrase in phrases:
        if phrase_pattern(phrase).search(text):
            matches.append(phrase)
    return matches


def score_family(text: str, rules: dict[str, Any], family: str) -> dict[str, Any]:
    family_rules = rules.get(family, {})
    strong_terms = matched_phrases(text, family_rules.get("strong_phrases", []) or [])
    moderate_terms = matched_phrases(text, family_rules.get("moderate_phrases", []) or [])
    scoring = rules.get("scoring", {})
    strong_weight = int(scoring.get("strong_weight", 2))
    moderate_weight = int(scoring.get("moderate_weight", 1))
    score = strong_weight * len(strong_terms) + moderate_weight * len(moderate_terms)
    return {
        "score": score,
        "strong_terms": strong_terms,
        "moderate_terms": moderate_terms,
        "terms": strong_terms + moderate_terms,
    }


def score_text(text: str, rules: dict[str, Any]) -> dict[str, Any]:
    return {
        "causal": score_family(text, rules, "causal"),
        "predictive": score_family(text, rules, "predictive"),
    }


def confidence_from_score(score_data: dict[str, Any]) -> str:
    if score_data["strong_terms"]:
        return "high"
    if score_data["score"] > 0:
        return "medium"
    return "low"


def classify_rule_based(row: Mapping[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    fields = rules.get("text_fields", ["title", "abstract"])
    text = build_classification_text(row, fields)
    text_quality_flags = classification_text_quality_flags(row, fields)
    text_chars = len(text)
    minimum_chars = int(rules.get("minimum_usable_text_chars", 250))
    scores = score_text(text, rules)
    causal = scores["causal"]
    predictive = scores["predictive"]
    causal_score = int(causal["score"])
    predictive_score = int(predictive["score"])
    causal_terms = causal["terms"]
    predictive_terms = predictive["terms"]
    dominance_margin = int(rules.get("scoring", {}).get("dominance_margin", 2))

    if text_chars < minimum_chars:
        category = "insufficient_text"
        confidence = "low"
        if text_quality_flags:
            reason = "Title and abstract text are too short after removing source boilerplate."
        else:
            reason = "Title and abstract text are too short for reliable rule-based classification."
    elif causal_score > 0 and predictive_score == 0:
        category = "causal"
        confidence = confidence_from_score(causal)
        reason = "Matched causal language: " + ", ".join(causal_terms[:6])
    elif predictive_score > 0 and causal_score == 0:
        category = "predictive"
        confidence = confidence_from_score(predictive)
        reason = "Matched predictive language: " + ", ".join(predictive_terms[:6])
    elif causal_score > 0 and predictive_score > 0:
        if causal_score >= predictive_score + dominance_margin:
            category = "causal"
            confidence = "medium"
            reason = "Matched both causal and predictive language, with stronger causal score."
        elif predictive_score >= causal_score + dominance_margin:
            category = "predictive"
            confidence = "medium"
            reason = "Matched both causal and predictive language, with stronger predictive score."
        else:
            category = "other"
            confidence = "low"
            reason = "Matched both causal and predictive language without a clear dominant category."
    else:
        category = "other"
        confidence = "medium"
        reason = "No causal or predictive rule terms matched in usable title/abstract text."

    assert category in CATEGORY_VALUES
    assert confidence in CONFIDENCE_VALUES
    return {
        "causal_predictive_category": category,
        "classification_confidence": confidence,
        "classification_reason": reason,
        "causal_language_indicator": causal_score,
        "predictive_language_indicator": predictive_score,
        "causal_language_terms": "|".join(causal_terms),
        "predictive_language_terms": "|".join(predictive_terms),
        "classification_method": "rule_based",
        "classification_text_chars": text_chars,
        "has_usable_classification_text": text_chars >= minimum_chars,
        "classification_text_quality_flags": text_quality_flags,
    }


def classify_dataframe(df: pd.DataFrame, rules: dict[str, Any]) -> pd.DataFrame:
    classified_rows = [classify_rule_based(row, rules) for row in df.to_dict(orient="records")]
    classified = pd.DataFrame(classified_rows)
    return pd.concat([df.reset_index(drop=True), classified], axis=1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/final/articles_pilot.csv")
    parser.add_argument("--output", default="data/final/articles_classified_pilot.csv")
    parser.add_argument("--rules", default="config/classification_rules.yml")
    args = parser.parse_args()

    rules = load_rules(Path(args.rules))
    articles = pd.read_csv(args.input, dtype=str).fillna("")
    classified = classify_dataframe(articles, rules)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    classified.to_csv(output, index=False)
    print(f"rows={len(classified)}")
    print(classified["causal_predictive_category"].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
