from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "lib"))

from econqt_common import clean_text  # noqa: E402


TARGET_COLUMNS = [
    "target_rank",
    "journal_short",
    "decade",
    "cell_rows",
    "insufficient_rows",
    "insufficient_share",
    "target_level",
    "target_score",
    "target_share",
    "recoveries_to_target_share",
    "stretch_share",
    "recoveries_to_stretch_share",
    "projected_share_after_ready_r001",
    "ready_r001_target_coverage",
    "queue_target_coverage",
    "queue_rows",
    "ready_r001_rows",
    "partial_short_text_rows",
    "missing_abstract_rows",
    "oa_pdf_rows",
    "first_recovery_rank",
    "first_ready_review_rank",
    "recommended_next_step",
]

TARGET_QUEUE_COLUMNS = [
    "target_rank",
    "target_level",
    "journal_short",
    "decade",
    "target_queue_rank",
    "recovery_rank",
    "recovery_batch",
    "recovery_priority",
    "recovery_action",
    "article_id",
    "publication_year",
    "title",
    "doi",
    "oa_pdf_url",
    "classification_text_chars",
    "text_enrichment_status",
    "abstract_source",
    "source_hint",
    "recommended_next_step",
]


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def numeric_value(value: Any, default: float = 0) -> float:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return default if pd.isna(parsed) else float(parsed)


