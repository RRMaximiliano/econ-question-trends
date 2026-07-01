from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, List

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "lib"))

from econqt_common import ensure_dirs, load_journals, project_root_from_arg, utc_now_iso  # noqa: E402


CORE_FIELDS = [
    "doi",
    "title",
    "abstract",
    "volume",
    "issue",
    "pages_raw",
    "author_names",
    "author_affiliations_raw",
    "jel_codes",
    "keywords",
    "article_type",
]


FINAL_FIELDS = [
    "title",
    "abstract",
    "journal",
    "publication_year",
    "doi",
    "volume",
    "issue",
    "pages_raw",
    "article_type",
    "author_names",
    "author_affiliations_raw",
    "num_authors",
    "jel_codes",
    "keywords",
    "field_jel_primary",
    "field_jel_broad",
]


def is_nonmissing(series: pd.Series) -> pd.Series:
    stripped = series.astype(str).str.strip()
    return series.notna() & ~stripped.isin(["", "[]", "{}"])


def df_to_markdown(df: pd.DataFrame, max_rows: int = 30) -> str:
    if df.empty:
        return "_No rows._"
    shown = df.head(max_rows).copy()
    shown = shown.fillna("")
    headers = list(shown.columns)
    rows = [headers] + shown.astype(str).values.tolist()
    widths = [max(len(row[i]) for row in rows) for i in range(len(headers))]
    header = "| " + " | ".join(headers[i].ljust(widths[i]) for i in range(len(headers))) + " |"
    separator = "| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |"
    body = ["| " + " | ".join(row[i].ljust(widths[i]) for i in range(len(headers))) + " |" for row in rows[1:]]
    suffix = "\n\n_Only first {max_rows} rows shown._".format(max_rows=max_rows) if len(df) > max_rows else ""
    return "\n".join([header, separator] + body) + suffix


def coverage_by_source(source_df: pd.DataFrame) -> pd.DataFrame:
    if source_df.empty:
        return pd.DataFrame()
    source_df = source_df.copy()
    source_df["publication_year"] = pd.to_numeric(source_df["publication_year"], errors="coerce").astype("Int64")
    rows = []
    for keys, group in source_df.groupby(["source", "journal_short", "publication_year"], dropna=False):
        row = {
            "source": keys[0],
            "journal_short": keys[1],
            "publication_year": keys[2],
            "record_count": len(group),
        }
        for field in CORE_FIELDS:
            row[f"share_with_{field}"] = round(float(is_nonmissing(group[field]).mean()), 4) if field in group else 0
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["source", "journal_short", "publication_year"])


def missingness_table(articles: pd.DataFrame) -> pd.DataFrame:
    rows = []
    total = len(articles)
    for field in FINAL_FIELDS:
        if field not in articles:
            continue
        nonmissing = int(is_nonmissing(articles[field]).sum())
        rows.append(
            {
                "variable": field,
                "nonmissing_count": nonmissing,
                "missing_count": total - nonmissing,
                "nonmissing_share": round(nonmissing / total, 4) if total else 0,
            }
        )
    return pd.DataFrame(rows)


def article_counts(articles: pd.DataFrame) -> pd.DataFrame:
    if articles.empty:
        return pd.DataFrame()
    articles = articles.copy()
    articles["publication_year"] = pd.to_numeric(articles["publication_year"], errors="coerce").astype("Int64")
    counts = (
        articles.groupby(["journal_short", "publication_year"], dropna=False)
        .size()
        .reset_index(name="article_count")
        .sort_values(["journal_short", "publication_year"])
    )
    return counts


