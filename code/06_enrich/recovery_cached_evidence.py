from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "lib"))
sys.path.append(str(Path(__file__).resolve().parent))

from econqt_common import clean_text, load_yaml, normalize_doi, normalize_title, source_text_quality_flag, strip_source_boilerplate  # noqa: E402
from recovery_batches import recovery_form_html  # noqa: E402
from text_enrichment import df_to_markdown, parse_sources, text_chars, try_sources  # noqa: E402


DEFAULT_AUDIT_SOURCES = ["openalex", "crossref", "econpapers", "publisher_metadata", "semantic_scholar", "unpaywall"]

DETAIL_COLUMNS = [
    "review_rank",
    "article_id",
    "quick_win_tier",
    "journal_short",
    "publication_year",
    "title",
    "doi",
    "cached_evidence_status",
    "recommended_action",
    "candidate_source",
    "candidate_status",
    "candidate_text_chars",
    "candidate_abstract_chars",
    "current_text_chars",
    "chars_needed_to_threshold",
    "candidate_delta_chars",
    "candidate_quality_flags",
    "candidate_url",
    "candidate_source_record_id",
    "candidate_oa_pdf_url",
    "attempted_cached_sources",
    "attempt_statuses",
    "evidence_tier_suggestion",
    "review_note",
]

SUMMARY_COLUMNS = [
    "cached_evidence_status",
    "quick_win_tier",
    "rows",
    "first_review_rank",
    "candidate_sources",
    "recommended_action",
]

ACTION_PACKET_COLUMNS = [
    "review_rank",
    "article_id",
    "quick_win_tier",
    "cell_target_rank",
    "cell_target_level",
    "cell_recoveries_to_target_share",
    "cell_projected_share_after_ready_r001",
    "cell_ready_r001_target_coverage",
    "action_group",
    "reviewer_action",
    "stop_rule",
    "suggested_evidence_tier",
    "source_to_check_first",
    "source_to_avoid",
    "cached_evidence_status",
    "candidate_source",
    "candidate_text_chars",
    "current_text_chars",
    "chars_needed_to_threshold",
    "candidate_quality_flags",
    "source_route_family",
    "automation_status",
    "title",
    "doi",
    "source_links",
    "current_abstract",
    "candidate_url",
    "candidate_source_record_id",
    "review_note",
    "cell_recommended_next_step",
]

ACTION_SUMMARY_COLUMNS = [
    "action_group",
    "quick_win_tier",
    "rows",
    "first_review_rank",
    "reviewer_action",
]

ACTION_REVIEW_PACKET_INDEX_COLUMNS = [
    "packet_order",
    "action_group",
    "rows",
    "first_review_rank",
    "last_review_rank",
    "quick_win_tiers",
    "csv_path",
    "html_path",
    "next_step",
]


def numeric_value(value: Any, default: int = 0) -> int:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return default if pd.isna(parsed) else int(parsed)


def source_records_for_row(row: pd.Series | dict[str, Any], source_records: pd.DataFrame) -> list[dict[str, Any]]:
    if source_records.empty or "abstract" not in source_records.columns:
        return []

    work = source_records.copy().fillna("")
    if "doi_norm" not in work.columns:
        doi_values = work["doi"] if "doi" in work.columns else pd.Series("", index=work.index)
        work["doi_norm"] = doi_values.map(normalize_doi)
    if "title_norm" not in work.columns:
        title_values = work["title"] if "title" in work.columns else pd.Series("", index=work.index)
        work["title_norm"] = title_values.map(normalize_title)

    doi = normalize_doi(row.get("doi", "") if hasattr(row, "get") else "")
    title_norm = normalize_title(row.get("title", "") if hasattr(row, "get") else "")
    journal = clean_text(row.get("journal_short", "") if hasattr(row, "get") else "").lower()
    year = clean_text(row.get("publication_year", "") if hasattr(row, "get") else "")

    if doi:
        matches = work[work["doi_norm"].eq(doi)].copy()
    else:
        journal_values = work.get("journal_short", pd.Series("", index=work.index)).astype(str).str.lower()
        year_values = work.get("publication_year", pd.Series("", index=work.index)).astype(str)
        matches = work[work["title_norm"].eq(title_norm) & journal_values.eq(journal) & year_values.eq(year)].copy()

    candidates: list[dict[str, Any]] = []
    for _, record in matches.iterrows():
        abstract = strip_source_boilerplate(record.get("abstract"))
        if not abstract:
            continue
        source = clean_text(record.get("source"))
        candidates.append(
            {
                "source": f"source_records:{source}" if source else "source_records",
                "status": "found",
                "abstract": abstract,
                "url": clean_text(record.get("article_url")) or clean_text(record.get("source_query_url")),
                "source_record_id": clean_text(record.get("source_record_id")) or clean_text(record.get("openalex_id")) or clean_text(record.get("crossref_id")),
                "oa_pdf_url": "",
                "detail": "source_records_exact_doi" if doi else "source_records_exact_title_year",
                "error": "",
                "cached": True,
            }
        )
    return candidates


