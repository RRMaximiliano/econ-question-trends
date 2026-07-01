from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

LIB_DIR = Path(__file__).resolve().parents[1] / "lib"
ENRICH_DIR = Path(__file__).resolve().parents[1] / "06_enrich"
for directory in [LIB_DIR, ENRICH_DIR]:
    if str(directory) not in sys.path:
        sys.path.append(str(directory))

from econqt_common import clean_text, load_yaml, normalize_doi  # noqa: E402
from text_enrichment import NONRESEARCH_SCOPES, classify_article_scope  # noqa: E402


CANDIDATE_COLUMNS = [
    "dataset",
    "article_id",
    "journal_short",
    "publication_year",
    "decade",
    "title",
    "doi",
    "causal_predictive_category",
    "current_article_scope",
    "proposed_article_scope",
    "proposed_scope_reason",
    "recovery_batch",
    "recovery_rank",
    "recommended_action",
    "human_scope_decision",
    "scope_review_notes",
]

SUMMARY_COLUMNS = [
    "dataset",
    "proposed_article_scope",
    "proposed_scope_reason",
    "journal_short",
    "decade",
    "recovery_batch",
    "candidate_rows",
]

SCOPE_DECISIONS = ["exclude_nonresearch", "keep_research", "unsure"]
SCOPE_DECISION_RUBRIC = [
    "`exclude_nonresearch`: use for corrections, errata, retractions, referee lists, society-election notices, supplements, data/code appendices, or other paratext that is not a standalone research article.",
    "`keep_research`: use only when the row contains substantive standalone research and should remain in the trend denominator.",
    "`unsure`: use when the title or metadata are not enough to decide; leave a note describing the ambiguity.",
    "Completed decisions require `reviewer_id` and ISO `review_date`. Do not change causal/predictive labels in this packet.",
]
SCOPE_AFTER_EXPORT_COMMANDS = [
    "Place the exported CSV at `data/intermediate/scope_review/scope_review_packet.csv`.",
    "Run the dry-run validator: `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_apply_scope_review_decisions.py`.",
    "Review `docs/scope_review_apply.md`, `outputs/tables/enriched/scope_review_apply_errors.csv`, and `outputs/tables/enriched/scope_review_apply_changes.csv`; continue only when `error_rows=0` and the proposed changes match the reviewed packet.",
    "Apply only after the dry-run is clean: `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_apply_scope_review_decisions.py --apply`.",
    "Refresh handoff status: `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_human_review_refresh.py`.",
]
RECENT_SCOPE_PRIORITY_YEARS = {"2023", "2024", "2025"}
RECENT_SCOPE_PRIORITY_JOURNALS = {"aer", "ecta", "jpe", "qje", "restud"}
RECENT_SCOPE_PRIORITY = "P1_recent_2023_2025_top5"
BACKLOG_SCOPE_PRIORITY = "P2_scope_review_backlog"
PACKET_COLUMNS = [
    "scope_review_id",
    "scope_review_priority",
    "article_id",
    "journal_short",
    "publication_year",
    "decade",
    "title",
    "doi",
    "current_article_scope",
    "proposed_article_scope",
    "proposed_scope_reason",
    "causal_predictive_categories",
    "appears_in_datasets",
    "recovery_batches",
    "recovery_ranks",
    "recommended_action",
    "human_scope_decision",
    "scope_review_notes",
    "reviewer_id",
    "review_date",
]
COMPLETION_COLUMNS = ["metric", "value"]
GUIDE_COLUMNS = [
    "scope_review_id",
    "article_id",
    "scope_pattern_family",
    "review_lens",
    "review_focus",
    "pattern_group_key",
    "pattern_group_rows",
]
GUIDE_SUMMARY_COLUMNS = [
    "scope_pattern_family",
    "proposed_article_scope",
    "review_lens",
    "pattern_group_rows",
    "completed_decisions",
    "remaining_decisions",
    "review_focus",
]


def cell_text(row: pd.Series | dict[str, Any], column: str, default: str = "") -> str:
    value = row.get(column, default) if hasattr(row, "get") else default
    return clean_text(value)


def decade_from_year(year_value: Any) -> str:
    year = pd.to_numeric(pd.Series([year_value]), errors="coerce").iloc[0]
    if pd.isna(year):
        return "missing"
    return str(int(year) // 10 * 10)


def category_for_row(row: pd.Series | dict[str, Any], *, dataset: str) -> str:
    category = cell_text(row, "causal_predictive_category") or cell_text(row, "current_category")
    if category:
        return category
    if dataset in {"recovery_queue", "active_batch"}:
        return "insufficient_text"
    return ""


def scope_review_candidates_for_dataset(
    dataset: str,
    df: pd.DataFrame,
    *,
    scope_patterns: dict[str, list[str]] | None = None,
    excluded_scopes: set[str] | None = None,
) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=CANDIDATE_COLUMNS)

    excluded = excluded_scopes or set(NONRESEARCH_SCOPES)
    patterns = scope_patterns or {}
    rows: list[dict[str, Any]] = []
    work = df.copy().fillna("")

    for _, row in work.iterrows():
        current_scope = cell_text(row, "article_scope") or cell_text(row, "current_article_scope")
        proposed_scope, proposed_reason = classify_article_scope(row.to_dict(), patterns)
        if proposed_scope not in excluded or current_scope in excluded:
            continue

        rows.append(
            {
                "dataset": dataset,
                "article_id": cell_text(row, "article_id"),
                "journal_short": cell_text(row, "journal_short"),
                "publication_year": cell_text(row, "publication_year"),
                "decade": cell_text(row, "decade") or decade_from_year(cell_text(row, "publication_year")),
                "title": cell_text(row, "title"),
                "doi": normalize_doi(cell_text(row, "doi")),
                "causal_predictive_category": category_for_row(row, dataset=dataset),
                "current_article_scope": current_scope,
                "proposed_article_scope": proposed_scope,
                "proposed_scope_reason": proposed_reason,
                "recovery_batch": cell_text(row, "recovery_batch"),
                "recovery_rank": cell_text(row, "recovery_rank"),
                "recommended_action": "review_scope_before_recovery",
                "human_scope_decision": "",
                "scope_review_notes": "",
            }
        )

    if not rows:
        return pd.DataFrame(columns=CANDIDATE_COLUMNS)
    out = pd.DataFrame(rows, columns=CANDIDATE_COLUMNS)
    out["_rank"] = pd.to_numeric(out["recovery_rank"], errors="coerce").fillna(999999).astype(int)
    return (
        out.sort_values(["dataset", "_rank", "journal_short", "publication_year", "title"], ascending=[True, True, True, True, True])
        .drop(columns=["_rank"])
        .reset_index(drop=True)
    )


