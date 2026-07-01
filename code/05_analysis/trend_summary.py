from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ANALYSIS_DIR = Path(__file__).resolve().parent
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.append(str(ANALYSIS_DIR))

from classification_diagnostics import (  # noqa: E402
    analysis_scope_filter,
    category_sensitivity_shares,
    df_to_markdown,
    load_config,
    title_only_triage_candidates,
)

CLASSIFY_DIR = Path(__file__).resolve().parents[1] / "04_classify"
if str(CLASSIFY_DIR) not in sys.path:
    sys.path.append(str(CLASSIFY_DIR))

from rule_based import load_rules as load_classification_rules  # noqa: E402


def filter_year_window(df: pd.DataFrame, start_year: int, end_year: int) -> pd.DataFrame:
    work = df.copy().fillna("")
    if "publication_year" not in work:
        raise ValueError("Missing publication_year column.")
    year = pd.to_numeric(work["publication_year"], errors="coerce")
    return work[year.between(start_year, end_year, inclusive="both")].copy().reset_index(drop=True)


def trend_changes(
    trend_df: pd.DataFrame,
    *,
    start_year: int,
    end_year: int,
    group_cols: list[str] | None = None,
) -> pd.DataFrame:
    group_cols = group_cols or []
    required = {"scenario", "publication_year", "category", "article_count", "group_total", "category_share"}
    missing = required - set(trend_df.columns)
    if missing:
        raise ValueError(f"Missing required trend columns: {', '.join(sorted(missing))}")
    work = trend_df.copy().fillna("")
    key_cols = ["scenario"] + group_cols + ["category"]
    total_key_cols = ["scenario"] + group_cols
    start_totals = (
        work[work["publication_year"].astype(str).eq(str(start_year))]
        .groupby(total_key_cols, dropna=False)["group_total"]
        .max()
        .reset_index()
        .rename(columns={"group_total": "_start_group_total"})
    )
    end_totals = (
        work[work["publication_year"].astype(str).eq(str(end_year))]
        .groupby(total_key_cols, dropna=False)["group_total"]
        .max()
        .reset_index()
        .rename(columns={"group_total": "_end_group_total"})
    )
    start = work[work["publication_year"].astype(str).eq(str(start_year))].copy()
    end = work[work["publication_year"].astype(str).eq(str(end_year))].copy()
    start = start[key_cols + ["category_share", "article_count", "group_total"]].rename(
        columns={
            "category_share": "start_share",
            "article_count": "start_article_count",
            "group_total": "start_group_total",
        }
    )
    end = end[key_cols + ["category_share", "article_count", "group_total"]].rename(
        columns={
            "category_share": "end_share",
            "article_count": "end_article_count",
            "group_total": "end_group_total",
        }
    )
    merged = start.merge(end, on=key_cols, how="outer").fillna(0)
    if not start_totals.empty:
        merged = merged.merge(start_totals, on=total_key_cols, how="left")
    else:
        merged["_start_group_total"] = 0
    if not end_totals.empty:
        merged = merged.merge(end_totals, on=total_key_cols, how="left")
    else:
        merged["_end_group_total"] = 0
    for column in ["start_share", "end_share"]:
        merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(0.0)
    for column in ["start_article_count", "start_group_total", "end_article_count", "end_group_total"]:
        merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(0).astype(int)
    merged["_start_group_total"] = pd.to_numeric(merged["_start_group_total"], errors="coerce").fillna(0).astype(int)
    merged["_end_group_total"] = pd.to_numeric(merged["_end_group_total"], errors="coerce").fillna(0).astype(int)
    merged.loc[merged["start_group_total"].eq(0), "start_group_total"] = merged.loc[
        merged["start_group_total"].eq(0), "_start_group_total"
    ]
    merged.loc[merged["end_group_total"].eq(0), "end_group_total"] = merged.loc[
        merged["end_group_total"].eq(0), "_end_group_total"
    ]
    merged["start_year"] = start_year
    merged["end_year"] = end_year
    merged["share_change"] = (merged["end_share"] - merged["start_share"]).round(6)
    ordered_cols = key_cols + [
        "start_year",
        "end_year",
        "start_share",
        "end_share",
        "share_change",
        "start_article_count",
        "end_article_count",
        "start_group_total",
        "end_group_total",
    ]
    return merged[ordered_cols].sort_values(key_cols).reset_index(drop=True)


