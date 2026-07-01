from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "lib"))
sys.path.append(str(Path(__file__).resolve().parent))

from econqt_common import clean_text, load_yaml, normalize_doi  # noqa: E402
from insufficient_text_expansion import doi_prefix_family  # noqa: E402
from text_enrichment import NONRESEARCH_SCOPES, classify_article_scope  # noqa: E402


WORKPLAN_COLUMNS = [
    "recovery_batch",
    "batch_row",
    "recovery_rank",
    "article_id",
    "journal_short",
    "publication_year",
    "title",
    "doi",
    "doi_prefix",
    "recovery_action",
    "article_scope",
    "article_scope_reason",
    "scope_review_decision",
    "row_status",
    "recommended_workflow",
    "source_artifact",
    "route_status",
    "route_note",
    "pdf_text_status",
    "pdf_detail",
    "review_note",
    "abstract",
    "source",
    "source_url",
    "source_record_id",
]


def nonempty(value: Any) -> bool:
    return clean_text(value) != ""


def suspect_pdf_url(url: Any) -> bool:
    lower = clean_text(url).lower()
    suspect_markers = [
        "code of conduct",
        "code-of-conduct",
        "professional conduct",
        "professional-conduct",
        "referee",
        "election of fellows",
    ]
    return any(marker in lower for marker in suspect_markers)


def route_lookup(route_matrix: pd.DataFrame) -> dict[str, dict[str, str]]:
    if route_matrix.empty or "route_unit" not in route_matrix.columns:
        return {}
    work = route_matrix.copy().fillna("")
    out: dict[str, dict[str, str]] = {}
    for _, row in work.iterrows():
        unit = clean_text(row.get("route_unit", ""))
        if unit:
            out[unit] = {column: clean_text(row.get(column, "")) for column in work.columns}
    return out


def pdf_lookup(pdf_text: pd.DataFrame) -> dict[str, dict[str, str]]:
    if pdf_text.empty or "article_id" not in pdf_text.columns:
        return {}
    work = pdf_text.copy().fillna("")
    out: dict[str, dict[str, str]] = {}
    for _, row in work.iterrows():
        article_id = clean_text(row.get("article_id", ""))
        if article_id:
            out[article_id] = {column: clean_text(row.get(column, "")) for column in work.columns}
    return out


def scope_decision_lookup(scope_packet: pd.DataFrame) -> dict[str, dict[str, str]]:
    if scope_packet.empty or "article_id" not in scope_packet.columns:
        return {}
    work = scope_packet.copy().fillna("")
    out: dict[str, dict[str, str]] = {}
    for _, row in work.iterrows():
        article_id = clean_text(row.get("article_id", ""))
        decision = clean_text(row.get("human_scope_decision", ""))
        if article_id and decision:
            out[article_id] = {column: clean_text(row.get(column, "")) for column in work.columns}
    return out


def route_for_row(row: pd.Series | dict[str, Any], routes: dict[str, dict[str, str]]) -> dict[str, str]:
    prefix = doi_prefix_family(row.get("doi", "")) if hasattr(row, "get") else ""
    if prefix and prefix in routes:
        return routes[prefix]
    action = clean_text(row.get("recovery_action", "")) if hasattr(row, "get") else ""
    if action == "extend_existing_short_abstract":
        return routes.get("partial_short_text_extension", {})
    if action == "review_openalex_or_title_match":
        return routes.get("openalex_or_title_search", {})
    if action == "review_oa_pdf_or_first_pages":
        return routes.get("oa_pdf_review", {})
    return {}