def candidate_score(candidate: dict[str, Any], row: pd.Series | dict[str, Any], minimum_chars: int) -> tuple[int, int, int]:
    abstract = strip_source_boilerplate(candidate.get("abstract"))
    quality_flag = source_text_quality_flag(candidate.get("abstract"))
    chars = text_chars(row.get("title", "") if hasattr(row, "get") else "", abstract) if abstract else 0
    import_ready = int(bool(abstract and not quality_flag and chars >= minimum_chars))
    clean_partial = int(bool(abstract and not quality_flag))
    return (import_ready, clean_partial, chars)


def best_candidate(candidates: list[dict[str, Any]], row: pd.Series | dict[str, Any], minimum_chars: int) -> dict[str, Any]:
    if not candidates:
        return {}
    return max(candidates, key=lambda candidate: candidate_score(candidate, row, minimum_chars))


def evidence_status(
    *,
    candidate: dict[str, Any],
    candidate_text_chars: int,
    candidate_abstract_chars: int,
    current_text_chars: int,
    minimum_chars: int,
    quality_flags: str,
    fallback_status: str,
    candidate_oa_pdf_url: str,
) -> str:
    if quality_flags:
        return "cached_suspect_text_only"
    if candidate_abstract_chars:
        if candidate_text_chars >= minimum_chars:
            return "cached_import_candidate"
        if candidate_text_chars > current_text_chars:
            return "cached_partial_extension_candidate"
        if candidate_abstract_chars < 80:
            return "cached_fragment_only"
        return "cached_current_text_only"
    if candidate_oa_pdf_url:
        return "cached_pdf_candidate_only"
    if fallback_status == "rate_limited":
        return "cached_prior_rate_limited_only"
    if fallback_status == "not_cached":
        return "no_cached_response"
    return "no_cached_text_candidate"


def recommended_action(status: str) -> str:
    return {
        "cached_import_candidate": "Review the cached text and provenance; if the title/year match is correct, copy it into the tiered export with an importable evidence_tier.",
        "cached_partial_extension_candidate": "Review whether the cached text can extend the row, but keep searching if it still does not reach the usable-text threshold.",
        "cached_current_text_only": "The local cache only repeats the existing short text; do not rerun the same source unless source logic changes.",
        "cached_fragment_only": "The local cache contains only a fragment; treat it as context, not importable recovery text.",
        "cached_suspect_text_only": "Do not reuse this cached text; replace it with explicit abstract metadata from a different source.",
        "cached_pdf_candidate_only": "Use only if the PDF is clearly public and not already blocked; otherwise recover metadata manually.",
        "cached_prior_rate_limited_only": "Do not treat the cached rate-limit response as evidence; use another source or retry later with rate-limit controls.",
        "no_cached_response": "No local cached response is available for the configured sources; use the manual source route.",
        "no_cached_text_candidate": "Cached responses do not expose usable text; use the manual source route.",
    }.get(status, "Review manually before importing.")


def evidence_tier_suggestion(status: str) -> str:
    if status == "cached_import_candidate":
        return "review_required_tier_a_or_b"
    if status in {"cached_partial_extension_candidate", "cached_current_text_only", "cached_fragment_only"}:
        return "review_context_only"
    if status == "cached_pdf_candidate_only":
        return "review_required_tier_c_if_public_pdf_text"
    return "not_importable_from_cache"