def load_recommendation(path: Path) -> dict[str, str]:
    if not path.exists():
        return {"recommendation": "missing", "reasons": "Recommendation file was not found."}
    frame = pd.read_csv(path, dtype=str).fillna("")
    if frame.empty:
        return {"recommendation": "missing", "reasons": "Recommendation file was empty."}
    return frame.iloc[0].to_dict()


def write_trend_report(
    path: Path,
    *,
    classified_path: Path,
    start_year: int,
    end_year: int,
    recommendation: dict[str, str],
    recent_trends: pd.DataFrame,
    recent_changes: pd.DataFrame,
    journal_trends: pd.DataFrame,
    journal_changes: pd.DataFrame,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Recent Trend Summary",
        "",
        f"- Classified input: `{classified_path}`",
        f"- Window: {start_year}-{end_year}",
        f"- Expansion recommendation: `{recommendation.get('recommendation', 'missing')}`",
        f"- Recommendation reasons: {recommendation.get('reasons', '') or 'None recorded.'}",
        "",
        "This report is descriptive and validation-gated. Do not treat these trends as final evidence until manual validation passes the project gate.",
        "",
        "## Recent Category Shares",
        "",
        df_to_markdown(recent_trends, max_rows=40),
        "",
        "## Recent Category Share Changes",
        "",
        df_to_markdown(recent_changes, max_rows=40),
        "",
        "## Recent Journal Category Shares",
        "",
        df_to_markdown(journal_trends, max_rows=60),
        "",
        "## Recent Journal Category Share Changes",
        "",
        df_to_markdown(journal_changes, max_rows=60),
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def run_trend_summary(
    *,
    classified_path: Path,
    config_path: Path,
    rules_path: Path,
    recommendation_path: Path,
    output_dir: Path,
    report_path: Path,
    start_year: int,
    end_year: int,
) -> None:
    config = load_config(config_path)
    rules = load_classification_rules(rules_path)
    original = pd.read_csv(classified_path, dtype=str).fillna("")
    classified, _ = analysis_scope_filter(original, config)
    title_triage = title_only_triage_candidates(classified, rules)
    window = filter_year_window(classified, start_year, end_year)

    recent_trends = category_sensitivity_shares(window, ["publication_year"], title_triage)
    recent_changes = trend_changes(recent_trends, start_year=start_year, end_year=end_year)
    journal_trends = category_sensitivity_shares(window, ["journal_short", "publication_year"], title_triage)
    journal_changes = trend_changes(journal_trends, start_year=start_year, end_year=end_year, group_cols=["journal_short"])
    recommendation = load_recommendation(recommendation_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    recent_trends.to_csv(output_dir / "recent_category_trends.csv", index=False)
    recent_changes.to_csv(output_dir / "recent_category_trend_changes.csv", index=False)
    journal_trends.to_csv(output_dir / "recent_journal_category_trends.csv", index=False)
    journal_changes.to_csv(output_dir / "recent_journal_category_trend_changes.csv", index=False)
    write_trend_report(
        report_path,
        classified_path=classified_path,
        start_year=start_year,
        end_year=end_year,
        recommendation=recommendation,
        recent_trends=recent_trends,
        recent_changes=recent_changes,
        journal_trends=journal_trends,
        journal_changes=journal_changes,
    )
    print(f"window_rows={len(window)}")
    print(f"report={report_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--classified", default="data/final/articles_classified_enriched_pilot.csv")
    parser.add_argument("--config", default="config/classification_diagnostics.yml")
    parser.add_argument("--rules", default="config/classification_rules.yml")
    parser.add_argument("--recommendation", default="outputs/tables/enriched/classification_recommendation.csv")
    parser.add_argument("--output-dir", default="outputs/tables/enriched")
    parser.add_argument("--report", default="docs/recent_trend_summary_enriched.md")
    parser.add_argument("--start-year", type=int, default=2023)
    parser.add_argument("--end-year", type=int, default=2025)
    args = parser.parse_args()
    run_trend_summary(
        classified_path=Path(args.classified),
        config_path=Path(args.config),
        rules_path=Path(args.rules),
        recommendation_path=Path(args.recommendation),
        output_dir=Path(args.output_dir),
        report_path=Path(args.report),
        start_year=args.start_year,
        end_year=args.end_year,
    )


if __name__ == "__main__":
    main()
