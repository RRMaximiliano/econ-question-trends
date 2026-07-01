from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "lib"))
sys.path.append(str(Path(__file__).resolve().parent))

from econqt_common import clean_text  # noqa: E402
from evidence_tier_policy import (  # noqa: E402
    evidence_tier_error_code,
)
from recovery_batch_split import SPLIT_GROUP_ORDER, df_to_markdown, split_summary_rows  # noqa: E402


READY_STAGE_GROUPS = {
    "ready_partial_text_extension",
    "ready_manual_metadata",
    "ready_autofill_or_completed",
}
EDITABLE_COLUMNS = ["abstract", "source", "source_url", "source_record_id", "evidence_tier", "notes"]
STAGE_CHANGE_COLUMNS = [
    "article_id",
    "split_group",
    "quick_win_tier",
    "source_file",
    "staged_fields",
    "abstract_chars",
    "source",
    "source_url",
    "source_record_id",
    "evidence_tier",
]
STAGE_ERROR_COLUMNS = [
    "source_file",
    "row_number",
    "article_id",
    "split_group",
    "field",
    "value",
    "error",
]


def numeric_value(value: Any, default: int = 0) -> int:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return default if pd.isna(parsed) else int(parsed)


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("") if path.exists() and path.is_file() else pd.DataFrame()


def reviewer_input_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(item for item in path.glob("*.csv") if item.is_file())
    return []


def source_ready(row: pd.Series) -> bool:
    source = clean_text(row.get("source"))
    source_url = clean_text(row.get("source_url"))
    source_record_id = clean_text(row.get("source_record_id"))
    return bool(source and (source_url or source_record_id))


def evidence_tier_error(row: pd.Series) -> tuple[str, str] | None:
    evidence_tier = row_value(row, "evidence_tier")
    tier_error = evidence_tier_error_code(evidence_tier)
    if tier_error:
        return tier_error, evidence_tier
    return None


def row_value(row: pd.Series, column: str) -> str:
    return clean_text(row.get(column))


def merge_reviewer_fields(base: pd.Series, reviewer: pd.Series) -> pd.Series:
    merged = base.copy()
    for column in EDITABLE_COLUMNS:
        reviewer_value = row_value(reviewer, column)
        if reviewer_value:
            merged[column] = reviewer_value
    return merged


def split_rows_from_summary(split_summary: pd.DataFrame) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    work = split_summary.copy().fillna("") if not split_summary.empty else pd.DataFrame()
    for group in SPLIT_GROUP_ORDER:
        rows = work[work.get("split_group", pd.Series(dtype=str)).astype(str).eq(group)] if "split_group" in work.columns else pd.DataFrame()
        if rows.empty:
            frames[group] = pd.DataFrame()
            continue
        output_csv = clean_text(rows.iloc[0].get("output_csv"))
        if not output_csv:
            frames[group] = pd.DataFrame()
            continue
        path = Path(output_csv)
        frames[group] = read_csv_if_exists(path)
    return frames


def split_lookup(split_frames: dict[str, pd.DataFrame]) -> dict[str, tuple[str, int]]:
    lookup: dict[str, tuple[str, int]] = {}
    for group, frame in split_frames.items():
        if frame.empty or "article_id" not in frame.columns:
            continue
        for idx, row in frame.fillna("").iterrows():
            article_id = clean_text(row.get("article_id"))
            if article_id:
                lookup[article_id] = (group, idx)
    return lookup


def imported_article_ids(imported_history: pd.DataFrame) -> set[str]:
    if imported_history.empty or "article_id" not in imported_history.columns:
        return set()
    return {
        article_id
        for article_id in imported_history["article_id"].map(clean_text).tolist()
        if article_id
    }


def completed_candidate(row: pd.Series, merged: pd.Series, base: pd.Series) -> bool:
    split_group = row_value(base, "split_group")
    reviewer_source_any = any(row_value(row, column) for column in ["source", "source_url", "source_record_id"])
    reviewer_abstract = row_value(row, "abstract")
    base_abstract = row_value(base, "abstract")
    current_abstract = row_value(base, "current_abstract")
    if source_ready(merged):
        return True
    if split_group == "ready_partial_text_extension" and reviewer_abstract and reviewer_abstract != current_abstract:
        return True
    if reviewer_abstract and reviewer_abstract != base_abstract:
        return True
    return reviewer_source_any


