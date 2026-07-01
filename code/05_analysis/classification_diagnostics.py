from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

import pandas as pd
import yaml

CLASSIFY_DIR = Path(__file__).resolve().parents[1] / "04_classify"
if str(CLASSIFY_DIR) not in sys.path:
    sys.path.append(str(CLASSIFY_DIR))

from rule_based import build_classification_text, confidence_from_score, load_rules as load_classification_rules, score_text  # noqa: E402


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def is_nonmissing(series: pd.Series) -> pd.Series:
    return series.notna() & (series.astype(str).str.strip() != "")


def resolved_category(df: pd.DataFrame) -> pd.Series:
    if {"llm_category", "llm_status"}.issubset(df.columns):
        llm_ok = (df["llm_status"].astype(str) == "ok") & is_nonmissing(df["llm_category"])
    else:
        llm_ok = pd.Series(False, index=df.index)

    if "causal_predictive_category" not in df.columns:
        raise ValueError("Missing category column: causal_predictive_category")
    category = df["causal_predictive_category"].astype(str).copy()
    if llm_ok.any():
        category.loc[llm_ok] = df.loc[llm_ok, "llm_category"].astype(str)
    return category.replace("", "missing")


def resolved_confidence(df: pd.DataFrame) -> pd.Series:
    if {"llm_confidence", "llm_status"}.issubset(df.columns):
        llm_ok = (df["llm_status"].astype(str) == "ok") & is_nonmissing(df["llm_confidence"])
    else:
        llm_ok = pd.Series(False, index=df.index)

    if "classification_confidence" not in df.columns:
        raise ValueError("Missing confidence column: classification_confidence")
    confidence = df["classification_confidence"].astype(str).copy()
    if llm_ok.any():
        confidence.loc[llm_ok] = df.loc[llm_ok, "llm_confidence"].astype(str)
    return confidence.replace("", "missing")


def category_column(df: pd.DataFrame) -> pd.Series:
    return resolved_category(df)


def confidence_column(df: pd.DataFrame) -> pd.Series:
    return resolved_confidence(df)


def category_shares(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    work = df.copy()
    work["category"] = resolved_category(work)
    return category_shares_from_column(work, group_cols, "category")


def category_shares_from_column(df: pd.DataFrame, group_cols: list[str], category_col: str) -> pd.DataFrame:
    work = df.copy()
    count_cols = group_cols + ["category"]
    work["category"] = work[category_col].astype(str).replace("", "missing")
    counts = work.groupby(count_cols, dropna=False).size().reset_index(name="article_count")
    totals = work.groupby(group_cols, dropna=False).size().reset_index(name="group_total") if group_cols else pd.DataFrame({"group_total": [len(work)]})
    if group_cols:
        out = counts.merge(totals, on=group_cols, how="left")
    else:
        out = counts.assign(group_total=len(work))
    out["category_share"] = (out["article_count"] / out["group_total"]).round(6)
    return out.sort_values(group_cols + ["category"] if group_cols else ["category"]).reset_index(drop=True)


def confidence_distribution(df: pd.DataFrame, group_cols: list[str] | None = None) -> pd.DataFrame:
    group_cols = group_cols or []
    work = df.copy()
    work["confidence"] = resolved_confidence(work)
    count_cols = group_cols + ["confidence"]
    counts = work.groupby(count_cols, dropna=False).size().reset_index(name="article_count")
    totals = work.groupby(group_cols, dropna=False).size().reset_index(name="group_total") if group_cols else pd.DataFrame({"group_total": [len(work)]})
    if group_cols:
        out = counts.merge(totals, on=group_cols, how="left")
    else:
        out = counts.assign(group_total=len(work))
    out["confidence_share"] = (out["article_count"] / out["group_total"]).round(6)
    return out.sort_values(group_cols + ["confidence"] if group_cols else ["confidence"]).reset_index(drop=True)


def insufficient_text_rates(df: pd.DataFrame, group_cols: list[str] | None = None) -> pd.DataFrame:
    group_cols = group_cols or []
    work = df.copy()
    work["category"] = resolved_category(work)
    work["is_insufficient_text"] = work["category"] == "insufficient_text"
    if group_cols:
        out = (
            work.groupby(group_cols, dropna=False)["is_insufficient_text"]
            .agg(insufficient_text_count="sum", group_total="count")
            .reset_index()
        )
    else:
        out = pd.DataFrame(
            {
                "insufficient_text_count": [int(work["is_insufficient_text"].sum())],
                "group_total": [len(work)],
            }
        )
    out["insufficient_text_share"] = (out["insufficient_text_count"] / out["group_total"]).round(6)
    return out


EVIDENCE_TIER_COLUMN = "text_enrichment_evidence_tier"
FORMAL_ABSTRACT_TIER = "tier_a_formal_abstract"
NO_RECOVERED_TEXT_TIER = "no_recovered_text_tier"
MISSING_RECOVERED_TEXT_TIER = "missing_recovered_text_tier"


def evidence_tier_values(df: pd.DataFrame) -> pd.Series:
    if EVIDENCE_TIER_COLUMN in df.columns:
        return df[EVIDENCE_TIER_COLUMN].fillna("").astype(str).str.strip()
    return pd.Series("", index=df.index, dtype="object")


def evidence_tier_bucket(df: pd.DataFrame) -> pd.Series:
    tier = evidence_tier_values(df)
    bucket = tier.mask(tier.eq(""), NO_RECOVERED_TEXT_TIER)
    if "text_enrichment_status" in df.columns:
        enriched_without_tier = df["text_enrichment_status"].fillna("").astype(str).str.strip().eq("enriched") & tier.eq("")
        bucket.loc[enriched_without_tier] = MISSING_RECOVERED_TEXT_TIER
    return bucket


def evidence_tier_category_shares(df: pd.DataFrame) -> pd.DataFrame:
    columns = ["evidence_tier", "category", "article_count", "group_total", "category_share"]
    if df.empty:
        return pd.DataFrame(columns=columns)
    work = df.copy()
    work["evidence_tier"] = evidence_tier_bucket(work)
    work["_resolved_category"] = resolved_category(work)
    shares = category_shares_from_column(work, ["evidence_tier"], "_resolved_category")
    return shares[columns]


EVIDENCE_TIER_SENSITIVITY_SCENARIOS = [
    "baseline_current_labels",
    "formal_abstract_only",
    "no_recovered_text",
]


def evidence_tier_sensitivity_categories(df: pd.DataFrame, scenario: str) -> tuple[pd.Series, pd.Series]:
    category = resolved_category(df).copy()
    tier = evidence_tier_values(df)
    has_recovered_tier = tier.ne("")
    if scenario == "baseline_current_labels":
        demoted = pd.Series(False, index=df.index)
    elif scenario == "formal_abstract_only":
        demoted = has_recovered_tier & tier.ne(FORMAL_ABSTRACT_TIER)
    elif scenario == "no_recovered_text":
        demoted = has_recovered_tier
    else:
        raise ValueError(f"Unknown evidence-tier sensitivity scenario: {scenario}")
    category.loc[demoted] = "insufficient_text"
    return category, demoted


def evidence_tier_sensitivity_shares(df: pd.DataFrame, group_cols: list[str] | None = None) -> pd.DataFrame:
    group_cols = group_cols or []
    columns = ["scenario"] + group_cols + ["category", "article_count", "group_total", "category_share"]
    if df.empty:
        return pd.DataFrame(columns=columns)
    frames: list[pd.DataFrame] = []
    for scenario in EVIDENCE_TIER_SENSITIVITY_SCENARIOS:
        work = df.copy()
        work["_sensitivity_category"], _ = evidence_tier_sensitivity_categories(work, scenario)
        shares = category_shares_from_column(work, group_cols, "_sensitivity_category")
        shares.insert(0, "scenario", scenario)
        frames.append(shares)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=columns)