def scope_review_candidates(
    datasets: dict[str, pd.DataFrame],
    *,
    scope_patterns: dict[str, list[str]] | None = None,
    excluded_scopes: set[str] | None = None,
) -> pd.DataFrame:
    frames = [
        scope_review_candidates_for_dataset(
            dataset,
            df,
            scope_patterns=scope_patterns,
            excluded_scopes=excluded_scopes,
        )
        for dataset, df in datasets.items()
    ]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return pd.DataFrame(columns=CANDIDATE_COLUMNS)
    return pd.concat(frames, ignore_index=True)[CANDIDATE_COLUMNS]


def scope_review_summary(candidates: pd.DataFrame) -> pd.DataFrame:
    if candidates.empty:
        return pd.DataFrame(columns=SUMMARY_COLUMNS)
    work = candidates.copy().fillna("")
    group_columns = [
        "dataset",
        "proposed_article_scope",
        "proposed_scope_reason",
        "journal_short",
        "decade",
        "recovery_batch",
    ]
    for column in group_columns:
        if column not in work.columns:
            work[column] = ""
    summary = (
        work.groupby(group_columns, dropna=False)
        .size()
        .reset_index(name="candidate_rows")
    )
    return summary.sort_values(["candidate_rows", "dataset", "journal_short", "decade"], ascending=[False, True, True, True]).reset_index(drop=True)[
        SUMMARY_COLUMNS
    ]


def joined_unique(values: pd.Series) -> str:
    unique = []
    for value in values.astype(str).tolist():
        text = clean_text(value)
        if text and text not in unique:
            unique.append(text)
    return "|".join(unique)


def existing_scope_review_decisions(existing_packet: pd.DataFrame | None) -> dict[str, dict[str, str]]:
    if existing_packet is None or existing_packet.empty or "article_id" not in existing_packet.columns:
        return {}
    work = existing_packet.copy().fillna("")
    out: dict[str, dict[str, str]] = {}
    decision_columns = ["human_scope_decision", "scope_review_notes", "reviewer_id", "review_date"]
    for _, row in work.iterrows():
        article_id = cell_text(row, "article_id")
        if not article_id:
            continue
        values = {column: cell_text(row, column) for column in decision_columns}
        if any(values.values()):
            out[article_id] = values
    return out


def scope_review_priority_for_row(row: pd.Series | dict[str, Any]) -> str:
    year = cell_text(row, "publication_year")
    journal = cell_text(row, "journal_short").lower()
    if year in RECENT_SCOPE_PRIORITY_YEARS and journal in RECENT_SCOPE_PRIORITY_JOURNALS:
        return RECENT_SCOPE_PRIORITY
    return BACKLOG_SCOPE_PRIORITY