def cached_evidence_for_row(
    row: pd.Series,
    *,
    config: dict[str, Any],
    cache_dir: Path,
    sources: list[str],
    source_records: pd.DataFrame,
    minimum_chars: int,
) -> dict[str, Any]:
    result, attempts = try_sources(
        row.to_dict(),
        sources=sources,
        config=config,
        cache_dir=cache_dir,
        refresh=False,
        allow_title_search=False,
        cached_only=True,
    )
    candidates = []
    if clean_text(result.get("abstract")):
        candidates.append(result)
    candidates.extend(source_records_for_row(row, source_records))
    candidate = best_candidate(candidates, row, minimum_chars)

    raw_abstract = clean_text(candidate.get("abstract")) if candidate else ""
    candidate_abstract = strip_source_boilerplate(raw_abstract)
    candidate_text_chars = text_chars(row.get("title", ""), candidate_abstract) if candidate_abstract else 0
    candidate_abstract_chars = len(candidate_abstract)
    current_text_chars = numeric_value(row.get("current_text_chars"), 0)
    quality_flags = source_text_quality_flag(raw_abstract)
    candidate_oa_pdf_url = clean_text(candidate.get("oa_pdf_url")) if candidate else clean_text(result.get("oa_pdf_url"))
    status = evidence_status(
        candidate=candidate,
        candidate_text_chars=candidate_text_chars,
        candidate_abstract_chars=candidate_abstract_chars,
        current_text_chars=current_text_chars,
        minimum_chars=minimum_chars,
        quality_flags=quality_flags,
        fallback_status=clean_text(result.get("status")),
        candidate_oa_pdf_url=candidate_oa_pdf_url,
    )
    attempt_statuses = [f"{clean_text(attempt.get('source'))}:{clean_text(attempt.get('status'))}" for attempt in attempts]
    return {
        "review_rank": clean_text(row.get("review_rank")),
        "article_id": clean_text(row.get("article_id")),
        "quick_win_tier": clean_text(row.get("quick_win_tier")),
        "journal_short": clean_text(row.get("journal_short")),
        "publication_year": clean_text(row.get("publication_year")),
        "title": clean_text(row.get("title")),
        "doi": normalize_doi(row.get("doi")),
        "cached_evidence_status": status,
        "recommended_action": recommended_action(status),
        "candidate_source": clean_text(candidate.get("source")) if candidate else clean_text(result.get("source")),
        "candidate_status": clean_text(candidate.get("status")) if candidate else clean_text(result.get("status")),
        "candidate_text_chars": candidate_text_chars,
        "candidate_abstract_chars": candidate_abstract_chars,
        "current_text_chars": current_text_chars,
        "chars_needed_to_threshold": max(0, minimum_chars - current_text_chars),
        "candidate_delta_chars": candidate_text_chars - current_text_chars,
        "candidate_quality_flags": quality_flags,
        "candidate_url": clean_text(candidate.get("url")) if candidate else clean_text(result.get("url")),
        "candidate_source_record_id": clean_text(candidate.get("source_record_id")) if candidate else clean_text(result.get("source_record_id")),
        "candidate_oa_pdf_url": candidate_oa_pdf_url,
        "attempted_cached_sources": "|".join(sources),
        "attempt_statuses": "|".join(status for status in attempt_statuses if status),
        "evidence_tier_suggestion": evidence_tier_suggestion(status),
        "review_note": clean_text(candidate.get("detail")) if candidate else clean_text(result.get("detail")),
    }


def cached_evidence_summary(detail: pd.DataFrame) -> pd.DataFrame:
    if detail.empty:
        return pd.DataFrame(columns=SUMMARY_COLUMNS)
    work = detail.copy().fillna("")
    work["_review_rank"] = pd.to_numeric(work.get("review_rank", ""), errors="coerce").fillna(999999).astype(int)
    rows: list[dict[str, Any]] = []
    for (status, tier), group in work.groupby(["cached_evidence_status", "quick_win_tier"], sort=False, dropna=False):
        sources = [clean_text(source) for source in group["candidate_source"].tolist() if clean_text(source)]
        rows.append(
            {
                "cached_evidence_status": clean_text(status),
                "quick_win_tier": clean_text(tier),
                "rows": len(group),
                "first_review_rank": int(group["_review_rank"].min()),
                "candidate_sources": "|".join(dict.fromkeys(sources)),
                "recommended_action": recommended_action(clean_text(status)),
            }
        )
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS).sort_values(["first_review_rank", "cached_evidence_status"]).reset_index(drop=True)


def action_group_for_row(row: pd.Series | dict[str, Any]) -> str:
    status = clean_text(row.get("cached_evidence_status", "") if hasattr(row, "get") else "")
    tier = clean_text(row.get("quick_win_tier", "") if hasattr(row, "get") else "")
    if status == "cached_import_candidate":
        return "review_cached_import_candidate"
    if status == "cached_partial_extension_candidate":
        return "review_cached_extension_candidate"
    if status == "cached_current_text_only" and tier == "tier_1_partial_near_threshold":
        return "find_external_extension"
    if status == "cached_current_text_only":
        return "do_not_rerun_cached_source"
    if status == "cached_suspect_text_only":
        return "replace_boilerplate_from_new_source"
    if status == "cached_fragment_only":
        return "find_fuller_metadata"
    if status == "no_cached_text_candidate":
        return "manual_metadata_search"
    if status == "cached_pdf_candidate_only":
        return "verify_pdf_or_use_metadata"
    if status == "cached_prior_rate_limited_only":
        return "avoid_rate_limited_cache"
    if status == "no_cached_response":
        return "manual_source_route_no_cache"
    return "manual_review"