def workflow_for_row(
    row: pd.Series | dict[str, Any],
    *,
    route: dict[str, str],
    pdf: dict[str, str],
    article_scope: str = "",
    article_scope_reason: str = "",
    scope_decision: dict[str, str] | None = None,
) -> tuple[str, str, str, str]:
    decision = scope_decision or {}
    human_scope_decision = clean_text(decision.get("human_scope_decision", ""))
    if human_scope_decision == "exclude_nonresearch":
        return (
            "scope_review_excluded_nonresearch",
            "Do not recover abstract text for this row unless the scope decision is changed.",
            "docs/scope_review_packet.md",
            f"Scope review excluded row: {clean_text(decision.get('scope_review_notes', ''))}",
        )
    if human_scope_decision == "unsure":
        return (
            "scope_review_unsure_before_recovery",
            "Resolve this scope decision before spending time on abstract recovery.",
            "docs/scope_review_packet.md",
            f"Scope review marked unsure: {clean_text(decision.get('scope_review_notes', ''))}",
        )

    if clean_text(article_scope) in NONRESEARCH_SCOPES:
        return (
            "scope_review_before_recovery",
            "Confirm this row belongs in the analysis scope before spending time on abstract recovery.",
            "config/text_enrichment.yml",
            f"Scope triage suggests {clean_text(article_scope)}: {clean_text(article_scope_reason)}",
        )

    if nonempty(row.get("abstract", "")):
        return (
            "completed_backfill",
            "Already has a backfilled abstract; preserve this row and import with --skip-empty-abstracts.",
            "data/intermediate/insufficient_text_recovery_batches/",
            "Backfill fields are already filled.",
        )

    action = clean_text(row.get("recovery_action", ""))
    route_status = clean_text(route.get("current_route_status", ""))
    pdf_status = clean_text(pdf.get("pdf_text_status", ""))
    pdf_detail = clean_text(pdf.get("pdf_detail", ""))

    if action == "review_oa_pdf_or_first_pages":
        if pdf_status == "extracted":
            return (
                "autofill_pdf_text",
                "Autofill the extracted first-pages text into the recovery batch, then import completed rows.",
                clean_text(pdf.get("oa_pdf_url", "")) or "data/intermediate/insufficient_text_recovery_batch_R001_pdf_text.csv",
                "PDF text has already been extracted for this row.",
            )
        if suspect_pdf_url(row.get("oa_pdf_url", "")):
            return (
                "suspect_pdf_url_use_manual_metadata",
                "Do not use this PDF URL as article text; recover only from explicit article metadata or a verified article PDF.",
                clean_text(row.get("article_url", "")) or "data/intermediate/insufficient_text_recovery_batches/",
                "The OA PDF URL appears to point to a non-article document.",
            )
        if pdf_status in {"download_error", "extract_error", "too_short", "skipped_missing_url"}:
            return (
                "pdf_route_blocked_use_manual_metadata",
                "Do not retry this PDF route unchanged; use explicit abstract metadata from indexes, publisher pages, or source-confirmed manual recovery.",
                "outputs/tables/enriched/remaining_oa_pdf_download_blockers.csv",
                f"Prior PDF status is {pdf_status}: {pdf_detail}",
            )
        return (
            "try_public_pdf_once",
            "Try PDF/OCR only if the PDF is clearly public and not already blocked; otherwise use manual metadata recovery.",
            clean_text(row.get("oa_pdf_url", "")),
            "No prior PDF status was found for this row.",
        )

    if action == "extend_existing_short_abstract":
        return (
            "manual_extend_partial_text",
            "Extend the existing short text from explicit source metadata; keep the source URL and record ID.",
            clean_text(row.get("article_url", "")) or "data/intermediate/insufficient_text_recovery_batches/",
            "This row already has partial text or metadata signal; source-confirmed extension is safer than broad scraping.",
        )

    if action == "recover_abstract_from_doi_or_publisher":
        if route_status in {"unsupported_existing_route", "do_not_rerun_landing_pages", "manual_or_new_template_only"}:
            return (
                "manual_index_or_new_template",
                "Do not rerun existing source logic; recover from explicit index metadata or add a tested lawful source template first.",
                clean_text(route.get("next_artifact", "")) or "data/intermediate/insufficient_text_recovery_batches/",
                clean_text(route.get("source_route_note", "")),
            )
        if route_status in {"ready_bounded_source_pass", "source_specific_probe_needed", "candidate_route_requires_parser_or_url_update"}:
            return (
                "source_specific_followup",
                clean_text(route.get("recommended_route_action", "")),
                clean_text(route.get("next_artifact", "")),
                clean_text(route.get("source_route_note", "")),
            )
        if route_status == "scienceon_bounded_recovery":
            return (
                "scienceon_bounded_recovery",
                clean_text(route.get("recommended_route_action", "")),
                clean_text(route.get("next_artifact", "")) or "run_scienceon_recovery_scan.py",
                clean_text(route.get("source_route_note", "")),
            )
        return (
            "manual_doi_metadata_review",
            "Use DOI, OpenAlex, Crossref, or title-search links to find an explicit abstract; import only source-confirmed abstracts.",
            clean_text(row.get("doi_url", "")) or clean_text(row.get("article_url", "")),
            "No supported automated route is recommended for this row.",
        )

    if action == "review_openalex_or_title_match":
        return (
            "manual_index_title_match",
            "Use title-search links and import only high-confidence abstract matches with source URL recorded.",
            clean_text(row.get("openalex_title_search_url", "")),
            "Title-only category suggestions must stay triage notes until an explicit abstract is recovered.",
        )

    return (
        "manual_review",
        "Inspect the row manually before choosing a recovery source.",
        "data/intermediate/insufficient_text_recovery_batches/",
        "No specific recovery rule matched this row.",
    )


