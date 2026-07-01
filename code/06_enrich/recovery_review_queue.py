from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "lib"))
sys.path.append(str(Path(__file__).resolve().parent))

from abstract_backfill import df_to_markdown  # noqa: E402
from econqt_common import clean_text, load_yaml, source_text_quality_flag  # noqa: E402
from recovery_batches import RECOVERY_PACKET_COLUMNS, recovery_form_html  # noqa: E402


READY_REVIEW_GROUPS = {
    "ready_partial_text_extension",
    "ready_manual_metadata",
    "ready_autofill_or_completed",
}

TIER_ORDER = {
    "source_metadata_fix": 0,
    "tier_1_partial_near_threshold": 1,
    "tier_2_partial_replace_suspect_text": 2,
    "tier_3_partial_extension": 3,
    "tier_4_manual_metadata_has_context": 4,
    "tier_5_manual_metadata_pdf_blocked": 5,
    "tier_6_manual_metadata_sparse": 6,
    "completed_ready_for_preflight": 7,
}

QUEUE_BASE_COLUMNS = [
    "review_rank",
    "review_stage",
    "quick_win_tier",
    "review_task",
    "required_fields",
    "chars_needed_to_threshold",
    "current_text_chars",
    "completion_status",
    "current_text_quality_flag",
    "recovery_batch",
    "split_group",
    "row_status",
    "batch_row",
    "recovery_rank",
    "recovery_priority",
    "article_id",
    "journal_short",
    "publication_year",
    "title",
    "doi",
    "source_hint",
    "source_artifact",
    "article_url",
    "doi_url",
    "openalex_work_url",
    "crossref_work_url",
    "openalex_title_search_url",
    "crossref_title_search_url",
    "semantic_scholar_title_search_url",
    "current_abstract_source",
    "text_enrichment_status",
    "prior_attempt_summary",
    "prior_attempt_detail_summary",
    "recommended_workflow",
    "notes",
]
QUEUE_EXTRA_CONTEXT_COLUMNS = [
    "current_abstract",
    "current_abstract_chars",
    "current_abstract_source",
    "review_note",
]
QUEUE_COLUMNS = QUEUE_BASE_COLUMNS + [
    column for column in RECOVERY_PACKET_COLUMNS + QUEUE_EXTRA_CONTEXT_COLUMNS if column not in QUEUE_BASE_COLUMNS
]

SUMMARY_COLUMNS = [
    "recovery_batch",
    "review_stage",
    "quick_win_tier",
    "split_group",
    "row_status",
    "rows",
    "median_chars_needed_to_threshold",
    "recommended_start",
]

SOURCE_GUIDE_COLUMNS = [
    "review_rank",
    "article_id",
    "title",
    "quick_win_tier",
    "row_status",
    "source_route_family",
    "first_source_to_check",
    "fallback_source_to_check",
    "acceptable_evidence",
    "stop_rule",
    "source_links",
]

SOURCE_GUIDE_SUMMARY_COLUMNS = [
    "source_route_family",
    "rows",
    "quick_win_tiers",
    "first_source_to_check",
    "acceptable_evidence",
    "stop_rule",
]
TIERED_PACKET_INDEX_COLUMNS = [
    "packet_order",
    "quick_win_tier",
    "rows",
    "first_review_rank",
    "last_review_rank",
    "recommended_start",
    "source_route_families",
    "csv_path",
    "html_path",
    "next_step",
]


def numeric_value(value: Any, default: int = 0) -> int:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return default if pd.isna(parsed) else int(parsed)


def ready_split_summary_rows(split_summary: pd.DataFrame) -> pd.DataFrame:
    if split_summary.empty or "split_group" not in split_summary.columns:
        return pd.DataFrame(columns=split_summary.columns)
    work = split_summary.copy().fillna("")
    work["_rows"] = pd.to_numeric(work.get("rows", ""), errors="coerce").fillna(0).astype(int)
    return work[work["split_group"].isin(READY_REVIEW_GROUPS) & work["_rows"].gt(0)].drop(columns=["_rows"]).reset_index(drop=True)


def source_ready(row: pd.Series) -> bool:
    source = clean_text(row.get("source"))
    source_url = clean_text(row.get("source_url"))
    source_record_id = clean_text(row.get("source_record_id"))
    return bool(source and (source_url or source_record_id))


def completion_status(row: pd.Series) -> str:
    abstract = clean_text(row.get("abstract"))
    if not abstract:
        return "needs_abstract_recovery"
    if source_ready(row):
        return "ready_to_import"
    return "needs_source_metadata"


