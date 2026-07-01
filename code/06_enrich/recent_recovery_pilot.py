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
from recovery_progress import df_to_markdown  # noqa: E402
from recovery_review_queue import (  # noqa: E402
    acceptable_evidence,
    doi_route_family,
    fallback_source_to_check,
    first_source_to_check,
    stop_rule,
)


DEFAULT_YEARS = ["2023", "2024", "2025"]
DEFAULT_JOURNALS = ["aer", "ecta", "jpe", "qje", "restud"]
TRIAGE_COLUMNS = [
    "recent_rank",
    "recent_lane",
    "article_id",
    "journal_short",
    "publication_year",
    "title",
    "doi",
    "recovery_batch",
    "recovery_rank",
    "recovery_action",
    "text_enrichment_status",
    "source_route_family",
    "first_source_to_check",
    "stop_rule",
]
SUMMARY_COLUMNS = ["metric", "value"]


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("") if path.exists() else pd.DataFrame()


def parse_csv_list(value: str | None, default: list[str]) -> list[str]:
    if value is None:
        return list(default)
    parsed = [clean_text(part).lower() for part in value.split(",") if clean_text(part)]
    return parsed or list(default)


def route_family_for_recent_row(row: pd.Series) -> str:
    status = clean_text(row.get("text_enrichment_status"))
    oa_pdf_url = clean_text(row.get("oa_pdf_url"))
    if status == "pdf_candidate" or oa_pdf_url:
        return "pdf_blocker_metadata"
    return doi_route_family(row.get("doi"))


def recent_recovery_triage(
    recovery_queue: pd.DataFrame,
    scope_packet: pd.DataFrame,
    *,
    years: list[str] | None = None,
    journals: list[str] | None = None,
) -> pd.DataFrame:
    years = [str(year) for year in (years or DEFAULT_YEARS)]
    journals = [journal.lower() for journal in (journals or DEFAULT_JOURNALS)]
    if recovery_queue.empty:
        return pd.DataFrame(columns=TRIAGE_COLUMNS)
    work = recovery_queue.copy().fillna("")
    for column in RECOVERY_PACKET_COLUMNS:
        if column not in work.columns:
            work[column] = ""
    if "abstract" not in work.columns and "backfill_abstract" in work.columns:
        work["abstract"] = work["backfill_abstract"]
    scoped_ids = set(scope_packet.get("article_id", pd.Series(dtype=str)).astype(str)) if not scope_packet.empty else set()
    work = work[
        work["publication_year"].astype(str).isin(years)
        & work["journal_short"].astype(str).str.lower().isin(journals)
    ].copy()
    if work.empty:
        return pd.DataFrame(columns=TRIAGE_COLUMNS)

    work["recent_lane"] = work["article_id"].astype(str).map(lambda article_id: "scope_review_first" if article_id in scoped_ids else "recover_text")
    work["_lane_order"] = work["recent_lane"].map({"recover_text": 1, "scope_review_first": 2}).fillna(9).astype(int)
    work["_year"] = pd.to_numeric(work["publication_year"], errors="coerce").fillna(9999).astype(int)
    work["_rank"] = pd.to_numeric(work.get("recovery_rank", ""), errors="coerce").fillna(999999).astype(int)
    work = work.sort_values(["_lane_order", "_year", "journal_short", "_rank", "title"]).reset_index(drop=True)
    work["recent_rank"] = [str(index + 1) for index in range(len(work))]
    route_families = work.apply(route_family_for_recent_row, axis=1)
    work["source_route_family"] = route_families
    work["first_source_to_check"] = route_families.map(first_source_to_check)
    work["fallback_source_to_check"] = route_families.map(fallback_source_to_check)
    work["acceptable_evidence"] = route_families.map(acceptable_evidence)
    work["stop_rule"] = route_families.map(stop_rule)
    work["review_note"] = work["recent_lane"].map(
        {
            "recover_text": "Recent top-5 scoped row; recover only source-confirmed abstract/description evidence.",
            "scope_review_first": "Likely recent paratext; complete scope review before spending abstract-recovery effort.",
        }
    )
    return work.drop(columns=["_lane_order", "_year", "_rank"]).reset_index(drop=True)


