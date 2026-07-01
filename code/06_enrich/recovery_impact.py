from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "lib"))
sys.path.append(str(Path(__file__).resolve().parent))

from econqt_common import clean_text  # noqa: E402
from insufficient_text_expansion import doi_prefix_family, expansion_lane  # noqa: E402


SNAPSHOT_COLUMNS = [
    "snapshot_label",
    "article_id",
    "journal_short",
    "publication_year",
    "decade",
    "title",
    "doi",
    "causal_predictive_category",
    "classification_text_chars",
    "has_usable_classification_text",
    "abstract_source",
    "text_enrichment_status",
    "recovery_rank",
    "recovery_batch",
    "recovery_priority",
    "recovery_action",
    "expansion_lane",
    "route_unit",
    "current_route_status",
    "source_route_note",
    "import_source_file",
]

CHANGE_COLUMNS = [
    "article_id",
    "journal_short",
    "publication_year",
    "decade",
    "title",
    "before_category",
    "after_category",
    "before_text_chars",
    "after_text_chars",
    "recovered_from_insufficient",
    "newly_insufficient",
    "before_recovery_batch",
    "before_recovery_action",
    "before_expansion_lane",
    "before_route_unit",
    "after_abstract_source",
    "after_text_enrichment_status",
    "import_source_file",
]

SUMMARY_COLUMNS = [
    "summary_group",
    "summary_value",
    "total_rows",
    "before_insufficient_rows",
    "after_insufficient_rows",
    "recovered_rows",
    "newly_insufficient_rows",
    "net_insufficient_change",
    "median_after_text_chars",
]

EXPERIMENT_COLUMNS = [
    "experiment_rank",
    "experiment_id",
    "experiment_type",
    "route_unit",
    "target_journal_short",
    "target_decade",
    "candidate_rows",
    "ready_rows",
    "expected_payoff",
    "source_artifact",
    "start_rule",
    "success_rule",
    "stop_rule",
    "next_command_or_packet",
]


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("") if path.exists() else pd.DataFrame()


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


def numeric_value(value: Any, default: int = 0) -> int:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return default if pd.isna(parsed) else int(parsed)