def current_text_quality_flag(row: pd.Series) -> str:
    return source_text_quality_flag(row.get("current_abstract") or row.get("abstract"))


def review_stage_for_status(status: str) -> str:
    if status == "needs_source_metadata":
        return "source_metadata_fix"
    if status == "ready_to_import":
        return "ready_to_import"
    return "recover_abstract"


def quick_win_tier(row: pd.Series, *, minimum_chars: int) -> str:
    status = completion_status(row)
    if status == "needs_source_metadata":
        return "source_metadata_fix"
    if status == "ready_to_import":
        return "completed_ready_for_preflight"
    split_group = clean_text(row.get("split_group"))
    row_status = clean_text(row.get("row_status"))
    current_chars = numeric_value(row.get("current_text_chars"), 0)
    chars_needed = max(0, minimum_chars - current_chars)
    quality_flag = current_text_quality_flag(row)
    if split_group == "ready_partial_text_extension" and quality_flag:
        return "tier_2_partial_replace_suspect_text"
    if split_group == "ready_partial_text_extension" and chars_needed <= 75:
        return "tier_1_partial_near_threshold"
    if split_group == "ready_partial_text_extension":
        return "tier_3_partial_extension"
    if "pdf_route_blocked" in row_status or "suspect_pdf_url" in row_status:
        return "tier_5_manual_metadata_pdf_blocked"
    if current_chars > 0 or clean_text(row.get("current_abstract_source")):
        return "tier_4_manual_metadata_has_context"
    return "tier_6_manual_metadata_sparse"


def review_task(row: pd.Series, *, minimum_chars: int) -> str:
    status = completion_status(row)
    if status == "needs_source_metadata":
        return "Filled abstract needs source plus source_url or source_record_id before import."
    if status == "ready_to_import":
        return "No manual text recovery needed; confirm with preflight before import."
    split_group = clean_text(row.get("split_group"))
    row_status = clean_text(row.get("row_status"))
    if split_group == "ready_partial_text_extension":
        if current_text_quality_flag(row):
            return "Replace suspect current text with source-confirmed abstract or description; do not extend boilerplate."
        return f"Extend existing text to at least {minimum_chars} chars using explicit source metadata."
    if "pdf_route_blocked" in row_status or "suspect_pdf_url" in row_status:
        return "Do not retry the blocked PDF route; recover only an explicit abstract from source-confirmed metadata."
    return "Find an explicit abstract in DOI, publisher, index, or title-match metadata and record the source."


def first_nonempty(row: pd.Series, columns: list[str]) -> str:
    for column in columns:
        value = clean_text(row.get(column))
        if value:
            return value
    return ""


def source_hint(row: pd.Series) -> str:
    return first_nonempty(
        row,
        [
            "source_artifact",
            "doi_url",
            "article_url",
            "openalex_work_url",
            "crossref_work_url",
            "openalex_title_search_url",
            "crossref_title_search_url",
            "semantic_scholar_title_search_url",
        ],
    )


def doi_route_family(doi: Any) -> str:
    value = clean_text(doi).lower()
    if value.startswith("10.2307/"):
        return "jstor_or_legacy_doi"
    if value.startswith("10.1086/"):
        return "jpe_chicago_or_repec"
    if value.startswith("10.1257/"):
        return "aea_publisher_metadata"
    if value.startswith("10.1111/"):
        return "wiley_or_society_metadata"
    if value.startswith("10.1093/qje") or value.startswith("10.1093/restud"):
        return "oup_journal_metadata"
    if value.startswith("10.3982/"):
        return "econometric_society_metadata"
    if value:
        return "doi_or_publisher_metadata"
    return "title_index_search"


def source_route_family(row: pd.Series) -> str:
    quick_win = clean_text(row.get("quick_win_tier"))
    split_group = clean_text(row.get("split_group"))
    row_status = clean_text(row.get("row_status"))
    text_status = clean_text(row.get("text_enrichment_status"))
    source_artifact = clean_text(row.get("source_artifact"))
    if quick_win == "source_metadata_fix":
        return "source_metadata_fix"
    if split_group == "ready_partial_text_extension":
        return "partial_text_extension"
    if "pdf_route_blocked" in row_status or "suspect_pdf_url" in row_status or text_status == "pdf_candidate" or "pdf_download_blockers" in source_artifact:
        return "pdf_blocker_metadata"
    return doi_route_family(row.get("doi"))


