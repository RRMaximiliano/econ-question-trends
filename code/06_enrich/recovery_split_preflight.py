from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "lib"))
sys.path.append(str(Path(__file__).resolve().parent))

from abstract_backfill import (  # noqa: E402
    ERROR_COLUMNS,
    abstract_backfill_to_enrichment,
    df_to_markdown,
    filter_empty_abstract_rows,
)
from econqt_common import clean_text, load_yaml  # noqa: E402


READY_PREFLIGHT_GROUPS = {
    "ready_partial_text_extension",
    "ready_manual_metadata",
    "ready_autofill_or_completed",
}

PREFLIGHT_SUMMARY_COLUMNS = [
    "recovery_batch",
    "split_group",
    "preflight_status",
    "input_csv",
    "total_rows",
    "skipped_empty_abstract_rows",
    "candidate_rows_after_skip",
    "import_ready_rows",
    "error_rows",
    "source_ready_backfill_abstracts",
    "source_incomplete_backfill_abstracts",
    "recommended_next_step",
]
PREFLIGHT_ERROR_COLUMNS = ["recovery_batch", "split_group", "input_csv"] + ERROR_COLUMNS


def numeric_value(value: Any, default: int = 0) -> int:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return default if pd.isna(parsed) else int(parsed)


def source_readiness_counts(frame: pd.DataFrame) -> tuple[int, int]:
    if frame.empty:
        return 0, 0
    abstracts = frame.get("abstract", pd.Series("", index=frame.index, dtype=str)).astype(str).str.strip()
    sources = frame.get("source", pd.Series("", index=frame.index, dtype=str)).astype(str).str.strip()
    source_urls = frame.get("source_url", pd.Series("", index=frame.index, dtype=str)).astype(str).str.strip()
    source_record_ids = frame.get("source_record_id", pd.Series("", index=frame.index, dtype=str)).astype(str).str.strip()
    completed = abstracts.ne("")
    source_ready = completed & sources.ne("") & (source_urls.ne("") | source_record_ids.ne(""))
    source_incomplete = completed & ~source_ready
    return int(source_ready.sum()), int(source_incomplete.sum())


def path_from_cell(value: Any) -> Path:
    return Path(clean_text(value))


def preflight_status(candidate_rows: int, error_rows: int) -> str:
    if error_rows > 0:
        return "blocked_errors"
    if candidate_rows == 0:
        return "pass_empty"
    return "pass_ready"


