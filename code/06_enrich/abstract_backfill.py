from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "lib"))
sys.path.append(str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parents[1] / "05_analysis"))

from econqt_common import clean_text, load_yaml, normalize_doi  # noqa: E402
from evidence_tier_policy import (  # noqa: E402
    evidence_tier_error_code,
    evidence_tier_error_detail,
)
from scope_review_apply import apply_scope_decisions_to_frame, validate_scope_review_packet  # noqa: E402
from text_enrichment import (  # noqa: E402
    apply_enrichment_to_articles,
    classify_article_scope,
    merge_enrichment_results,
    text_chars,
    title_match_score,
    write_summary,
)


BACKFILL_COLUMNS = {
    "article_id": ["article_id", "id"],
    "doi": ["doi", "DOI"],
    "title": ["title", "article_title"],
    "publication_year": ["publication_year", "year"],
    "abstract": ["abstract", "backfill_abstract", "enriched_abstract"],
    "source": ["source", "abstract_source", "backfill_source"],
    "source_url": ["source_url", "url", "enrichment_url"],
    "source_record_id": ["source_record_id", "record_id"],
    "evidence_tier": ["evidence_tier", "evidence_quality", "recovery_evidence_tier"],
    "notes": ["notes", "backfill_notes"],
}

ERROR_COLUMNS = ["row_number", "article_id", "doi", "title", "error", "detail"]
IMPORTED_COLUMNS = [
    "article_id",
    "journal_short",
    "publication_year",
    "title",
    "doi",
    "article_url",
    "current_abstract_chars",
    "current_text_chars",
    "article_scope",
    "article_scope_reason",
    "enrichment_status",
    "enrichment_source",
    "enriched_abstract",
    "enriched_text_chars",
    "enrichment_url",
    "source_record_id",
    "evidence_tier",
    "oa_pdf_url",
    "attempted_sources",
    "enrichment_detail",
    "enrichment_error",
]
IMPORTED_HISTORY_COLUMNS = IMPORTED_COLUMNS + ["import_source_file"]
ERROR_HISTORY_COLUMNS = ERROR_COLUMNS + ["import_source_file"]


def first_present(row: pd.Series, names: list[str]) -> str:
    for name in names:
        if name in row.index:
            value = clean_text(row.get(name))
            if value:
                return value
    return ""


