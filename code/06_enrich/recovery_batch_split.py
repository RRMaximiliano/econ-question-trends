from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "lib"))
sys.path.append(str(Path(__file__).resolve().parent))

from econqt_common import clean_text  # noqa: E402
from recovery_batches import RECOVERY_PACKET_COLUMNS, recovery_form_html  # noqa: E402
from recovery_batch_workplan import WORKPLAN_COLUMNS  # noqa: E402


READY_PARTIAL_TEXT_EXTENSION = {"manual_extend_partial_text"}
READY_MANUAL_METADATA = {
    "manual_index_or_new_template",
    "manual_doi_metadata_review",
    "manual_index_title_match",
    "pdf_route_blocked_use_manual_metadata",
    "suspect_pdf_url_use_manual_metadata",
    "source_specific_followup",
    "scienceon_bounded_recovery",
    "try_public_pdf_once",
    "manual_review",
}
WAITING_SCOPE_REVIEW = {
    "scope_review_before_recovery",
    "scope_review_unsure_before_recovery",
}
EXCLUDED_NONRESEARCH = {"scope_review_excluded_nonresearch"}
READY_AUTOFILL_OR_COMPLETED = {"autofill_pdf_text", "completed_backfill"}

SPLIT_GROUP_ORDER = [
    "ready_partial_text_extension",
    "ready_manual_metadata",
    "ready_autofill_or_completed",
    "waiting_scope_review",
    "excluded_nonresearch",
    "other_manual_review",
]

SPLIT_REPORT_COLUMNS = [
    "recovery_batch",
    "split_group",
    "rows",
    "completed_backfill_abstracts",
    "source_ready_backfill_abstracts",
    "source_incomplete_backfill_abstracts",
    "remaining_backfill_abstracts",
    "output_csv",
    "output_html",
    "recommended_next_step",
]

WORKPLAN_CONTEXT_COLUMNS = [
    "split_group",
    "row_status",
    "recommended_workflow",
    "source_artifact",
    "route_status",
    "route_note",
    "pdf_text_status",
    "pdf_detail",
    "review_note",
    "scope_review_decision",
    "article_scope",
    "article_scope_reason",
    "doi_prefix",
]

ARTICLE_CONTEXT_COLUMNS = [
    "current_abstract",
    "current_abstract_chars",
    "current_abstract_source",
    "current_text_chars",
    "text_enrichment_status",
    "text_enrichment_source",
    "text_enrichment_url",
    "article_type",
    "primary_source",
    "classification_confidence",
    "classification_reason",
    "has_usable_classification_text",
]

ATTEMPT_CONTEXT_COLUMNS = [
    "prior_attempt_summary",
    "prior_attempt_detail_summary",
]


def split_group_for_status(row_status: Any) -> str:
    status = clean_text(row_status)
    if status in READY_PARTIAL_TEXT_EXTENSION:
        return "ready_partial_text_extension"
    if status in READY_MANUAL_METADATA:
        return "ready_manual_metadata"
    if status in READY_AUTOFILL_OR_COMPLETED:
        return "ready_autofill_or_completed"
    if status in WAITING_SCOPE_REVIEW:
        return "waiting_scope_review"
    if status in EXCLUDED_NONRESEARCH:
        return "excluded_nonresearch"
    return "other_manual_review"


def recommended_next_step(split_group: str) -> str:
    if split_group == "ready_partial_text_extension":
        return "Extend partial text from explicit source metadata, record source details and evidence_tier, then import completed rows with --skip-empty-abstracts."
    if split_group == "ready_manual_metadata":
        return "Recover only source-confirmed abstracts from DOI, publisher, index, or title-match metadata; record evidence_tier and do not retry blocked PDF routes unchanged."
    if split_group == "ready_autofill_or_completed":
        return "Preserve already-filled rows or autofill accepted PDF text before importing completed rows."
    if split_group == "waiting_scope_review":
        return "Do not spend abstract-recovery time until the scope-review packet has a keep/exclude/unsure decision."
    if split_group == "excluded_nonresearch":
        return "Do not recover abstract text unless the scope decision changes; this row is outside the research denominator."
    return "Inspect the workplan notes before choosing a recovery route."