def scope_review_packet(candidates: pd.DataFrame, existing_packet: pd.DataFrame | None = None) -> pd.DataFrame:
    if candidates.empty:
        return pd.DataFrame(columns=PACKET_COLUMNS)

    work = candidates.copy().fillna("")
    for column in CANDIDATE_COLUMNS:
        if column not in work.columns:
            work[column] = ""
    existing = existing_scope_review_decisions(existing_packet)
    rows: list[dict[str, Any]] = []
    for article_id, group in work.groupby("article_id", sort=False, dropna=False):
        group = group.copy()
        first = group.iloc[0]
        saved = existing.get(clean_text(article_id), {})
        rows.append(
            {
                "scope_review_id": "",
                "scope_review_priority": scope_review_priority_for_row(first),
                "article_id": clean_text(article_id),
                "journal_short": cell_text(first, "journal_short"),
                "publication_year": cell_text(first, "publication_year"),
                "decade": cell_text(first, "decade"),
                "title": cell_text(first, "title"),
                "doi": normalize_doi(cell_text(first, "doi")),
                "current_article_scope": cell_text(first, "current_article_scope"),
                "proposed_article_scope": joined_unique(group["proposed_article_scope"]),
                "proposed_scope_reason": joined_unique(group["proposed_scope_reason"]),
                "causal_predictive_categories": joined_unique(group["causal_predictive_category"]),
                "appears_in_datasets": joined_unique(group["dataset"]),
                "recovery_batches": joined_unique(group["recovery_batch"]),
                "recovery_ranks": joined_unique(group["recovery_rank"]),
                "recommended_action": "review_scope_before_recovery",
                "human_scope_decision": saved.get("human_scope_decision", ""),
                "scope_review_notes": saved.get("scope_review_notes", ""),
                "reviewer_id": saved.get("reviewer_id", ""),
                "review_date": saved.get("review_date", ""),
            }
        )
    out = pd.DataFrame(rows, columns=PACKET_COLUMNS)
    out["_rank"] = pd.to_numeric(out["recovery_ranks"].astype(str).str.split("|").str[0], errors="coerce").fillna(999999).astype(int)
    out["_year"] = pd.to_numeric(out["publication_year"], errors="coerce").fillna(9999).astype(int)
    recent = out[out["scope_review_priority"].eq(RECENT_SCOPE_PRIORITY)].sort_values(
        ["_year", "journal_short", "_rank", "title"],
        ascending=[True, True, True, True],
    )
    backlog = out[~out["scope_review_priority"].eq(RECENT_SCOPE_PRIORITY)].sort_values(
        ["_rank", "journal_short", "publication_year", "title"],
        ascending=[True, True, True, True],
    )
    out = pd.concat([recent, backlog], ignore_index=True).drop(columns=["_rank", "_year"]).reset_index(drop=True)
    out["scope_review_id"] = [f"SR{i:04d}" for i in range(1, len(out) + 1)]
    return out[PACKET_COLUMNS]


def scope_review_completion_summary(packet: pd.DataFrame) -> pd.DataFrame:
    if packet.empty:
        return pd.DataFrame(
            [
                {"metric": "scope_review_rows", "value": "0"},
                {"metric": "completed_scope_review_decisions", "value": "0"},
                {"metric": "remaining_scope_review_decisions", "value": "0"},
                {"metric": "first_incomplete_scope_review_id", "value": ""},
            ],
            columns=COMPLETION_COLUMNS,
        )
    work = packet.copy().fillna("")
    decision = work["human_scope_decision"].astype(str).str.strip() if "human_scope_decision" in work.columns else pd.Series("", index=work.index)
    completed = decision.ne("")
    first_incomplete = ""
    if (~completed).any() and "scope_review_id" in work.columns:
        first_incomplete = clean_text(work.loc[~completed, "scope_review_id"].iloc[0])
    rows = [
        {"metric": "scope_review_rows", "value": str(len(work))},
        {"metric": "completed_scope_review_decisions", "value": str(int(completed.sum()))},
        {"metric": "remaining_scope_review_decisions", "value": str(int((~completed).sum()))},
        {"metric": "first_incomplete_scope_review_id", "value": first_incomplete},
    ]
    for decision_value in SCOPE_DECISIONS:
        rows.append({"metric": f"decision_{decision_value}", "value": str(int(decision.eq(decision_value).sum()))})
    return pd.DataFrame(rows, columns=COMPLETION_COLUMNS)


def scope_pattern_family(row: pd.Series | dict[str, Any]) -> str:
    reason = cell_text(row, "proposed_scope_reason").lower()
    title = cell_text(row, "title").lower()
    text = f"{reason} {title}"
    if any(token in text for token in ["correction", "erratum", "corrigendum", "retraction"]):
        return "correction_erratum"
    if "supplement" in text:
        return "supplement_or_data_files"
    if "election of fellows" in text or "fellows of the econometric society" in text:
        return "society_election"
    if "referee" in text:
        return "referee_list"
    if any(token in text for token in ["annual report", "association", "committee", "minutes of", "president"]):
        return "society_governance"
    if any(token in text for token in ["front matter", "back matter", "journal of political economy", "econometrica", "quarterly journal", "review of economic studies", "american economic review"]):
        return "journal_frontmatter"
    if any(token in text for token in ["comment", "reply", "discussion"]):
        return "comment_reply_discussion"
    if any(token in text for token in ["nobel lecture", "presidential address", "address"]):
        return "lecture_address"
    if any(token in text for token in ["index", "forthcoming", "accepted manuscripts", "announcements", "books received", "volume contents"]):
        return "index_or_announcement"
    return "other_scope_pattern"


def review_lens_for_family(family: str) -> str:
    return {
        "correction_erratum": "Usually exclude if it only corrects a prior article.",
        "supplement_or_data_files": "Usually exclude if it is supplementary files, data, code, or a guide rather than a standalone article.",
        "society_election": "Usually exclude as society paratext.",
        "referee_list": "Usually exclude as editorial paratext.",
        "society_governance": "Usually exclude as association or journal governance material.",
        "journal_frontmatter": "Usually exclude as front matter, masthead, contents, or journal metadata.",
        "comment_reply_discussion": "Review carefully; keep only if comments/replies are in the analysis denominator by design.",
        "lecture_address": "Review against the denominator rule for addresses and lectures.",
        "index_or_announcement": "Usually exclude if it is an index, announcement, or contents list.",
        "other_scope_pattern": "Inspect title and source context before deciding.",
    }.get(family, "Inspect title and source context before deciding.")