def write_text(path: Path, lines: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        fh.write("\n".join(lines).rstrip() + "\n")


def make_reports(project_root: Path, start_year: int, end_year: int, run_id: str) -> None:
    ensure_dirs(project_root)
    source_path = project_root / "data" / "intermediate" / "source_records.csv"
    articles_path = project_root / "data" / "final" / "articles_pilot.csv"
    source_df = pd.read_csv(source_path, dtype=str).fillna("")
    articles = pd.read_csv(articles_path, dtype=str).fillna("")

    source_coverage = coverage_by_source(source_df)
    missingness = missingness_table(articles)
    counts = article_counts(articles)

    source_coverage.to_csv(project_root / "outputs" / "tables" / "source_coverage_by_journal_year.csv", index=False)
    missingness.to_csv(project_root / "outputs" / "tables" / "missingness_by_variable.csv", index=False)
    counts.to_csv(project_root / "outputs" / "tables" / "article_counts_by_journal_year.csv", index=False)

    journals = pd.DataFrame(load_journals(project_root))
    source_totals = (
        source_df.groupby(["source", "journal_short"], dropna=False)
        .size()
        .reset_index(name="source_records")
        .sort_values(["source", "journal_short"])
    )
    abstract_counts = (
        articles.assign(has_abstract=is_nonmissing(articles["abstract"]))
        .groupby("journal_short", dropna=False)["has_abstract"]
        .agg(["sum", "count"])
        .reset_index()
        .rename(columns={"sum": "articles_with_abstract", "count": "articles"})
    )
    if not abstract_counts.empty:
        abstract_counts["abstract_share"] = (
            abstract_counts["articles_with_abstract"].astype(float) / abstract_counts["articles"].astype(float)
        ).round(4)

    coverage_lines: List[str] = [
        "# Phase 1 Coverage Report",
        "",
        f"Generated UTC: {utc_now_iso()}",
        f"Run ID: `{run_id}`",
        f"Pilot period: {start_year}-{end_year}",
        "",
        "## Scope",
        "",
        "This report covers the five-journal pilot using public Crossref and OpenAlex metadata.",
        "",
        "## Journal Registry",
        "",
        df_to_markdown(journals[["journal_short", "journal", "issn_l", "openalex_source_id"]]),
        "",
        "## Source Record Totals",
        "",
        df_to_markdown(source_totals),
        "",
        "## Final Article Counts By Journal-Year",
        "",
        df_to_markdown(counts, max_rows=50),
        "",
        "## Abstract Coverage In Final Article File",
        "",
        df_to_markdown(abstract_counts),
        "",
        "## Missingness By Variable",
        "",
        df_to_markdown(missingness),
        "",
        "## Known Limitations From This Batch",
        "",
        "- Crossref and OpenAlex are public metadata sources; neither should be treated as complete for article type, JEL codes, or publication-time affiliations.",
        "- JEL code fields are intentionally left missing unless a source provides explicit JEL metadata.",
        "- OpenAlex abstracts may be reconstructed from inverted indexes and are unavailable for some records.",
        "- Article type is source-provided only. This batch does not infer comments, replies, notes, proceedings, or reviews from titles.",
        "- OpenAlex sometimes labels journal DOI records as `preprint` or `report`; these are retained but flagged as `nonstandard_article_type` in `metadata_warning`.",
        "- Publisher, JSTOR, EconLit, and RePEc enrichment are not included yet.",
        "",
        "## Recommendation",
        "",
        "Use these diagnostics to decide whether public metadata coverage is adequate for exploratory work before adding restricted or publisher-specific sources.",
    ]
    write_text(project_root / "docs" / "coverage_report.md", coverage_lines)

    data_doc_lines: List[str] = [
        "# Data Documentation",
        "",
        f"Generated UTC: {utc_now_iso()}",
        f"Run ID: `{run_id}`",
        "",
        "## Data Sources Used",
        "",
        "- Crossref REST API: DOI-centered bibliographic metadata.",
        "- OpenAlex Works API: work discovery, abstracts where available, authorships, institutions, keywords, concepts, topics, and DOI links.",
        "",
        "## Output Datasets",
        "",
        "- `data/intermediate/source_records.csv`: standardized source-level records before deduplication.",
        "- `data/final/articles_pilot.csv`: deduplicated article-level pilot file.",
        "",
        "## Deduplication",
        "",
        "Records are grouped by normalized DOI when available. Records without DOI are grouped by normalized title, journal, and publication year. Fuzzy title matching is not used for automatic deduplication.",
        "",
        "## Variable Provenance",
        "",
        "The final article file includes source columns such as `title_source`, `abstract_source`, `bibliographic_source`, `authors_source`, `affiliations_source`, `jel_source`, and `keywords_source`.",
        "",
        "## Missingness",
        "",
        df_to_markdown(missingness),
        "",
        "## Known Limitations",
        "",
        "- This is a public-source metadata pilot, not a final archival article database.",
        "- Article type/category coverage is incomplete and source-provided only.",
        "- Source-provided article type is too coarse for full research-article restrictions in this batch. Crossref mostly returns `journal-article`, while OpenAlex may return `article`, `preprint`, `report`, `paratext`, or `erratum`.",
        "- JEL code coverage is currently missing because neither Crossref nor OpenAlex reliably supplies JEL metadata in this workflow.",
        "- Affiliation metadata should be interpreted cautiously; OpenAlex institutions and raw affiliation strings may not always represent publication-time affiliations cleanly.",
        "- Abstract missingness must be accounted for before any classification exercise.",
        "",
        "## Next Expansion Options",
        "",
        "- Add publisher table-of-contents scraping or APIs for article type validation.",
        "- Add JSTOR support for historical coverage, subject to access terms.",
        "- Add EconLit exports for JEL codes, keywords, article types, and abstracts where institutional terms allow.",
        "- Add RePEc as an economics-specific supplemental source.",
    ]
    write_text(project_root / "docs" / "data_documentation.md", data_doc_lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--start-year", type=int, required=True)
    parser.add_argument("--end-year", type=int, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    make_reports(project_root_from_arg(args.project_root), args.start_year, args.end_year, args.run_id)


if __name__ == "__main__":
    main()