def partial_text_was_extended(row: pd.Series, base: pd.Series) -> bool:
    abstract = row_value(row, "abstract")
    current_abstract = row_value(base, "current_abstract")
    current_chars = numeric_value(base.get("current_abstract_chars"), 0)
    if current_abstract and abstract == current_abstract:
        return False
    if current_chars and len(abstract) <= current_chars:
        return False
    return bool(abstract)


def submitted_partial_text_already_current(row: pd.Series, base: pd.Series) -> bool:
    abstract = row_value(row, "abstract")
    current_abstract = row_value(base, "current_abstract")
    return bool(abstract and current_abstract and abstract == current_abstract)


def error_row(
    *,
    source_file: Path,
    row_number: int,
    article_id: str,
    split_group: str,
    field: str,
    value: str,
    error: str,
) -> dict[str, Any]:
    return {
        "source_file": str(source_file),
        "row_number": row_number,
        "article_id": article_id,
        "split_group": split_group,
        "field": field,
        "value": value,
        "error": error,
    }


def stage_change_row(source_file: Path, row: pd.Series, merged: pd.Series, staged_fields: list[str]) -> dict[str, Any]:
    return {
        "article_id": row_value(merged, "article_id"),
        "split_group": row_value(merged, "split_group"),
        "quick_win_tier": row_value(row, "quick_win_tier"),
        "source_file": str(source_file),
        "staged_fields": "|".join(staged_fields),
        "abstract_chars": len(row_value(merged, "abstract")),
        "source": row_value(merged, "source"),
        "source_url": row_value(merged, "source_url"),
        "source_record_id": row_value(merged, "source_record_id"),
        "evidence_tier": row_value(merged, "evidence_tier"),
    }