def article_context(articles: pd.DataFrame) -> pd.DataFrame:
    if articles.empty or "article_id" not in articles.columns:
        return pd.DataFrame(columns=["article_id"] + ARTICLE_CONTEXT_COLUMNS)
    rows: list[dict[str, Any]] = []
    for _, row in articles.copy().fillna("").iterrows():
        article_id = clean_text(row.get("article_id"))
        if not article_id:
            continue
        abstract = clean_text(row.get("abstract"))
        rows.append(
            {
                "article_id": article_id,
                "current_abstract": abstract,
                "current_abstract_chars": str(len(abstract)),
                "current_abstract_source": clean_text(row.get("abstract_source")),
                "current_text_chars": clean_text(row.get("classification_text_chars")) or clean_text(row.get("text_enrichment_chars")),
                "text_enrichment_status": clean_text(row.get("text_enrichment_status")),
                "text_enrichment_source": clean_text(row.get("text_enrichment_source")),
                "text_enrichment_url": clean_text(row.get("text_enrichment_url")),
                "article_type": clean_text(row.get("article_type")),
                "primary_source": clean_text(row.get("primary_source")),
                "classification_confidence": clean_text(row.get("classification_confidence")),
                "classification_reason": clean_text(row.get("classification_reason")),
                "has_usable_classification_text": clean_text(row.get("has_usable_classification_text")),
            }
        )
    out = pd.DataFrame(rows, columns=["article_id"] + ARTICLE_CONTEXT_COLUMNS)
    return out.drop_duplicates("article_id", keep="first").reset_index(drop=True)


def attempt_context(attempts: pd.DataFrame) -> pd.DataFrame:
    if attempts.empty or "article_id" not in attempts.columns:
        return pd.DataFrame(columns=["article_id"] + ATTEMPT_CONTEXT_COLUMNS)
    rows: list[dict[str, Any]] = []
    work = attempts.copy().fillna("")
    for article_id, group in work.groupby("article_id", sort=True, dropna=False):
        clean_id = clean_text(article_id)
        if not clean_id:
            continue
        attempt_parts: list[str] = []
        detail_parts: list[str] = []
        seen_attempts: set[str] = set()
        seen_details: set[str] = set()
        for _, row in group.iterrows():
            source = clean_text(row.get("attempt_source"))
            status = clean_text(row.get("attempt_status"))
            if source or status:
                attempt = ":".join(part for part in [source, status] if part)
                if attempt not in seen_attempts:
                    attempt_parts.append(attempt)
                    seen_attempts.add(attempt)
            detail = clean_text(row.get("attempt_detail")) or clean_text(row.get("attempt_error"))
            if source and detail:
                detail_value = f"{source}={detail}"
                if detail_value not in seen_details:
                    detail_parts.append(detail_value)
                    seen_details.add(detail_value)
        rows.append(
            {
                "article_id": clean_id,
                "prior_attempt_summary": "; ".join(attempt_parts),
                "prior_attempt_detail_summary": "; ".join(detail_parts),
            }
        )
    return pd.DataFrame(rows, columns=["article_id"] + ATTEMPT_CONTEXT_COLUMNS)