def reviewer_action(group: str) -> str:
    return {
        "review_cached_import_candidate": "Verify title/year/provenance, then copy the cached abstract or source description into the tiered export with an importable evidence tier.",
        "review_cached_extension_candidate": "Use the cached text only if it materially extends the row; keep searching if it still fails the usable-text threshold.",
        "find_external_extension": "Do not rerun the cached source; find a small source-confirmed extension from DOI, publisher, index, or library metadata.",
        "do_not_rerun_cached_source": "The cache repeats the current short text; use a different source route or leave unresolved.",
        "replace_boilerplate_from_new_source": "Ignore cached boilerplate and replace the row from explicit non-boilerplate abstract metadata.",
        "find_fuller_metadata": "Treat the cached fragment as context only; find a fuller abstract or source-confirmed description before import.",
        "manual_metadata_search": "Use DOI, publisher, index, library, or title-match records to find explicit abstract text; title-only matches stay out of final text.",
        "verify_pdf_or_use_metadata": "Use the PDF only if it is clearly public, article-specific, and not already blocked; otherwise recover source metadata manually.",
        "avoid_rate_limited_cache": "Do not treat the cached rate-limit result as evidence; use another source or retry later with rate-limit controls.",
        "manual_source_route_no_cache": "No local cached response exists for the configured sources; follow the source guide manually.",
    }.get(group, "Review manually before importing.")


def source_to_avoid(row: pd.Series | dict[str, Any], group: str) -> str:
    candidate_source = clean_text(row.get("candidate_source", "") if hasattr(row, "get") else "")
    if group in {"find_external_extension", "do_not_rerun_cached_source"}:
        return f"Do not rerun {candidate_source or 'the cached source'} unchanged."
    if group == "replace_boilerplate_from_new_source":
        return "Do not reuse JSTOR/access/rights boilerplate as abstract text."
    if group == "verify_pdf_or_use_metadata":
        return "Do not retry blocked, HTML, paywalled, or non-article PDF routes unchanged."
    if group == "avoid_rate_limited_cache":
        return f"Do not use the cached {candidate_source or 'source'} rate-limit response as evidence."
    return ""


def suggested_evidence_tier(row: pd.Series | dict[str, Any], group: str) -> str:
    if group == "review_cached_import_candidate":
        return "tier_a_formal_abstract or tier_b_source_description after reviewer verification"
    if group in {"find_external_extension", "review_cached_extension_candidate", "replace_boilerplate_from_new_source", "find_fuller_metadata", "manual_metadata_search"}:
        return "tier_a_formal_abstract or tier_b_source_description"
    if group == "verify_pdf_or_use_metadata":
        return "tier_c_first_page_abstract_or_intro only for verified public article PDF text; otherwise tier_a or tier_b metadata"
    return "not importable until explicit text and provenance are found"