def evidence_tier_sensitivity_summary(df: pd.DataFrame) -> pd.DataFrame:
    categories = ["causal", "predictive", "other", "insufficient_text"]
    columns = [
        "scenario",
        "rows",
        "rows_with_recovered_text_tier",
        "rows_demoted_to_insufficient_text",
        *[f"{category}_count" for category in categories],
        *[f"{category}_share" for category in categories],
    ]
    if df.empty:
        return pd.DataFrame(columns=columns)
    tier = evidence_tier_values(df)
    rows: list[dict[str, Any]] = []
    for scenario in EVIDENCE_TIER_SENSITIVITY_SCENARIOS:
        scenario_categories, demoted = evidence_tier_sensitivity_categories(df, scenario)
        counts = scenario_categories.value_counts().to_dict()
        row: dict[str, Any] = {
            "scenario": scenario,
            "rows": len(df),
            "rows_with_recovered_text_tier": int(tier.ne("").sum()),
            "rows_demoted_to_insufficient_text": int(demoted.sum()),
        }
        for category in categories:
            count = int(counts.get(category, 0))
            row[f"{category}_count"] = count
            row[f"{category}_share"] = round(count / len(df), 6) if len(df) else 0.0
        rows.append(row)
    return pd.DataFrame(rows, columns=columns)


def abstract_coverage(df: pd.DataFrame, group_cols: list[str] | None = None) -> pd.DataFrame:
    group_cols = group_cols or []
    work = df.copy()
    work["has_abstract"] = is_nonmissing(work["abstract"]) if "abstract" in work else False
    if group_cols:
        out = work.groupby(group_cols, dropna=False)["has_abstract"].agg(abstract_count="sum", group_total="count").reset_index()
    else:
        out = pd.DataFrame({"abstract_count": [int(work["has_abstract"].sum())], "group_total": [len(work)]})
    out["abstract_share"] = (out["abstract_count"] / out["group_total"]).round(6)
    return out