def normalize_backfill_rows(backfill_df: pd.DataFrame, default_source: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for index, row in backfill_df.fillna("").iterrows():
        normalized = {key: first_present(row, aliases) for key, aliases in BACKFILL_COLUMNS.items()}
        normalized["_provided_source"] = normalized["source"]
        normalized["_provided_source_url"] = normalized["source_url"]
        normalized["_provided_source_record_id"] = normalized["source_record_id"]
        normalized["row_number"] = int(index) + 2
        normalized["doi"] = normalize_doi(normalized["doi"])
        normalized["source"] = normalized["source"] or default_source
        rows.append(normalized)
    return pd.DataFrame(rows)


def row_has_backfill_abstract(row: pd.Series) -> bool:
    return bool(first_present(row, BACKFILL_COLUMNS["abstract"]))


def filter_empty_abstract_rows(backfill_df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    if backfill_df.empty:
        return backfill_df.copy(), 0
    keep_mask = backfill_df.fillna("").apply(row_has_backfill_abstract, axis=1)
    return backfill_df.loc[keep_mask].copy(), int((~keep_mask).sum())


def article_lookup_tables(articles_df: pd.DataFrame) -> tuple[dict[str, pd.Series], dict[str, list[pd.Series]]]:
    articles = articles_df.copy().fillna("")
    by_article_id = {clean_text(row.get("article_id")): row for _, row in articles.iterrows() if clean_text(row.get("article_id"))}
    by_doi: dict[str, list[pd.Series]] = {}
    if "doi" in articles:
        for _, row in articles.iterrows():
            doi = normalize_doi(row.get("doi"))
            if doi:
                by_doi.setdefault(doi, []).append(row)
    return by_article_id, by_doi


def best_title_year_match(backfill_row: pd.Series, articles_df: pd.DataFrame, minimum_title_match: float) -> tuple[pd.Series | None, str]:
    title = clean_text(backfill_row.get("title"))
    if not title:
        return None, "missing_title"
    candidates = articles_df.copy().fillna("")
    year = clean_text(backfill_row.get("publication_year"))
    if year and "publication_year" in candidates:
        candidates = candidates[candidates["publication_year"].astype(str).eq(year)].copy()
    if candidates.empty:
        return None, "no_candidates_for_year"
    scored: list[tuple[float, pd.Series]] = []
    for _, candidate in candidates.iterrows():
        score = title_match_score(title, candidate.get("title", ""))
        if score >= minimum_title_match:
            scored.append((score, candidate))
    if not scored:
        return None, "no_title_match"
    scored.sort(key=lambda pair: pair[0], reverse=True)
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None, f"ambiguous_title_match_score={scored[0][0]:.3f}"
    return scored[0][1], f"title_match_score={scored[0][0]:.3f}"


def match_backfill_row(
    backfill_row: pd.Series,
    articles_df: pd.DataFrame,
    by_article_id: dict[str, pd.Series],
    by_doi: dict[str, list[pd.Series]],
    minimum_title_match: float,
) -> tuple[pd.Series | None, str]:
    article_id = clean_text(backfill_row.get("article_id"))
    if article_id:
        article = by_article_id.get(article_id)
        if article is None:
            return None, "unknown_article_id"
        return article, "article_id"

    doi = normalize_doi(backfill_row.get("doi"))
    if doi:
        matches = by_doi.get(doi, [])
        if len(matches) == 1:
            return matches[0], "doi"
        if len(matches) > 1:
            return None, "ambiguous_doi"
        return None, "unknown_doi"

    return best_title_year_match(backfill_row, articles_df, minimum_title_match)


def error_row(backfill_row: pd.Series, error: str, detail: str = "") -> dict[str, Any]:
    return {
        "row_number": clean_text(backfill_row.get("row_number")),
        "article_id": clean_text(backfill_row.get("article_id")),
        "doi": clean_text(backfill_row.get("doi")),
        "title": clean_text(backfill_row.get("title")),
        "error": error,
        "detail": detail,
    }


def source_metadata_error(backfill_row: pd.Series) -> tuple[str, str] | None:
    source = clean_text(backfill_row.get("_provided_source"))
    source_url = clean_text(backfill_row.get("_provided_source_url"))
    source_record_id = clean_text(backfill_row.get("_provided_source_record_id"))
    evidence_tier = clean_text(backfill_row.get("evidence_tier"))
    if not source:
        return "missing_source", "Filled abstract rows must record the source used for recovery."
    if not source_url and not source_record_id:
        return "missing_source_locator", "Filled abstract rows must include source_url or source_record_id."
    tier_error = evidence_tier_error_code(evidence_tier)
    if tier_error:
        return tier_error, evidence_tier_error_detail(tier_error)
    return None


def abstract_backfill_to_enrichment(
    backfill_df: pd.DataFrame,
    articles_df: pd.DataFrame,
    *,
    minimum_chars: int,
    default_source: str = "curated_backfill",
    minimum_title_match: float = 0.9,
    scope_patterns: dict[str, list[str]] | None = None,
    require_source_metadata: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    normalized = normalize_backfill_rows(backfill_df, default_source)
    articles = articles_df.copy().fillna("")
    by_article_id, by_doi = article_lookup_tables(articles)
    scope_patterns = scope_patterns or {}
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    seen_article_ids: set[str] = set()

    for _, backfill_row in normalized.iterrows():
        abstract = clean_text(backfill_row.get("abstract"))
        if not abstract:
            errors.append(error_row(backfill_row, "missing_abstract"))
            continue
        if require_source_metadata:
            source_error = source_metadata_error(backfill_row)
            if source_error is not None:
                errors.append(error_row(backfill_row, source_error[0], source_error[1]))
                continue

        article, match_detail = match_backfill_row(backfill_row, articles, by_article_id, by_doi, minimum_title_match)
        if article is None:
            errors.append(error_row(backfill_row, "unmatched_article", match_detail))
            continue

        article_id = clean_text(article.get("article_id"))
        if article_id in seen_article_ids:
            errors.append(error_row(backfill_row, "duplicate_backfill_article_id", article_id))
            continue
        seen_article_ids.add(article_id)

        source_title = clean_text(backfill_row.get("title"))
        if source_title:
            score = title_match_score(source_title, article.get("title", ""))
            if score < minimum_title_match:
                errors.append(error_row(backfill_row, "title_mismatch", f"title_match_score={score:.3f};matched_by={match_detail}"))
                seen_article_ids.remove(article_id)
                continue

        article_scope, scope_reason = classify_article_scope(article.to_dict(), scope_patterns)
        enriched_chars = text_chars(article.get("title", ""), abstract)
        status = "enriched" if enriched_chars >= minimum_chars else "partial_short_text"
        source = clean_text(backfill_row.get("source")) or default_source
        evidence_tier = clean_text(backfill_row.get("evidence_tier"))
        detail_parts = [f"matched_by={match_detail}"]
        if evidence_tier:
            detail_parts.append(f"evidence_tier={evidence_tier}")
        notes = clean_text(backfill_row.get("notes"))
        if notes:
            detail_parts.append(f"notes={notes}")
        rows.append(
            {
                "article_id": article_id,
                "journal_short": clean_text(article.get("journal_short")),
                "publication_year": clean_text(article.get("publication_year")),
                "title": clean_text(article.get("title")),
                "doi": normalize_doi(article.get("doi")),
                "article_url": clean_text(article.get("article_url")),
                "current_abstract_chars": len(clean_text(article.get("abstract"))),
                "current_text_chars": text_chars(article.get("title", ""), article.get("abstract", "")),
                "article_scope": article_scope,
                "article_scope_reason": scope_reason,
                "enrichment_status": status,
                "enrichment_source": source,
                "enriched_abstract": abstract,
                "enriched_text_chars": enriched_chars,
                "enrichment_url": clean_text(backfill_row.get("source_url")),
                "source_record_id": clean_text(backfill_row.get("source_record_id")),
                "evidence_tier": evidence_tier,
                "oa_pdf_url": "",
                "attempted_sources": source,
                "enrichment_detail": ";".join(detail_parts),
                "enrichment_error": "",
            }
        )

    return pd.DataFrame(rows, columns=IMPORTED_COLUMNS), pd.DataFrame(errors, columns=ERROR_COLUMNS)


def annotate_import_source(df: pd.DataFrame, columns: list[str], source_file: Path) -> pd.DataFrame:
    out = df.copy().fillna("") if df is not None else pd.DataFrame()
    for column in columns:
        if column != "import_source_file" and column not in out.columns:
            out[column] = ""
    out = out.reindex(columns=[column for column in columns if column != "import_source_file"], fill_value="")
    out["import_source_file"] = str(source_file)
    return out.reindex(columns=columns, fill_value="")


def merge_import_history(previous: pd.DataFrame, current: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    previous_norm = previous.copy().fillna("") if previous is not None and not previous.empty else pd.DataFrame(columns=columns)
    current_norm = current.copy().fillna("") if current is not None and not current.empty else pd.DataFrame(columns=columns)
    previous_norm = previous_norm.reindex(columns=columns, fill_value="")
    current_norm = current_norm.reindex(columns=columns, fill_value="")
    if previous_norm.empty and current_norm.empty:
        return pd.DataFrame(columns=columns)
    return pd.concat([previous_norm, current_norm], ignore_index=True).drop_duplicates().reset_index(drop=True)


def reapply_scope_review_decisions_to_articles(articles: pd.DataFrame, scope_review_packet: Path | None) -> pd.DataFrame:
    if scope_review_packet is None or not scope_review_packet.exists() or articles.empty:
        return articles
    packet = pd.read_csv(scope_review_packet, dtype=str).fillna("")
    if packet.empty or "article_id" not in articles.columns:
        return articles
    target_ids = set(articles["article_id"].astype(str))
    errors = validate_scope_review_packet(packet, target_ids)
    if not errors.empty:
        return articles
    updated, _ = apply_scope_decisions_to_frame(articles, packet, errors)
    return updated


def write_backfill_report(
    path: Path,
    imported: pd.DataFrame,
    errors: pd.DataFrame,
    skipped_empty_abstract_rows: int = 0,
    imported_history: pd.DataFrame | None = None,
    error_history: pd.DataFrame | None = None,
    dry_run: bool = False,
    require_source_metadata: bool = False,
    state_update_skipped: bool = False,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    status = imported["enrichment_status"].value_counts(dropna=False).rename_axis("status").reset_index(name="rows") if not imported.empty else pd.DataFrame()
    source = imported["enrichment_source"].value_counts(dropna=False).rename_axis("source").reset_index(name="rows") if not imported.empty else pd.DataFrame()
    lines = [
        "# Abstract Backfill Dry-Run Report" if dry_run else "# Abstract Backfill Import Report",
        "",
        f"- Mode: {'dry-run' if dry_run else 'apply'}",
        f"- Require source metadata: {str(require_source_metadata).lower()}",
        f"- State update skipped: {str(state_update_skipped).lower()}",
        f"- Imported rows: {len(imported)}",
        f"- Error rows: {len(errors)}",
        f"- Skipped empty abstract rows: {skipped_empty_abstract_rows}",
        f"- Cumulative imported history rows: {len(imported_history) if imported_history is not None else len(imported)}",
        f"- Cumulative error history rows: {len(error_history) if error_history is not None else len(errors)}",
        "",
        "## Imported Status",
        "",
        df_to_markdown(status),
        "",
        "## Imported Source",
        "",
        df_to_markdown(source),
    ]
    if not errors.empty:
        lines.extend(["", "## Errors", "", df_to_markdown(errors, max_rows=40)])
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def df_to_markdown(df: pd.DataFrame, max_rows: int = 30) -> str:
    if df.empty:
        return "_No rows._"
    shown = df.head(max_rows).fillna("")
    headers = list(shown.columns)
    rows = [headers] + shown.astype(str).values.tolist()
    widths = [max(len(row[i]) for row in rows) for i in range(len(headers))]
    header = "| " + " | ".join(headers[i].ljust(widths[i]) for i in range(len(headers))) + " |"
    separator = "| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |"
    body = ["| " + " | ".join(row[i].ljust(widths[i]) for i in range(len(headers))) + " |" for row in rows[1:]]
    suffix = f"\n\n_Only first {max_rows} rows shown._" if len(df) > max_rows else ""
    return "\n".join([header, separator] + body) + suffix


def run_abstract_backfill_import(
    *,
    backfill_input: Path,
    articles_input: Path,
    enrichment_candidates: Path,
    attempts_path: Path,
    config_path: Path,
    output_imported: Path,
    output_errors: Path,
    output_imported_history: Path,
    output_errors_history: Path,
    output_candidates: Path,
    output_articles: Path,
    output_pdf_candidates: Path,
    report_path: Path,
    enrichment_report_path: Path,
    scope_review_packet: Path | None = None,
    default_source: str,
    minimum_title_match: float,
    skip_empty_abstracts: bool,
    dry_run: bool = False,
    require_source_metadata: bool = False,
    fail_on_errors: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    config = load_yaml(config_path)
    minimum_chars = int(config.get("minimum_usable_text_chars", 250))
    backfill = pd.read_csv(backfill_input, dtype=str).fillna("")
    skipped_empty_abstract_rows = 0
    if skip_empty_abstracts:
        backfill, skipped_empty_abstract_rows = filter_empty_abstract_rows(backfill)
    articles = pd.read_csv(articles_input, dtype=str).fillna("")
    previous = pd.read_csv(enrichment_candidates, dtype=str).fillna("") if enrichment_candidates.exists() else pd.DataFrame()
    attempts = pd.read_csv(attempts_path, dtype=str).fillna("") if attempts_path.exists() else pd.DataFrame()
    previous_imported_history = pd.read_csv(output_imported_history, dtype=str).fillna("") if output_imported_history.exists() else pd.DataFrame(columns=IMPORTED_HISTORY_COLUMNS)
    previous_error_history = pd.read_csv(output_errors_history, dtype=str).fillna("") if output_errors_history.exists() else pd.DataFrame(columns=ERROR_HISTORY_COLUMNS)
    imported, errors = abstract_backfill_to_enrichment(
        backfill,
        articles,
        minimum_chars=minimum_chars,
        default_source=default_source,
        minimum_title_match=minimum_title_match,
        scope_patterns=config.get("article_scope_patterns", {}) or {},
        require_source_metadata=require_source_metadata,
    )
    current_imported_history = annotate_import_source(imported, IMPORTED_HISTORY_COLUMNS, backfill_input)
    current_error_history = annotate_import_source(errors, ERROR_HISTORY_COLUMNS, backfill_input)
    imported_history = merge_import_history(previous_imported_history, current_imported_history, IMPORTED_HISTORY_COLUMNS)
    error_history = merge_import_history(previous_error_history, current_error_history, ERROR_HISTORY_COLUMNS)

    if dry_run:
        for path, frame in [(output_imported, imported), (output_errors, errors)]:
            path.parent.mkdir(parents=True, exist_ok=True)
            frame.to_csv(path, index=False)
        write_backfill_report(
            report_path,
            imported,
            errors,
            skipped_empty_abstract_rows=skipped_empty_abstract_rows,
            imported_history=previous_imported_history,
            error_history=previous_error_history,
            dry_run=True,
            require_source_metadata=require_source_metadata,
            state_update_skipped=True,
        )
        print(f"imported_rows={len(imported)}")
        print(f"error_rows={len(errors)}")
        print(f"skipped_empty_abstract_rows={skipped_empty_abstract_rows}")
        print(f"dry_run=true")
        print(f"require_source_metadata={str(require_source_metadata).lower()}")
        print(f"updated_candidates=not_written_dry_run")
        print(f"updated_articles=not_written_dry_run")
        print(f"report={report_path}")
        return imported, errors

    if fail_on_errors and not errors.empty:
        for path, frame in [(output_imported, imported), (output_errors, errors)]:
            path.parent.mkdir(parents=True, exist_ok=True)
            frame.to_csv(path, index=False)
        write_backfill_report(
            report_path,
            imported,
            errors,
            skipped_empty_abstract_rows=skipped_empty_abstract_rows,
            imported_history=previous_imported_history,
            error_history=previous_error_history,
            dry_run=False,
            require_source_metadata=require_source_metadata,
            state_update_skipped=True,
        )
        print(f"imported_rows={len(imported)}")
        print(f"error_rows={len(errors)}")
        print(f"skipped_empty_abstract_rows={skipped_empty_abstract_rows}")
        print(f"dry_run=false")
        print(f"require_source_metadata={str(require_source_metadata).lower()}")
        print(f"state_update=skipped_errors")
        print(f"updated_candidates=not_written_errors")
        print(f"updated_articles=not_written_errors")
        print(f"report={report_path}")
        return imported, errors

    merged = merge_enrichment_results(previous, imported)
    enriched_articles = apply_enrichment_to_articles(
        articles,
        merged,
        minimum_chars=minimum_chars,
        scope_patterns=config.get("article_scope_patterns", {}) or {},
    )
    enriched_articles = reapply_scope_review_decisions_to_articles(enriched_articles, scope_review_packet)
    pdf_candidates = merged[merged["oa_pdf_url"].astype(str).str.strip() != ""].copy() if not merged.empty else pd.DataFrame()

    for path, frame in [
        (output_imported, imported),
        (output_errors, errors),
        (output_imported_history, imported_history),
        (output_errors_history, error_history),
        (output_candidates, merged),
        (output_articles, enriched_articles),
        (output_pdf_candidates, pdf_candidates),
    ]:
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)

    write_backfill_report(
        report_path,
        imported,
        errors,
        skipped_empty_abstract_rows=skipped_empty_abstract_rows,
        imported_history=imported_history,
        error_history=error_history,
        dry_run=False,
        require_source_metadata=require_source_metadata,
        state_update_skipped=False,
    )
    write_summary(enrichment_report_path, merged, attempts, pdf_candidates)
    print(f"imported_rows={len(imported)}")
    print(f"error_rows={len(errors)}")
    print(f"skipped_empty_abstract_rows={skipped_empty_abstract_rows}")
    print(f"imported_history_rows={len(imported_history)}")
    print(f"error_history_rows={len(error_history)}")
    print(f"dry_run=false")
    print(f"require_source_metadata={str(require_source_metadata).lower()}")
    print(f"state_update=written")
    print(f"updated_candidates={output_candidates}")
    print(f"updated_articles={output_articles}")
    return imported, errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="CSV with article_id or DOI/title plus abstract text.")
    parser.add_argument("--articles-input", default="data/final/articles_pilot.csv")
    parser.add_argument("--enrichment-candidates", default="data/intermediate/text_enrichment_candidates.csv")
    parser.add_argument("--attempts", default="data/intermediate/text_enrichment_attempts.csv")
    parser.add_argument("--config", default="config/text_enrichment.yml")
    parser.add_argument("--output-imported", default="data/intermediate/abstract_backfill_imported.csv")
    parser.add_argument("--output-errors", default="data/intermediate/abstract_backfill_import_errors.csv")
    parser.add_argument("--output-imported-history", default="data/intermediate/abstract_backfill_import_history.csv")
    parser.add_argument("--output-errors-history", default="data/intermediate/abstract_backfill_import_error_history.csv")
    parser.add_argument("--output-candidates", default="data/intermediate/text_enrichment_candidates.csv")
    parser.add_argument("--output-articles", default="data/final/articles_enriched_pilot.csv")
    parser.add_argument("--output-pdf-candidates", default="data/intermediate/text_enrichment_pdf_candidates.csv")
    parser.add_argument("--scope-review-packet", default="data/intermediate/scope_review/scope_review_packet.csv")
    parser.add_argument("--report", default="docs/abstract_backfill_import_report.md")
    parser.add_argument("--enrichment-report", default="docs/text_enrichment_report.md")
    parser.add_argument("--default-source", default="curated_backfill")
    parser.add_argument("--minimum-title-match", type=float, default=0.9)
    parser.add_argument("--skip-empty-abstracts", action="store_true", help="Skip rows with no abstract text before validation. Useful for partially filled recovery batches.")
    parser.add_argument("--dry-run", action="store_true", help="Validate a backfill CSV and write dry-run imported/error tables without updating enrichment histories or final article files.")
    parser.add_argument("--require-source-metadata", action="store_true", help="Require filled abstract rows to include source plus source_url or source_record_id.")
    parser.add_argument("--fail-on-errors", action="store_true", help="Do not update enrichment histories or final article files when validation errors are present.")
    args = parser.parse_args()
    if args.dry_run:
        if args.output_imported == parser.get_default("output_imported"):
            args.output_imported = "outputs/tables/enriched/abstract_backfill_dry_run_imported.csv"
        if args.output_errors == parser.get_default("output_errors"):
            args.output_errors = "outputs/tables/enriched/abstract_backfill_dry_run_errors.csv"
        if args.report == parser.get_default("report"):
            args.report = "docs/abstract_backfill_dry_run_report.md"
    _, errors = run_abstract_backfill_import(
        backfill_input=Path(args.input),
        articles_input=Path(args.articles_input),
        enrichment_candidates=Path(args.enrichment_candidates),
        attempts_path=Path(args.attempts),
        config_path=Path(args.config),
        output_imported=Path(args.output_imported),
        output_errors=Path(args.output_errors),
        output_imported_history=Path(args.output_imported_history),
        output_errors_history=Path(args.output_errors_history),
        output_candidates=Path(args.output_candidates),
        output_articles=Path(args.output_articles),
        output_pdf_candidates=Path(args.output_pdf_candidates),
        scope_review_packet=Path(args.scope_review_packet) if args.scope_review_packet else None,
        report_path=Path(args.report),
        enrichment_report_path=Path(args.enrichment_report),
        default_source=args.default_source,
        minimum_title_match=args.minimum_title_match,
        skip_empty_abstracts=args.skip_empty_abstracts,
        dry_run=args.dry_run,
        require_source_metadata=args.require_source_metadata,
        fail_on_errors=args.fail_on_errors,
    )
    if (args.dry_run or args.fail_on_errors) and not errors.empty:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