def first_source_to_check(family: str) -> str:
    return {
        "source_metadata_fix": "Use the source already used for the filled abstract; add source plus source_url or source_record_id.",
        "partial_text_extension": "Start from the current abstract source and listed DOI/OpenAlex/Crossref records; replace any boilerplate before extending from explicit source metadata.",
        "pdf_blocker_metadata": "Do not retry the blocked PDF route; check DOI, publisher, index, or library metadata for an explicit abstract.",
        "jstor_or_legacy_doi": "Check DOI/JSTOR or library-index metadata for an explicit abstract; do not count an access-challenge page alone.",
        "jpe_chicago_or_repec": "Check the Chicago/JPE DOI page or RePEc/EconPapers metadata when it exposes an explicit abstract.",
        "aea_publisher_metadata": "Check AEA article metadata for the 10.1257 DOI, then confirm with DOI/Crossref/OpenAlex links.",
        "wiley_or_society_metadata": "Check Wiley, society, or library-index metadata for an explicit abstract.",
        "oup_journal_metadata": "Check the OUP journal page for the DOI, then DOI/Crossref/OpenAlex links.",
        "econometric_society_metadata": "Check Econometric Society metadata for the DOI, then DOI/Crossref/OpenAlex links.",
        "doi_or_publisher_metadata": "Check the DOI/publisher landing page first, then Crossref/OpenAlex records.",
        "title_index_search": "Use title-search links only to locate an explicit abstract or source-confirmed metadata record.",
    }.get(family, "Check listed source links for an explicit abstract and provenance.")


def fallback_source_to_check(family: str) -> str:
    return {
        "source_metadata_fix": "If the prior source is unclear, leave the row incomplete until provenance is recovered.",
        "partial_text_extension": "If the current source has only short text, use DOI, publisher, or index metadata with a recorded URL or record ID.",
        "pdf_blocker_metadata": "Use explicit metadata from DOI/publisher/index pages; use a reachable OA PDF only if the route is not the blocked URL.",
        "jstor_or_legacy_doi": "Use EconLit, library index records, or title-search results only when they expose an abstract.",
        "jpe_chicago_or_repec": "Use Crossref/OpenAlex for IDs and metadata, but do not import title-only matches.",
        "aea_publisher_metadata": "Use Crossref/OpenAlex or title search only if the abstract text is visible and source-confirmed.",
        "wiley_or_society_metadata": "Use DOI, Crossref/OpenAlex, or title-search records only if an abstract is visible.",
        "oup_journal_metadata": "Use index/title-search records only if they expose an abstract and match title/year.",
        "econometric_society_metadata": "Use DOI/Crossref/OpenAlex or title-search records only if an abstract is visible.",
        "doi_or_publisher_metadata": "Use title-search links as a fallback; require a high-confidence title/year match and explicit abstract.",
        "title_index_search": "If search results only provide title/citation metadata, keep the row unresolved.",
    }.get(family, "Use fallback metadata only when the abstract and provenance are explicit.")


def acceptable_evidence(family: str) -> str:
    base = "Recovered abstract text plus source, either source_url or source_record_id, and an importable evidence_tier."
    if family == "source_metadata_fix":
        return f"{base} The abstract is already filled; only provenance is missing."
    if family == "partial_text_extension":
        return f"{base} The added or replacement text must come from explicit metadata, not title-only inference or boilerplate."
    return f"{base} Title-only category suggestions are not acceptable recovery evidence."


def stop_rule(family: str) -> str:
    if family == "source_metadata_fix":
        return "Stop before import if source, source_url, and source_record_id are still blank or ambiguous."
    if family == "partial_text_extension":
        return "Stop if the source cannot replace or extend the text to the usable-text threshold or provenance is missing."
    if family == "pdf_blocker_metadata":
        return "Stop if the only evidence is a blocked PDF, paywall page, access challenge, or citation-only page."
    if family in {"jstor_or_legacy_doi", "wiley_or_society_metadata", "oup_journal_metadata", "econometric_society_metadata"}:
        return "Stop if the route only returns access challenges, citation metadata, or title-only matches."
    if family == "title_index_search":
        return "Stop if no explicit abstract is visible on the matched source record."
    return "Stop if provenance is weak, ambiguous, or title-only."


def source_links(row: pd.Series) -> str:
    links: list[str] = []
    for label, column in [
        ("hint", "source_hint"),
        ("doi", "doi_url"),
        ("article", "article_url"),
        ("openalex", "openalex_work_url"),
        ("crossref", "crossref_work_url"),
        ("openalex_title", "openalex_title_search_url"),
        ("crossref_title", "crossref_title_search_url"),
        ("semantic_scholar_title", "semantic_scholar_title_search_url"),
    ]:
        value = clean_text(row.get(column))
        if value and f"{label}={value}" not in links:
            links.append(f"{label}={value}")
    return " | ".join(links[:5])