def stage_tiered_reviewer_exports(
    *,
    split_summary: pd.DataFrame,
    reviewer_input: Path,
    imported_history: pd.DataFrame | None = None,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame]:
    split_frames = split_rows_from_summary(split_summary)
    lookup = split_lookup(split_frames)
    already_imported = imported_article_ids(imported_history if imported_history is not None else pd.DataFrame())
    updates: dict[str, tuple[Path, pd.Series, list[str], str]] = {}
    errors: list[dict[str, Any]] = []

    for source_file in reviewer_input_files(reviewer_input):
        submission = pd.read_csv(source_file, dtype=str).fillna("")
        if "article_id" not in submission.columns:
            errors.append(
                error_row(
                    source_file=source_file,
                    row_number=0,
                    article_id="",
                    split_group="",
                    field="article_id",
                    value="",
                    error="missing_article_id_column",
                )
            )
            continue
        for idx, row in submission.iterrows():
            article_id = row_value(row, "article_id")
            row_number = idx + 2
            if not article_id:
                continue
            if article_id in already_imported:
                continue
            if article_id not in lookup:
                errors.append(
                    error_row(
                        source_file=source_file,
                        row_number=row_number,
                        article_id=article_id,
                        split_group=row_value(row, "split_group"),
                        field="article_id",
                        value=article_id,
                        error="tiered_row_not_in_ready_split",
                    )
                )
                continue
            split_group, split_idx = lookup[article_id]
            if split_group not in READY_STAGE_GROUPS:
                errors.append(
                    error_row(
                        source_file=source_file,
                        row_number=row_number,
                        article_id=article_id,
                        split_group=split_group,
                        field="split_group",
                        value=split_group,
                        error="tiered_row_not_stageable",
                    )
                )
                continue
            submitted_group = row_value(row, "split_group")
            if submitted_group and submitted_group != split_group:
                errors.append(
                    error_row(
                        source_file=source_file,
                        row_number=row_number,
                        article_id=article_id,
                        split_group=submitted_group,
                        field="split_group",
                        value=submitted_group,
                        error="tiered_split_group_mismatch",
                    )
                )
                continue
            base = split_frames[split_group].loc[split_idx].copy()
            merged = merge_reviewer_fields(base, row)
            if split_group == "ready_partial_text_extension" and submitted_partial_text_already_current(row, base):
                continue
            if not completed_candidate(row, merged, base):
                continue
            if not row_value(merged, "abstract"):
                errors.append(
                    error_row(
                        source_file=source_file,
                        row_number=row_number,
                        article_id=article_id,
                        split_group=split_group,
                        field="abstract",
                        value="",
                        error="missing_staged_abstract",
                    )
                )
                continue
            if not source_ready(merged):
                errors.append(
                    error_row(
                        source_file=source_file,
                        row_number=row_number,
                        article_id=article_id,
                        split_group=split_group,
                        field="source|source_url|source_record_id",
                        value="|".join(row_value(merged, column) for column in ["source", "source_url", "source_record_id"]),
                        error="missing_staged_source_provenance",
                    )
                )
                continue
            tier_error = evidence_tier_error(merged)
            if tier_error is not None:
                errors.append(
                    error_row(
                        source_file=source_file,
                        row_number=row_number,
                        article_id=article_id,
                        split_group=split_group,
                        field="evidence_tier",
                        value=tier_error[1],
                        error=tier_error[0],
                    )
                )
                continue
            if split_group == "ready_partial_text_extension" and not partial_text_was_extended(merged, base):
                errors.append(
                    error_row(
                        source_file=source_file,
                        row_number=row_number,
                        article_id=article_id,
                        split_group=split_group,
                        field="abstract",
                        value=str(len(row_value(merged, "abstract"))),
                        error="partial_text_not_extended",
                    )
                )
                continue
            staged_fields = [column for column in EDITABLE_COLUMNS if row_value(merged, column) != row_value(base, column)]
            if article_id in updates:
                previous_file = updates[article_id][0]
                errors.append(
                    error_row(
                        source_file=source_file,
                        row_number=row_number,
                        article_id=article_id,
                        split_group=split_group,
                        field="article_id",
                        value=str(previous_file),
                        error="duplicate_completed_tiered_row",
                    )
                )
                continue
            updates[article_id] = (source_file, merged, staged_fields, split_group)

    staged_frames = {group: frame.copy() for group, frame in split_frames.items()}
    changes: list[dict[str, Any]] = []
    if not errors:
        for article_id, (source_file, merged, staged_fields, split_group) in updates.items():
            _, split_idx = lookup[article_id]
            for column in EDITABLE_COLUMNS:
                if column not in staged_frames[split_group].columns:
                    staged_frames[split_group][column] = ""
                staged_frames[split_group].at[split_idx, column] = row_value(merged, column)
            changes.append(stage_change_row(source_file, pd.Series(dtype=str), merged, staged_fields))

    changes_df = pd.DataFrame(changes, columns=STAGE_CHANGE_COLUMNS)
    errors_df = pd.DataFrame(errors, columns=STAGE_ERROR_COLUMNS)
    return staged_frames, changes_df, errors_df


def write_staged_split_packets(
    *,
    staged_frames: dict[str, pd.DataFrame],
    output_dir: Path,
    output_summary: Path,
    batch_id: str,
) -> pd.DataFrame:
    output_dir.mkdir(parents=True, exist_ok=True)
    for group in SPLIT_GROUP_ORDER:
        frame = staged_frames.get(group, pd.DataFrame())
        if frame.empty:
            continue
        frame.to_csv(output_dir / f"insufficient_text_recovery_batch_{batch_id}_{group}.csv", index=False)
    summary = split_summary_rows(staged_frames, batch_id=batch_id, output_dir=output_dir, html_dir=None)
    output_summary.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output_summary, index=False)
    return summary