def recovery_batch_workplan(
    batch: pd.DataFrame,
    pdf_text: pd.DataFrame,
    route_matrix: pd.DataFrame,
    *,
    scope_patterns: dict[str, list[str]] | None = None,
    scope_packet: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if batch.empty:
        return pd.DataFrame(columns=WORKPLAN_COLUMNS)
    routes = route_lookup(route_matrix)
    pdfs = pdf_lookup(pdf_text)
    scope_decisions = scope_decision_lookup(scope_packet if scope_packet is not None else pd.DataFrame())
    patterns = scope_patterns or {}
    rows: list[dict[str, Any]] = []
    work = batch.copy().fillna("")
    for _, row in work.iterrows():
        article_id = clean_text(row.get("article_id", ""))
        prefix = doi_prefix_family(row.get("doi", ""))
        route = route_for_row(row, routes)
        pdf = pdfs.get(article_id, {})
        article_scope, article_scope_reason = classify_article_scope(row.to_dict(), patterns)
        scope_decision = scope_decisions.get(article_id, {})
        human_scope_decision = clean_text(scope_decision.get("human_scope_decision", ""))
        if human_scope_decision == "keep_research":
            article_scope = "research_article"
            article_scope_reason = "scope_review_decision=keep_research"
        elif human_scope_decision == "exclude_nonresearch":
            article_scope = clean_text(scope_decision.get("proposed_article_scope", "")) or article_scope
            article_scope_reason = f"scope_review_decision=exclude_nonresearch;{clean_text(scope_decision.get('proposed_scope_reason', ''))}".rstrip(";")
        status, workflow, artifact, note = workflow_for_row(
            row,
            route=route,
            pdf=pdf,
            article_scope=article_scope,
            article_scope_reason=article_scope_reason,
            scope_decision=scope_decision,
        )
        rows.append(
            {
                "recovery_batch": clean_text(row.get("recovery_batch", "")),
                "batch_row": clean_text(row.get("batch_row", "")),
                "recovery_rank": clean_text(row.get("recovery_rank", "")),
                "article_id": article_id,
                "journal_short": clean_text(row.get("journal_short", "")),
                "publication_year": clean_text(row.get("publication_year", "")),
                "title": clean_text(row.get("title", "")),
                "doi": normalize_doi(row.get("doi", "")),
                "doi_prefix": prefix,
                "recovery_action": clean_text(row.get("recovery_action", "")),
                "article_scope": article_scope,
                "article_scope_reason": article_scope_reason,
                "scope_review_decision": human_scope_decision,
                "row_status": status,
                "recommended_workflow": workflow,
                "source_artifact": artifact,
                "route_status": clean_text(route.get("current_route_status", "")),
                "route_note": clean_text(route.get("source_route_note", "")),
                "pdf_text_status": clean_text(pdf.get("pdf_text_status", "")),
                "pdf_detail": clean_text(pdf.get("pdf_detail", "")),
                "review_note": note,
                "abstract": clean_text(row.get("abstract", "")),
                "source": clean_text(row.get("source", "")),
                "source_url": clean_text(row.get("source_url", "")),
                "source_record_id": clean_text(row.get("source_record_id", "")),
            }
        )
    out = pd.DataFrame(rows, columns=WORKPLAN_COLUMNS)
    out["_rank"] = pd.to_numeric(out["recovery_rank"], errors="coerce").fillna(999999).astype(int)
    return out.sort_values(["_rank", "batch_row", "article_id"]).drop(columns=["_rank"]).reset_index(drop=True)


def markdown_cell(value: Any) -> str:
    return str(value).replace("\r", " ").replace("\n", " ").replace("|", "\\|")


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


def write_workplan_report(path: Path, workplan: pd.DataFrame, *, batch_path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if workplan.empty:
        status_counts = pd.DataFrame(columns=["row_status", "rows"])
        action_counts = pd.DataFrame(columns=["recovery_action", "row_status", "rows"])
        preview = workplan
        batch_id = ""
    else:
        batch_id = clean_text(workplan.iloc[0].get("recovery_batch", ""))
        status_counts = workplan.groupby("row_status", dropna=False).size().reset_index(name="rows").sort_values(["rows", "row_status"], ascending=[False, True])
        action_counts = (
            workplan.groupby(["recovery_action", "row_status"], dropna=False)
            .size()
            .reset_index(name="rows")
            .sort_values(["recovery_action", "rows", "row_status"], ascending=[True, False, True])
        )
        preview = workplan[
            [
                "batch_row",
                "article_id",
                "journal_short",
                "publication_year",
                "title",
                "recovery_action",
                "article_scope",
                "scope_review_decision",
                "row_status",
                "recommended_workflow",
                "source_artifact",
            ]
        ]
    lines = [
        f"# Recovery Batch {batch_id or ''} Workplan".rstrip(),
        "",
        f"- Batch input: `{batch_path}`",
        f"- Rows: {len(workplan)}",
        "",
        "Use this workplan to avoid retrying already-blocked source routes. Fill only explicit, source-confirmed abstracts in the recovery batch CSV or HTML form.",
        "",
        "## Row Status Counts",
        "",
        df_to_markdown(status_counts, max_rows=30),
        "",
        "## Action And Status Counts",
        "",
        df_to_markdown(action_counts, max_rows=40),
        "",
        "## Row Workplan",
        "",
        df_to_markdown(preview, max_rows=60),
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("") if path.exists() else pd.DataFrame()


def run_recovery_batch_workplan(
    *,
    batch_path: Path,
    pdf_text_path: Path,
    route_matrix_path: Path,
    scope_packet_path: Path | None,
    config_path: Path | None,
    output_path: Path,
    report_path: Path,
) -> pd.DataFrame:
    batch = read_csv_if_exists(batch_path)
    pdf_text = read_csv_if_exists(pdf_text_path)
    route_matrix = read_csv_if_exists(route_matrix_path)
    scope_packet = read_csv_if_exists(scope_packet_path) if scope_packet_path is not None else pd.DataFrame()
    config = load_yaml(config_path) if config_path is not None and config_path.exists() else {}
    workplan = recovery_batch_workplan(batch, pdf_text, route_matrix, scope_patterns=config.get("article_scope_patterns", {}) or {}, scope_packet=scope_packet)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    workplan.to_csv(output_path, index=False)
    write_workplan_report(report_path, workplan, batch_path=batch_path)
    print(f"workplan_rows={len(workplan)}")
    if not workplan.empty:
        print(workplan["row_status"].value_counts(dropna=False).to_string())
    print(f"output={output_path}")
    print(f"report={report_path}")
    return workplan


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", default="data/intermediate/insufficient_text_recovery_batches/insufficient_text_recovery_batch_R001.csv")
    parser.add_argument("--pdf-text", default="data/intermediate/insufficient_text_recovery_batch_R001_pdf_text.csv")
    parser.add_argument("--route-matrix", default="outputs/tables/enriched/insufficient_text_source_route_matrix.csv")
    parser.add_argument("--scope-packet", default="data/intermediate/scope_review/scope_review_packet.csv")
    parser.add_argument("--config", default="config/text_enrichment.yml")
    parser.add_argument("--output", default="outputs/tables/enriched/recovery_batch_R001_workplan.csv")
    parser.add_argument("--report", default="docs/recovery_batch_R001_workplan.md")
    args = parser.parse_args()
    run_recovery_batch_workplan(
        batch_path=Path(args.batch),
        pdf_text_path=Path(args.pdf_text),
        route_matrix_path=Path(args.route_matrix),
        scope_packet_path=Path(args.scope_packet) if args.scope_packet else None,
        config_path=Path(args.config),
        output_path=Path(args.output),
        report_path=Path(args.report),
    )


if __name__ == "__main__":
    main()