def recovery_source_guide(queue: pd.DataFrame) -> pd.DataFrame:
    if queue.empty:
        return pd.DataFrame(columns=SOURCE_GUIDE_COLUMNS)
    rows: list[dict[str, Any]] = []
    for _, row in queue.fillna("").iterrows():
        family = source_route_family(row)
        rows.append(
            {
                "review_rank": clean_text(row.get("review_rank")),
                "article_id": clean_text(row.get("article_id")),
                "title": clean_text(row.get("title")),
                "quick_win_tier": clean_text(row.get("quick_win_tier")),
                "row_status": clean_text(row.get("row_status")),
                "source_route_family": family,
                "first_source_to_check": first_source_to_check(family),
                "fallback_source_to_check": fallback_source_to_check(family),
                "acceptable_evidence": acceptable_evidence(family),
                "stop_rule": stop_rule(family),
                "source_links": source_links(row),
            }
        )
    return pd.DataFrame(rows, columns=SOURCE_GUIDE_COLUMNS)


def recovery_source_guide_summary(guide: pd.DataFrame) -> pd.DataFrame:
    if guide.empty:
        return pd.DataFrame(columns=SOURCE_GUIDE_SUMMARY_COLUMNS)
    rows: list[dict[str, Any]] = []
    for family, group in guide.groupby("source_route_family", sort=False, dropna=False):
        tiers = [tier for tier in sorted(set(group["quick_win_tier"].astype(str))) if tier]
        first = group.iloc[0]
        rows.append(
            {
                "source_route_family": clean_text(family),
                "rows": len(group),
                "quick_win_tiers": "|".join(tiers),
                "first_source_to_check": clean_text(first.get("first_source_to_check")),
                "acceptable_evidence": clean_text(first.get("acceptable_evidence")),
                "stop_rule": clean_text(first.get("stop_rule")),
            }
        )
    return pd.DataFrame(rows, columns=SOURCE_GUIDE_SUMMARY_COLUMNS)


def guided_recovery_form_rows(queue: pd.DataFrame, guide: pd.DataFrame) -> pd.DataFrame:
    if queue.empty:
        return queue.copy()
    guide_columns = [
        "article_id",
        "source_route_family",
        "first_source_to_check",
        "fallback_source_to_check",
        "acceptable_evidence",
        "stop_rule",
    ]
    available_guide_columns = [column for column in guide_columns if column in guide.columns]
    if not available_guide_columns or "article_id" not in available_guide_columns:
        return queue.copy()
    merged = queue.copy().fillna("").merge(
        guide[available_guide_columns].drop_duplicates("article_id", keep="first"),
        on="article_id",
        how="left",
    )
    return merged.fillna("")


def already_has_usable_enriched_text(row: pd.Series, *, minimum_chars: int) -> bool:
    text_status = clean_text(row.get("text_enrichment_status"))
    has_usable = clean_text(row.get("has_usable_classification_text")).lower() == "true"
    current_chars = numeric_value(row.get("current_text_chars"), 0)
    return text_status == "enriched" and (has_usable or current_chars >= minimum_chars)


def normalize_review_row(row: pd.Series, *, minimum_chars: int) -> dict[str, Any]:
    current_chars = numeric_value(row.get("current_text_chars"), 0)
    status = completion_status(row)
    meta_columns = {
        "review_rank",
        "review_stage",
        "quick_win_tier",
        "review_task",
        "required_fields",
        "chars_needed_to_threshold",
        "current_text_chars",
        "completion_status",
        "current_text_quality_flag",
        "source_hint",
    }
    values = {column: clean_text(row.get(column)) for column in QUEUE_COLUMNS if column not in meta_columns}
    quality_flag = current_text_quality_flag(row)
    if not values.get("abstract") and clean_text(row.get("split_group")) == "ready_partial_text_extension" and not quality_flag:
        values["abstract"] = clean_text(row.get("current_abstract"))
    return {
        "review_rank": "",
        "review_stage": review_stage_for_status(status),
        "quick_win_tier": quick_win_tier(row, minimum_chars=minimum_chars),
        "review_task": review_task(row, minimum_chars=minimum_chars),
        "required_fields": "abstract; source; source_url or source_record_id; evidence_tier",
        "chars_needed_to_threshold": max(0, minimum_chars - current_chars),
        "current_text_chars": current_chars,
        "completion_status": status,
        "current_text_quality_flag": quality_flag,
        "source_hint": source_hint(row),
        **values,
    }