def write_stage_report(
    path: Path,
    *,
    reviewer_input: Path,
    staged_summary: pd.DataFrame,
    changes: pd.DataFrame,
    errors: pd.DataFrame,
    output_summary: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Recovery Batch R001 Tiered Stage",
        "",
        "This report stages completed tiered recovery-form exports into split-packet copies. It does not update final article files, enrichment histories, or the original split packets.",
        "",
        f"- Reviewer input: `{reviewer_input}`",
        f"- Staged split summary: `{output_summary}`",
        f"- Staged rows: {len(changes)}",
        f"- Error rows: {len(errors)}",
        "",
        "Run preflight against the staged summary before importing:",
        "",
        "```bash",
        f"python3 run_recovery_split_preflight.py --split-summary {output_summary}",
        "```",
        "",
        "## Staged Summary",
        "",
        df_to_markdown(staged_summary, max_rows=20),
        "",
        "## Staged Changes",
        "",
        df_to_markdown(changes, max_rows=40),
        "",
        "## Errors",
        "",
        df_to_markdown(errors, max_rows=40),
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def run_recovery_tiered_stage(
    *,
    split_summary_path: Path,
    reviewer_input: Path,
    imported_history_path: Path | None,
    output_dir: Path,
    output_summary: Path,
    output_changes: Path,
    output_errors: Path,
    report_path: Path,
    batch_id: str = "R001",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    split_summary = read_csv_if_exists(split_summary_path)
    imported_history = read_csv_if_exists(imported_history_path) if imported_history_path is not None else pd.DataFrame()
    staged_frames, changes, errors = stage_tiered_reviewer_exports(
        split_summary=split_summary,
        reviewer_input=reviewer_input,
        imported_history=imported_history,
    )
    if errors.empty:
        staged_summary = write_staged_split_packets(
            staged_frames=staged_frames,
            output_dir=output_dir,
            output_summary=output_summary,
            batch_id=batch_id,
        )
    else:
        staged_summary = split_summary.copy().fillna("")
        output_summary.parent.mkdir(parents=True, exist_ok=True)
        staged_summary.to_csv(output_summary, index=False)

    output_changes.parent.mkdir(parents=True, exist_ok=True)
    output_errors.parent.mkdir(parents=True, exist_ok=True)
    changes.to_csv(output_changes, index=False)
    errors.to_csv(output_errors, index=False)
    write_stage_report(
        report_path,
        reviewer_input=reviewer_input,
        staged_summary=staged_summary,
        changes=changes,
        errors=errors,
        output_summary=output_summary,
    )

    print(f"staged_rows={len(changes)}")
    print(f"stage_errors={len(errors)}")
    print(f"staged_summary={output_summary}")
    print(f"changes={output_changes}")
    print(f"errors={output_errors}")
    print(f"report={report_path}")
    return staged_summary, changes, errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split-summary", default="outputs/tables/enriched/recovery_batch_R001_split_summary.csv")
    parser.add_argument("--reviewer-input", default="data/intermediate/insufficient_text_recovery_review_exports/R001")
    parser.add_argument("--imported-history", default="data/intermediate/abstract_backfill_import_history.csv")
    parser.add_argument("--output-dir", default="data/intermediate/insufficient_text_recovery_staged/R001")
    parser.add_argument("--output-summary", default="outputs/tables/enriched/recovery_batch_R001_staged_split_summary.csv")
    parser.add_argument("--output-changes", default="outputs/tables/enriched/recovery_batch_R001_tiered_stage_changes.csv")
    parser.add_argument("--output-errors", default="outputs/tables/enriched/recovery_batch_R001_tiered_stage_errors.csv")
    parser.add_argument("--report", default="docs/recovery_batch_R001_tiered_stage.md")
    parser.add_argument("--batch-id", default="R001")
    args = parser.parse_args()
    _, _, errors = run_recovery_tiered_stage(
        split_summary_path=Path(args.split_summary),
        reviewer_input=Path(args.reviewer_input),
        imported_history_path=Path(args.imported_history),
        output_dir=Path(args.output_dir),
        output_summary=Path(args.output_summary),
        output_changes=Path(args.output_changes),
        output_errors=Path(args.output_errors),
        report_path=Path(args.report),
        batch_id=args.batch_id,
    )
    if not errors.empty:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