def review_focus_for_family(family: str) -> str:
    return {
        "correction_erratum": "Confirm whether this row is only a correction, erratum, corrigendum, or retraction. Exclude nonresearch paratext; keep only if it contains substantive original research.",
        "supplement_or_data_files": "Confirm whether this is a supplement, data-file guide, code/program note, or appendix-only material. Exclude if it is not a standalone research article.",
        "society_election": "Confirm it is an election/fellows notice rather than a research article. These repeated society notices should generally leave the research denominator.",
        "referee_list": "Confirm it is a referee acknowledgement/list. These are editorial paratext and should not consume abstract-recovery time.",
        "society_governance": "Check whether this is association governance, annual-report, committee, or minutes material rather than research content.",
        "journal_frontmatter": "Check whether this is front matter, back matter, masthead, table of contents, or journal title metadata.",
        "comment_reply_discussion": "Apply the project denominator rule for comments, replies, and discussions. Mark unsure if substantive research content makes the denominator decision ambiguous.",
        "lecture_address": "Apply the project denominator rule for lectures and addresses. Mark unsure if this should be adjudicated before denominator changes.",
        "index_or_announcement": "Confirm whether this is only an index, announcement, forthcoming-papers list, books-received list, or volume contents.",
        "other_scope_pattern": "Review the title and any source context. Use unsure when the title pattern is not enough to decide the denominator.",
    }.get(family, "Review the title and any source context. Use unsure when the title pattern is not enough to decide the denominator.")