def recent_recovery_packet(triage: pd.DataFrame) -> pd.DataFrame:
    if triage.empty:
        return pd.DataFrame(columns=RECOVERY_PACKET_COLUMNS)
    packet = triage[triage["recent_lane"].astype(str).eq("recover_text")].copy().fillna("")
    for column in RECOVERY_PACKET_COLUMNS:
        if column not in packet.columns:
            packet[column] = ""
    return packet


def recent_recovery_summary(triage: pd.DataFrame, packet: pd.DataFrame, *, years: list[str], journals: list[str]) -> pd.DataFrame:
    lanes = triage["recent_lane"].value_counts().to_dict() if not triage.empty else {}
    rows: list[dict[str, Any]] = [
        {"metric": "recent_years", "value": "|".join(years)},
        {"metric": "recent_journals", "value": "|".join(journals)},
        {"metric": "recent_queue_rows", "value": len(triage)},
        {"metric": "recent_scope_review_first_rows", "value": int(lanes.get("scope_review_first", 0))},
        {"metric": "recent_recover_text_rows", "value": int(lanes.get("recover_text", 0))},
        {"metric": "recent_recovery_packet_rows", "value": len(packet)},
    ]
    if not packet.empty:
        rows.append(
            {
                "metric": "recent_recovery_journal_years",
                "value": "|".join(
                    dict.fromkeys(
                        f"{clean_text(row.get('journal_short'))}:{clean_text(row.get('publication_year'))}"
                        for _, row in packet.iterrows()
                    )
                ),
            }
        )
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


