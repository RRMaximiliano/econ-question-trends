from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "lib"))
sys.path.append(str(Path(__file__).resolve().parent))

from econqt_common import clean_text  # noqa: E402


BACKFILL_FIELDS = ["abstract", "source", "source_url", "source_record_id", "evidence_tier", "notes"]


def eligible_enrichment_rows(enrichment_df: pd.DataFrame) -> pd.DataFrame:
    if enrichment_df.empty:
        return pd.DataFrame()
    work = enrichment_df.copy().fillna("")
    required = {"article_id", "enrichment_status", "enriched_abstract"}
    missing = required.difference(work.columns)
    if missing:
        raise ValueError(f"Missing enrichment columns: {', '.join(sorted(missing))}")
    mask = work["enrichment_status"].astype(str).eq("enriched") & work["enriched_abstract"].astype(str).map(clean_text).ne("")
    return work.loc[mask].copy()


def enrichment_source_name(enrichment_row: pd.Series) -> str:
    source = clean_text(enrichment_row.get("enrichment_source"))
    return source or "text_enrichment"


def append_autofill_note(existing: Any, enrichment_row: pd.Series) -> str:
    notes = clean_text(existing)
    parts = ["autofilled_from_text_enrichment"]
    detail = clean_text(enrichment_row.get("enrichment_detail"))
    if detail:
        parts.append(f"enrichment_detail={detail}")
    source = clean_text(enrichment_row.get("enrichment_source"))
    if source == "oa_pdf_first_pages":
        parts.append("source_text_type=first_pages")
    addition = ";".join(parts)
    if not notes:
        return addition
    if "autofilled_from_text_enrichment" in notes:
        return notes
    return f"{notes};{addition}"


def evidence_tier_for_autofill(enrichment_row: pd.Series) -> str:
    explicit = clean_text(enrichment_row.get("evidence_tier"))
    if explicit:
        return explicit
    source = clean_text(enrichment_row.get("enrichment_source"))
    if source == "oa_pdf_first_pages":
        return "tier_c_first_page_abstract_or_intro"
    return "tier_a_formal_abstract"


def autofill_recovery_batch(
    batch_df: pd.DataFrame,
    enrichment_df: pd.DataFrame,
    *,
    overwrite_existing: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    batch = batch_df.copy().fillna("")
    for column in BACKFILL_FIELDS:
        if column not in batch.columns:
            batch[column] = ""

    eligible = eligible_enrichment_rows(enrichment_df)
    if eligible.empty:
        summary = pd.DataFrame(columns=["article_id", "title", "source", "source_url", "filled"])
        return batch, summary

    lookup = eligible.set_index("article_id", drop=False)
    filled_rows: list[dict[str, Any]] = []

    for idx, row in batch.iterrows():
        article_id = clean_text(row.get("article_id"))
        if not article_id or article_id not in lookup.index:
            continue
        if clean_text(row.get("abstract")) and not overwrite_existing:
            continue
        match = lookup.loc[article_id]
        if isinstance(match, pd.DataFrame):
            match = match.iloc[0]

        batch.at[idx, "abstract"] = clean_text(match.get("enriched_abstract"))
        batch.at[idx, "source"] = enrichment_source_name(match)
        batch.at[idx, "source_url"] = clean_text(match.get("enrichment_url"))
        batch.at[idx, "source_record_id"] = clean_text(match.get("source_record_id"))
        batch.at[idx, "evidence_tier"] = evidence_tier_for_autofill(match)
        batch.at[idx, "notes"] = append_autofill_note(row.get("notes"), match)
        filled_rows.append(
            {
                "article_id": article_id,
                "title": clean_text(row.get("title")),
                "source": batch.at[idx, "source"],
                "source_url": batch.at[idx, "source_url"],
                "filled": True,
            }
        )

    summary = pd.DataFrame(filled_rows, columns=["article_id", "title", "source", "source_url", "filled"])
    return batch, summary


def write_autofill_report(path: Path, *, batch_path: Path, output_path: Path, summary: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    source_counts = summary["source"].value_counts(dropna=False).rename_axis("source").reset_index(name="rows") if not summary.empty else pd.DataFrame()
    lines = [
        "# Recovery Batch Autofill Report",
        "",
        f"- Batch input: `{batch_path}`",
        f"- Batch output: `{output_path}`",
        f"- Filled rows: {len(summary)}",
        "",
        "## Source Counts",
        "",
        df_to_markdown(source_counts),
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def df_to_markdown(df: pd.DataFrame, max_rows: int = 30) -> str:
    if df.empty:
        return "_No rows._"
    shown = df.head(max_rows).fillna("")
    headers = list(shown.columns)
    rows = [headers] + shown.astype(str).values.tolist()
    widths = [max(len(row[i]) for row in rows) for i in range(len(headers))]
    header = "| " + " | ".join(headers[i].ljust(widths[i]) for i in range(len(headers))) + " |"
    separator = "| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |"
    body = ["| " + " | ".join(row[i].ljust(widths[i]) for i in range(len(headers))) + " |" for row in rows[1:]]
    suffix = f"\n\n_Only first {max_rows} rows shown._" if len(df) > max_rows else ""
    return "\n".join([header, separator] + body) + suffix


def run_recovery_batch_autofill(
    *,
    batch_input: Path,
    enrichment_candidates: Path,
    batch_output: Path,
    summary_output: Path,
    report_path: Path,
    overwrite_existing: bool,
) -> None:
    batch = pd.read_csv(batch_input, dtype=str).fillna("")
    enrichment = pd.read_csv(enrichment_candidates, dtype=str).fillna("")
    filled_batch, summary = autofill_recovery_batch(batch, enrichment, overwrite_existing=overwrite_existing)

    batch_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    filled_batch.to_csv(batch_output, index=False)
    summary.to_csv(summary_output, index=False)
    write_autofill_report(report_path, batch_path=batch_input, output_path=batch_output, summary=summary)

    print(f"filled_rows={len(summary)}")
    print(f"batch_output={batch_output}")
    print(f"summary_output={summary_output}")
    print(f"report={report_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-input", required=True)
    parser.add_argument("--enrichment-candidates", default="data/intermediate/text_enrichment_candidates.csv")
    parser.add_argument("--batch-output", default="")
    parser.add_argument("--summary-output", default="outputs/tables/enriched/recovery_batch_autofill_summary.csv")
    parser.add_argument("--report", default="docs/recovery_batch_autofill_report.md")
    parser.add_argument("--overwrite-existing", action="store_true")
    args = parser.parse_args()

    batch_input = Path(args.batch_input)
    batch_output = Path(args.batch_output) if args.batch_output else batch_input
    run_recovery_batch_autofill(
        batch_input=batch_input,
        enrichment_candidates=Path(args.enrichment_candidates),
        batch_output=batch_output,
        summary_output=Path(args.summary_output),
        report_path=Path(args.report),
        overwrite_existing=args.overwrite_existing,
    )


if __name__ == "__main__":
    main()