def merge_batch_with_workplan(
    batch: pd.DataFrame,
    workplan: pd.DataFrame,
    articles: pd.DataFrame | None = None,
    attempts: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if batch.empty:
        return pd.DataFrame(columns=RECOVERY_PACKET_COLUMNS + WORKPLAN_CONTEXT_COLUMNS)
    if "article_id" not in batch.columns:
        raise ValueError("batch input must include article_id")
    if "article_id" not in workplan.columns:
        raise ValueError("workplan input must include article_id")

    batch_work = batch.copy().fillna("")
    workplan_work = workplan.copy().fillna("")
    for column in RECOVERY_PACKET_COLUMNS:
        if column not in batch_work.columns:
            batch_work[column] = ""
    keep_workplan_columns = ["article_id"] + [column for column in WORKPLAN_COLUMNS if column in workplan_work.columns and column != "article_id"]
    merged = batch_work[RECOVERY_PACKET_COLUMNS].merge(
        workplan_work[keep_workplan_columns],
        on="article_id",
        how="left",
        suffixes=("", "_workplan"),
    )
    if merged["article_id"].duplicated().any():
        duplicated = sorted(set(merged.loc[merged["article_id"].duplicated(), "article_id"].astype(str).tolist()))
        raise ValueError(f"duplicate article_id rows after merge: {', '.join(duplicated[:5])}")

    for column in WORKPLAN_CONTEXT_COLUMNS:
        source_column = f"{column}_workplan" if f"{column}_workplan" in merged.columns else column
        if source_column not in merged.columns:
            merged[column] = ""
        elif source_column != column:
            merged[column] = merged[source_column]
    if "row_status" not in merged.columns:
        merged["row_status"] = ""
    merged["split_group"] = merged["row_status"].map(split_group_for_status)

    for column in WORKPLAN_CONTEXT_COLUMNS:
        if column not in merged.columns:
            merged[column] = ""
    context_frames = [
        article_context(articles if articles is not None else pd.DataFrame()),
        attempt_context(attempts if attempts is not None else pd.DataFrame()),
    ]
    for context in context_frames:
        if context.empty:
            continue
        merged = merged.merge(context, on="article_id", how="left")
    for column in ARTICLE_CONTEXT_COLUMNS + ATTEMPT_CONTEXT_COLUMNS:
        if column not in merged.columns:
            merged[column] = ""
        merged[column] = merged[column].fillna("").astype(str)
    return merged


def split_columns(frame: pd.DataFrame) -> list[str]:
    columns = [column for column in RECOVERY_PACKET_COLUMNS if column in frame.columns]
    columns.extend(column for column in WORKPLAN_CONTEXT_COLUMNS if column in frame.columns and column not in columns)
    columns.extend(column for column in ARTICLE_CONTEXT_COLUMNS if column in frame.columns and column not in columns)
    columns.extend(column for column in ATTEMPT_CONTEXT_COLUMNS if column in frame.columns and column not in columns)
    return columns


def split_recovery_batch(
    batch: pd.DataFrame,
    workplan: pd.DataFrame,
    articles: pd.DataFrame | None = None,
    attempts: pd.DataFrame | None = None,
) -> dict[str, pd.DataFrame]:
    merged = merge_batch_with_workplan(batch, workplan, articles, attempts)
    if merged.empty:
        return {group: merged.copy() for group in SPLIT_GROUP_ORDER}
    columns = split_columns(merged)
    out: dict[str, pd.DataFrame] = {}
    for group in SPLIT_GROUP_ORDER:
        group_frame = merged[merged["split_group"].eq(group)].copy()
        out[group] = group_frame[columns].reset_index(drop=True)
    return out


def split_summary_rows(
    split_frames: dict[str, pd.DataFrame],
    *,
    batch_id: str,
    output_dir: Path,
    html_dir: Path | None,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for group in SPLIT_GROUP_ORDER:
        frame = split_frames.get(group, pd.DataFrame())
        output_csv = output_dir / f"insufficient_text_recovery_batch_{batch_id}_{group}.csv"
        output_html = html_dir / f"insufficient_text_recovery_batch_{batch_id}_{group}.html" if html_dir is not None else None
        abstracts = frame.get("abstract", pd.Series(dtype=str)).astype(str).str.strip()
        sources = frame.get("source", pd.Series("", index=frame.index, dtype=str)).astype(str).str.strip()
        source_urls = frame.get("source_url", pd.Series("", index=frame.index, dtype=str)).astype(str).str.strip()
        source_record_ids = frame.get("source_record_id", pd.Series("", index=frame.index, dtype=str)).astype(str).str.strip()
        completed = abstracts.ne("") if len(frame) else pd.Series(dtype=bool)
        source_ready = completed & sources.ne("") & (source_urls.ne("") | source_record_ids.ne(""))
        source_incomplete = completed & ~source_ready
        rows.append(
            {
                "recovery_batch": batch_id,
                "split_group": group,
                "rows": len(frame),
                "completed_backfill_abstracts": int(completed.sum()) if len(frame) else 0,
                "source_ready_backfill_abstracts": int(source_ready.sum()) if len(frame) else 0,
                "source_incomplete_backfill_abstracts": int(source_incomplete.sum()) if len(frame) else 0,
                "remaining_backfill_abstracts": int(abstracts.eq("").sum()) if len(frame) else 0,
                "output_csv": str(output_csv) if len(frame) else "",
                "output_html": str(output_html) if output_html is not None and len(frame) else "",
                "recommended_next_step": recommended_next_step(group),
            }
        )
    return pd.DataFrame(rows, columns=SPLIT_REPORT_COLUMNS)


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


def write_split_report(path: Path, summary: pd.DataFrame, split_frames: dict[str, pd.DataFrame], *, batch_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    status_rows: list[dict[str, Any]] = []
    for group, frame in split_frames.items():
        if frame.empty:
            continue
        for status, count in frame["row_status"].astype(str).value_counts().sort_index().items():
            status_rows.append({"split_group": group, "row_status": status, "rows": int(count)})
    status_counts = pd.DataFrame(status_rows, columns=["split_group", "row_status", "rows"])

    preview_columns = [
        "split_group",
        "batch_row",
        "article_id",
        "journal_short",
        "publication_year",
        "title",
        "row_status",
        "recommended_workflow",
        "source_artifact",
        "current_text_chars",
        "current_abstract_source",
        "prior_attempt_summary",
    ]
    preview_frames = [frame[[column for column in preview_columns if column in frame.columns]].copy() for frame in split_frames.values() if not frame.empty]
    preview = pd.concat(preview_frames, ignore_index=True) if preview_frames else pd.DataFrame(columns=preview_columns)

    lines = [
        f"# Recovery Batch {batch_id} Split Packets",
        "",
        "These split packets reorganize the editable recovery batch by workplan status. They do not change final classified data or scope metadata.",
        "",
        "Work `ready_partial_text_extension` and `ready_manual_metadata` first. Leave `waiting_scope_review` untouched until the scope-review packet has decisions. Leave `excluded_nonresearch` untouched unless a scope decision changes.",
        "",
        "Completed rows must include `abstract`, `source`, either `source_url` or `source_record_id`, and an importable `evidence_tier`. Importable tiers are `tier_a_formal_abstract`, `tier_b_source_description`, and `tier_c_first_page_abstract_or_intro`; title-only or blocked tiers stay unresolved.",
        "",
        "Completed split CSVs are still importable with:",
        "",
        "```bash",
        "python3 run_recovery_review_queue.py",
        "python3 run_recovery_split_preflight.py",
        "python3 run_import_abstract_backfill.py --input <split_csv> --skip-empty-abstracts --dry-run --require-source-metadata",
        "python3 run_import_abstract_backfill.py --input <split_csv> --skip-empty-abstracts --require-source-metadata --fail-on-errors",
        "```",
        "",
        "## Split Summary",
        "",
        df_to_markdown(summary, max_rows=20),
        "",
        "## Row Status Counts",
        "",
        df_to_markdown(status_counts, max_rows=40),
        "",
        "## Row Preview",
        "",
        df_to_markdown(preview, max_rows=60),
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("") if path.exists() else pd.DataFrame()


def write_recovery_batch_splits(
    *,
    batch_path: Path,
    workplan_path: Path,
    articles_path: Path | None,
    attempts_path: Path | None,
    output_dir: Path,
    html_dir: Path | None,
    summary_output: Path,
    report_path: Path,
    no_empty_files: bool = True,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    batch = read_csv_if_exists(batch_path)
    workplan = read_csv_if_exists(workplan_path)
    articles = read_csv_if_exists(articles_path) if articles_path is not None else pd.DataFrame()
    attempts = read_csv_if_exists(attempts_path) if attempts_path is not None else pd.DataFrame()
    split_frames = split_recovery_batch(batch, workplan, articles, attempts)
    batch_id = clean_text(first_nonempty(batch, "recovery_batch")) or clean_text(first_nonempty(workplan, "recovery_batch")) or "R001"

    output_dir.mkdir(parents=True, exist_ok=True)
    if html_dir is not None:
        html_dir.mkdir(parents=True, exist_ok=True)

    summary = split_summary_rows(split_frames, batch_id=batch_id, output_dir=output_dir, html_dir=html_dir)
    for group, frame in split_frames.items():
        if no_empty_files and frame.empty:
            continue
        csv_path = output_dir / f"insufficient_text_recovery_batch_{batch_id}_{group}.csv"
        frame.to_csv(csv_path, index=False)
        if html_dir is not None:
            html_path = html_dir / f"insufficient_text_recovery_batch_{batch_id}_{group}.html"
            form_frame = frame.copy()
            for column in RECOVERY_PACKET_COLUMNS:
                if column not in form_frame.columns:
                    form_frame[column] = ""
            recovery_form = recovery_form_html(
                form_frame,
                title=f"Insufficient Text Recovery {batch_id} {group}",
            )
            html_path.write_text(recovery_form, encoding="utf-8")

    summary_output.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(summary_output, index=False)
    write_split_report(report_path, summary, split_frames, batch_id=batch_id)
    print(f"split_groups={len(split_frames)}")
    print(summary[["split_group", "rows"]].to_string(index=False))
    print(f"summary={summary_output}")
    print(f"report={report_path}")
    return split_frames, summary


def first_nonempty(frame: pd.DataFrame, column: str) -> str:
    if frame.empty or column not in frame.columns:
        return ""
    values = [clean_text(value) for value in frame[column].tolist()]
    return next((value for value in values if value), "")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", default="data/intermediate/insufficient_text_recovery_batches/insufficient_text_recovery_batch_R001.csv")
    parser.add_argument("--workplan", default="outputs/tables/enriched/recovery_batch_R001_workplan.csv")
    parser.add_argument("--articles", default="data/final/articles_classified_enriched_pilot.csv")
    parser.add_argument("--attempts", default="data/intermediate/text_enrichment_attempts.csv")
    parser.add_argument("--output-dir", default="data/intermediate/insufficient_text_recovery_splits/R001")
    parser.add_argument("--html-dir", default="data/intermediate/insufficient_text_recovery_split_forms/R001")
    parser.add_argument("--summary-output", default="outputs/tables/enriched/recovery_batch_R001_split_summary.csv")
    parser.add_argument("--report", default="docs/recovery_batch_R001_split.md")
    parser.add_argument("--no-html", action="store_true")
    parser.add_argument("--write-empty-files", action="store_true")
    args = parser.parse_args()
    write_recovery_batch_splits(
        batch_path=Path(args.batch),
        workplan_path=Path(args.workplan),
        articles_path=Path(args.articles) if args.articles else None,
        attempts_path=Path(args.attempts) if args.attempts else None,
        output_dir=Path(args.output_dir),
        html_dir=None if args.no_html else Path(args.html_dir),
        summary_output=Path(args.summary_output),
        report_path=Path(args.report),
        no_empty_files=not args.write_empty_files,
    )


if __name__ == "__main__":
    main()