def write_recent_recovery_report(
    path: Path,
    *,
    triage: pd.DataFrame,
    packet: pd.DataFrame,
    summary: pd.DataFrame,
    triage_output: Path,
    packet_output: Path,
    form_output: Path,
    export_path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    triage_preview = triage[[column for column in TRIAGE_COLUMNS if column in triage.columns]].copy() if not triage.empty else pd.DataFrame(columns=TRIAGE_COLUMNS)
    packet_preview_columns = ["recent_rank", "article_id", "journal_short", "publication_year", "title", "doi", "source_route_family", "first_source_to_check", "stop_rule"]
    packet_preview = packet[[column for column in packet_preview_columns if column in packet.columns]].copy() if not packet.empty else pd.DataFrame(columns=packet_preview_columns)
    lines = [
        "# Recent 2023-2025 Recovery Pilot",
        "",
        "This generated handoff keeps the user's requested recent top-5 pilot separate from the broader R001 backfill. It is non-mutating and does not change abstracts, labels, scope decisions, or final article files.",
        "",
        f"- Triage CSV: `{triage_output}`",
        f"- Recovery packet CSV: `{packet_output}`",
        f"- Browser form: `{form_output}`",
        f"- Suggested export path: `{export_path}`",
        "",
        "## Summary",
        "",
        df_to_markdown(summary, max_rows=20),
        "",
        "## Reviewer Rule",
        "",
        "- Work `recover_text` rows first; they remain in the recent analysis denominator and need source-confirmed text.",
        "- Do not recover abstracts for `scope_review_first` rows until the scope packet marks them `keep_research` or `unsure` with notes.",
        "- Completed recovery rows require `abstract`, `source`, either `source_url` or `source_record_id`, and an importable `evidence_tier`.",
        "- Keep title-only, citation-only, search-snippet-only, blocked-PDF-only, and provenance-free evidence unresolved.",
        "",
        "## After Export Commands",
        "",
        "Run the dry-run first after saving completed browser-form exports to the suggested export path.",
        "",
        "```bash",
        f"PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_import_abstract_backfill.py --input {export_path} --skip-empty-abstracts --dry-run --require-source-metadata",
        f"PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_import_abstract_backfill.py --input {export_path} --skip-empty-abstracts --require-source-metadata --fail-on-errors",
        "PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_text_enrichment.py",
        "PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_classification_pilot.py --input data/final/articles_enriched_pilot.csv --output data/final/articles_classified_enriched_pilot.csv",
        "PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_classification_diagnostics.py --classified data/final/articles_classified_enriched_pilot.csv --validation data/intermediate/manual_validation_sample.csv --output-dir outputs/tables/enriched --report docs/classification_diagnostics_enriched.md",
        "PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_human_review_refresh.py",
        "```",
        "",
        "## Recover-Text Rows",
        "",
        df_to_markdown(packet_preview, max_rows=20),
        "",
        "## Full Recent Triage",
        "",
        df_to_markdown(triage_preview, max_rows=40),
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def run_recent_recovery_pilot(
    *,
    recovery_queue_path: Path,
    scope_packet_path: Path,
    triage_output: Path,
    packet_output: Path,
    summary_output: Path,
    form_output: Path,
    report_path: Path,
    export_path: Path,
    years: list[str] | None = None,
    journals: list[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    years = [str(year) for year in (years or DEFAULT_YEARS)]
    journals = [journal.lower() for journal in (journals or DEFAULT_JOURNALS)]
    recovery_queue = read_csv_if_exists(recovery_queue_path)
    scope_packet = read_csv_if_exists(scope_packet_path)
    triage = recent_recovery_triage(recovery_queue, scope_packet, years=years, journals=journals)
    packet = recent_recovery_packet(triage)
    summary = recent_recovery_summary(triage, packet, years=years, journals=journals)

    for path, frame in [(triage_output, triage), (packet_output, packet), (summary_output, summary)]:
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)
    form_output.parent.mkdir(parents=True, exist_ok=True)
    form_output.write_text(recovery_form_html(packet, title="Recent 2023-2025 Insufficient Text Recovery"), encoding="utf-8")
    write_recent_recovery_report(
        report_path,
        triage=triage,
        packet=packet,
        summary=summary,
        triage_output=triage_output,
        packet_output=packet_output,
        form_output=form_output,
        export_path=export_path,
    )
    lookup = dict(zip(summary["metric"], summary["value"]))
    print(f"recent_queue_rows={lookup.get('recent_queue_rows', '0')}")
    print(f"recent_scope_review_first_rows={lookup.get('recent_scope_review_first_rows', '0')}")
    print(f"recent_recover_text_rows={lookup.get('recent_recover_text_rows', '0')}")
    print(f"triage={triage_output}")
    print(f"packet={packet_output}")
    print(f"form={form_output}")
    print(f"report={report_path}")
    return triage, packet, summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recovery-queue", default="outputs/tables/enriched/insufficient_text_recovery_queue.csv")
    parser.add_argument("--scope-packet", default="data/intermediate/scope_review/scope_review_packet.csv")
    parser.add_argument("--triage-output", default="outputs/tables/enriched/recent_2023_2025_insufficient_text_triage.csv")
    parser.add_argument("--packet-output", default="outputs/tables/enriched/recent_2023_2025_recovery_packet.csv")
    parser.add_argument("--summary-output", default="outputs/tables/enriched/recent_2023_2025_recovery_summary.csv")
    parser.add_argument("--form-output", default="data/intermediate/insufficient_text_recovery_review_forms/recent_2023_2025/recent_2023_2025_recovery_packet.html")
    parser.add_argument("--report", default="docs/recent_2023_2025_recovery_pilot.md")
    parser.add_argument("--export-path", default="data/intermediate/insufficient_text_recovery_review_exports/recent_2023_2025/recent_2023_2025_recovery_packet.csv")
    parser.add_argument("--years", default=",".join(DEFAULT_YEARS))
    parser.add_argument("--journals", default=",".join(DEFAULT_JOURNALS))
    args = parser.parse_args()
    run_recent_recovery_pilot(
        recovery_queue_path=Path(args.recovery_queue),
        scope_packet_path=Path(args.scope_packet),
        triage_output=Path(args.triage_output),
        packet_output=Path(args.packet_output),
        summary_output=Path(args.summary_output),
        form_output=Path(args.form_output),
        report_path=Path(args.report),
        export_path=Path(args.export_path),
        years=parse_csv_list(args.years, DEFAULT_YEARS),
        journals=parse_csv_list(args.journals, DEFAULT_JOURNALS),
    )


if __name__ == "__main__":
    main()