def merge_context(base: pd.DataFrame, context: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    if base.empty or context.empty or "article_id" not in context.columns:
        return base
    keep = [column for column in ["article_id"] + columns if column in context.columns]
    if len(keep) <= 1:
        return base
    return base.merge(context[keep].drop_duplicates("article_id", keep="first"), on="article_id", how="left")


def merge_cell_targets(base: pd.DataFrame, cell_targets: pd.DataFrame) -> pd.DataFrame:
    if base.empty or cell_targets.empty or not {"journal_short", "decade"}.issubset(base.columns) or not {"journal_short", "decade"}.issubset(cell_targets.columns):
        return base
    target_columns = {
        "target_rank": "cell_target_rank",
        "target_level": "cell_target_level",
        "recoveries_to_target_share": "cell_recoveries_to_target_share",
        "projected_share_after_ready_r001": "cell_projected_share_after_ready_r001",
        "ready_r001_target_coverage": "cell_ready_r001_target_coverage",
        "recommended_next_step": "cell_recommended_next_step",
    }
    keep = ["journal_short", "decade"] + [column for column in target_columns if column in cell_targets.columns]
    if len(keep) <= 2:
        return base
    targets = cell_targets[keep].drop_duplicates(["journal_short", "decade"], keep="first").rename(columns=target_columns)
    return base.merge(targets, on=["journal_short", "decade"], how="left")


def recovery_action_packet(
    detail: pd.DataFrame,
    *,
    queue: pd.DataFrame,
    source_guide: pd.DataFrame,
    automation_detail: pd.DataFrame,
    cell_targets: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if detail.empty:
        return pd.DataFrame(columns=ACTION_PACKET_COLUMNS)
    work = detail.copy().fillna("")
    work = merge_context(
        work,
        queue,
        ["decade", "current_abstract", "source_hint", "doi_url", "openalex_work_url", "crossref_work_url", "openalex_title_search_url", "crossref_title_search_url"],
    ).fillna("")
    work = merge_cell_targets(work, cell_targets if cell_targets is not None else pd.DataFrame()).fillna("")
    work = merge_context(
        work,
        source_guide,
        ["source_route_family", "first_source_to_check", "fallback_source_to_check", "acceptable_evidence", "stop_rule", "source_links"],
    ).fillna("")
    work = merge_context(
        work,
        automation_detail,
        ["automation_status", "automation_blocker", "safe_next_action", "source_route_note"],
    ).fillna("")

    rows: list[dict[str, Any]] = []
    for _, row in work.iterrows():
        group = action_group_for_row(row)
        source_to_check_first = clean_text(row.get("first_source_to_check"))
        if not source_to_check_first:
            source_to_check_first = clean_text(row.get("candidate_url")) or clean_text(row.get("source_hint"))
        stop = clean_text(row.get("stop_rule"))
        if clean_text(row.get("safe_next_action")):
            stop = f"{stop} {clean_text(row.get('safe_next_action'))}".strip()
        rows.append(
            {
                "review_rank": clean_text(row.get("review_rank")),
                "article_id": clean_text(row.get("article_id")),
                "quick_win_tier": clean_text(row.get("quick_win_tier")),
                "cell_target_rank": clean_text(row.get("cell_target_rank")),
                "cell_target_level": clean_text(row.get("cell_target_level")),
                "cell_recoveries_to_target_share": clean_text(row.get("cell_recoveries_to_target_share")),
                "cell_projected_share_after_ready_r001": clean_text(row.get("cell_projected_share_after_ready_r001")),
                "cell_ready_r001_target_coverage": clean_text(row.get("cell_ready_r001_target_coverage")),
                "action_group": group,
                "reviewer_action": reviewer_action(group),
                "stop_rule": stop,
                "suggested_evidence_tier": suggested_evidence_tier(row, group),
                "source_to_check_first": source_to_check_first,
                "source_to_avoid": source_to_avoid(row, group),
                "cached_evidence_status": clean_text(row.get("cached_evidence_status")),
                "candidate_source": clean_text(row.get("candidate_source")),
                "candidate_text_chars": clean_text(row.get("candidate_text_chars")),
                "current_text_chars": clean_text(row.get("current_text_chars")),
                "chars_needed_to_threshold": clean_text(row.get("chars_needed_to_threshold")),
                "candidate_quality_flags": clean_text(row.get("candidate_quality_flags")),
                "source_route_family": clean_text(row.get("source_route_family")),
                "automation_status": clean_text(row.get("automation_status")),
                "title": clean_text(row.get("title")),
                "doi": normalize_doi(row.get("doi")),
                "source_links": clean_text(row.get("source_links")),
                "current_abstract": clean_text(row.get("current_abstract")),
                "candidate_url": clean_text(row.get("candidate_url")),
                "candidate_source_record_id": clean_text(row.get("candidate_source_record_id")),
                "review_note": clean_text(row.get("review_note")) or clean_text(row.get("source_route_note")),
                "cell_recommended_next_step": clean_text(row.get("cell_recommended_next_step")),
            }
        )
    return pd.DataFrame(rows, columns=ACTION_PACKET_COLUMNS)


def recovery_action_summary(action_packet: pd.DataFrame) -> pd.DataFrame:
    if action_packet.empty:
        return pd.DataFrame(columns=ACTION_SUMMARY_COLUMNS)
    work = action_packet.copy().fillna("")
    work["_review_rank"] = pd.to_numeric(work.get("review_rank", ""), errors="coerce").fillna(999999).astype(int)
    rows: list[dict[str, Any]] = []
    for (group, tier), subset in work.groupby(["action_group", "quick_win_tier"], sort=False, dropna=False):
        rows.append(
            {
                "action_group": clean_text(group),
                "quick_win_tier": clean_text(tier),
                "rows": len(subset),
                "first_review_rank": int(subset["_review_rank"].min()),
                "reviewer_action": reviewer_action(clean_text(group)),
            }
        )
    return pd.DataFrame(rows, columns=ACTION_SUMMARY_COLUMNS).sort_values(["first_review_rank", "action_group"]).reset_index(drop=True)


def action_slug(value: str) -> str:
    text = clean_text(value).lower()
    chars = [char if char.isalnum() else "_" for char in text]
    slug = "".join(chars)
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_") or "manual_review"


def action_packet_form_rows(queue: pd.DataFrame, action_packet: pd.DataFrame) -> pd.DataFrame:
    if queue.empty or action_packet.empty or "article_id" not in queue.columns or "article_id" not in action_packet.columns:
        return pd.DataFrame()
    action_columns = [
        "article_id",
        "action_group",
        "cell_target_rank",
        "cell_target_level",
        "cell_recoveries_to_target_share",
        "cell_projected_share_after_ready_r001",
        "cell_ready_r001_target_coverage",
        "cell_recommended_next_step",
        "reviewer_action",
        "source_to_avoid",
        "suggested_evidence_tier",
        "cached_evidence_status",
        "candidate_source",
        "candidate_text_chars",
        "candidate_quality_flags",
        "candidate_url",
        "candidate_source_record_id",
        "automation_status",
    ]
    keep = [column for column in action_columns if column in action_packet.columns]
    merged = queue.copy().fillna("").merge(action_packet[keep].drop_duplicates("article_id", keep="first"), on="article_id", how="inner")
    return merged.fillna("")


def write_action_reviewer_packets(
    *,
    queue: pd.DataFrame,
    action_packet: pd.DataFrame,
    output_dir: Path,
    html_dir: Path,
    index_output: Path,
    batch_id: str = "R001",
) -> pd.DataFrame:
    output_dir.mkdir(parents=True, exist_ok=True)
    html_dir.mkdir(parents=True, exist_ok=True)
    for old_path in output_dir.glob(f"recovery_batch_{batch_id}_action_*.csv"):
        if old_path.is_file():
            old_path.unlink()
    for old_path in html_dir.glob(f"recovery_batch_{batch_id}_action_*.html"):
        if old_path.is_file():
            old_path.unlink()

    form_rows = action_packet_form_rows(queue, action_packet)
    if form_rows.empty or "action_group" not in form_rows.columns:
        index = pd.DataFrame(columns=ACTION_REVIEW_PACKET_INDEX_COLUMNS)
        index_output.parent.mkdir(parents=True, exist_ok=True)
        index.to_csv(index_output, index=False)
        return index

    form_rows["_review_rank_numeric"] = pd.to_numeric(form_rows.get("review_rank", ""), errors="coerce").fillna(999999).astype(int)
    form_rows = form_rows.sort_values(["_review_rank_numeric", "article_id"]).drop(columns=["_review_rank_numeric"]).reset_index(drop=True)
    action_order = (
        form_rows.groupby("action_group", sort=False, dropna=False)["review_rank"]
        .apply(lambda values: pd.to_numeric(values, errors="coerce").fillna(999999).astype(int).min())
        .sort_values()
    )
    index_rows: list[dict[str, Any]] = []
    for packet_order, action_group in enumerate(action_order.index.tolist(), start=1):
        packet = form_rows[form_rows["action_group"].astype(str).eq(str(action_group))].copy().fillna("")
        if packet.empty:
            continue
        slug = action_slug(str(action_group))
        filename_base = f"recovery_batch_{batch_id}_action_{packet_order:02d}_{slug}"
        csv_path = output_dir / f"{filename_base}.csv"
        html_path = html_dir / f"{filename_base}.html"
        packet.to_csv(csv_path, index=False)
        html_path.write_text(
            recovery_form_html(packet, title=f"Insufficient Text Recovery {batch_id} Action {packet_order:02d} {action_group}"),
            encoding="utf-8",
        )
        ranks = pd.to_numeric(packet.get("review_rank", ""), errors="coerce").dropna().astype(int).tolist()
        tiers = [clean_text(tier) for tier in packet.get("quick_win_tier", pd.Series(dtype=str)).tolist() if clean_text(tier)]
        index_rows.append(
            {
                "packet_order": packet_order,
                "action_group": clean_text(action_group),
                "rows": len(packet),
                "first_review_rank": min(ranks) if ranks else "",
                "last_review_rank": max(ranks) if ranks else "",
                "quick_win_tiers": "|".join(dict.fromkeys(tiers)),
                "csv_path": str(csv_path),
                "html_path": str(html_path),
                "next_step": "Fill abstract/source provenance, export CSV to data/intermediate/insufficient_text_recovery_review_exports/R001/, run recovery tiered staging, then run recovery split preflight.",
            }
        )
    index = pd.DataFrame(index_rows, columns=ACTION_REVIEW_PACKET_INDEX_COLUMNS)
    index_output.parent.mkdir(parents=True, exist_ok=True)
    index.to_csv(index_output, index=False)
    return index


def recovery_cached_evidence(
    queue: pd.DataFrame,
    *,
    config: dict[str, Any],
    cache_dir: Path,
    sources: list[str],
    source_records: pd.DataFrame,
) -> pd.DataFrame:
    if queue.empty:
        return pd.DataFrame(columns=DETAIL_COLUMNS)
    minimum_chars = int(config.get("minimum_usable_text_chars", 250))
    rows = [
        cached_evidence_for_row(
            row,
            config=config,
            cache_dir=cache_dir,
            sources=sources,
            source_records=source_records,
            minimum_chars=minimum_chars,
        )
        for _, row in queue.fillna("").iterrows()
    ]
    return pd.DataFrame(rows, columns=DETAIL_COLUMNS)


def write_cached_evidence_report(path: Path, detail: pd.DataFrame, summary: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    preview_columns = [
        "review_rank",
        "cached_evidence_status",
        "quick_win_tier",
        "candidate_source",
        "candidate_text_chars",
        "current_text_chars",
        "candidate_quality_flags",
        "title",
        "recommended_action",
    ]
    preview = detail[[column for column in preview_columns if column in detail.columns]].head(40).copy() if not detail.empty else pd.DataFrame(columns=preview_columns)
    lines = [
        "# Recovery Batch R001 Cached Evidence Audit",
        "",
        "This audit is non-mutating. It checks the R001 recovery queue against local cached source responses and `data/intermediate/source_records.csv`; it does not call the network, import abstracts, change labels, or update final article files.",
        "",
        "Use this report to separate rows where the local cache only repeats short or suspect text from rows where cached metadata may already contain importable text. Any accepted row still needs reviewer confirmation plus `abstract`, `source`, either `source_url` or `source_record_id`, and an importable evidence tier in the recovery export.",
        "",
        "## Summary",
        "",
        df_to_markdown(summary, max_rows=40),
        "",
        "## Row Preview",
        "",
        df_to_markdown(preview, max_rows=40),
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_action_packet_report(path: Path, action_packet: pd.DataFrame, summary: pd.DataFrame, packet_index: pd.DataFrame | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    preview_columns = [
        "review_rank",
        "action_group",
        "quick_win_tier",
        "cell_target_rank",
        "cell_target_level",
        "cell_recoveries_to_target_share",
        "chars_needed_to_threshold",
        "title",
        "reviewer_action",
        "source_to_avoid",
    ]
    preview = action_packet[[column for column in preview_columns if column in action_packet.columns]].head(50).copy() if not action_packet.empty else pd.DataFrame(columns=preview_columns)
    lines = [
        "# Recovery Batch R001 Action Packet",
        "",
        "This packet is non-mutating. It combines the R001 recovery queue, source guide, cached-evidence audit, and automation audit into row-level reviewer actions. It does not import text, change labels, call the network, or update final article files.",
        "",
        "Use this before opening individual source pages: it tells reviewers when a cached source should not be rerun, when boilerplate must be replaced, and when manual metadata search is the only useful path.",
        "",
        "## Action Summary",
        "",
        df_to_markdown(summary, max_rows=40),
        "",
        "## Reviewer Packets",
        "",
        df_to_markdown(packet_index if packet_index is not None else pd.DataFrame(), max_rows=40),
        "",
        "## Row Preview",
        "",
        df_to_markdown(preview, max_rows=50),
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def run_recovery_cached_evidence(
    *,
    queue_path: Path,
    config_path: Path,
    cache_dir: Path,
    source_records_path: Path,
    sources_value: str | None,
    output_detail: Path,
    output_summary: Path,
    report_path: Path,
    source_guide_path: Path | None = None,
    automation_detail_path: Path | None = None,
    cell_targets_path: Path | None = None,
    output_action_packet: Path | None = None,
    output_action_summary: Path | None = None,
    action_report_path: Path | None = None,
    action_packet_dir: Path | None = None,
    action_form_dir: Path | None = None,
    action_packet_index_output: Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    config = load_yaml(config_path)
    queue = read_csv_if_exists(queue_path)
    source_records = read_csv_if_exists(source_records_path)
    sources = parse_sources(sources_value, config) if sources_value else DEFAULT_AUDIT_SOURCES
    detail = recovery_cached_evidence(queue, config=config, cache_dir=cache_dir, sources=sources, source_records=source_records)
    summary = cached_evidence_summary(detail)
    output_detail.parent.mkdir(parents=True, exist_ok=True)
    output_summary.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(output_detail, index=False)
    summary.to_csv(output_summary, index=False)
    write_cached_evidence_report(report_path, detail, summary)
    if output_action_packet is not None and output_action_summary is not None and action_report_path is not None:
        action_packet = recovery_action_packet(
            detail,
            queue=queue,
            source_guide=read_csv_if_exists(source_guide_path) if source_guide_path is not None else pd.DataFrame(),
            automation_detail=read_csv_if_exists(automation_detail_path) if automation_detail_path is not None else pd.DataFrame(),
            cell_targets=read_csv_if_exists(cell_targets_path) if cell_targets_path is not None else pd.DataFrame(),
        )
        action_summary = recovery_action_summary(action_packet)
        action_packet_index = pd.DataFrame(columns=ACTION_REVIEW_PACKET_INDEX_COLUMNS)
        if action_packet_dir is not None and action_form_dir is not None and action_packet_index_output is not None:
            action_packet_index = write_action_reviewer_packets(
                queue=queue,
                action_packet=action_packet,
                output_dir=action_packet_dir,
                html_dir=action_form_dir,
                index_output=action_packet_index_output,
            )
        output_action_packet.parent.mkdir(parents=True, exist_ok=True)
        output_action_summary.parent.mkdir(parents=True, exist_ok=True)
        action_packet.to_csv(output_action_packet, index=False)
        action_summary.to_csv(output_action_summary, index=False)
        write_action_packet_report(action_report_path, action_packet, action_summary, action_packet_index)
    print(f"cached_evidence_rows={len(detail)}")
    print(f"cached_evidence_summary_rows={len(summary)}")
    print(f"detail={output_detail}")
    print(f"summary={output_summary}")
    print(f"report={report_path}")
    if output_action_packet is not None and output_action_summary is not None and action_report_path is not None:
        print(f"action_packet={output_action_packet}")
        print(f"action_summary={output_action_summary}")
        print(f"action_report={action_report_path}")
        if action_packet_index_output is not None:
            print(f"action_packet_index={action_packet_index_output}")
    return detail, summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", default="outputs/tables/enriched/recovery_batch_R001_review_queue.csv")
    parser.add_argument("--config", default="config/text_enrichment.yml")
    parser.add_argument("--cache-dir", default="data/intermediate/text_enrichment_cache")
    parser.add_argument("--source-records", default="data/intermediate/source_records.csv")
    parser.add_argument("--sources", default=None, help="Comma-separated source list. Defaults to a cached-audit order.")
    parser.add_argument("--output-detail", default="outputs/tables/enriched/recovery_batch_R001_cached_evidence.csv")
    parser.add_argument("--output-summary", default="outputs/tables/enriched/recovery_batch_R001_cached_evidence_summary.csv")
    parser.add_argument("--report", default="docs/recovery_batch_R001_cached_evidence.md")
    parser.add_argument("--source-guide", default="outputs/tables/enriched/recovery_batch_R001_source_guide.csv")
    parser.add_argument("--automation-detail", default="outputs/tables/enriched/recovery_automation_audit_detail.csv")
    parser.add_argument("--cell-targets", default="outputs/tables/enriched/recovery_cell_targets.csv")
    parser.add_argument("--output-action-packet", default="outputs/tables/enriched/recovery_batch_R001_action_packet.csv")
    parser.add_argument("--output-action-summary", default="outputs/tables/enriched/recovery_batch_R001_action_summary.csv")
    parser.add_argument("--action-report", default="docs/recovery_batch_R001_action_packet.md")
    parser.add_argument("--action-packet-dir", default="outputs/tables/enriched/recovery_batch_R001_action_packets")
    parser.add_argument("--action-form-dir", default="data/intermediate/insufficient_text_recovery_review_forms/R001/actions")
    parser.add_argument("--action-packet-index", default="outputs/tables/enriched/recovery_batch_R001_action_packet_index.csv")
    args = parser.parse_args()
    run_recovery_cached_evidence(
        queue_path=Path(args.queue),
        config_path=Path(args.config),
        cache_dir=Path(args.cache_dir),
        source_records_path=Path(args.source_records),
        sources_value=args.sources,
        output_detail=Path(args.output_detail),
        output_summary=Path(args.output_summary),
        report_path=Path(args.report),
        source_guide_path=Path(args.source_guide),
        automation_detail_path=Path(args.automation_detail),
        cell_targets_path=Path(args.cell_targets),
        output_action_packet=Path(args.output_action_packet),
        output_action_summary=Path(args.output_action_summary),
        action_report_path=Path(args.action_report),
        action_packet_dir=Path(args.action_packet_dir),
        action_form_dir=Path(args.action_form_dir),
        action_packet_index_output=Path(args.action_packet_index),
    )


if __name__ == "__main__":
    main()