def recovery_review_queue(split_summary: pd.DataFrame, *, minimum_chars: int) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, split_row in ready_split_summary_rows(split_summary).iterrows():
        path = Path(clean_text(split_row.get("output_csv")))
        if not path.exists():
            continue
        split = pd.read_csv(path, dtype=str).fillna("")
        if "split_group" not in split.columns:
            split["split_group"] = clean_text(split_row.get("split_group"))
        if "recovery_batch" not in split.columns:
            split["recovery_batch"] = clean_text(split_row.get("recovery_batch"))
        for _, row in split.iterrows():
            if already_has_usable_enriched_text(row, minimum_chars=minimum_chars):
                continue
            rows.append(normalize_review_row(row, minimum_chars=minimum_chars))
    if not rows:
        return pd.DataFrame(columns=QUEUE_COLUMNS)

    out = pd.DataFrame(rows, columns=QUEUE_COLUMNS)
    out["_tier_order"] = out["quick_win_tier"].map(TIER_ORDER).fillna(99).astype(int)
    out["_chars_needed"] = pd.to_numeric(out["chars_needed_to_threshold"], errors="coerce").fillna(0).astype(int)
    out["_recovery_rank"] = pd.to_numeric(out["recovery_rank"], errors="coerce").fillna(999999).astype(int)
    # For partial-text rows, higher current text means fewer characters to recover; for other rows, keep original recovery order.
    out = out.sort_values(
        ["_tier_order", "_chars_needed", "_recovery_rank", "journal_short", "publication_year", "title"],
        ascending=[True, True, True, True, True, True],
    ).reset_index(drop=True)
    out["review_rank"] = [str(index + 1) for index in range(len(out))]
    return out[QUEUE_COLUMNS]


def queue_summary(queue: pd.DataFrame) -> pd.DataFrame:
    if queue.empty:
        return pd.DataFrame(columns=SUMMARY_COLUMNS)
    work = queue.copy().fillna("")
    work["_chars_needed"] = pd.to_numeric(work["chars_needed_to_threshold"], errors="coerce").fillna(0).astype(int)
    grouped = (
        work.groupby(["recovery_batch", "review_stage", "quick_win_tier", "split_group", "row_status"], sort=False, dropna=False)
        .agg(rows=("article_id", "count"), median_chars_needed_to_threshold=("_chars_needed", "median"))
        .reset_index()
    )
    grouped["median_chars_needed_to_threshold"] = grouped["median_chars_needed_to_threshold"].round().astype(int)
    grouped["recommended_start"] = grouped["quick_win_tier"].map(
        {
            "source_metadata_fix": "Fix source fields before import.",
            "tier_1_partial_near_threshold": "Start here for fastest usable-text gains.",
            "tier_2_partial_replace_suspect_text": "Replace boilerplate/current suspect text from explicit metadata.",
            "tier_3_partial_extension": "Extend from the listed source hint.",
            "tier_4_manual_metadata_has_context": "Use existing context plus DOI/index metadata.",
            "tier_5_manual_metadata_pdf_blocked": "Avoid blocked PDFs; use metadata only.",
            "tier_6_manual_metadata_sparse": "Lower-yield manual search.",
            "completed_ready_for_preflight": "Already source-ready; confirm preflight.",
        }
    ).fillna("")
    return grouped[SUMMARY_COLUMNS]


def tier_slug(value: str) -> str:
    text = clean_text(value).lower()
    chars = [char if char.isalnum() else "_" for char in text]
    slug = "".join(chars)
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_") or "missing"


def ordered_tiers(queue: pd.DataFrame) -> list[str]:
    if queue.empty or "quick_win_tier" not in queue.columns:
        return []
    tiers = [clean_text(tier) for tier in queue["quick_win_tier"].dropna().astype(str).unique() if clean_text(tier)]
    return sorted(tiers, key=lambda tier: (TIER_ORDER.get(tier, 99), tier))


def recommended_start_for_tier(summary: pd.DataFrame, tier: str) -> str:
    if summary.empty or not {"quick_win_tier", "recommended_start"}.issubset(summary.columns):
        return ""
    matches = summary[summary["quick_win_tier"].astype(str).eq(tier)]
    starts = [clean_text(value) for value in matches["recommended_start"].tolist() if clean_text(value)]
    return " | ".join(dict.fromkeys(starts))