def preflight_split_row(
    split_row: pd.Series,
    *,
    articles: pd.DataFrame,
    config: dict[str, Any],
    default_source: str = "curated_backfill",
    minimum_title_match: float = 0.9,
    skip_empty_abstracts: bool = True,
) -> tuple[dict[str, Any], pd.DataFrame]:
    batch_id = clean_text(split_row.get("recovery_batch"))
    split_group = clean_text(split_row.get("split_group"))
    input_csv = clean_text(split_row.get("output_csv"))
    recommended_next_step = clean_text(split_row.get("recommended_next_step"))
    expected_rows = numeric_value(split_row.get("rows"), 0)

    if not input_csv or not path_from_cell(input_csv).exists():
        summary = {
            "recovery_batch": batch_id,
            "split_group": split_group,
            "preflight_status": "missing_file",
            "input_csv": input_csv,
            "total_rows": expected_rows,
            "skipped_empty_abstract_rows": 0,
            "candidate_rows_after_skip": 0,
            "import_ready_rows": 0,
            "error_rows": 1,
            "source_ready_backfill_abstracts": numeric_value(split_row.get("source_ready_backfill_abstracts"), 0),
            "source_incomplete_backfill_abstracts": numeric_value(split_row.get("source_incomplete_backfill_abstracts"), 0),
            "recommended_next_step": recommended_next_step,
        }
        error = pd.DataFrame(
            [
                {
                    "recovery_batch": batch_id,
                    "split_group": split_group,
                    "input_csv": input_csv,
                    "row_number": "",
                    "article_id": "",
                    "doi": "",
                    "title": "",
                    "error": "missing_split_file",
                    "detail": "Split summary points to a missing or blank output_csv.",
                }
            ],
            columns=PREFLIGHT_ERROR_COLUMNS,
        )
        return summary, error

    backfill = pd.read_csv(path_from_cell(input_csv), dtype=str).fillna("")
    total_rows = len(backfill)
    source_ready, source_incomplete = source_readiness_counts(backfill)
    skipped_empty_rows = 0
    candidate_backfill = backfill
    if skip_empty_abstracts:
        candidate_backfill, skipped_empty_rows = filter_empty_abstract_rows(backfill)

    imported, errors = abstract_backfill_to_enrichment(
        candidate_backfill,
        articles,
        minimum_chars=int(config.get("minimum_usable_text_chars", 250)),
        default_source=default_source,
        minimum_title_match=minimum_title_match,
        scope_patterns=config.get("article_scope_patterns", {}) or {},
        require_source_metadata=True,
    )
    annotated_errors = errors.copy()
    if annotated_errors.empty:
        annotated_errors = pd.DataFrame(columns=PREFLIGHT_ERROR_COLUMNS)
    else:
        annotated_errors.insert(0, "input_csv", input_csv)
        annotated_errors.insert(0, "split_group", split_group)
        annotated_errors.insert(0, "recovery_batch", batch_id)
        annotated_errors = annotated_errors.reindex(columns=PREFLIGHT_ERROR_COLUMNS, fill_value="")

    candidate_rows = len(candidate_backfill)
    error_rows = len(errors)
    summary = {
        "recovery_batch": batch_id,
        "split_group": split_group,
        "preflight_status": preflight_status(candidate_rows, error_rows),
        "input_csv": input_csv,
        "total_rows": total_rows,
        "skipped_empty_abstract_rows": skipped_empty_rows,
        "candidate_rows_after_skip": candidate_rows,
        "import_ready_rows": len(imported),
        "error_rows": error_rows,
        "source_ready_backfill_abstracts": source_ready,
        "source_incomplete_backfill_abstracts": source_incomplete,
        "recommended_next_step": recommended_next_step,
    }
    return summary, annotated_errors


def ready_split_rows(split_summary: pd.DataFrame) -> pd.DataFrame:
    if split_summary.empty or "split_group" not in split_summary.columns:
        return pd.DataFrame(columns=split_summary.columns)
    work = split_summary.copy().fillna("")
    work["_rows"] = pd.to_numeric(work.get("rows", ""), errors="coerce").fillna(0).astype(int)
    return work[work["split_group"].isin(READY_PREFLIGHT_GROUPS) & work["_rows"].gt(0)].drop(columns=["_rows"]).reset_index(drop=True)