def scope_review_guide(packet: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if packet.empty:
        return pd.DataFrame(columns=GUIDE_COLUMNS), pd.DataFrame(columns=GUIDE_SUMMARY_COLUMNS)
    work = packet.copy().fillna("")
    if "human_scope_decision" not in work.columns:
        work["human_scope_decision"] = ""
    work["scope_pattern_family"] = work.apply(scope_pattern_family, axis=1)
    work["review_lens"] = work["scope_pattern_family"].map(review_lens_for_family)
    work["review_focus"] = work["scope_pattern_family"].map(review_focus_for_family)
    work["pattern_group_key"] = work["proposed_article_scope"].astype(str) + "|" + work["scope_pattern_family"].astype(str)
    group_sizes = work.groupby("pattern_group_key", dropna=False).size().to_dict()
    work["pattern_group_rows"] = work["pattern_group_key"].map(group_sizes).fillna(0).astype(int)
    guide = work[GUIDE_COLUMNS].copy()
    guide_summary = (
        work.assign(_completed=work["human_scope_decision"].astype(str).str.strip().ne(""))
        .groupby(["scope_pattern_family", "proposed_article_scope", "review_lens", "review_focus"], dropna=False)
        .agg(pattern_group_rows=("article_id", "count"), completed_decisions=("_completed", "sum"))
        .reset_index()
    )
    guide_summary["completed_decisions"] = guide_summary["completed_decisions"].astype(int)
    guide_summary["remaining_decisions"] = guide_summary["pattern_group_rows"].astype(int) - guide_summary["completed_decisions"].astype(int)
    return (
        guide[GUIDE_COLUMNS].reset_index(drop=True),
        guide_summary[GUIDE_SUMMARY_COLUMNS]
        .sort_values(["pattern_group_rows", "scope_pattern_family"], ascending=[False, True])
        .reset_index(drop=True),
    )


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


def count_table(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=columns + ["candidate_rows"])
    work = df.copy()
    for column in columns:
        if column not in work.columns:
            work[column] = ""
    return (
        work.groupby(columns, dropna=False)
        .size()
        .reset_index(name="candidate_rows")
        .sort_values(["candidate_rows"] + columns, ascending=[False] + [True] * len(columns))
        .reset_index(drop=True)
    )


def write_scope_review_report(path: Path, candidates: pd.DataFrame, summary: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    preview_columns = [
        "dataset",
        "article_id",
        "journal_short",
        "publication_year",
        "title",
        "doi",
        "current_article_scope",
        "proposed_article_scope",
        "proposed_scope_reason",
        "recovery_batch",
        "recovery_rank",
    ]
    preview = candidates[[column for column in preview_columns if column in candidates.columns]] if not candidates.empty else candidates
    lines = [
        "# Scope Review Audit",
        "",
        "This is a non-mutating audit. It does not change `causal_predictive_category`, manual validation labels, or source article files.",
        "",
        f"- Candidate rows: {len(candidates)}",
        f"- Unique candidate articles: {candidates['article_id'].nunique() if not candidates.empty and 'article_id' in candidates.columns else 0}",
        "",
        "## By Dataset",
        "",
        df_to_markdown(count_table(candidates, ["dataset"]), max_rows=20),
        "",
        "## By Proposed Scope",
        "",
        df_to_markdown(count_table(candidates, ["proposed_article_scope"]), max_rows=20),
        "",
        "## By Recovery Batch",
        "",
        df_to_markdown(count_table(candidates, ["recovery_batch"]), max_rows=30),
        "",
        "## Summary Detail",
        "",
        df_to_markdown(summary, max_rows=30),
        "",
        "## Candidate Preview",
        "",
        df_to_markdown(preview, max_rows=25),
        "",
        "## Next Command",
        "",
        "After human scope decisions are resolved, rerun:",
        "",
        "```bash",
        "PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_project_status.py",
        "PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_batch_workplan.py",
        "```",
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def scope_review_form_html(packet_df: pd.DataFrame, *, title: str) -> str:
    packet = packet_df.copy().fillna("")
    columns = list(packet.columns)
    rows = packet.to_dict(orient="records")
    payload = json.dumps({"columns": columns, "rows": rows}, ensure_ascii=False)
    title_text = html.escape(title)
    decision_options = "".join(f'<option value="{html.escape(decision)}">{html.escape(decision)}</option>' for decision in SCOPE_DECISIONS)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title_text}</title>
  <style>
    :root {{ color-scheme: light; --text: #1f2933; --muted: #667085; --line: #d7dce2; --panel: #f7f8fa; --accent: #215c5c; }}
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: var(--text); background: #fff; }}
    header {{ position: sticky; top: 0; z-index: 3; display: flex; justify-content: space-between; gap: 16px; align-items: center; padding: 14px 20px; border-bottom: 1px solid var(--line); background: rgba(255,255,255,.96); }}
    h1 {{ margin: 0; font-size: 18px; font-weight: 650; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 18px 20px 48px; }}
    .actions {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
    button {{ border: 1px solid var(--accent); background: var(--accent); color: white; padding: 8px 12px; border-radius: 6px; font-size: 14px; cursor: pointer; }}
    button.secondary {{ background: white; color: var(--accent); }}
    input, select, textarea {{ box-sizing: border-box; width: 100%; border: 1px solid var(--line); border-radius: 6px; padding: 7px 8px; font: inherit; font-size: 14px; background: #fff; }}
    textarea {{ min-height: 56px; resize: vertical; }}
    .bulk-input {{ width: 130px; }}
    .bulk-select {{ width: 220px; }}
    .status {{ font-size: 13px; color: var(--muted); }}
    .row.filtered {{ display: none; }}
    .rubric {{ display: grid; gap: 8px; margin: 0 0 16px; padding: 12px; border: 1px solid var(--line); border-radius: 8px; background: #fbfcfd; font-size: 13px; line-height: 1.4; color: #334155; }}
    .rubric-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 8px; }}
    .rubric strong {{ color: var(--text); font-weight: 650; }}
    .row {{ border: 1px solid var(--line); border-radius: 8px; margin: 14px 0; overflow: hidden; }}
    .row.issue {{ border-color: #d97706; }}
    .row-head {{ display: flex; justify-content: space-between; gap: 12px; padding: 10px 12px; background: var(--panel); border-bottom: 1px solid var(--line); font-size: 13px; color: var(--muted); }}
    .row-body {{ padding: 12px; }}
    .title {{ font-size: 16px; font-weight: 650; margin-bottom: 8px; }}
    .meta {{ color: var(--muted); font-size: 13px; line-height: 1.45; margin-bottom: 12px; }}
    .fields {{ display: grid; grid-template-columns: 220px 1fr 120px 130px; gap: 10px; align-items: start; }}
    label {{ display: block; font-size: 12px; color: var(--muted); margin-bottom: 4px; }}
    @media (max-width: 900px) {{ header {{ align-items: flex-start; flex-direction: column; }} .fields {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>{title_text}</h1>
      <div class="status" id="status"></div>
    </div>
    <div class="actions">
      <input id="bulk_reviewer" class="bulk-input" placeholder="reviewer_id">
      <button type="button" class="secondary" onclick="fillReviewer()">Set Reviewer</button>
      <button type="button" class="secondary" onclick="fillToday()">Set Today</button>
      <select id="priority_filter" class="bulk-select" aria-label="Review priority" onchange="applyFilters()"></select>
      <select id="bulk_family" class="bulk-select" aria-label="Pattern family"></select>
      <select id="bulk_decision" class="bulk-select" aria-label="Bulk decision">
        <option value=""></option>{decision_options}
      </select>
      <button type="button" class="secondary" onclick="fillFamilyDecision()">Fill Pattern Blanks</button>
      <button type="button" onclick="exportCsv()">Export CSV</button>
      <button type="button" class="secondary" onclick="saveLocal()">Save In Browser</button>
      <button type="button" class="secondary" onclick="loadLocal()">Load Saved</button>
    </div>
  </header>
  <main>
    <section class="rubric" aria-label="Scope decision rubric">
      <div><strong>Scope decision rule:</strong> decide whether the row belongs in the research-analysis denominator. Do not edit causal/predictive labels here.</div>
      <div class="rubric-grid">
        <div><strong>exclude_nonresearch:</strong> correction, erratum, retraction, referee list, society notice, supplement, data/code appendix, or other non-standalone paratext.</div>
        <div><strong>keep_research:</strong> substantive standalone research that should remain in the trend denominator.</div>
        <div><strong>unsure:</strong> title or metadata are not enough to decide; leave a note describing the ambiguity.</div>
        <div><strong>Before export:</strong> completed decisions need reviewer_id and review_date in YYYY-MM-DD format.</div>
        <div><strong>After export:</strong> run <code>PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_apply_scope_review_decisions.py</code> first; use <code>--apply</code> only after the dry-run report has zero errors.</div>
      </div>
    </section>
    <div id="rows"></div>
  </main>
  <script>
    const DATA = {payload};
    const DECISION_OPTIONS = `{decision_options}`;
    const STORAGE_KEY = "econqt-scope-review-" + location.pathname.split("/").pop();
    function escapeHtml(value) {{
      return String(value || "").replace(/[&<>"']/g, c => ({{"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#39;"}}[c]));
    }}
    function fieldId(rowIndex, field) {{ return `${{field}}_${{rowIndex}}`; }}
    function patternFamilies() {{
      const counts = new Map();
      DATA.rows.forEach(row => {{
        const family = row.scope_pattern_family || "missing_family";
        counts.set(family, (counts.get(family) || 0) + 1);
      }});
      return Array.from(counts.entries()).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
    }}
    function priorityGroups() {{
      const counts = new Map();
      DATA.rows.forEach(row => {{
        const priority = row.scope_review_priority || "missing_priority";
        counts.set(priority, (counts.get(priority) || 0) + 1);
      }});
      return Array.from(counts.entries());
    }}
    function renderPriorityFilter() {{
      const select = document.getElementById("priority_filter");
      select.innerHTML = '<option value="">all priorities</option>' + priorityGroups().map(([priority, count]) => `<option value="${{escapeHtml(priority)}}">${{escapeHtml(priority)}} (${{count}})</option>`).join("");
    }}
    function renderBulkFamilies() {{
      const select = document.getElementById("bulk_family");
      select.innerHTML = '<option value=""></option>' + patternFamilies().map(([family, count]) => `<option value="${{escapeHtml(family)}}">${{escapeHtml(family)}} (${{count}})</option>`).join("");
    }}
    function render() {{
      renderBulkFamilies();
      renderPriorityFilter();
      document.getElementById("rows").innerHTML = DATA.rows.map((row, index) => `
        <section class="row" id="${{fieldId(index, "row")}}">
          <div class="row-head">
            <span>${{escapeHtml(row.scope_review_id)}} · ${{escapeHtml(row.scope_review_priority || "")}} · ${{escapeHtml(row.article_id)}}</span>
            <span>${{escapeHtml(row.journal_short)}} · ${{escapeHtml(row.publication_year)}} · ${{escapeHtml(row.recovery_batches || "no recovery batch")}}</span>
          </div>
          <div class="row-body">
            <div class="title">${{escapeHtml(row.title)}}</div>
            <div class="meta">
              <div>Review priority: ${{escapeHtml(row.scope_review_priority || "")}}</div>
              <div>Current scope: ${{escapeHtml(row.current_article_scope || "missing")}}</div>
              <div>Proposed scope: ${{escapeHtml(row.proposed_article_scope)}} · ${{escapeHtml(row.proposed_scope_reason)}}</div>
              <div>Review guide: ${{escapeHtml(row.scope_pattern_family || "")}} · ${{escapeHtml(row.review_lens || "")}}</div>
              <div>${{escapeHtml(row.review_focus || "")}}</div>
              <div>Pattern group rows: ${{escapeHtml(row.pattern_group_rows || "")}}</div>
              <div>Datasets: ${{escapeHtml(row.appears_in_datasets)}} · category: ${{escapeHtml(row.causal_predictive_categories)}} · DOI: ${{escapeHtml(row.doi)}}</div>
            </div>
            <div class="fields">
              <div>
                <label for="${{fieldId(index, "human_scope_decision")}}">human_scope_decision</label>
                <select id="${{fieldId(index, "human_scope_decision")}}" data-row="${{index}}" data-field="human_scope_decision">
                  <option value=""></option>${{DECISION_OPTIONS}}
                </select>
              </div>
              <div>
                <label for="${{fieldId(index, "scope_review_notes")}}">scope_review_notes</label>
                <textarea id="${{fieldId(index, "scope_review_notes")}}" data-row="${{index}}" data-field="scope_review_notes"></textarea>
              </div>
              <div>
                <label for="${{fieldId(index, "reviewer_id")}}">reviewer_id</label>
                <input id="${{fieldId(index, "reviewer_id")}}" data-row="${{index}}" data-field="reviewer_id">
              </div>
              <div>
                <label for="${{fieldId(index, "review_date")}}">review_date</label>
                <input id="${{fieldId(index, "review_date")}}" data-row="${{index}}" data-field="review_date" placeholder="YYYY-MM-DD">
              </div>
            </div>
          </div>
        </section>`).join("");
      document.querySelectorAll("[data-field]").forEach(el => el.addEventListener("input", updateStatus));
      applyRowValues(DATA.rows);
      loadLocal();
      applyFilters();
    }}
    function collectRows() {{
      return DATA.rows.map((row, index) => {{
        const out = {{...row}};
        ["human_scope_decision", "scope_review_notes", "reviewer_id", "review_date"].forEach(field => {{
          const el = document.getElementById(fieldId(index, field));
          out[field] = el ? el.value.trim() : "";
        }});
        return out;
      }});
    }}
    function applyRowValues(rows) {{
      rows.forEach((row, index) => {{
        ["human_scope_decision", "scope_review_notes", "reviewer_id", "review_date"].forEach(field => {{
          const el = document.getElementById(fieldId(index, field));
          if (el) el.value = row[field] || "";
        }});
      }});
    }}
    function csvEscape(value) {{
      const text = String(value ?? "");
      return /[",\\n\\r]/.test(text) ? '"' + text.replace(/"/g, '""') + '"' : text;
    }}
    function formIssues(rows) {{
      const issues = [];
      rows.forEach((row, index) => {{
        const decision = row.human_scope_decision || "";
        if (decision && !row.reviewer_id) issues.push({{index, field: "reviewer_id", issue: "missing reviewer"}});
        if (decision && !row.review_date) issues.push({{index, field: "review_date", issue: "missing review date"}});
        if (row.review_date && !/^\\d{{4}}-\\d{{2}}-\\d{{2}}$/.test(row.review_date)) issues.push({{index, field: "review_date", issue: "date must be YYYY-MM-DD"}});
      }});
      return issues;
    }}
    function visibleRowCount() {{
      return Array.from(document.querySelectorAll(".row")).filter(row => !row.classList.contains("filtered")).length;
    }}
    function applyFilters() {{
      const priority = document.getElementById("priority_filter").value;
      DATA.rows.forEach((row, index) => {{
        const el = document.getElementById(fieldId(index, "row"));
        if (!el) return;
        const hidden = priority && (row.scope_review_priority || "missing_priority") !== priority;
        el.classList.toggle("filtered", Boolean(hidden));
      }});
      updateStatus();
    }}
    function updateStatus() {{
      const rows = collectRows();
      const completed = rows.filter(row => row.human_scope_decision).length;
      const issues = formIssues(rows);
      document.getElementById("status").textContent = `${{completed}} / ${{rows.length}} decisions completed · ${{visibleRowCount()}} shown` + (issues.length ? ` · ${{issues.length}} QA issues` : "");
      document.querySelectorAll(".row").forEach(row => row.classList.remove("issue"));
      issues.forEach(issue => document.getElementById(fieldId(issue.index, "row"))?.classList.add("issue"));
    }}
    function saveLocal() {{ localStorage.setItem(STORAGE_KEY, JSON.stringify(collectRows())); updateStatus(); }}
    function loadLocal() {{
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
      if (Array.isArray(saved)) applyRowValues(saved);
      updateStatus();
    }}
    function fillReviewer() {{
      const reviewer = document.getElementById("bulk_reviewer").value.trim();
      if (!reviewer) return;
      document.querySelectorAll('[data-field="reviewer_id"]').forEach(el => {{ if (!el.value) el.value = reviewer; }});
      updateStatus();
    }}
    function fillToday() {{
      const today = new Date().toISOString().slice(0, 10);
      document.querySelectorAll('[data-field="review_date"]').forEach(el => {{ if (!el.value) el.value = today; }});
      updateStatus();
    }}
    function fillFamilyDecision() {{
      const family = document.getElementById("bulk_family").value;
      const decision = document.getElementById("bulk_decision").value;
      if (!family || !decision) return;
      let filled = 0;
      DATA.rows.forEach((row, index) => {{
        if ((row.scope_pattern_family || "missing_family") !== family) return;
        const decisionEl = document.getElementById(fieldId(index, "human_scope_decision"));
        if (decisionEl && !decisionEl.value) {{
          decisionEl.value = decision;
          filled += 1;
        }}
      }});
      if (filled) {{
        saveLocal();
      }} else {{
        updateStatus();
      }}
    }}
    function exportCsv() {{
      const rows = collectRows();
      const issues = formIssues(rows);
      if (issues.length && !confirm(`${{issues.length}} QA issues found. Export anyway?`)) return;
      const columns = DATA.columns;
      const csv = [columns.join(","), ...rows.map(row => columns.map(column => csvEscape(row[column] ?? "")).join(","))].join("\\n");
      const blob = new Blob([csv], {{type: "text/csv"}});
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "scope_review_packet.csv";
      a.click();
      URL.revokeObjectURL(url);
    }}
    render();
  </script>
</body>
</html>
"""


def write_scope_review_guide_report(path: Path, guide: pd.DataFrame, guide_summary: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Scope Review Guide",
        "",
        "This guide is non-mutating. It groups repeated title-pattern cases to help reviewers work faster, but it does not make or apply scope decisions.",
        "",
        "## Pattern Groups",
        "",
        df_to_markdown(guide_summary, max_rows=30),
        "",
        "## Row Guide",
        "",
        df_to_markdown(guide, max_rows=70),
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_scope_review_packet_report(
    path: Path,
    packet: pd.DataFrame,
    completion: pd.DataFrame,
    *,
    packet_path: Path,
    form_path: Path,
    guide_summary: pd.DataFrame | None = None,
    guide_report_path: Path | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lookup = dict(zip(completion["metric"], completion["value"])) if not completion.empty else {}
    decision_counts = completion[completion["metric"].astype(str).str.startswith("decision_")].copy() if not completion.empty else pd.DataFrame()
    preview_columns = [
        "scope_review_id",
        "scope_review_priority",
        "article_id",
        "journal_short",
        "publication_year",
        "title",
        "proposed_article_scope",
        "proposed_scope_reason",
        "recovery_batches",
        "human_scope_decision",
    ]
    preview = packet[[column for column in preview_columns if column in packet.columns]] if not packet.empty else packet
    priority_counts = count_table(packet, ["scope_review_priority"]) if not packet.empty and "scope_review_priority" in packet.columns else pd.DataFrame()
    lines = [
        "# Scope Review Packet",
        "",
        "Use this packet to decide whether candidate rows belong in the research-analysis denominator. Do not edit causal/predictive labels here.",
        "",
        f"- Packet CSV: `{packet_path}`",
        f"- Browser form: `{form_path}`",
        f"- Completed decisions: {lookup.get('completed_scope_review_decisions', '0')} / {lookup.get('scope_review_rows', '0')}",
        f"- Remaining decisions: {lookup.get('remaining_scope_review_decisions', '0')}",
        f"- First incomplete row: `{lookup.get('first_incomplete_scope_review_id', '')}`",
        "",
        "Allowed decisions: `exclude_nonresearch`, `keep_research`, `unsure`.",
        "",
        "## Decision Rubric",
        "",
        *[f"- {item}" for item in SCOPE_DECISION_RUBRIC],
        "",
        "## Decision Counts",
        "",
        df_to_markdown(decision_counts, max_rows=10),
        "",
        "## Review Priority",
        "",
        df_to_markdown(priority_counts, max_rows=10),
        "",
        "## After Export Commands",
        "",
        *[f"- {item}" for item in SCOPE_AFTER_EXPORT_COMMANDS],
        "",
        "## Review Pattern Guide",
        "",
        df_to_markdown(guide_summary if guide_summary is not None else pd.DataFrame(), max_rows=20),
        "",
        f"Full guide: `{guide_report_path}`" if guide_report_path is not None else "",
        "",
        "## Packet Preview",
        "",
        df_to_markdown(preview, max_rows=30),
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("") if path.exists() else pd.DataFrame()


def run_scope_review_audit(
    *,
    classified_path: Path,
    recovery_queue_path: Path,
    active_batch_path: Path | None,
    config_path: Path,
    output_candidates: Path,
    output_summary: Path,
    report_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    config = load_yaml(config_path) if config_path.exists() else {}
    patterns = config.get("article_scope_patterns", {}) or {}
    datasets = {
        "classified_file": read_csv_if_exists(classified_path),
        "recovery_queue": read_csv_if_exists(recovery_queue_path),
    }
    if active_batch_path is not None:
        datasets["active_batch"] = read_csv_if_exists(active_batch_path)

    candidates = scope_review_candidates(datasets, scope_patterns=patterns)
    summary = scope_review_summary(candidates)
    output_candidates.parent.mkdir(parents=True, exist_ok=True)
    output_summary.parent.mkdir(parents=True, exist_ok=True)
    candidates.to_csv(output_candidates, index=False)
    summary.to_csv(output_summary, index=False)
    write_scope_review_report(report_path, candidates, summary)
    print(f"scope_review_candidates={len(candidates)}")
    if not candidates.empty:
        print(candidates["dataset"].value_counts(dropna=False).to_string())
    print(f"candidates={output_candidates}")
    print(f"summary={output_summary}")
    print(f"report={report_path}")
    return candidates, summary


def run_scope_review_packet(
    *,
    candidates_path: Path,
    existing_packet_path: Path | None,
    output_packet: Path,
    output_completion: Path,
    output_form: Path,
    output_guide: Path | None = None,
    output_guide_summary: Path | None = None,
    guide_report_path: Path | None = None,
    report_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    candidates = read_csv_if_exists(candidates_path)
    existing_packet = read_csv_if_exists(existing_packet_path) if existing_packet_path is not None else pd.DataFrame()
    packet = scope_review_packet(candidates, existing_packet=existing_packet)
    completion = scope_review_completion_summary(packet)
    guide, guide_summary = scope_review_guide(packet)
    packet_for_form = packet.merge(guide, on=["scope_review_id", "article_id"], how="left") if not packet.empty else packet.copy()
    output_packet.parent.mkdir(parents=True, exist_ok=True)
    output_completion.parent.mkdir(parents=True, exist_ok=True)
    output_form.parent.mkdir(parents=True, exist_ok=True)
    packet.to_csv(output_packet, index=False)
    completion.to_csv(output_completion, index=False)
    if output_guide is not None:
        output_guide.parent.mkdir(parents=True, exist_ok=True)
        guide.to_csv(output_guide, index=False)
    if output_guide_summary is not None:
        output_guide_summary.parent.mkdir(parents=True, exist_ok=True)
        guide_summary.to_csv(output_guide_summary, index=False)
    if guide_report_path is not None:
        write_scope_review_guide_report(guide_report_path, guide, guide_summary)
    output_form.write_text(scope_review_form_html(packet_for_form, title="Scope Review Packet"), encoding="utf-8")
    write_scope_review_packet_report(
        report_path,
        packet,
        completion,
        packet_path=output_packet,
        form_path=output_form,
        guide_summary=guide_summary,
        guide_report_path=guide_report_path,
    )
    print(f"scope_review_rows={len(packet)}")
    lookup = dict(zip(completion["metric"], completion["value"])) if not completion.empty else {}
    print(f"completed_scope_review_decisions={lookup.get('completed_scope_review_decisions', '0')}")
    print(f"remaining_scope_review_decisions={lookup.get('remaining_scope_review_decisions', '0')}")
    print(f"packet={output_packet}")
    print(f"form={output_form}")
    print(f"completion={output_completion}")
    print(f"report={report_path}")
    return packet, completion


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--classified", default="data/final/articles_classified_enriched_pilot.csv")
    parser.add_argument("--recovery-queue", default="outputs/tables/enriched/insufficient_text_recovery_queue.csv")
    parser.add_argument("--active-batch", default="data/intermediate/insufficient_text_recovery_batches/insufficient_text_recovery_batch_R001.csv")
    parser.add_argument("--config", default="config/text_enrichment.yml")
    parser.add_argument("--output-candidates", default="outputs/tables/enriched/scope_review_candidates.csv")
    parser.add_argument("--output-summary", default="outputs/tables/enriched/scope_review_summary.csv")
    parser.add_argument("--report", default="docs/scope_review_audit.md")
    args = parser.parse_args()
    run_scope_review_audit(
        classified_path=Path(args.classified),
        recovery_queue_path=Path(args.recovery_queue),
        active_batch_path=Path(args.active_batch) if args.active_batch else None,
        config_path=Path(args.config),
        output_candidates=Path(args.output_candidates),
        output_summary=Path(args.output_summary),
        report_path=Path(args.report),
    )


if __name__ == "__main__":
    main()