def source_families_for_articles(guide: pd.DataFrame, article_ids: set[str]) -> str:
    if guide.empty or not {"article_id", "source_route_family"}.issubset(guide.columns):
        return ""
    matches = guide[guide["article_id"].astype(str).isin(article_ids)]
    families = [clean_text(value) for value in matches["source_route_family"].tolist() if clean_text(value)]
    return "|".join(dict.fromkeys(families))


def write_tiered_recovery_packet_report(path: Path, packet_index: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Recovery Batch R001 Tiered Packets",
        "",
        "These packets are non-mutating helper views over the R001 recovery queue. They do not change abstract text, source metadata, scope decisions, labels, or final article files.",
        "",
        "Use the packets in order. Start with the near-threshold partial-text rows, export completed CSVs from the HTML forms, place them in `data/intermediate/insufficient_text_recovery_review_exports/R001/`, then run `python3 run_recovery_tiered_stage.py` before preflight.",
        "",
        "Every completed row still needs `abstract`, `source`, either `source_url` or `source_record_id`, and an importable `evidence_tier`. Partial-text rows are prefilled with the current short abstract only when that current text is not flagged as boilerplate; flagged rows require replacement text from source-confirmed metadata.",
        "",
        "Importable evidence tiers are `tier_a_formal_abstract`, `tier_b_source_description`, and `tier_c_first_page_abstract_or_intro`. `tier_d_title_only_triage` and `tier_e_blocked` stay out of final classification text.",
        "",
        "## Packet Index",
        "",
        df_to_markdown(packet_index, max_rows=30),
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_tiered_recovery_packets(
    *,
    queue: pd.DataFrame,
    guide: pd.DataFrame,
    summary: pd.DataFrame,
    output_dir: Path,
    html_dir: Path,
    index_output: Path,
    report_path: Path,
    batch_id: str = "R001",
) -> pd.DataFrame:
    output_dir.mkdir(parents=True, exist_ok=True)
    html_dir.mkdir(parents=True, exist_ok=True)
    for old_path in output_dir.glob(f"recovery_batch_{batch_id}_tier_*.csv"):
        if old_path.is_file():
            old_path.unlink()
    for old_path in html_dir.glob(f"recovery_batch_{batch_id}_tier_*.html"):
        if old_path.is_file():
            old_path.unlink()
    index_rows: list[dict[str, Any]] = []
    for packet_order, tier in enumerate(ordered_tiers(queue), start=1):
        packet = queue[queue["quick_win_tier"].astype(str).eq(tier)].copy().fillna("")
        if packet.empty:
            continue
        form_rows = guided_recovery_form_rows(packet, guide)
        slug = tier_slug(tier)
        filename_base = f"recovery_batch_{batch_id}_tier_{packet_order:02d}_{slug}"
        csv_path = output_dir / f"{filename_base}.csv"
        html_path = html_dir / f"{filename_base}.html"
        form_rows.to_csv(csv_path, index=False)
        html_path.write_text(
            recovery_form_html(form_rows, title=f"Insufficient Text Recovery {batch_id} Tier {packet_order:02d} {tier}"),
            encoding="utf-8",
        )
        ranks = pd.to_numeric(packet["review_rank"], errors="coerce").dropna().astype(int).tolist()
        article_ids = {clean_text(value) for value in packet["article_id"].tolist() if clean_text(value)}
        index_rows.append(
            {
                "packet_order": packet_order,
                "quick_win_tier": tier,
                "rows": len(packet),
                "first_review_rank": min(ranks) if ranks else "",
                "last_review_rank": max(ranks) if ranks else "",
                "recommended_start": recommended_start_for_tier(summary, tier),
                "source_route_families": source_families_for_articles(guide, article_ids),
                "csv_path": str(csv_path),
                "html_path": str(html_path),
                "next_step": "Fill abstract/source provenance, export CSV to the tiered review exports directory, run recovery tiered staging, then run recovery split preflight on the staged split summary.",
            }
        )
    packet_index = pd.DataFrame(index_rows, columns=TIERED_PACKET_INDEX_COLUMNS)
    index_output.parent.mkdir(parents=True, exist_ok=True)
    packet_index.to_csv(index_output, index=False)
    write_tiered_recovery_packet_report(report_path, packet_index)
    return packet_index


def write_source_guide_report(path: Path, guide: pd.DataFrame, summary: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    preview_columns = [
        "review_rank",
        "source_route_family",
        "quick_win_tier",
        "article_id",
        "title",
        "first_source_to_check",
        "stop_rule",
    ]
    preview = guide[[column for column in preview_columns if column in guide.columns]].head(40).copy() if not guide.empty else pd.DataFrame(columns=preview_columns)
    lines = [
        "# Recovery Batch R001 Source Guide",
        "",
        "This guide is non-mutating. It helps reviewers choose source routes for the recovery queue, but it does not change abstract text, source metadata, scope decisions, labels, or final article files.",
        "",
        "Use the guide to decide where to look first and when to stop. Import preflight still requires `abstract`, `source`, either `source_url` or `source_record_id`, and an importable `evidence_tier` for every completed row.",
        "",
        "## Source Route Summary",
        "",
        df_to_markdown(summary, max_rows=30),
        "",
        "## Row Guide Preview",
        "",
        df_to_markdown(preview, max_rows=40),
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_guided_recovery_form(path: Path, queue: pd.DataFrame, guide: pd.DataFrame, *, title: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    form_rows = guided_recovery_form_rows(queue, guide)
    path.write_text(recovery_form_html(form_rows, title=title), encoding="utf-8")


def write_review_queue_report(
    path: Path,
    queue: pd.DataFrame,
    summary: pd.DataFrame,
    *,
    minimum_chars: int,
    guide_report_path: Path | None = None,
    guided_form_path: Path | None = None,
    tiered_report_path: Path | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    preview_columns = [
        "review_rank",
        "quick_win_tier",
        "chars_needed_to_threshold",
        "current_text_quality_flag",
        "batch_row",
        "article_id",
        "journal_short",
        "publication_year",
        "title",
        "source_hint",
        "review_task",
    ]
    preview = queue[[column for column in preview_columns if column in queue.columns]].head(30).copy() if not queue.empty else pd.DataFrame(columns=preview_columns)
    stage_counts = queue["review_stage"].value_counts().rename_axis("review_stage").reset_index(name="rows") if not queue.empty else pd.DataFrame(columns=["review_stage", "rows"])
    lines = [
        "# Recovery Batch R001 Review Queue",
        "",
        "This queue is non-mutating. It combines the ready split packets into a reviewer-facing order and does not change abstract text, source metadata, scope decisions, labels, or final article files.",
        "",
        f"- Minimum usable classification text: {minimum_chars} chars",
        f"- Queue rows: {len(queue)}",
        "",
        "Reviewer fields required before import: `abstract`, `source`, either `source_url` or `source_record_id`, and `evidence_tier`.",
        "",
        "Use `tier_a_formal_abstract`, `tier_b_source_description`, or `tier_c_first_page_abstract_or_intro` for importable text. Keep `tier_d_title_only_triage` and `tier_e_blocked` unresolved.",
        "",
        "Suggested order: fix any `source_metadata_fix` rows first, then work clean `tier_1_partial_near_threshold` rows, then `tier_2_partial_replace_suspect_text`, then deeper partial extensions and manual metadata tiers.",
        f"Source-route guide: `{guide_report_path}`" if guide_report_path is not None else "",
        f"Guided recovery form: `{guided_form_path}`" if guided_form_path is not None else "",
        f"Tiered quick-win packets: `{tiered_report_path}`" if tiered_report_path is not None else "",
        "",
        "## Stage Counts",
        "",
        df_to_markdown(stage_counts),
        "",
        "## Queue Summary",
        "",
        df_to_markdown(summary, max_rows=40),
        "",
        "## Top Queue Rows",
        "",
        df_to_markdown(preview, max_rows=30),
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("") if path.exists() else pd.DataFrame()


def run_recovery_review_queue(
    *,
    split_summary_path: Path,
    config_path: Path,
    output_queue: Path,
    output_summary: Path,
    report_path: Path,
    output_guide: Path | None = None,
    output_guide_summary: Path | None = None,
    guide_report_path: Path | None = None,
    guided_form_path: Path | None = None,
    tiered_output_dir: Path | None = None,
    tiered_form_dir: Path | None = None,
    tiered_index_output: Path | None = None,
    tiered_report_path: Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    config = load_yaml(config_path)
    minimum_chars = int(config.get("minimum_usable_text_chars", 250))
    split_summary = read_csv_if_exists(split_summary_path)
    queue = recovery_review_queue(split_summary, minimum_chars=minimum_chars)
    summary = queue_summary(queue)
    guide = recovery_source_guide(queue)
    guide_summary = recovery_source_guide_summary(guide)

    output_queue.parent.mkdir(parents=True, exist_ok=True)
    output_summary.parent.mkdir(parents=True, exist_ok=True)
    queue.to_csv(output_queue, index=False)
    summary.to_csv(output_summary, index=False)
    if output_guide is not None:
        output_guide.parent.mkdir(parents=True, exist_ok=True)
        guide.to_csv(output_guide, index=False)
    if output_guide_summary is not None:
        output_guide_summary.parent.mkdir(parents=True, exist_ok=True)
        guide_summary.to_csv(output_guide_summary, index=False)
    if guide_report_path is not None:
        write_source_guide_report(guide_report_path, guide, guide_summary)
    if guided_form_path is not None:
        write_guided_recovery_form(guided_form_path, queue, guide, title="Insufficient Text Recovery R001 Guided Queue")
    tiered_index = pd.DataFrame(columns=TIERED_PACKET_INDEX_COLUMNS)
    if tiered_output_dir is not None and tiered_form_dir is not None and tiered_index_output is not None and tiered_report_path is not None:
        tiered_index = write_tiered_recovery_packets(
            queue=queue,
            guide=guide,
            summary=summary,
            output_dir=tiered_output_dir,
            html_dir=tiered_form_dir,
            index_output=tiered_index_output,
            report_path=tiered_report_path,
        )
    write_review_queue_report(
        report_path,
        queue,
        summary,
        minimum_chars=minimum_chars,
        guide_report_path=guide_report_path,
        guided_form_path=guided_form_path,
        tiered_report_path=tiered_report_path,
    )

    print(f"review_queue_rows={len(queue)}")
    print(f"summary_rows={len(summary)}")
    print(f"source_guide_rows={len(guide)}")
    print(f"queue={output_queue}")
    print(f"summary={output_summary}")
    if output_guide is not None:
        print(f"source_guide={output_guide}")
    if output_guide_summary is not None:
        print(f"source_guide_summary={output_guide_summary}")
    if guide_report_path is not None:
        print(f"source_guide_report={guide_report_path}")
    if guided_form_path is not None:
        print(f"guided_form={guided_form_path}")
    if tiered_index_output is not None:
        print(f"tiered_packets={len(tiered_index)}")
        print(f"tiered_index={tiered_index_output}")
    if tiered_report_path is not None:
        print(f"tiered_report={tiered_report_path}")
    print(f"report={report_path}")
    return queue, summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split-summary", default="outputs/tables/enriched/recovery_batch_R001_split_summary.csv")
    parser.add_argument("--config", default="config/text_enrichment.yml")
    parser.add_argument("--output-queue", default="outputs/tables/enriched/recovery_batch_R001_review_queue.csv")
    parser.add_argument("--output-summary", default="outputs/tables/enriched/recovery_batch_R001_review_queue_summary.csv")
    parser.add_argument("--output-source-guide", default="outputs/tables/enriched/recovery_batch_R001_source_guide.csv")
    parser.add_argument("--output-source-guide-summary", default="outputs/tables/enriched/recovery_batch_R001_source_guide_summary.csv")
    parser.add_argument("--source-guide-report", default="docs/recovery_batch_R001_source_guide.md")
    parser.add_argument("--guided-form", default="data/intermediate/insufficient_text_recovery_review_forms/R001/recovery_batch_R001_guided_queue.html")
    parser.add_argument("--tiered-output-dir", default="outputs/tables/enriched/recovery_batch_R001_tiered_packets")
    parser.add_argument("--tiered-form-dir", default="data/intermediate/insufficient_text_recovery_review_forms/R001/tiered")
    parser.add_argument("--tiered-index-output", default="outputs/tables/enriched/recovery_batch_R001_tiered_packet_index.csv")
    parser.add_argument("--tiered-report", default="docs/recovery_batch_R001_tiered_packets.md")
    parser.add_argument("--report", default="docs/recovery_batch_R001_review_queue.md")
    args = parser.parse_args()
    run_recovery_review_queue(
        split_summary_path=Path(args.split_summary),
        config_path=Path(args.config),
        output_queue=Path(args.output_queue),
        output_summary=Path(args.output_summary),
        report_path=Path(args.report),
        output_guide=Path(args.output_source_guide),
        output_guide_summary=Path(args.output_source_guide_summary),
        guide_report_path=Path(args.source_guide_report),
        guided_form_path=Path(args.guided_form),
        tiered_output_dir=Path(args.tiered_output_dir),
        tiered_form_dir=Path(args.tiered_form_dir),
        tiered_index_output=Path(args.tiered_index_output),
        tiered_report_path=Path(args.tiered_report),
    )


if __name__ == "__main__":
    main()