def remaining_insufficient_text_profile(df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "journal_short",
        "decade",
        "rows",
        "insufficient_rows",
        "insufficient_share",
        "has_doi_rows",
        "has_openalex_rows",
        "has_oa_pdf_rows",
        "missing_abstract_rows",
        "partial_short_text_rows",
    ]
    if df.empty:
        return pd.DataFrame(columns=columns)

    work = df.copy()
    work["category"] = resolved_category(work)
    year = pd.to_numeric(work["publication_year"], errors="coerce") if "publication_year" in work else pd.Series(pd.NA, index=work.index)
    decade = (year // 10 * 10).astype("Int64").astype(str).replace("<NA>", "missing")
    work["decade"] = decade
    work["is_insufficient_text"] = work["category"].eq("insufficient_text")
    work["has_doi"] = is_nonmissing(work["doi"]) if "doi" in work else False
    work["has_openalex_id"] = is_nonmissing(work["openalex_id"]) if "openalex_id" in work else False
    work["has_oa_pdf"] = is_nonmissing(work["oa_pdf_url"]) if "oa_pdf_url" in work else False
    work["has_abstract"] = is_nonmissing(work["abstract"]) if "abstract" in work else False
    work["is_partial_short_text"] = (
        work["text_enrichment_status"].astype(str).eq("partial_short_text") if "text_enrichment_status" in work else False
    )
    if "journal_short" not in work:
        work["journal_short"] = "missing"

    rows: list[dict[str, Any]] = []
    for (journal, group_decade), group in work.groupby(["journal_short", "decade"], dropna=False):
        insufficient = group[group["is_insufficient_text"]].copy()
        group_total = len(group)
        insufficient_rows = len(insufficient)
        rows.append(
            {
                "journal_short": str(journal) if str(journal) else "missing",
                "decade": str(group_decade),
                "rows": group_total,
                "insufficient_rows": insufficient_rows,
                "insufficient_share": round(insufficient_rows / group_total, 6) if group_total else 0.0,
                "has_doi_rows": int(insufficient["has_doi"].sum()) if insufficient_rows else 0,
                "has_openalex_rows": int(insufficient["has_openalex_id"].sum()) if insufficient_rows else 0,
                "has_oa_pdf_rows": int(insufficient["has_oa_pdf"].sum()) if insufficient_rows else 0,
                "missing_abstract_rows": int((~insufficient["has_abstract"]).sum()) if insufficient_rows else 0,
                "partial_short_text_rows": int(insufficient["is_partial_short_text"].sum()) if insufficient_rows else 0,
            }
        )
    return (
        pd.DataFrame(rows, columns=columns)
        .sort_values(["insufficient_rows", "insufficient_share", "journal_short", "decade"], ascending=[False, False, True, True])
        .reset_index(drop=True)
    )


def title_only_suggestion(row: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    title_text = build_classification_text(row, ["title"])
    scores = score_text(title_text, rules)
    causal = scores["causal"]
    predictive = scores["predictive"]
    causal_score = int(causal["score"])
    predictive_score = int(predictive["score"])
    causal_terms = causal["terms"]
    predictive_terms = predictive["terms"]
    dominance_margin = int(rules.get("scoring", {}).get("dominance_margin", 2))

    if causal_score > 0 and predictive_score == 0:
        category = "causal"
        confidence = confidence_from_score(causal)
        reason = "Title matched causal language: " + ", ".join(causal_terms[:6])
    elif predictive_score > 0 and causal_score == 0:
        category = "predictive"
        confidence = confidence_from_score(predictive)
        reason = "Title matched predictive language: " + ", ".join(predictive_terms[:6])
    elif causal_score > 0 and predictive_score > 0:
        if causal_score >= predictive_score + dominance_margin:
            category = "causal"
            confidence = "medium"
            reason = "Title matched both causal and predictive language, with stronger causal score."
        elif predictive_score >= causal_score + dominance_margin:
            category = "predictive"
            confidence = "medium"
            reason = "Title matched both causal and predictive language, with stronger predictive score."
        else:
            category = "other"
            confidence = "low"
            reason = "Title matched both causal and predictive language without a clear dominant category."
    else:
        category = "other"
        confidence = "low"
        reason = "No causal or predictive rule terms matched in the title."

    return {
        "title_only_suggested_category": category,
        "title_only_confidence": confidence,
        "title_only_reason": reason,
        "title_causal_language_indicator": causal_score,
        "title_predictive_language_indicator": predictive_score,
        "title_causal_language_terms": "|".join(causal_terms),
        "title_predictive_language_terms": "|".join(predictive_terms),
    }


def title_only_triage_candidates(df: pd.DataFrame, rules: dict[str, Any]) -> pd.DataFrame:
    columns = [
        "article_id",
        "journal_short",
        "publication_year",
        "title",
        "classification_text_chars",
        "current_category",
        "title_causal_language_indicator",
        "title_predictive_language_indicator",
        "title_causal_language_terms",
        "title_predictive_language_terms",
        "title_only_suggested_category",
        "title_only_confidence",
        "title_only_reason",
        "needs_manual_review",
    ]
    if df.empty:
        return pd.DataFrame(columns=columns)

    work = df.copy()
    work["current_category"] = resolved_category(work)
    candidates = work[work["current_category"].eq("insufficient_text")].copy()
    if candidates.empty:
        return pd.DataFrame(columns=columns)

    suggestions = pd.DataFrame([title_only_suggestion(row, rules) for row in candidates.to_dict(orient="records")])
    base_columns = ["article_id", "journal_short", "publication_year", "title", "classification_text_chars", "current_category"]
    for column in base_columns:
        if column not in candidates:
            candidates[column] = ""
    out = pd.concat([candidates[base_columns].reset_index(drop=True), suggestions.reset_index(drop=True)], axis=1)
    out["needs_manual_review"] = True
    confidence_order = {"high": 0, "medium": 1, "low": 2}
    category_order = {"causal": 0, "predictive": 1, "other": 2, "insufficient_text": 3}
    out["_confidence_order"] = out["title_only_confidence"].map(confidence_order).fillna(9)
    out["_category_order"] = out["title_only_suggested_category"].map(category_order).fillna(9)
    return out.sort_values(
        ["_confidence_order", "_category_order", "journal_short", "publication_year", "title"],
        ascending=[True, True, True, True, True],
    )[columns].reset_index(drop=True)


RECOVERY_QUEUE_COLUMNS = [
    "recovery_rank",
    "recovery_batch",
    "recovery_priority",
    "recovery_priority_score",
    "recovery_action",
    "recovery_reason",
    "article_id",
    "journal_short",
    "publication_year",
    "decade",
    "title",
    "doi",
    "openalex_id",
    "article_url",
    "oa_pdf_url",
    "text_enrichment_status",
    "text_enrichment_source",
    "abstract_source",
    "classification_text_chars",
    "title_only_suggested_category",
    "title_only_confidence",
    "title_only_reason",
    "doi_url",
    "crossref_work_url",
    "openalex_work_url",
    "openalex_title_search_url",
    "crossref_title_search_url",
    "semantic_scholar_title_search_url",
    "backfill_abstract",
    "source",
    "source_url",
    "source_record_id",
    "notes",
]


def cell_text(row: pd.Series | dict[str, Any], column: str) -> str:
    value = row.get(column, "") if hasattr(row, "get") else ""
    return "" if pd.isna(value) else str(value).strip()


def recovery_decade(year_value: Any) -> str:
    year = pd.to_numeric(pd.Series([year_value]), errors="coerce").iloc[0]
    if pd.isna(year):
        return "missing"
    return str(int(year) // 10 * 10)


def doi_resolver_url(doi: str) -> str:
    doi = doi.strip()
    return f"https://doi.org/{quote(doi, safe='/:;()._-')}" if doi else ""


def crossref_work_url(doi: str) -> str:
    doi = doi.strip()
    return f"https://api.crossref.org/works/{quote(doi, safe='')}" if doi else ""


def openalex_work_url(openalex_id: str) -> str:
    value = openalex_id.strip()
    if not value:
        return ""
    if value.startswith("https://openalex.org/"):
        return value
    return f"https://openalex.org/{value}"


def title_lookup_url(base_url: str, title: str) -> str:
    title = title.strip()
    return f"{base_url}{quote(title)}" if title else ""


def recovery_priority_bucket(score: int) -> str:
    if score >= 16:
        return "high"
    if score >= 10:
        return "medium"
    return "low"


def recovery_action_and_score(row: pd.Series, title_category: str) -> tuple[int, str, str]:
    score = 0
    reasons: list[str] = []
    year = pd.to_numeric(pd.Series([cell_text(row, "publication_year")]), errors="coerce").iloc[0]
    journal = cell_text(row, "journal_short").lower()
    doi = cell_text(row, "doi")
    openalex_id = cell_text(row, "openalex_id")
    article_url = cell_text(row, "article_url")
    oa_pdf_url = cell_text(row, "oa_pdf_url")
    abstract_source = cell_text(row, "abstract_source")
    status = cell_text(row, "text_enrichment_status")

    if pd.notna(year):
        year_int = int(year)
        if year_int < 1990:
            score += 6
            reasons.append("pre_1990_high_missingness")
        elif year_int < 2000:
            score += 5
            reasons.append("1990s_high_missingness")
        elif year_int < 2010:
            score += 3
            reasons.append("pre_2010_missingness")
        else:
            score += 1
            reasons.append("recent_missingness")

    if journal in {"aer", "ecta", "jpe"}:
        score += 3
        reasons.append("priority_journal_cell")
    elif journal in {"qje", "restud"}:
        score += 1
        reasons.append("secondary_journal_cell")

    if status == "partial_short_text" or abstract_source:
        score += 4
        reasons.append("partial_text_can_be_extended")
    else:
        score += 3
        reasons.append("missing_abstract")

    if oa_pdf_url:
        score += 5
        reasons.append("oa_pdf_available")
    if doi:
        score += 4
        reasons.append("doi_available")
    if openalex_id:
        score += 2
        reasons.append("openalex_id_available")
    if article_url:
        score += 1
        reasons.append("article_landing_url_available")
    if title_category in {"causal", "predictive"}:
        score += 2
        reasons.append(f"title_triage_{title_category}")

    if oa_pdf_url:
        action = "review_oa_pdf_or_first_pages"
    elif status == "partial_short_text" or abstract_source:
        action = "extend_existing_short_abstract"
    elif doi:
        action = "recover_abstract_from_doi_or_publisher"
    elif openalex_id:
        action = "review_openalex_or_title_match"
    elif article_url:
        action = "review_article_landing_page"
    else:
        action = "manual_title_year_search"

    return score, action, "|".join(reasons)


def insufficient_text_recovery_queue(df: pd.DataFrame, title_triage: pd.DataFrame | None = None) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=RECOVERY_QUEUE_COLUMNS)

    work = df.copy()
    work["current_category"] = resolved_category(work)
    work = work[work["current_category"].eq("insufficient_text")].copy()
    if work.empty:
        return pd.DataFrame(columns=RECOVERY_QUEUE_COLUMNS)

    triage_lookup: dict[str, dict[str, str]] = {}
    if title_triage is not None and not title_triage.empty and "article_id" in title_triage:
        triage_columns = ["title_only_suggested_category", "title_only_confidence", "title_only_reason"]
        available = ["article_id"] + [column for column in triage_columns if column in title_triage]
        for row in title_triage[available].fillna("").to_dict(orient="records"):
            triage_lookup[str(row.get("article_id", ""))] = {column: str(row.get(column, "")) for column in triage_columns}

    rows: list[dict[str, Any]] = []
    for _, row in work.fillna("").iterrows():
        article_id = cell_text(row, "article_id")
        title_info = triage_lookup.get(article_id, {})
        title_category = title_info.get("title_only_suggested_category", "")
        score, action, reason = recovery_action_and_score(row, title_category)
        title = cell_text(row, "title")
        doi = cell_text(row, "doi")
        openalex_id = cell_text(row, "openalex_id")
        rows.append(
            {
                "recovery_rank": 0,
                "recovery_batch": "",
                "recovery_priority": recovery_priority_bucket(score),
                "recovery_priority_score": score,
                "recovery_action": action,
                "recovery_reason": reason,
                "article_id": article_id,
                "journal_short": cell_text(row, "journal_short"),
                "publication_year": cell_text(row, "publication_year"),
                "decade": recovery_decade(cell_text(row, "publication_year")),
                "title": title,
                "doi": doi,
                "openalex_id": openalex_id,
                "article_url": cell_text(row, "article_url"),
                "oa_pdf_url": cell_text(row, "oa_pdf_url"),
                "text_enrichment_status": cell_text(row, "text_enrichment_status"),
                "text_enrichment_source": cell_text(row, "text_enrichment_source"),
                "abstract_source": cell_text(row, "abstract_source"),
                "classification_text_chars": cell_text(row, "classification_text_chars"),
                "title_only_suggested_category": title_category,
                "title_only_confidence": title_info.get("title_only_confidence", ""),
                "title_only_reason": title_info.get("title_only_reason", ""),
                "doi_url": doi_resolver_url(doi),
                "crossref_work_url": crossref_work_url(doi),
                "openalex_work_url": openalex_work_url(openalex_id),
                "openalex_title_search_url": title_lookup_url("https://api.openalex.org/works?per-page=5&search=", title),
                "crossref_title_search_url": title_lookup_url("https://api.crossref.org/works?rows=5&query.title=", title),
                "semantic_scholar_title_search_url": title_lookup_url("https://www.semanticscholar.org/search?q=", title),
                "backfill_abstract": "",
                "source": "",
                "source_url": "",
                "source_record_id": "",
                "notes": f"suggested_action={action};recovery_reason={reason}",
            }
        )

    out = pd.DataFrame(rows, columns=RECOVERY_QUEUE_COLUMNS)
    out = out.sort_values(
        ["recovery_priority_score", "journal_short", "publication_year", "title"],
        ascending=[False, True, True, True],
    ).reset_index(drop=True)
    out["recovery_rank"] = range(1, len(out) + 1)
    out["recovery_batch"] = [f"R{((index // 100) + 1):03d}" for index in range(len(out))]
    return out[RECOVERY_QUEUE_COLUMNS]


SENSITIVITY_SCENARIOS = [
    "baseline",
    "exclude_insufficient_text",
    "insufficient_text_as_other",
    "title_triage_non_other",
    "title_triage_all_suggestions",
]


def category_sensitivity_shares(df: pd.DataFrame, group_cols: list[str], title_triage: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["scenario"] + group_cols + ["category", "article_count", "group_total", "category_share"])

    base = df.copy()
    base["_resolved_category"] = resolved_category(base)
    title_lookup: dict[str, str] = {}
    if not title_triage.empty and {"article_id", "title_only_suggested_category"}.issubset(title_triage.columns):
        title_lookup = {
            str(row["article_id"]): str(row["title_only_suggested_category"])
            for _, row in title_triage[["article_id", "title_only_suggested_category"]].fillna("").iterrows()
            if str(row["article_id"])
        }

    scenario_frames: list[pd.DataFrame] = []
    for scenario in SENSITIVITY_SCENARIOS:
        work = base.copy()
        work["_sensitivity_category"] = work["_resolved_category"].copy()
        insufficient_mask = work["_sensitivity_category"].eq("insufficient_text")
        if scenario == "exclude_insufficient_text":
            work = work[~insufficient_mask].copy()
        elif scenario == "insufficient_text_as_other":
            work.loc[insufficient_mask, "_sensitivity_category"] = "other"
        elif scenario == "title_triage_non_other":
            suggestions = work["article_id"].astype(str).map(title_lookup).fillna("")
            replace_mask = insufficient_mask & suggestions.isin(["causal", "predictive"])
            work.loc[replace_mask, "_sensitivity_category"] = suggestions.loc[replace_mask]
        elif scenario == "title_triage_all_suggestions":
            suggestions = work["article_id"].astype(str).map(title_lookup).fillna("")
            replace_mask = insufficient_mask & suggestions.isin(["causal", "predictive", "other"])
            work.loc[replace_mask, "_sensitivity_category"] = suggestions.loc[replace_mask]

        shares = category_shares_from_column(work, group_cols, "_sensitivity_category")
        shares.insert(0, "scenario", scenario)
        scenario_frames.append(shares)

    return pd.concat(scenario_frames, ignore_index=True) if scenario_frames else pd.DataFrame()


def analysis_scope_filter(df: pd.DataFrame, config: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    scope_column = str(config.get("analysis_scope_column", "") or "")
    excluded_scopes = {str(scope) for scope in config.get("excluded_analysis_scopes", []) or []}
    if not scope_column or scope_column not in df.columns or not excluded_scopes:
        summary = pd.DataFrame(
            [
                {
                    "scope": "all_rows",
                    "rows": len(df),
                    "included_in_analysis": True,
                    "reason": "no_scope_filter_configured_or_available",
                }
            ]
        )
        return df.copy(), summary

    work = df.copy()
    work["_analysis_scope_value"] = work[scope_column].replace("", "missing").astype(str)
    work["_included_in_analysis"] = ~work["_analysis_scope_value"].isin(excluded_scopes)
    summary = (
        work.groupby(["_analysis_scope_value", "_included_in_analysis"], dropna=False)
        .size()
        .reset_index(name="rows")
        .rename(columns={"_analysis_scope_value": "scope", "_included_in_analysis": "included_in_analysis"})
        .sort_values(["included_in_analysis", "scope"], ascending=[False, True])
        .reset_index(drop=True)
    )
    summary["reason"] = summary["scope"].map(lambda scope: "excluded_nonresearch_scope" if scope in excluded_scopes else "")
    filtered = work[work["_included_in_analysis"]].drop(columns=["_analysis_scope_value", "_included_in_analysis"]).copy()
    return filtered, summary


VALIDATION_CATEGORY_METRIC_COLUMNS = [
    "label",
    "true_positive",
    "predicted_count",
    "manual_count",
    "precision",
    "recall",
    "f1",
]

VALIDATION_DISAGREEMENT_COLUMNS = [
    "validation_id",
    "article_id",
    "journal_short",
    "publication_year",
    "title",
    "manual_label",
    "manual_confidence",
    "predicted_label",
    "predicted_confidence",
    "classification_reason",
    "manual_notes",
]

VALIDATION_ADJUDICATION_COLUMNS = VALIDATION_DISAGREEMENT_COLUMNS + [
    "adjudicated_label",
    "adjudication_notes",
    "adjudicator_id",
    "adjudication_date",
]


def category_validation_metrics(labeled: pd.DataFrame) -> pd.DataFrame:
    if labeled.empty:
        return pd.DataFrame(columns=VALIDATION_CATEGORY_METRIC_COLUMNS)
    labels = sorted(
        label
        for label in set(labeled["manual_label"].dropna().astype(str)) | set(labeled["predicted_label"].dropna().astype(str))
        if label
    )
    rows: list[dict[str, Any]] = []
    for label in labels:
        manual_mask = labeled["manual_label"].astype(str).eq(label)
        predicted_mask = labeled["predicted_label"].astype(str).eq(label)
        true_positive = int((manual_mask & predicted_mask).sum())
        predicted_count = int(predicted_mask.sum())
        manual_count = int(manual_mask.sum())
        precision = round(true_positive / predicted_count, 6) if predicted_count else float("nan")
        recall = round(true_positive / manual_count, 6) if manual_count else float("nan")
        if pd.notna(precision) and pd.notna(recall) and precision + recall > 0:
            f1 = round(2 * precision * recall / (precision + recall), 6)
        else:
            f1 = float("nan")
        rows.append(
            {
                "label": label,
                "true_positive": true_positive,
                "predicted_count": predicted_count,
                "manual_count": manual_count,
                "precision": precision,
                "recall": recall,
                "f1": f1,
            }
        )
    return pd.DataFrame(rows, columns=VALIDATION_CATEGORY_METRIC_COLUMNS)


def validation_disagreements(labeled: pd.DataFrame) -> pd.DataFrame:
    if labeled.empty or "agreement" not in labeled:
        return pd.DataFrame(columns=VALIDATION_DISAGREEMENT_COLUMNS)
    disagreements = labeled[~labeled["agreement"]].copy()
    if disagreements.empty:
        return pd.DataFrame(columns=VALIDATION_DISAGREEMENT_COLUMNS)
    output_columns = [
        *VALIDATION_DISAGREEMENT_COLUMNS,
        *[column for column in VALIDATION_ADJUDICATION_COLUMNS if column not in VALIDATION_DISAGREEMENT_COLUMNS],
    ]
    for column in output_columns:
        if column not in disagreements:
            disagreements[column] = ""
    return disagreements[output_columns].reset_index(drop=True)


def validation_adjudication_packet(disagreements: pd.DataFrame) -> pd.DataFrame:
    packet = disagreements.copy().fillna("")
    for column in VALIDATION_ADJUDICATION_COLUMNS:
        if column not in packet:
            packet[column] = ""
    return packet[VALIDATION_ADJUDICATION_COLUMNS].reset_index(drop=True)


def validation_metrics(classified_df: pd.DataFrame, validation_df: pd.DataFrame | None) -> dict[str, pd.DataFrame]:
    if validation_df is None or validation_df.empty or "manual_label" not in validation_df.columns:
        return {
            "status": pd.DataFrame([{"validation_status": "unavailable", "reason": "No validation file with manual_label was provided."}])
        }

    validation_work = validation_df.copy()
    if "adjudicated_label" in validation_work.columns:
        validation_work["manual_label_original"] = validation_work["manual_label"].astype(str)
        adjudicated_mask = is_nonmissing(validation_work["adjudicated_label"])
        validation_work.loc[adjudicated_mask, "manual_label"] = validation_work.loc[adjudicated_mask, "adjudicated_label"].astype(str)
    labeled = validation_work[is_nonmissing(validation_work["manual_label"])].copy()
    if labeled.empty:
        return {
            "status": pd.DataFrame([{"validation_status": "unavailable", "reason": "Validation file has no completed manual_label values."}])
        }

    category_lookup = classified_df[["article_id"]].copy()
    category_lookup["predicted_label"] = resolved_category(classified_df)
    confidence_lookup = classified_df[["article_id"]].copy()
    confidence_lookup["predicted_confidence"] = resolved_confidence(classified_df)
    reason_lookup = classified_df[["article_id"]].copy()
    reason_lookup["_predicted_classification_reason"] = classified_df["classification_reason"] if "classification_reason" in classified_df else ""
    merged = (
        labeled.merge(category_lookup, on="article_id", how="left")
        .merge(confidence_lookup, on="article_id", how="left")
        .merge(reason_lookup, on="article_id", how="left")
    )
    if "classification_reason" not in merged:
        merged["classification_reason"] = merged["_predicted_classification_reason"]
    elif "_predicted_classification_reason" in merged:
        missing_reason = ~is_nonmissing(merged["classification_reason"])
        merged.loc[missing_reason, "classification_reason"] = merged.loc[missing_reason, "_predicted_classification_reason"]
    if "_predicted_classification_reason" in merged:
        merged = merged.drop(columns=["_predicted_classification_reason"])
    merged["agreement"] = merged["manual_label"].astype(str) == merged["predicted_label"].astype(str)
    confusion = pd.crosstab(
        merged["manual_label"],
        merged["predicted_label"],
        dropna=False,
    ).reset_index()
    overall = pd.DataFrame(
        [
            {
                "validation_status": "available",
                "labeled_count": len(merged),
                "agreement_rate": round(float(merged["agreement"].mean()), 6),
                "high_confidence_labeled_count": int((merged["predicted_confidence"] == "high").sum()),
                "high_confidence_agreement_rate": round(
                    float(merged.loc[merged["predicted_confidence"] == "high", "agreement"].mean())
                    if (merged["predicted_confidence"] == "high").any()
                    else float("nan"),
                    6,
                ),
            }
        ]
    )
    disagreements = validation_disagreements(merged)
    return {
        "confusion": confusion,
        "metrics": overall,
        "category_metrics": category_validation_metrics(merged),
        "disagreements": disagreements,
        "adjudication_packet": validation_adjudication_packet(disagreements),
        "labeled": merged,
    }


def expansion_recommendation(classified_df: pd.DataFrame, validation: dict[str, pd.DataFrame], config: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    abstract_overall = abstract_coverage(classified_df)
    abstract_by_journal = abstract_coverage(classified_df, ["journal_short"]) if "journal_short" in classified_df else pd.DataFrame()
    insufficient_overall = insufficient_text_rates(classified_df)

    overall_abstract_share = float(abstract_overall["abstract_share"].iloc[0]) if not abstract_overall.empty else 0.0
    min_journal_abstract_share = (
        float(abstract_by_journal["abstract_share"].min()) if not abstract_by_journal.empty else overall_abstract_share
    )
    insufficient_share = float(insufficient_overall["insufficient_text_share"].iloc[0])

    if overall_abstract_share < float(config["minimum_overall_abstract_share"]):
        reasons.append(
            f"Overall abstract coverage is {overall_abstract_share:.1%}, below the {float(config['minimum_overall_abstract_share']):.0%} threshold."
        )
    if min_journal_abstract_share < float(config["minimum_journal_abstract_share"]):
        reasons.append(
            f"At least one journal has abstract coverage of {min_journal_abstract_share:.1%}, below the {float(config['minimum_journal_abstract_share']):.0%} threshold."
        )
    if insufficient_share > float(config["maximum_insufficient_text_share"]):
        reasons.append(
            f"Insufficient-text share is {insufficient_share:.1%}, above the {float(config['maximum_insufficient_text_share']):.0%} threshold."
        )

    validation_status = validation.get("metrics", validation.get("status", pd.DataFrame())).iloc[0].to_dict()
    if validation_status.get("validation_status") == "available":
        high_agreement = validation_status.get("high_confidence_agreement_rate")
        if pd.notna(high_agreement) and float(high_agreement) < float(config["minimum_high_confidence_validation_agreement"]):
            reasons.append(
                f"High-confidence validation agreement is {float(high_agreement):.1%}, below the {float(config['minimum_high_confidence_validation_agreement']):.0%} threshold."
            )
    else:
        reasons.append("Manual validation labels are not available yet.")

    if any("abstract coverage" in reason or "Insufficient-text" in reason for reason in reasons):
        decision = "pause_for_metadata_enrichment"
    elif any("Manual validation labels are not available yet." in reason for reason in reasons):
        decision = "pause_for_manual_validation"
    elif any("validation" in reason or "agreement" in reason for reason in reasons):
        decision = "pause_for_classifier_revision"
    else:
        decision = "proceed"

    return {
        "recommendation": decision,
        "reasons": reasons,
        "overall_abstract_share": overall_abstract_share,
        "min_journal_abstract_share": min_journal_abstract_share,
        "insufficient_text_share": insufficient_share,
    }


def df_to_markdown(df: pd.DataFrame, max_rows: int = 30) -> str:
    if df.empty:
        return "_No rows._"
    shown = df.head(max_rows).fillna("")
    headers = [markdown_cell(column) for column in shown.columns]
    rows = [headers] + [[markdown_cell(value) for value in row] for row in shown.astype(str).values.tolist()]
    widths = [max(len(row[i]) for row in rows) for i in range(len(headers))]
    header = "| " + " | ".join(headers[i].ljust(widths[i]) for i in range(len(headers))) + " |"
    separator = "| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |"
    body = ["| " + " | ".join(row[i].ljust(widths[i]) for i in range(len(headers))) + " |" for row in rows[1:]]
    suffix = f"\n\n_Only first {max_rows} rows shown._" if len(df) > max_rows else ""
    return "\n".join([header, separator] + body) + suffix


def markdown_cell(value: Any) -> str:
    return str(value).replace("\r", " ").replace("\n", " ").replace("|", "\\|")


def label_source(df: pd.DataFrame) -> str:
    if "llm_status" in df and (df["llm_status"].astype(str) == "ok").any():
        return "hybrid_llm_when_ok_else_rule_based"
    if "classification_method" in df:
        methods = sorted(set(df["classification_method"].dropna().astype(str)))
        return "|".join(methods)
    return "unknown"


def write_report(
    path: Path,
    *,
    classified_path: str,
    validation_path: str | None,
    classified_df: pd.DataFrame,
    original_row_count: int,
    scope_summary: pd.DataFrame,
    category_year: pd.DataFrame,
    category_journal: pd.DataFrame,
    confidence: pd.DataFrame,
    insufficient: pd.DataFrame,
    remaining_insufficient: pd.DataFrame,
    title_triage: pd.DataFrame,
    recovery_queue: pd.DataFrame,
    sensitivity_year: pd.DataFrame,
    sensitivity_journal: pd.DataFrame,
    evidence_tier_categories: pd.DataFrame,
    evidence_tier_sensitivity_overall: pd.DataFrame,
    evidence_tier_sensitivity_year: pd.DataFrame,
    evidence_tier_sensitivity_journal: pd.DataFrame,
    validation: dict[str, pd.DataFrame],
    recommendation: dict[str, Any],
) -> None:
    validation_table = validation.get("metrics", validation.get("status", pd.DataFrame()))
    reasons = recommendation["reasons"] or ["No pause rule triggered."]
    lines: list[str] = [
        "# Classification Diagnostics",
        "",
        "## Scope",
        "",
        f"- Classified input: `{classified_path}`",
        f"- Validation input: `{validation_path or 'not provided'}`",
        f"- Label source: `{label_source(classified_df)}`",
        f"- Input rows: {original_row_count}",
        f"- Analysis rows: {len(classified_df)}",
        "",
        "## Analysis Scope",
        "",
        df_to_markdown(scope_summary, max_rows=20),
        "",
        "## Expansion Recommendation",
        "",
        f"Recommendation: `{recommendation['recommendation']}`",
        "",
        "Reasons:",
        "",
        *[f"- {reason}" for reason in reasons],
        "",
        "## Key Coverage Metrics",
        "",
        f"- Overall abstract coverage: {recommendation['overall_abstract_share']:.1%}",
        f"- Minimum journal abstract coverage: {recommendation['min_journal_abstract_share']:.1%}",
        f"- Insufficient-text share: {recommendation['insufficient_text_share']:.1%}",
        "",
        "## Category Shares By Journal",
        "",
        df_to_markdown(category_journal, max_rows=40),
        "",
        "## Category Shares By Year",
        "",
        df_to_markdown(category_year, max_rows=40),
        "",
        "## Confidence Distribution",
        "",
        df_to_markdown(confidence, max_rows=20),
        "",
        "## Insufficient Text Rates",
        "",
        df_to_markdown(insufficient, max_rows=20),
        "",
        "## Remaining Insufficient Text Profile",
        "",
        df_to_markdown(remaining_insufficient, max_rows=20),
        "",
        "## Title-Only Triage Candidates",
        "",
        df_to_markdown(title_triage, max_rows=20),
        "",
        "## Insufficient Text Recovery Queue",
        "",
        df_to_markdown(recovery_queue, max_rows=20),
        "",
        "## Sensitivity Category Shares By Year",
        "",
        df_to_markdown(sensitivity_year, max_rows=40),
        "",
        "## Sensitivity Category Shares By Journal",
        "",
        df_to_markdown(sensitivity_journal, max_rows=40),
        "",
        "## Evidence-Tier Robustness",
        "",
        "- `baseline_current_labels` uses all accepted recovered-text tiers.",
        "- `formal_abstract_only` reassigns non-tier-A recovered rows to `insufficient_text`.",
        "- `no_recovered_text` reassigns every recovered-tier row to `insufficient_text`.",
        "",
        "### Category Shares By Evidence Tier",
        "",
        df_to_markdown(evidence_tier_categories, max_rows=30),
        "",
        "### Overall Formal-Abstract Sensitivity",
        "",
        df_to_markdown(evidence_tier_sensitivity_overall, max_rows=10),
        "",
        "### Evidence-Tier Sensitivity By Year",
        "",
        df_to_markdown(evidence_tier_sensitivity_year, max_rows=40),
        "",
        "### Evidence-Tier Sensitivity By Journal",
        "",
        df_to_markdown(evidence_tier_sensitivity_journal, max_rows=40),
        "",
        "## Manual Validation",
        "",
        df_to_markdown(validation_table, max_rows=20),
        "",
        "## Manual Validation Category Metrics",
        "",
        df_to_markdown(validation.get("category_metrics", pd.DataFrame(columns=VALIDATION_CATEGORY_METRIC_COLUMNS)), max_rows=20),
        "",
        "## Manual Validation Disagreements",
        "",
        df_to_markdown(validation.get("disagreements", pd.DataFrame(columns=VALIDATION_DISAGREEMENT_COLUMNS)), max_rows=20),
        "",
        "## Manual Validation Adjudication Packet",
        "",
        df_to_markdown(validation.get("adjudication_packet", pd.DataFrame(columns=VALIDATION_ADJUDICATION_COLUMNS)), max_rows=20),
        "",
        "## Next Action",
        "",
    ]
    if recommendation["recommendation"] == "pause_for_metadata_enrichment":
        lines.append("Prioritize abstract enrichment and manual validation before using historical classification trends as substantive evidence.")
    elif recommendation["recommendation"] == "pause_for_manual_validation":
        lines.append("Complete manual validation labels before using historical classification trends as substantive evidence.")
    elif recommendation["recommendation"] == "pause_for_classifier_revision":
        lines.append("Complete manual validation and revise the classifier or prompt before using trend estimates.")
    else:
        lines.append("Proceed to analysis, while preserving the validation and missingness caveats.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def run_diagnostics(
    classified_path: Path,
    output_dir: Path,
    report_path: Path,
    config_path: Path,
    rules_path: Path,
    validation_path: Path | None = None,
) -> None:
    config = load_config(config_path)
    rules = load_classification_rules(rules_path)
    original_df = pd.read_csv(classified_path, dtype=str).fillna("")
    classified_df, scope_summary = analysis_scope_filter(original_df, config)
    validation_df = pd.read_csv(validation_path, dtype=str).fillna("") if validation_path and validation_path.exists() else None
    if validation_df is not None and "article_id" in validation_df.columns:
        validation_df = validation_df[validation_df["article_id"].isin(classified_df["article_id"])].copy()
    output_dir.mkdir(parents=True, exist_ok=True)

    category_year = category_shares(classified_df, ["publication_year"])
    category_journal = category_shares(classified_df, ["journal_short"])
    category_journal_year = category_shares(classified_df, ["journal_short", "publication_year"])
    category_article_type = category_shares(classified_df, ["article_type"]) if "article_type" in classified_df else pd.DataFrame()
    confidence = confidence_distribution(classified_df)
    insufficient = insufficient_text_rates(classified_df, ["journal_short"]) if "journal_short" in classified_df else insufficient_text_rates(classified_df)
    remaining_insufficient = remaining_insufficient_text_profile(classified_df)
    title_triage = title_only_triage_candidates(classified_df, rules)
    recovery_queue = insufficient_text_recovery_queue(classified_df, title_triage)
    sensitivity_year = category_sensitivity_shares(classified_df, ["publication_year"], title_triage)
    sensitivity_journal = category_sensitivity_shares(classified_df, ["journal_short"], title_triage)
    evidence_tier_categories = evidence_tier_category_shares(classified_df)
    evidence_tier_sensitivity_overall = evidence_tier_sensitivity_summary(classified_df)
    evidence_tier_sensitivity_year = evidence_tier_sensitivity_shares(classified_df, ["publication_year"])
    evidence_tier_sensitivity_journal = evidence_tier_sensitivity_shares(classified_df, ["journal_short"])
    validation = validation_metrics(classified_df, validation_df)
    recommendation = expansion_recommendation(classified_df, validation, config)

    category_year.to_csv(output_dir / "category_shares_by_year.csv", index=False)
    category_journal.to_csv(output_dir / "category_shares_by_journal.csv", index=False)
    category_journal_year.to_csv(output_dir / "category_shares_by_journal_year.csv", index=False)
    category_article_type.to_csv(output_dir / "category_shares_by_article_type.csv", index=False)
    confidence.to_csv(output_dir / "confidence_distribution.csv", index=False)
    insufficient.to_csv(output_dir / "insufficient_text_rates.csv", index=False)
    remaining_insufficient.to_csv(output_dir / "remaining_insufficient_text_profile.csv", index=False)
    title_triage.to_csv(output_dir / "title_only_triage_candidates.csv", index=False)
    recovery_queue.to_csv(output_dir / "insufficient_text_recovery_queue.csv", index=False)
    sensitivity_year.to_csv(output_dir / "category_sensitivity_by_year.csv", index=False)
    sensitivity_journal.to_csv(output_dir / "category_sensitivity_by_journal.csv", index=False)
    evidence_tier_categories.to_csv(output_dir / "evidence_tier_category_shares.csv", index=False)
    evidence_tier_sensitivity_overall.to_csv(output_dir / "evidence_tier_sensitivity_overall.csv", index=False)
    evidence_tier_sensitivity_year.to_csv(output_dir / "evidence_tier_sensitivity_by_year.csv", index=False)
    evidence_tier_sensitivity_journal.to_csv(output_dir / "evidence_tier_sensitivity_by_journal.csv", index=False)
    scope_summary.to_csv(output_dir / "analysis_scope_counts.csv", index=False)
    if "confusion" in validation:
        validation["confusion"].to_csv(output_dir / "validation_confusion_matrix.csv", index=False)
    validation.get("category_metrics", pd.DataFrame(columns=VALIDATION_CATEGORY_METRIC_COLUMNS)).to_csv(
        output_dir / "validation_category_metrics.csv", index=False
    )
    validation.get("disagreements", pd.DataFrame(columns=VALIDATION_DISAGREEMENT_COLUMNS)).to_csv(
        output_dir / "validation_disagreements.csv", index=False
    )
    validation.get("adjudication_packet", pd.DataFrame(columns=VALIDATION_ADJUDICATION_COLUMNS)).to_csv(
        output_dir / "validation_adjudication_packet.csv", index=False
    )
    validation.get("metrics", validation.get("status", pd.DataFrame())).to_csv(output_dir / "validation_metrics.csv", index=False)
    pd.DataFrame([{k: v for k, v in recommendation.items() if k != "reasons"}]).assign(
        reasons=" | ".join(recommendation["reasons"])
    ).to_csv(output_dir / "classification_recommendation.csv", index=False)

    write_report(
        report_path,
        classified_path=str(classified_path),
        validation_path=str(validation_path) if validation_path else None,
        classified_df=classified_df,
        original_row_count=len(original_df),
        scope_summary=scope_summary,
        category_year=category_year,
        category_journal=category_journal,
        confidence=confidence,
        insufficient=insufficient,
        remaining_insufficient=remaining_insufficient,
        title_triage=title_triage,
        recovery_queue=recovery_queue,
        sensitivity_year=sensitivity_year,
        sensitivity_journal=sensitivity_journal,
        evidence_tier_categories=evidence_tier_categories,
        evidence_tier_sensitivity_overall=evidence_tier_sensitivity_overall,
        evidence_tier_sensitivity_year=evidence_tier_sensitivity_year,
        evidence_tier_sensitivity_journal=evidence_tier_sensitivity_journal,
        validation=validation,
        recommendation=recommendation,
    )
    print(f"recommendation={recommendation['recommendation']}")
    print(f"report={report_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--classified", required=True)
    parser.add_argument("--validation", default=None)
    parser.add_argument("--output-dir", default="outputs/tables")
    parser.add_argument("--report", default="docs/classification_diagnostics.md")
    parser.add_argument("--config", default="config/classification_diagnostics.yml")
    parser.add_argument("--rules", default="config/classification_rules.yml")
    args = parser.parse_args()
    run_diagnostics(
        classified_path=Path(args.classified),
        validation_path=Path(args.validation) if args.validation else None,
        output_dir=Path(args.output_dir),
        report_path=Path(args.report),
        config_path=Path(args.config),
        rules_path=Path(args.rules),
    )


if __name__ == "__main__":
    main()