def write_preflight_report(path: Path, summary: pd.DataFrame, errors: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    batch_id = ""
    if not summary.empty and "recovery_batch" in summary.columns:
        batch_id = clean_text(summary.iloc[0].get("recovery_batch"))
    total_ready = int(pd.to_numeric(summary.get("import_ready_rows", pd.Series(dtype=str)), errors="coerce").fillna(0).sum()) if not summary.empty else 0
    total_errors = int(pd.to_numeric(summary.get("error_rows", pd.Series(dtype=str)), errors="coerce").fillna(0).sum()) if not summary.empty else 0
    total_skipped = int(pd.to_numeric(summary.get("skipped_empty_abstract_rows", pd.Series(dtype=str)), errors="coerce").fillna(0).sum()) if not summary.empty else 0
    lines = [
        f"# Recovery Batch {batch_id or 'Unknown'} Split Preflight",
        "",
        "This report is non-mutating. It validates ready split packets with the same matching, source-metadata, and evidence-tier checks used by `run_import_abstract_backfill.py --skip-empty-abstracts --require-source-metadata`, but it does not update enrichment histories or final article files.",
        "",
        f"- Ready split groups checked: {len(summary)}",
        f"- Import-ready rows: {total_ready}",
        f"- Error rows: {total_errors}",
        f"- Skipped empty abstract rows: {total_skipped}",
        "",
        "## Preflight Summary",
        "",
        df_to_markdown(summary, max_rows=30),
        "",
        "## Errors",
        "",
        df_to_markdown(errors, max_rows=50),
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("") if path.exists() else pd.DataFrame()


def run_recovery_split_preflight(
    *,
    split_summary_path: Path,
    articles_input: Path,
    config_path: Path,
    output_summary: Path,
    output_errors: Path,
    report_path: Path,
    default_source: str = "curated_backfill",
    minimum_title_match: float = 0.9,
    skip_empty_abstracts: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    split_summary = read_csv_if_exists(split_summary_path)
    articles = read_csv_if_exists(articles_input)
    config = load_yaml(config_path)
    rows = ready_split_rows(split_summary)
    summary_rows: list[dict[str, Any]] = []
    error_frames: list[pd.DataFrame] = []

    for _, split_row in rows.iterrows():
        summary, errors = preflight_split_row(
            split_row,
            articles=articles,
            config=config,
            default_source=default_source,
            minimum_title_match=minimum_title_match,
            skip_empty_abstracts=skip_empty_abstracts,
        )
        summary_rows.append(summary)
        if not errors.empty:
            error_frames.append(errors)

    summary_df = pd.DataFrame(summary_rows, columns=PREFLIGHT_SUMMARY_COLUMNS)
    errors_df = pd.concat(error_frames, ignore_index=True) if error_frames else pd.DataFrame(columns=PREFLIGHT_ERROR_COLUMNS)
    errors_df = errors_df.reindex(columns=PREFLIGHT_ERROR_COLUMNS, fill_value="")

    output_summary.parent.mkdir(parents=True, exist_ok=True)
    output_errors.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(output_summary, index=False)
    errors_df.to_csv(output_errors, index=False)
    write_preflight_report(report_path, summary_df, errors_df)

    print(f"preflight_split_groups={len(summary_df)}")
    print(f"import_ready_rows={int(pd.to_numeric(summary_df.get('import_ready_rows', pd.Series(dtype=str)), errors='coerce').fillna(0).sum()) if not summary_df.empty else 0}")
    print(f"error_rows={len(errors_df)}")
    print(f"summary={output_summary}")
    print(f"errors={output_errors}")
    print(f"report={report_path}")
    return summary_df, errors_df


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split-summary", default="outputs/tables/enriched/recovery_batch_R001_split_summary.csv")
    parser.add_argument("--articles-input", default="data/final/articles_pilot.csv")
    parser.add_argument("--config", default="config/text_enrichment.yml")
    parser.add_argument("--output-summary", default="outputs/tables/enriched/recovery_batch_R001_preflight_summary.csv")
    parser.add_argument("--output-errors", default="outputs/tables/enriched/recovery_batch_R001_preflight_errors.csv")
    parser.add_argument("--report", default="docs/recovery_batch_R001_preflight.md")
    parser.add_argument("--default-source", default="curated_backfill")
    parser.add_argument("--minimum-title-match", type=float, default=0.9)
    parser.add_argument("--no-skip-empty-abstracts", action="store_true")
    args = parser.parse_args()
    _, errors = run_recovery_split_preflight(
        split_summary_path=Path(args.split_summary),
        articles_input=Path(args.articles_input),
        config_path=Path(args.config),
        output_summary=Path(args.output_summary),
        output_errors=Path(args.output_errors),
        report_path=Path(args.report),
        default_source=args.default_source,
        minimum_title_match=args.minimum_title_match,
        skip_empty_abstracts=not args.no_skip_empty_abstracts,
    )
    if not errors.empty:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