def numeric_column(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(0, index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce").fillna(0)


def df_to_markdown(df: pd.DataFrame, max_rows: int = 30) -> str:
    if df.empty:
        return "_No rows._"
    shown = df.head(max_rows).fillna("")
    headers = [str(column).replace("|", "\\|") for column in shown.columns]
    rows = [headers] + [[str(value).replace("|", "\\|") for value in row] for row in shown.astype(str).values.tolist()]
    widths = [max(len(row[i]) for row in rows) for i in range(len(headers))]
    header = "| " + " | ".join(headers[i].ljust(widths[i]) for i in range(len(headers))) + " |"
    separator = "| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |"
    body = ["| " + " | ".join(row[i].ljust(widths[i]) for i in range(len(headers))) + " |" for row in rows[1:]]
    suffix = f"\n\n_Only first {max_rows} rows shown._" if len(df) > max_rows else ""
    return "\n".join([header, separator] + body) + suffix


def target_level(insufficient_rows: int, insufficient_share: float) -> str:
    if insufficient_rows >= 250 or insufficient_share >= 0.45:
        return "critical"
    if insufficient_rows >= 100 or insufficient_share >= 0.25:
        return "high"
    if insufficient_rows >= 50 or insufficient_share >= 0.15:
        return "medium"
    return "low"


def target_score(insufficient_rows: int, insufficient_share: float, ready_rows: int, partial_rows: int) -> int:
    return int(insufficient_rows + round(insufficient_share * 100) + min(ready_rows * 5, 50) + min(partial_rows, 50))


def recoveries_needed_for_share(insufficient_rows: int, cell_rows: int, target_share: float) -> int:
    if cell_rows <= 0:
        return 0
    allowed_insufficient = int(target_share * cell_rows)
    return max(0, insufficient_rows - allowed_insufficient)


def projected_insufficient_share(insufficient_rows: int, cell_rows: int, recovered_rows: int) -> float:
    if cell_rows <= 0:
        return 0.0
    return round(max(0, insufficient_rows - recovered_rows) / cell_rows, 6)


def coverage_ratio(available_rows: int, needed_rows: int) -> float:
    if needed_rows <= 0:
        return 1.0
    return round(min(available_rows / needed_rows, 1.0), 4)


def count_by_cell(frame: pd.DataFrame, value_column: str = "article_id") -> dict[tuple[str, str], int]:
    if frame.empty or "journal_short" not in frame.columns or "decade" not in frame.columns:
        return {}
    work = frame.copy().fillna("")
    if value_column in work.columns:
        work = work[work[value_column].astype(str).str.strip().ne("")]
    grouped = work.groupby(["journal_short", "decade"], dropna=False).size().astype(int)
    return {(clean_text(index[0]), clean_text(index[1])): int(value) for index, value in grouped.items()}


def min_rank_by_cell(frame: pd.DataFrame, rank_column: str) -> dict[tuple[str, str], int]:
    if frame.empty or "journal_short" not in frame.columns or "decade" not in frame.columns or rank_column not in frame.columns:
        return {}
    work = frame.copy().fillna("")
    work["_rank"] = numeric_column(work, rank_column).replace(0, pd.NA)
    work = work.dropna(subset=["_rank"])
    if work.empty:
        return {}
    grouped = work.groupby(["journal_short", "decade"], dropna=False)["_rank"].min()
    return {(clean_text(index[0]), clean_text(index[1])): int(value) for index, value in grouped.items()}


def source_hint(row: pd.Series) -> str:
    for column in ["doi_url", "article_url", "openalex_work_url", "crossref_work_url", "oa_pdf_url"]:
        value = clean_text(row.get(column))
        if value:
            return value
    doi = clean_text(row.get("doi"))
    return f"https://doi.org/{doi}" if doi else ""


def recommended_step(ready_rows: int, queue_rows: int, level: str, recoveries_to_target: int) -> str:
    if recoveries_to_target <= 0:
        return "Cell is already below the target insufficient-text share; keep it on monitoring."
    if ready_rows > 0:
        return f"Work ready R001 rows for this weak cell; {recoveries_to_target} recovered rows are needed to reach the target share."
    if queue_rows > 0 and level in {"critical", "high"}:
        return f"Prioritize this cell in the next recovery batch after R001 exports are staged; {recoveries_to_target} recovered rows are needed to reach the target share."
    if queue_rows > 0:
        return f"Keep this cell in the balanced recovery queue after higher-priority cells; {recoveries_to_target} recovered rows are needed to reach the target share."
    return "No queued recovery rows found for this cell; rerun diagnostics before assigning work."


def recovery_cell_targets(
    *,
    profile: pd.DataFrame,
    recovery_queue: pd.DataFrame,
    ready_queue: pd.DataFrame,
    max_targets: int = 20,
    min_insufficient_rows: int = 25,
    target_share: float = 0.20,
    stretch_share: float = 0.10,
) -> pd.DataFrame:
    if profile.empty:
        return pd.DataFrame(columns=TARGET_COLUMNS)

    queue_counts = count_by_cell(recovery_queue)
    ready_counts = count_by_cell(ready_queue)
    queue_ranks = min_rank_by_cell(recovery_queue, "recovery_rank")
    ready_ranks = min_rank_by_cell(ready_queue, "review_rank")

    rows: list[dict[str, Any]] = []
    work = profile.copy().fillna("")
    for _, row in work.iterrows():
        journal = clean_text(row.get("journal_short"))
        decade = clean_text(row.get("decade"))
        insufficient_rows = int(numeric_value(row.get("insufficient_rows"), 0))
        if insufficient_rows < min_insufficient_rows:
            continue
        insufficient_share = numeric_value(row.get("insufficient_share"), 0)
        ready_rows = ready_counts.get((journal, decade), 0)
        queue_rows = queue_counts.get((journal, decade), 0)
        level = target_level(insufficient_rows, insufficient_share)
        partial_rows = int(numeric_value(row.get("partial_short_text_rows"), 0))
        cell_rows = int(numeric_value(row.get("rows"), 0))
        target_need = recoveries_needed_for_share(insufficient_rows, cell_rows, target_share)
        stretch_need = recoveries_needed_for_share(insufficient_rows, cell_rows, stretch_share)
        rows.append(
            {
                "target_rank": 0,
                "journal_short": journal,
                "decade": decade,
                "cell_rows": cell_rows,
                "insufficient_rows": insufficient_rows,
                "insufficient_share": round(insufficient_share, 6),
                "target_level": level,
                "target_score": target_score(insufficient_rows, insufficient_share, ready_rows, partial_rows),
                "target_share": round(target_share, 4),
                "recoveries_to_target_share": target_need,
                "stretch_share": round(stretch_share, 4),
                "recoveries_to_stretch_share": stretch_need,
                "projected_share_after_ready_r001": projected_insufficient_share(insufficient_rows, cell_rows, ready_rows),
                "ready_r001_target_coverage": coverage_ratio(ready_rows, target_need),
                "queue_target_coverage": coverage_ratio(queue_rows, target_need),
                "queue_rows": queue_rows,
                "ready_r001_rows": ready_rows,
                "partial_short_text_rows": partial_rows,
                "missing_abstract_rows": int(numeric_value(row.get("missing_abstract_rows"), 0)),
                "oa_pdf_rows": int(numeric_value(row.get("has_oa_pdf_rows"), 0)),
                "first_recovery_rank": queue_ranks.get((journal, decade), ""),
                "first_ready_review_rank": ready_ranks.get((journal, decade), ""),
                "recommended_next_step": recommended_step(ready_rows, queue_rows, level, target_need),
            }
        )
    if not rows:
        return pd.DataFrame(columns=TARGET_COLUMNS)
    out = pd.DataFrame(rows, columns=TARGET_COLUMNS)
    out = out.sort_values(
        ["target_score", "insufficient_rows", "insufficient_share", "journal_short", "decade"],
        ascending=[False, False, False, True, True],
    ).head(max_targets).reset_index(drop=True)
    out["target_rank"] = range(1, len(out) + 1)
    return out.reindex(columns=TARGET_COLUMNS)


def recovery_cell_target_queue(
    *,
    targets: pd.DataFrame,
    recovery_queue: pd.DataFrame,
    rows_per_cell: int = 5,
) -> pd.DataFrame:
    if targets.empty or recovery_queue.empty:
        return pd.DataFrame(columns=TARGET_QUEUE_COLUMNS)
    queue = recovery_queue.copy().fillna("")
    for column in ["journal_short", "decade", "recovery_rank", "publication_year", "title"]:
        if column not in queue.columns:
            queue[column] = ""
    queue["_rank"] = numeric_column(queue, "recovery_rank")
    rows: list[dict[str, Any]] = []
    for _, target in targets.iterrows():
        journal = clean_text(target.get("journal_short"))
        decade = clean_text(target.get("decade"))
        cell = queue[
            queue.get("journal_short", pd.Series("", index=queue.index)).astype(str).str.strip().eq(journal)
            & queue.get("decade", pd.Series("", index=queue.index)).astype(str).str.strip().eq(decade)
        ].sort_values(["_rank", "publication_year", "title"], ascending=[True, True, True]).head(rows_per_cell)
        for cell_idx, row in enumerate(cell.itertuples(index=False), start=1):
            row_series = pd.Series(row._asdict())
            rows.append(
                {
                    "target_rank": target.get("target_rank"),
                    "target_level": target.get("target_level"),
                    "journal_short": journal,
                    "decade": decade,
                    "target_queue_rank": cell_idx,
                    "recovery_rank": clean_text(row_series.get("recovery_rank")),
                    "recovery_batch": clean_text(row_series.get("recovery_batch")),
                    "recovery_priority": clean_text(row_series.get("recovery_priority")),
                    "recovery_action": clean_text(row_series.get("recovery_action")),
                    "article_id": clean_text(row_series.get("article_id")),
                    "publication_year": clean_text(row_series.get("publication_year")),
                    "title": clean_text(row_series.get("title")),
                    "doi": clean_text(row_series.get("doi")),
                    "oa_pdf_url": clean_text(row_series.get("oa_pdf_url")),
                    "classification_text_chars": clean_text(row_series.get("classification_text_chars")),
                    "text_enrichment_status": clean_text(row_series.get("text_enrichment_status")),
                    "abstract_source": clean_text(row_series.get("abstract_source")),
                    "source_hint": source_hint(row_series),
                    "recommended_next_step": clean_text(target.get("recommended_next_step")),
                }
            )
    return pd.DataFrame(rows, columns=TARGET_QUEUE_COLUMNS)


def write_report(path: Path, targets: pd.DataFrame, target_queue: pd.DataFrame, *, output_targets: Path, output_queue: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    total_target_need = int(numeric_column(targets, "recoveries_to_target_share").sum()) if not targets.empty else 0
    total_stretch_need = int(numeric_column(targets, "recoveries_to_stretch_share").sum()) if not targets.empty else 0
    total_ready_rows = int(numeric_column(targets, "ready_r001_rows").sum()) if not targets.empty else 0
    lines = [
        "# Recovery Cell Targets",
        "",
        "This report prioritizes insufficient-text recovery by journal-decade cell so manual recovery improves trend credibility rather than only chasing the easiest rows. It is non-mutating and does not import abstracts.",
        "",
        f"- Target table: `{output_targets}`",
        f"- Target queue: `{output_queue}`",
        f"- Target cells: {len(targets)}",
        f"- Queued example rows: {len(target_queue)}",
        f"- Recoveries needed across target cells to reach target share: {total_target_need}",
        f"- Recoveries needed across target cells to reach stretch share: {total_stretch_need}",
        f"- Ready R001 rows inside target cells: {total_ready_rows}",
        "",
        "## Target Cells",
        "",
        df_to_markdown(targets, max_rows=30),
        "",
        "## First Rows Per Target Cell",
        "",
        df_to_markdown(target_queue, max_rows=60),
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def run_recovery_cell_targets(
    *,
    profile_path: Path,
    recovery_queue_path: Path,
    ready_queue_path: Path,
    output_targets: Path,
    output_queue: Path,
    report_path: Path,
    max_targets: int = 20,
    rows_per_cell: int = 5,
    min_insufficient_rows: int = 25,
    target_share: float = 0.20,
    stretch_share: float = 0.10,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    profile = read_csv_if_exists(profile_path)
    recovery_queue = read_csv_if_exists(recovery_queue_path)
    ready_queue = read_csv_if_exists(ready_queue_path)
    targets = recovery_cell_targets(
        profile=profile,
        recovery_queue=recovery_queue,
        ready_queue=ready_queue,
        max_targets=max_targets,
        min_insufficient_rows=min_insufficient_rows,
        target_share=target_share,
        stretch_share=stretch_share,
    )
    target_queue = recovery_cell_target_queue(targets=targets, recovery_queue=recovery_queue, rows_per_cell=rows_per_cell)

    output_targets.parent.mkdir(parents=True, exist_ok=True)
    output_queue.parent.mkdir(parents=True, exist_ok=True)
    targets.to_csv(output_targets, index=False)
    target_queue.to_csv(output_queue, index=False)
    write_report(report_path, targets, target_queue, output_targets=output_targets, output_queue=output_queue)

    print(f"target_cells={len(targets)}")
    print(f"target_queue_rows={len(target_queue)}")
    print(f"targets={output_targets}")
    print(f"queue={output_queue}")
    print(f"report={report_path}")
    return targets, target_queue


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="outputs/tables/enriched/remaining_insufficient_text_profile.csv")
    parser.add_argument("--recovery-queue", default="outputs/tables/enriched/insufficient_text_recovery_queue.csv")
    parser.add_argument("--ready-queue", default="outputs/tables/enriched/recovery_batch_R001_review_queue.csv")
    parser.add_argument("--output-targets", default="outputs/tables/enriched/recovery_cell_targets.csv")
    parser.add_argument("--output-queue", default="outputs/tables/enriched/recovery_cell_target_queue.csv")
    parser.add_argument("--report", default="docs/recovery_cell_targets.md")
    parser.add_argument("--max-targets", type=int, default=20)
    parser.add_argument("--rows-per-cell", type=int, default=5)
    parser.add_argument("--min-insufficient-rows", type=int, default=25)
    parser.add_argument("--target-share", type=float, default=0.20)
    parser.add_argument("--stretch-share", type=float, default=0.10)
    args = parser.parse_args()
    run_recovery_cell_targets(
        profile_path=Path(args.profile),
        recovery_queue_path=Path(args.recovery_queue),
        ready_queue_path=Path(args.ready_queue),
        output_targets=Path(args.output_targets),
        output_queue=Path(args.output_queue),
        report_path=Path(args.report),
        max_targets=args.max_targets,
        rows_per_cell=args.rows_per_cell,
        min_insufficient_rows=args.min_insufficient_rows,
        target_share=args.target_share,
        stretch_share=args.stretch_share,
    )


if __name__ == "__main__":
    main()