def numeric_column(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(0, index=df.index, dtype="int64")
    return pd.to_numeric(df[column], errors="coerce").fillna(0).astype(int)


def nonempty(value: Any) -> bool:
    return clean_text(value) != ""


def decade_from_year(value: Any) -> str:
    year = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(year):
        return ""
    return str(int(year) // 10 * 10)


def yes_no(value: Any) -> str:
    text = clean_text(value).lower()
    if text in {"true", "1", "yes", "y"}:
        return "yes"
    if text in {"false", "0", "no", "n"}:
        return "no"
    return clean_text(value)


def dedupe_by_article_id(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "article_id" not in df.columns:
        return pd.DataFrame()
    work = df.copy().fillna("")
    work = work[work["article_id"].astype(str).str.strip().ne("")]
    return work.drop_duplicates("article_id", keep="first").reset_index(drop=True)


def import_source_lookup(import_history: pd.DataFrame) -> dict[str, str]:
    if import_history.empty or "article_id" not in import_history.columns or "import_source_file" not in import_history.columns:
        return {}
    work = import_history.copy().fillna("")
    work = work[work["article_id"].astype(str).str.strip().ne("")]
    work = work[work["import_source_file"].astype(str).str.strip().ne("")]
    if work.empty:
        return {}
    latest = work.drop_duplicates("article_id", keep="last")
    return dict(zip(latest["article_id"].astype(str), latest["import_source_file"].astype(str)))


def route_lookup(route_matrix: pd.DataFrame) -> dict[str, dict[str, str]]:
    if route_matrix.empty or "route_unit" not in route_matrix.columns:
        return {}
    work = route_matrix.copy().fillna("")
    lookup: dict[str, dict[str, str]] = {}
    for _, row in work.iterrows():
        unit = clean_text(row.get("route_unit"))
        if unit:
            lookup[unit] = {column: clean_text(row.get(column)) for column in work.columns}
    return lookup


def route_unit_for_row(row: pd.Series, routes: dict[str, dict[str, str]]) -> tuple[str, dict[str, str]]:
    lane = expansion_lane(row)
    prefix = doi_prefix_family(row.get("doi", ""))
    candidates = [prefix, lane]
    for candidate in candidates:
        if candidate and candidate in routes:
            return candidate, routes[candidate]
    for unit, route in routes.items():
        if clean_text(route.get("unit_type")) == "expansion_lane" and unit == lane:
            return unit, route
    fallback = prefix or lane
    return fallback, {}


def snapshot_sort_key(row: dict[str, Any]) -> tuple[int, str, str]:
    return (
        numeric_value(row.get("recovery_rank"), 999999),
        clean_text(row.get("journal_short")),
        clean_text(row.get("article_id")),
    )


def recovery_snapshot(
    classified_df: pd.DataFrame,
    recovery_queue: pd.DataFrame,
    route_matrix: pd.DataFrame,
    import_history: pd.DataFrame | None = None,
    *,
    snapshot_label: str,
    include_article_ids: set[str] | None = None,
) -> pd.DataFrame:
    if classified_df.empty and recovery_queue.empty:
        return pd.DataFrame(columns=SNAPSHOT_COLUMNS)

    classified = dedupe_by_article_id(classified_df)
    queue = dedupe_by_article_id(recovery_queue)
    classified_lookup = classified.set_index("article_id", drop=False).to_dict(orient="index") if not classified.empty else {}
    queue_lookup = queue.set_index("article_id", drop=False).to_dict(orient="index") if not queue.empty else {}
    universe = set(queue_lookup)
    if include_article_ids:
        universe.update(article_id for article_id in include_article_ids if clean_text(article_id))
    if not universe and classified_lookup:
        universe = set(classified_lookup)

    routes = route_lookup(route_matrix)
    source_lookup = import_source_lookup(import_history if import_history is not None else pd.DataFrame())
    rows: list[dict[str, Any]] = []
    for article_id in universe:
        article = classified_lookup.get(article_id, {})
        queue_row = queue_lookup.get(article_id, {})
        row_source = {**article, **queue_row}
        route_unit, route = route_unit_for_row(pd.Series(row_source), routes) if row_source else ("", {})
        publication_year = clean_text(article.get("publication_year") or queue_row.get("publication_year"))
        classification_text_chars = clean_text(article.get("classification_text_chars"))
        if not classification_text_chars:
            classification_text_chars = clean_text(queue_row.get("current_text_chars"))
        rows.append(
            {
                "snapshot_label": snapshot_label,
                "article_id": article_id,
                "journal_short": clean_text(article.get("journal_short") or queue_row.get("journal_short")),
                "publication_year": publication_year,
                "decade": decade_from_year(publication_year) or clean_text(queue_row.get("decade")),
                "title": clean_text(article.get("title") or queue_row.get("title")),
                "doi": clean_text(article.get("doi") or queue_row.get("doi")),
                "causal_predictive_category": clean_text(article.get("causal_predictive_category")),
                "classification_text_chars": classification_text_chars,
                "has_usable_classification_text": yes_no(article.get("has_usable_classification_text")),
                "abstract_source": clean_text(article.get("abstract_source") or article.get("text_enrichment_source") or queue_row.get("abstract_source")),
                "text_enrichment_status": clean_text(article.get("text_enrichment_status") or queue_row.get("text_enrichment_status")),
                "recovery_rank": clean_text(queue_row.get("recovery_rank")),
                "recovery_batch": clean_text(queue_row.get("recovery_batch")),
                "recovery_priority": clean_text(queue_row.get("recovery_priority")),
                "recovery_action": clean_text(queue_row.get("recovery_action")),
                "expansion_lane": expansion_lane(pd.Series(row_source)) if row_source else "",
                "route_unit": route_unit,
                "current_route_status": clean_text(route.get("current_route_status")),
                "source_route_note": clean_text(route.get("source_route_note")),
                "import_source_file": source_lookup.get(article_id, ""),
            }
        )
    rows.sort(key=snapshot_sort_key)
    return pd.DataFrame(rows, columns=SNAPSHOT_COLUMNS)


def comparison_frame(before: pd.DataFrame, after: pd.DataFrame) -> pd.DataFrame:
    before_work = before.copy().fillna("")
    after_work = after.copy().fillna("")
    if before_work.empty or "article_id" not in before_work.columns:
        return pd.DataFrame()
    if after_work.empty:
        after_work = pd.DataFrame(columns=SNAPSHOT_COLUMNS)
    before_work = before_work.drop_duplicates("article_id", keep="first")
    after_work = after_work.drop_duplicates("article_id", keep="first")
    return before_work.merge(after_work, on="article_id", how="left", suffixes=("_before", "_after")).fillna("")


def recovery_impact_changes(before: pd.DataFrame, after: pd.DataFrame) -> pd.DataFrame:
    combined = comparison_frame(before, after)
    if combined.empty:
        return pd.DataFrame(columns=CHANGE_COLUMNS)
    rows: list[dict[str, Any]] = []
    for _, row in combined.iterrows():
        before_category = clean_text(row.get("causal_predictive_category_before"))
        after_category = clean_text(row.get("causal_predictive_category_after"))
        before_insufficient = before_category == "insufficient_text"
        after_insufficient = after_category == "insufficient_text"
        changed_state = before_insufficient != after_insufficient
        changed_category = before_category != after_category and (before_insufficient or after_insufficient)
        if not changed_state and not changed_category:
            continue
        rows.append(
            {
                "article_id": clean_text(row.get("article_id")),
                "journal_short": clean_text(row.get("journal_short_before") or row.get("journal_short_after")),
                "publication_year": clean_text(row.get("publication_year_before") or row.get("publication_year_after")),
                "decade": clean_text(row.get("decade_before") or row.get("decade_after")),
                "title": clean_text(row.get("title_before") or row.get("title_after")),
                "before_category": before_category,
                "after_category": after_category,
                "before_text_chars": clean_text(row.get("classification_text_chars_before")),
                "after_text_chars": clean_text(row.get("classification_text_chars_after")),
                "recovered_from_insufficient": str(before_insufficient and not after_insufficient),
                "newly_insufficient": str((not before_insufficient) and after_insufficient),
                "before_recovery_batch": clean_text(row.get("recovery_batch_before")),
                "before_recovery_action": clean_text(row.get("recovery_action_before")),
                "before_expansion_lane": clean_text(row.get("expansion_lane_before")),
                "before_route_unit": clean_text(row.get("route_unit_before")),
                "after_abstract_source": clean_text(row.get("abstract_source_after")),
                "after_text_enrichment_status": clean_text(row.get("text_enrichment_status_after")),
                "import_source_file": clean_text(row.get("import_source_file_after") or row.get("import_source_file_before")),
            }
        )
    return pd.DataFrame(rows, columns=CHANGE_COLUMNS)


def summarize_comparison(combined: pd.DataFrame, group_column: str, group_label: str) -> pd.DataFrame:
    if combined.empty:
        return pd.DataFrame(columns=SUMMARY_COLUMNS)
    work = combined.copy().fillna("")
    if group_column:
        work["_summary_value"] = work[group_column].replace("", "(blank)") if group_column in work.columns else "(missing)"
    else:
        work["_summary_value"] = "all"
    rows: list[dict[str, Any]] = []
    for value, group in work.groupby("_summary_value", dropna=False):
        before_insufficient = group["causal_predictive_category_before"].astype(str).eq("insufficient_text")
        after_insufficient = group["causal_predictive_category_after"].astype(str).eq("insufficient_text")
        after_chars = pd.to_numeric(group.get("classification_text_chars_after", ""), errors="coerce").dropna()
        rows.append(
            {
                "summary_group": group_label,
                "summary_value": clean_text(value),
                "total_rows": len(group),
                "before_insufficient_rows": int(before_insufficient.sum()),
                "after_insufficient_rows": int(after_insufficient.sum()),
                "recovered_rows": int((before_insufficient & ~after_insufficient).sum()),
                "newly_insufficient_rows": int((~before_insufficient & after_insufficient).sum()),
                "net_insufficient_change": int(after_insufficient.sum() - before_insufficient.sum()),
                "median_after_text_chars": int(after_chars.median()) if len(after_chars) else 0,
            }
        )
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


def recovery_impact_summary(before: pd.DataFrame, after: pd.DataFrame) -> pd.DataFrame:
    combined = comparison_frame(before, after)
    if combined.empty:
        return pd.DataFrame(columns=SUMMARY_COLUMNS)
    groups = [
        ("", "overall"),
        ("journal_short_before", "journal_short"),
        ("decade_before", "decade"),
        ("recovery_batch_before", "before_recovery_batch"),
        ("recovery_action_before", "before_recovery_action"),
        ("expansion_lane_before", "before_expansion_lane"),
        ("route_unit_before", "before_route_unit"),
        ("import_source_file_after", "import_source_file"),
    ]
    frames = [summarize_comparison(combined, column, label) for column, label in groups]
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=SUMMARY_COLUMNS)
    out["_sort_recovered"] = pd.to_numeric(out["recovered_rows"], errors="coerce").fillna(0).astype(int)
    out["_sort_total"] = pd.to_numeric(out["total_rows"], errors="coerce").fillna(0).astype(int)
    return out.sort_values(["summary_group", "_sort_recovered", "_sort_total", "summary_value"], ascending=[True, False, False, True]).drop(columns=["_sort_recovered", "_sort_total"]).reset_index(drop=True)


def current_summary(snapshot: pd.DataFrame) -> pd.DataFrame:
    if snapshot.empty:
        return pd.DataFrame(columns=SUMMARY_COLUMNS)
    work = snapshot.copy().fillna("")
    return recovery_impact_summary(work, work)


def count_review_rows(review_queue: pd.DataFrame, *, split_group: str = "", quick_win_tiers: set[str] | None = None) -> int:
    if review_queue.empty:
        return 0
    work = review_queue.copy().fillna("")
    if split_group and "split_group" in work.columns:
        work = work[work["split_group"].astype(str).eq(split_group)].copy()
    elif split_group:
        return 0
    if quick_win_tiers is not None and "quick_win_tier" in work.columns:
        work = work[work["quick_win_tier"].astype(str).isin(quick_win_tiers)].copy()
    return len(work)


def top_profile_cell(profile: pd.DataFrame, route_rows: pd.DataFrame | None = None) -> tuple[str, str]:
    work = profile.copy().fillna("") if profile is not None else pd.DataFrame()
    if work.empty:
        return "", ""
    work["_insufficient_rows"] = pd.to_numeric(work.get("insufficient_rows", ""), errors="coerce").fillna(0).astype(int)
    top = work.sort_values(["_insufficient_rows", "journal_short", "decade"], ascending=[False, True, True]).iloc[0]
    return clean_text(top.get("journal_short")), clean_text(top.get("decade"))


def experiment_row(
    *,
    experiment_rank: int,
    experiment_id: str,
    experiment_type: str,
    route_unit: str,
    target_journal_short: str,
    target_decade: str,
    candidate_rows: int,
    ready_rows: int,
    expected_payoff: str,
    source_artifact: str,
    start_rule: str,
    success_rule: str,
    stop_rule: str,
    next_command_or_packet: str,
) -> dict[str, Any]:
    return {
        "experiment_rank": experiment_rank,
        "experiment_id": experiment_id,
        "experiment_type": experiment_type,
        "route_unit": route_unit,
        "target_journal_short": target_journal_short,
        "target_decade": target_decade,
        "candidate_rows": candidate_rows,
        "ready_rows": ready_rows,
        "expected_payoff": expected_payoff,
        "source_artifact": source_artifact,
        "start_rule": start_rule,
        "success_rule": success_rule,
        "stop_rule": stop_rule,
        "next_command_or_packet": next_command_or_packet,
    }


def recovery_source_experiments(
    recovery_queue: pd.DataFrame,
    route_matrix: pd.DataFrame,
    review_queue: pd.DataFrame,
    split_summary: pd.DataFrame | None = None,
    remaining_profile: pd.DataFrame | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    rank = 1
    partial_rows = count_review_rows(review_queue, split_group="ready_partial_text_extension")
    partial_tier1 = count_review_rows(review_queue, split_group="ready_partial_text_extension", quick_win_tiers={"tier_1_partial_near_threshold"})
    partial_suspect = count_review_rows(review_queue, split_group="ready_partial_text_extension", quick_win_tiers={"tier_2_partial_replace_suspect_text"})
    partial_deeper = count_review_rows(review_queue, split_group="ready_partial_text_extension", quick_win_tiers={"tier_3_partial_extension"})
    if partial_rows:
        rows.append(
            experiment_row(
                experiment_rank=rank,
                experiment_id="R001_partial_extension",
                experiment_type="manual_partial_extension",
                route_unit="partial_short_text_extension",
                target_journal_short="multiple",
                target_decade="multiple",
                candidate_rows=partial_rows,
                ready_rows=partial_rows,
                expected_payoff=f"{partial_tier1} clean near-threshold rows can be extended quickly; {partial_suspect} suspect boilerplate rows need replacement text; {partial_deeper} more partial rows are source-guided.",
                source_artifact="docs/recovery_batch_R001_review_queue.md",
                start_rule="Start with clean tier_1_partial_near_threshold rows; replace tier_2_partial_replace_suspect_text rows from explicit source metadata rather than extending boilerplate.",
                success_rule="A completed row has abstract text plus source, source_url or source_record_id, importable evidence_tier, and reaches the usable-text threshold after reclassification.",
                stop_rule="Pause imports if any filled row lacks source metadata or importable evidence_tier.",
                next_command_or_packet="data/intermediate/insufficient_text_recovery_splits/R001/insufficient_text_recovery_batch_R001_ready_partial_text_extension.csv",
            )
        )
        rank += 1

    manual_rows = count_review_rows(review_queue, split_group="ready_manual_metadata")
    if manual_rows:
        rows.append(
            experiment_row(
                experiment_rank=rank,
                experiment_id="R001_manual_metadata",
                experiment_type="manual_metadata_backfill",
                route_unit="manual_metadata",
                target_journal_short="multiple",
                target_decade="multiple",
                candidate_rows=manual_rows,
                ready_rows=manual_rows,
                expected_payoff="Source-confirmed abstracts can recover rows where existing automated routes are blocked or unsupported.",
                source_artifact="docs/recovery_batch_R001_review_queue.md",
                start_rule="Use DOI, publisher, index, or title-match metadata; do not retry blocked PDFs unchanged.",
                success_rule="A completed row has explicit abstract text, source provenance, and importable evidence_tier accepted by the split preflight.",
                stop_rule="Stop on source-incomplete filled rows, missing/non-importable evidence_tier, or if matches are title-only without an explicit abstract.",
                next_command_or_packet="data/intermediate/insufficient_text_recovery_splits/R001/insufficient_text_recovery_batch_R001_ready_manual_metadata.csv",
            )
        )
        rank += 1

    split_summary = split_summary if split_summary is not None else pd.DataFrame()
    waiting_scope_rows = 0
    if not split_summary.empty and "split_group" in split_summary.columns:
        split_work = split_summary.copy().fillna("")
        split_work["_rows"] = pd.to_numeric(split_work.get("rows", ""), errors="coerce").fillna(0).astype(int)
        waiting_scope_rows = int(split_work[split_work["split_group"].astype(str).eq("waiting_scope_review")]["_rows"].sum())
    if waiting_scope_rows:
        rows.append(
            experiment_row(
                experiment_rank=rank,
                experiment_id="R001_scope_gate",
                experiment_type="scope_gate",
                route_unit="scope_review",
                target_journal_short="multiple",
                target_decade="multiple",
                candidate_rows=waiting_scope_rows,
                ready_rows=0,
                expected_payoff="Prevents likely nonresearch/parataxt rows from consuming abstract-recovery time.",
                source_artifact="docs/scope_review_packet.md",
                start_rule="Complete scope decisions before spending recovery time on waiting_scope_review rows.",
                success_rule="Each row has keep_research, exclude_nonresearch, or unsure recorded with reviewer metadata.",
                stop_rule="Do not recover abstracts for rows marked exclude_nonresearch unless the scope decision changes.",
                next_command_or_packet="data/intermediate/scope_review/scope_review_packet.csv",
            )
        )
        rank += 1

    route_work = route_matrix.copy().fillna("") if not route_matrix.empty else pd.DataFrame()
    if not route_work.empty:
        route_work["_row_count"] = pd.to_numeric(route_work.get("row_count", ""), errors="coerce").fillna(0).astype(int)
        if "current_route_status" not in route_work.columns:
            route_work = pd.DataFrame()
        else:
            route_work = route_work[
                route_work["current_route_status"].astype(str).isin(
                {
                    "unsupported_existing_route",
                    "do_not_rerun_landing_pages",
                    "source_specific_probe_needed",
                    "candidate_public_route_found",
                    "candidate_route_requires_parser_or_url_update",
                }
                )
            ].copy()
        if not route_work.empty and "route_unit" in route_work.columns:
            route_work = route_work.sort_values(["_row_count", "route_unit"], ascending=[False, True])
        for _, route in route_work.head(6).iterrows() if not route_work.empty else []:
            route_unit = clean_text(route.get("route_unit"))
            status = clean_text(route.get("current_route_status"))
            candidate_rows = numeric_value(route.get("row_count"), 0)
            journal, decade = top_profile_cell(remaining_profile if remaining_profile is not None else pd.DataFrame())
            found_public = status in {"candidate_public_route_found", "candidate_route_requires_parser_or_url_update", "source_specific_probe_needed"}
            rows.append(
                experiment_row(
                    experiment_rank=rank,
                    experiment_id=f"template_spike_{route_unit.replace('/', '_').replace('.', '_')}",
                    experiment_type="source_template_spike",
                    route_unit=route_unit,
                    target_journal_short=journal,
                    target_decade=decade,
                    candidate_rows=candidate_rows,
                    ready_rows=0,
                    expected_payoff=f"{candidate_rows} candidate rows, but route status is {status}.",
                    source_artifact=clean_text(route.get("next_artifact")),
                    start_rule="Start only with a bounded public metadata probe or parser patch; do not run a broad landing-page pass.",
                    success_rule="At least one sampled public route yields an explicit abstract or PDF candidate without access challenges.",
                    stop_rule="If 10 representative URLs produce 0 abstracts/PDF candidates or mostly access challenges, do not scale this route.",
                    next_command_or_packet=(
                        clean_text(route.get("next_artifact"))
                        if not found_public
                        else f"PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_text_enrichment.py --sources publisher_metadata --doi-prefixes {route_unit} --max-queries 25"
                    ),
                )
            )
            rank += 1

    if not recovery_queue.empty:
        queue = recovery_queue.copy().fillna("")
        doi_rows = int(queue["doi"].astype(str).str.strip().ne("").sum()) if "doi" in queue.columns else len(queue)
        openalex_rows = int(queue["openalex_id"].astype(str).str.strip().ne("").sum()) if "openalex_id" in queue.columns else len(queue)
        rows.append(
            experiment_row(
                experiment_rank=rank,
                experiment_id="credentialed_unpaywall",
                experiment_type="credentialed_api_pass",
                route_unit="unpaywall",
                target_journal_short="multiple",
                target_decade="multiple",
                candidate_rows=doi_rows,
                ready_rows=0,
                expected_payoff="May expose OA PDF URLs for DOI rows, but requires a real contact email.",
                source_artifact="data/intermediate/text_enrichment_attempts.csv",
                start_rule="Run only after CONTACT_EMAIL, CROSSREF_MAILTO, or OPENALEX_MAILTO is set.",
                success_rule="Recovered rows have explicit OA metadata and pass PDF/text extraction or abstract import checks.",
                stop_rule="Stop if responses only add blocked PDF URLs or no usable OA locations.",
                next_command_or_packet="PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_text_enrichment.py --sources unpaywall --limit 1000 --max-queries 1000",
            )
        )
        rank += 1
        rows.append(
            experiment_row(
                experiment_rank=rank,
                experiment_id="credentialed_semantic_scholar",
                experiment_type="credentialed_api_pass",
                route_unit="semantic_scholar",
                target_journal_short="multiple",
                target_decade="multiple",
                candidate_rows=openalex_rows,
                ready_rows=0,
                expected_payoff="May reduce rate-limit failures for DOI/OpenAlex rows if an API key is available.",
                source_artifact="data/intermediate/text_enrichment_attempts.csv",
                start_rule="Run only after SEMANTIC_SCHOLAR_API_KEY is available or use very small batches.",
                success_rule="Recovered rows have explicit abstracts and source_record_id values.",
                stop_rule="Stop on repeated 429 rate limits; do not switch to broad title search without a separate review.",
                next_command_or_packet="PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_text_enrichment.py --sources semantic_scholar --limit 1000 --max-queries 1000",
            )
        )

    if not rows:
        return pd.DataFrame(columns=EXPERIMENT_COLUMNS)
    return pd.DataFrame(rows, columns=EXPERIMENT_COLUMNS)


def snapshot_filename(label: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", clean_text(label) or "current").strip("._")
    return f"{safe or 'current'}.csv"


def resolve_snapshot_path(value: str, snapshot_dir: Path) -> Path:
    text = clean_text(value)
    if not text:
        return Path()
    path = Path(text)
    if path.exists():
        return path
    return snapshot_dir / snapshot_filename(text)


def write_recovery_impact_report(
    path: Path,
    *,
    snapshot: pd.DataFrame,
    summary: pd.DataFrame,
    changes: pd.DataFrame,
    experiments: pd.DataFrame,
    route_matrix: pd.DataFrame,
    remaining_profile: pd.DataFrame,
    review_queue: pd.DataFrame,
    compared_to: str = "",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    remaining_rows = len(snapshot[snapshot["causal_predictive_category"].astype(str).eq("insufficient_text")]) if not snapshot.empty else 0
    profile_preview = remaining_profile.head(12) if not remaining_profile.empty else pd.DataFrame()
    route_preview = (
        route_matrix[
            [
                column
                for column in [
                    "route_unit",
                    "row_count",
                    "decision",
                    "current_route_status",
                    "recommended_route_action",
                ]
                if column in route_matrix.columns
            ]
        ].head(12)
        if not route_matrix.empty
        else pd.DataFrame()
    )
    if not review_queue.empty:
        review_summary = (
            review_queue.groupby(["quick_win_tier", "split_group"], dropna=False)
            .size()
            .reset_index(name="rows")
            .sort_values(["quick_win_tier", "split_group"])
        )
    else:
        review_summary = pd.DataFrame(columns=["quick_win_tier", "split_group", "rows"])

    lines = [
        "# Recovery Impact Report",
        "",
        "This report is non-mutating. It does not change abstracts, source metadata, scope decisions, labels, or final article files.",
        "",
        f"- Current snapshot rows: {len(snapshot)}",
        f"- Current insufficient-text rows in snapshot: {remaining_rows}",
        f"- Recovery experiments: {len(experiments)}",
        f"- Comparison baseline: `{compared_to or 'none'}`",
        "",
        "## Top Journal-Decade Missingness Cells",
        "",
        df_to_markdown(profile_preview, max_rows=12),
        "",
        "## Top Route Units",
        "",
        df_to_markdown(route_preview, max_rows=12),
        "",
        "## R001 Ready Work",
        "",
        df_to_markdown(review_summary, max_rows=20),
        "",
        "## Recovery Experiment Queue",
        "",
        df_to_markdown(experiments, max_rows=20),
    ]
    if compared_to:
        lines.extend(
            [
                "",
                "## Before/After Impact",
                "",
                df_to_markdown(summary, max_rows=40),
                "",
                "## Changed Rows",
                "",
                df_to_markdown(changes, max_rows=40),
            ]
        )
    else:
        lines.extend(
            [
                "",
                "## Before/After Impact",
                "",
                "No comparison baseline was requested. Write a baseline snapshot before import, then rerun with `--compare-to <label>` after import and reclassification.",
            ]
        )
    lines.extend(
        [
            "",
            "## Do Not Do Yet",
            "",
            "- Do not run broad DOI landing-page retries for routes whose probes only found access challenges.",
            "- Do not turn title-only suggestions into final causal, predictive, or other labels.",
            "- Do not recover abstracts for rows waiting on scope review until those scope decisions are recorded.",
            "- Do not treat trend outputs as analysis-ready while the validation gate is blocked.",
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def run_recovery_impact_report(
    *,
    snapshot_label: str,
    write_snapshot: bool,
    compare_to: str,
    classified_path: Path,
    recovery_queue_path: Path,
    route_matrix_path: Path,
    import_history_path: Path,
    remaining_profile_path: Path,
    review_queue_path: Path,
    split_summary_path: Path,
    snapshot_dir: Path,
    output_summary: Path,
    output_changes: Path,
    output_experiments: Path,
    report_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    classified = read_csv_if_exists(classified_path)
    recovery_queue = read_csv_if_exists(recovery_queue_path)
    route_matrix = read_csv_if_exists(route_matrix_path)
    import_history = read_csv_if_exists(import_history_path)
    remaining_profile = read_csv_if_exists(remaining_profile_path)
    review_queue = read_csv_if_exists(review_queue_path)
    split_summary = read_csv_if_exists(split_summary_path)

    baseline_path = resolve_snapshot_path(compare_to, snapshot_dir) if compare_to else None
    before = read_csv_if_exists(baseline_path) if baseline_path is not None else pd.DataFrame()
    include_ids = set(before["article_id"].astype(str)) if not before.empty and "article_id" in before.columns else set()
    snapshot = recovery_snapshot(
        classified,
        recovery_queue,
        route_matrix,
        import_history,
        snapshot_label=snapshot_label,
        include_article_ids=include_ids,
    )
    changes = recovery_impact_changes(before, snapshot) if not before.empty else pd.DataFrame(columns=CHANGE_COLUMNS)
    summary = recovery_impact_summary(before, snapshot) if not before.empty else current_summary(snapshot)
    experiments = recovery_source_experiments(recovery_queue, route_matrix, review_queue, split_summary, remaining_profile)

    if write_snapshot:
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = snapshot_dir / snapshot_filename(snapshot_label)
        snapshot.to_csv(snapshot_path, index=False)

    for output_path, frame in [(output_summary, summary), (output_changes, changes), (output_experiments, experiments)]:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(output_path, index=False)
    write_recovery_impact_report(
        report_path,
        snapshot=snapshot,
        summary=summary,
        changes=changes,
        experiments=experiments,
        route_matrix=route_matrix,
        remaining_profile=remaining_profile,
        review_queue=review_queue,
        compared_to=str(baseline_path) if baseline_path is not None else "",
    )
    print(f"snapshot_rows={len(snapshot)}")
    print(f"summary_rows={len(summary)}")
    print(f"change_rows={len(changes)}")
    print(f"experiment_rows={len(experiments)}")
    print(f"summary={output_summary}")
    print(f"changes={output_changes}")
    print(f"experiments={output_experiments}")
    print(f"report={report_path}")
    return snapshot, summary, changes, experiments


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-label", default="current")
    parser.add_argument("--write-snapshot", action="store_true")
    parser.add_argument("--compare-to", default="")
    parser.add_argument("--classified", default="data/final/articles_classified_enriched_pilot.csv")
    parser.add_argument("--recovery-queue", default="outputs/tables/enriched/insufficient_text_recovery_queue.csv")
    parser.add_argument("--route-matrix", default="outputs/tables/enriched/insufficient_text_source_route_matrix.csv")
    parser.add_argument("--import-history", default="data/intermediate/abstract_backfill_import_history.csv")
    parser.add_argument("--remaining-profile", default="outputs/tables/enriched/remaining_insufficient_text_profile.csv")
    parser.add_argument("--review-queue", default="outputs/tables/enriched/recovery_batch_R001_review_queue.csv")
    parser.add_argument("--split-summary", default="outputs/tables/enriched/recovery_batch_R001_split_summary.csv")
    parser.add_argument("--snapshot-dir", default="data/intermediate/recovery_impact_snapshots")
    parser.add_argument("--output-summary", default="outputs/tables/enriched/recovery_impact_summary.csv")
    parser.add_argument("--output-changes", default="outputs/tables/enriched/recovery_impact_changes.csv")
    parser.add_argument("--output-experiments", default="outputs/tables/enriched/recovery_source_experiments.csv")
    parser.add_argument("--report", default="docs/recovery_impact_report.md")
    args = parser.parse_args()
    run_recovery_impact_report(
        snapshot_label=args.snapshot_label,
        write_snapshot=args.write_snapshot,
        compare_to=args.compare_to,
        classified_path=Path(args.classified),
        recovery_queue_path=Path(args.recovery_queue),
        route_matrix_path=Path(args.route_matrix),
        import_history_path=Path(args.import_history),
        remaining_profile_path=Path(args.remaining_profile),
        review_queue_path=Path(args.review_queue),
        split_summary_path=Path(args.split_summary),
        snapshot_dir=Path(args.snapshot_dir),
        output_summary=Path(args.output_summary),
        output_changes=Path(args.output_changes),
        output_experiments=Path(args.output_experiments),
        report_path=Path(args.report),
    )


if __name__ == "__main__":
    main()
