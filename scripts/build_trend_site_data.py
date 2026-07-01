from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SITE_DIR = PROJECT_ROOT / "site"
OUT_PATH = SITE_DIR / "data.js"


def read_csv(rel_path: str) -> pd.DataFrame:
    path = PROJECT_ROOT / rel_path
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    return df.to_dict(orient="records")


def metric_lookup(df: pd.DataFrame) -> dict[str, str]:
    if df.empty or not {"metric", "value"}.issubset(df.columns):
        return {}
    return dict(zip(df["metric"].astype(str), df["value"].astype(str)))


def first_record(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {}
    return df.iloc[0].to_dict()


def build_payload() -> dict[str, Any]:
    category_sensitivity = read_csv("outputs/tables/enriched/category_sensitivity_by_year.csv")
    evidence_tier_sensitivity = read_csv("outputs/tables/enriched/evidence_tier_sensitivity_by_year.csv")
    recent_trends = read_csv("outputs/tables/enriched/recent_category_trends.csv")
    recent_changes = read_csv("outputs/tables/enriched/recent_category_trend_changes.csv")
    recent_journal_trends = read_csv("outputs/tables/enriched/recent_journal_category_trends.csv")
    recent_journal_changes = read_csv("outputs/tables/enriched/recent_journal_category_trend_changes.csv")
    validation_metrics = read_csv("outputs/tables/enriched/validation_metrics.csv")
    validation_category_metrics = read_csv("outputs/tables/enriched/validation_category_metrics.csv")
    validation_gate = read_csv("outputs/tables/enriched/manual_validation_gate.csv")
    insufficient_rates = read_csv("outputs/tables/enriched/insufficient_text_rates.csv")
    project_status = read_csv("outputs/tables/enriched/project_status_summary.csv")

    return {
        "generatedAt": pd.Timestamp.utcnow().isoformat(),
        "sourceFiles": [
            "outputs/tables/enriched/category_sensitivity_by_year.csv",
            "outputs/tables/enriched/evidence_tier_sensitivity_by_year.csv",
            "outputs/tables/enriched/recent_category_trends.csv",
            "outputs/tables/enriched/recent_category_trend_changes.csv",
            "outputs/tables/enriched/recent_journal_category_trends.csv",
            "outputs/tables/enriched/recent_journal_category_trend_changes.csv",
            "outputs/tables/enriched/validation_metrics.csv",
            "outputs/tables/enriched/validation_category_metrics.csv",
            "outputs/tables/enriched/manual_validation_gate.csv",
            "outputs/tables/enriched/insufficient_text_rates.csv",
        ],
        "categorySensitivityByYear": records(category_sensitivity),
        "evidenceTierSensitivityByYear": records(evidence_tier_sensitivity),
        "recentCategoryTrends": records(recent_trends),
        "recentCategoryTrendChanges": records(recent_changes),
        "recentJournalCategoryTrends": records(recent_journal_trends),
        "recentJournalCategoryTrendChanges": records(recent_journal_changes),
        "validationMetrics": first_record(validation_metrics),
        "validationCategoryMetrics": records(validation_category_metrics),
        "validationGate": metric_lookup(validation_gate),
        "insufficientTextRates": records(insufficient_rates),
        "projectStatus": records(project_status),
    }


def main() -> None:
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_payload()
    json_text = json.dumps(payload, ensure_ascii=False, indent=2)
    OUT_PATH.write_text(f"window.EQT_TREND_DATA = {json_text};\n", encoding="utf-8")
    print(f"wrote={OUT_PATH}")
    print(f"records_category_sensitivity={len(payload['categorySensitivityByYear'])}")
    print(f"records_recent_journal_changes={len(payload['recentJournalCategoryTrendChanges'])}")


if __name__ == "__main__":
    main()
