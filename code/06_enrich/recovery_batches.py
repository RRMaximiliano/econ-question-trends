from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "lib"))
sys.path.append(str(Path(__file__).resolve().parent))

from econqt_common import clean_text  # noqa: E402
from evidence_tier_policy import EVIDENCE_TIER_OPTIONS  # noqa: E402


BACKFILL_COLUMNS = ["article_id", "doi", "title", "publication_year", "abstract", "source", "source_url", "source_record_id", "evidence_tier", "notes"]
EDITABLE_RECOVERY_COLUMNS = ["abstract", "source", "source_url", "source_record_id", "evidence_tier", "notes"]
BACKFILL_EDIT_COLUMNS = ["abstract", "source", "source_url", "source_record_id", "evidence_tier"]

RECOVERY_PACKET_COLUMNS = [
    "recovery_batch",
    "batch_row",
    "recovery_rank",
    "recovery_priority",
    "recovery_priority_score",
    "recovery_action",
    "recovery_reason",
    "article_id",
    "journal_short",
    "publication_year",
    "decade",
    "title",
    "doi",
    "openalex_id",
    "article_url",
    "oa_pdf_url",
    "doi_url",
    "crossref_work_url",
    "openalex_work_url",
    "openalex_title_search_url",
    "crossref_title_search_url",
    "semantic_scholar_title_search_url",
    "title_only_suggested_category",
    "title_only_confidence",
    "title_only_reason",
    "abstract",
    "source",
    "source_url",
    "source_record_id",
    "evidence_tier",
    "notes",
]


def normalize_queue(queue_df: pd.DataFrame, batch_size: int) -> pd.DataFrame:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    queue = queue_df.copy().fillna("").reset_index(drop=True)
    if "recovery_rank" not in queue.columns:
        queue["recovery_rank"] = range(1, len(queue) + 1)
    if "recovery_batch" not in queue.columns or not queue["recovery_batch"].astype(str).str.strip().any():
        queue["recovery_batch"] = [f"R{((index // batch_size) + 1):03d}" for index in range(len(queue))]
    if "abstract" not in queue.columns:
        queue["abstract"] = queue["backfill_abstract"] if "backfill_abstract" in queue.columns else ""
    for column in BACKFILL_COLUMNS:
        if column not in queue.columns:
            queue[column] = ""
    for column in RECOVERY_PACKET_COLUMNS:
        if column not in queue.columns:
            queue[column] = ""
    return queue


def read_existing_recovery_edits(output_dir: Path) -> pd.DataFrame:
    if not output_dir.exists():
        return pd.DataFrame(columns=["article_id"] + EDITABLE_RECOVERY_COLUMNS)
    frames: list[pd.DataFrame] = []
    for path in sorted(output_dir.glob("insufficient_text_recovery_batch_*.csv")):
        try:
            frame = pd.read_csv(path, dtype=str).fillna("")
        except Exception:  # noqa: BLE001
            continue
        if "article_id" not in frame.columns:
            continue
        for column in EDITABLE_RECOVERY_COLUMNS:
            if column not in frame.columns:
                frame[column] = ""
        frames.append(frame[["article_id"] + EDITABLE_RECOVERY_COLUMNS].copy())
    if not frames:
        return pd.DataFrame(columns=["article_id"] + EDITABLE_RECOVERY_COLUMNS)

    combined = pd.concat(frames, ignore_index=True).fillna("")
    combined["_filled_count"] = combined.apply(existing_edit_count, axis=1)
    combined = combined[combined["_filled_count"] > 0].copy()
    if combined.empty:
        return pd.DataFrame(columns=["article_id"] + EDITABLE_RECOVERY_COLUMNS)
    combined = combined.sort_values(["article_id", "_filled_count"], ascending=[True, False])
    return combined.drop_duplicates("article_id", keep="first")[["article_id"] + EDITABLE_RECOVERY_COLUMNS].reset_index(drop=True)


def is_user_note(value: Any) -> bool:
    note = clean_text(value)
    return bool(note and not note.startswith("suggested_action="))


def existing_edit_count(row: pd.Series) -> int:
    count = sum(1 for column in BACKFILL_EDIT_COLUMNS if clean_text(row.get(column)))
    if is_user_note(row.get("notes")):
        count += 1
    return count


def apply_existing_recovery_edits(queue_df: pd.DataFrame, existing_edits: pd.DataFrame) -> pd.DataFrame:
    if queue_df.empty or existing_edits.empty or "article_id" not in queue_df.columns:
        return queue_df.copy()
    out = queue_df.copy().fillna("")
    for column in EDITABLE_RECOVERY_COLUMNS:
        if column not in out.columns:
            out[column] = ""
    existing = existing_edits.copy().fillna("")
    for column in EDITABLE_RECOVERY_COLUMNS:
        if column not in existing.columns:
            existing[column] = ""
    existing_lookup = existing.set_index("article_id", drop=False)
    for idx, row in out.iterrows():
        article_id = clean_text(row.get("article_id"))
        if not article_id or article_id not in existing_lookup.index:
            continue
        edit_row = existing_lookup.loc[article_id]
        if isinstance(edit_row, pd.DataFrame):
            edit_row = edit_row.iloc[0]
        for column in EDITABLE_RECOVERY_COLUMNS:
            existing_value = clean_text(edit_row.get(column))
            if existing_value:
                if column == "notes" and not is_user_note(existing_value):
                    continue
                out.at[idx, column] = existing_value
    return out


def make_recovery_packets(queue_df: pd.DataFrame, batch_size: int = 100) -> list[tuple[str, pd.DataFrame]]:
    queue = normalize_queue(queue_df, batch_size)
    packets: list[tuple[str, pd.DataFrame]] = []
    for batch_id, batch in queue.groupby("recovery_batch", sort=True, dropna=False):
        packet = batch.copy().reset_index(drop=True)
        packet["batch_row"] = [f"{i:03d}" for i in range(1, len(packet) + 1)]
        for idx, row in packet.iterrows():
            action_note = f"suggested_action={clean_text(row.get('recovery_action'))}"
            reason_note = f"recovery_reason={clean_text(row.get('recovery_reason'))}"
            existing_notes = clean_text(row.get("notes"))
            packet.at[idx, "notes"] = existing_notes or f"{action_note};{reason_note}"
        packets.append((clean_text(batch_id), packet[RECOVERY_PACKET_COLUMNS].copy()))
    return packets


def batch_summary(packets: list[tuple[str, pd.DataFrame]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for batch_id, packet in packets:
        abstract_filled = packet["abstract"].astype(str).str.strip().ne("")
        row: dict[str, Any] = {
            "recovery_batch": batch_id,
            "total_rows": len(packet),
            "completed_backfill_abstracts": int(abstract_filled.sum()),
            "remaining_backfill_abstracts": int((~abstract_filled).sum()),
            "high_priority_rows": int(packet["recovery_priority"].astype(str).eq("high").sum()),
            "medium_priority_rows": int(packet["recovery_priority"].astype(str).eq("medium").sum()),
            "low_priority_rows": int(packet["recovery_priority"].astype(str).eq("low").sum()),
        }
        for action, count in packet["recovery_action"].astype(str).value_counts().sort_index().items():
            safe_action = action or "missing"
            row[f"action_{safe_action}"] = int(count)
        rows.append(row)
    return pd.DataFrame(rows).fillna(0)


def recovery_form_html(packet_df: pd.DataFrame, *, title: str) -> str:
    packet = packet_df.copy().fillna("")
    rows = packet.to_dict(orient="records")
    payload = json.dumps({"rows": rows}, ensure_ascii=False)
    title_text = html.escape(title)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title_text}</title>
  <style>
    :root {{ color-scheme: light; --text: #1f2933; --muted: #667085; --line: #d7dce2; --panel: #f7f8fa; --accent: #215c5c; }}
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: var(--text); background: #fff; }}
    header {{ position: sticky; top: 0; z-index: 2; display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 14px 20px; border-bottom: 1px solid var(--line); background: rgba(255,255,255,.96); }}
    h1 {{ margin: 0; font-size: 18px; font-weight: 650; }}
    main {{ padding: 18px 20px 32px; }}
    .toolbar {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
    button {{ border: 1px solid var(--accent); background: var(--accent); color: #fff; border-radius: 6px; padding: 8px 11px; font-weight: 600; cursor: pointer; }}
    .count {{ color: var(--muted); font-size: 13px; }}
    .item {{ border-top: 1px solid var(--line); padding: 18px 0; display: grid; grid-template-columns: minmax(220px, 340px) 1fr; gap: 18px; }}
    .meta {{ font-size: 13px; line-height: 1.45; color: var(--muted); }}
    .title {{ color: var(--text); font-size: 16px; line-height: 1.35; font-weight: 650; margin-bottom: 8px; }}
    .links {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }}
    a {{ color: #174e7a; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .context {{ margin-top: 10px; padding: 9px 10px; border: 1px solid var(--line); border-radius: 6px; background: var(--panel); color: var(--text); }}
    .context div {{ margin: 4px 0; }}
    .context strong {{ color: var(--muted); font-weight: 650; }}
    .fields {{ display: grid; gap: 10px; }}
    label {{ display: grid; gap: 5px; font-size: 12px; color: var(--muted); font-weight: 600; }}
    input, textarea {{ width: 100%; box-sizing: border-box; border: 1px solid var(--line); border-radius: 6px; padding: 8px 9px; font: inherit; color: var(--text); background: #fff; }}
    textarea {{ min-height: 120px; resize: vertical; line-height: 1.4; }}
    .inline {{ display: grid; grid-template-columns: repeat(3, minmax(120px, 1fr)); gap: 10px; }}
    @media (max-width: 820px) {{ .item {{ grid-template-columns: 1fr; }} .inline {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <header>
    <h1>{title_text}</h1>
    <div class="toolbar">
      <span class="count" id="count"></span>
      <button type="button" id="export">Export CSV</button>
    </div>
  </header>
  <main id="rows"></main>
  <script>
    const payload = {payload};
    const evidenceTierOptions = {json.dumps(EVIDENCE_TIER_OPTIONS)};
    const storageKey = "eqt_recovery_" + location.pathname;
    const saved = JSON.parse(localStorage.getItem(storageKey) || "{{}}");
    const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, ch => ({{"&":"&amp;","<":"&lt;",">":"&gt;","\\\"":"&quot;","'":"&#39;"}}[ch]));
    const fieldValue = (row, name) => saved[row.article_id]?.[name] ?? row[name] ?? "";
    const link = (label, url) => url ? `<a href="${{escapeHtml(url)}}" target="_blank" rel="noreferrer">${{escapeHtml(label)}}</a>` : "";
    const contextLine = (label, value) => String(value ?? "").trim() ? `<div><strong>${{escapeHtml(label)}}:</strong> ${{escapeHtml(value)}}</div>` : "";
    const contextBlock = row => {{
      const lines = [
        contextLine("Review rank", row.review_rank),
        contextLine("Action group", row.action_group),
        contextLine("Reviewer action", row.reviewer_action),
        contextLine("Source to avoid", row.source_to_avoid),
        contextLine("Suggested evidence tier", row.suggested_evidence_tier),
        contextLine("Row status", row.row_status),
        contextLine("Workflow", row.recommended_workflow),
        contextLine("Source route", row.source_route_family),
        contextLine("Cached evidence", row.cached_evidence_status),
        contextLine("Candidate source", row.candidate_source),
        contextLine("Candidate chars", row.candidate_text_chars),
        contextLine("Current text quality", row.current_text_quality_flag),
        contextLine("First source to check", row.first_source_to_check),
        contextLine("Fallback source", row.fallback_source_to_check),
        contextLine("Acceptable evidence", row.acceptable_evidence),
        contextLine("Stop rule", row.stop_rule),
        contextLine("Current text chars", row.current_text_chars),
        contextLine("Current abstract source", row.current_abstract_source),
        contextLine("Current abstract", row.current_abstract),
        contextLine("Prior attempts", row.prior_attempt_summary),
        contextLine("Attempt details", row.prior_attempt_detail_summary),
        contextLine("Review note", row.review_note)
      ].join("");
      return lines ? `<div class="context">${{lines}}</div>` : "";
    }};
    function saveField(articleId, name, value) {{
      saved[articleId] = saved[articleId] || {{}};
      saved[articleId][name] = value;
      localStorage.setItem(storageKey, JSON.stringify(saved));
      updateCount();
    }}
    function rowHtml(row) {{
      const id = escapeHtml(row.article_id);
      return `<section class="item">
        <div class="meta">
          <div class="title">${{escapeHtml(row.title)}}</div>
          <div>${{escapeHtml(row.journal_short)}} · ${{escapeHtml(row.publication_year)}} · rank ${{escapeHtml(row.recovery_rank)}} · ${{escapeHtml(row.recovery_priority)}}</div>
          <div>${{escapeHtml(row.recovery_action)}}</div>
          <div>${{escapeHtml(row.recovery_reason)}}</div>
          ${{contextBlock(row)}}
          <div class="links">
            ${{link("DOI", row.doi_url)}} ${{link("Article", row.article_url)}} ${{link("OA PDF", row.oa_pdf_url)}} ${{link("OpenAlex", row.openalex_work_url)}} ${{link("Crossref", row.crossref_work_url)}} ${{link("OpenAlex title", row.openalex_title_search_url)}} ${{link("Crossref title", row.crossref_title_search_url)}} ${{link("Semantic Scholar", row.semantic_scholar_title_search_url)}}
          </div>
        </div>
        <div class="fields">
          <label>Abstract<textarea data-id="${{id}}" data-name="abstract">${{escapeHtml(fieldValue(row, "abstract"))}}</textarea></label>
          <div class="inline">
            <label>Source<input data-id="${{id}}" data-name="source" value="${{escapeHtml(fieldValue(row, "source"))}}"></label>
            <label>Source URL<input data-id="${{id}}" data-name="source_url" value="${{escapeHtml(fieldValue(row, "source_url"))}}"></label>
            <label>Source Record ID<input data-id="${{id}}" data-name="source_record_id" value="${{escapeHtml(fieldValue(row, "source_record_id"))}}"></label>
          </div>
          <label>Evidence Tier<select data-id="${{id}}" data-name="evidence_tier">
            ${{evidenceTierOptions.map(option => `<option value="${{escapeHtml(option.value)}}" ${{String(fieldValue(row, "evidence_tier")) === option.value ? "selected" : ""}}>${{escapeHtml(option.label)}}</option>`).join("")}}
          </select></label>
          <label>Notes<input data-id="${{id}}" data-name="notes" value="${{escapeHtml(fieldValue(row, "notes"))}}"></label>
        </div>
      </section>`;
    }}
    function updateCount() {{
      const completed = payload.rows.filter(row => String(fieldValue(row, "abstract")).trim()).length;
      document.getElementById("count").textContent = `${{completed}} / ${{payload.rows.length}} abstracts filled`;
    }}
    function csvEscape(value) {{
      const text = String(value ?? "");
      return /[",\\n]/.test(text) ? `"${{text.replace(/"/g, '""')}}"` : text;
    }}
    document.getElementById("rows").innerHTML = payload.rows.map(rowHtml).join("");
    document.querySelectorAll("input, textarea, select").forEach(el => el.addEventListener("input", event => saveField(event.target.dataset.id, event.target.dataset.name, event.target.value)));
    document.getElementById("export").addEventListener("click", () => {{
      const columns = {json.dumps(RECOVERY_PACKET_COLUMNS)};
      const records = payload.rows.map(row => {{
        const out = {{...row, ...(saved[row.article_id] || {{}})}};
        return columns.map(column => csvEscape(out[column] ?? "")).join(",");
      }});
      const csv = [columns.join(","), ...records].join("\\n");
      const blob = new Blob([csv], {{type: "text/csv"}});
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "{html.escape(title).replace(' ', '_')}.csv";
      a.click();
      URL.revokeObjectURL(url);
    }});
    updateCount();
  </script>
</body>
</html>
"""


def write_recovery_batches(
    *,
    queue_path: Path,
    output_dir: Path,
    html_dir: Path | None,
    summary_output: Path,
    batch_size: int,
    preserve_existing: bool = True,
) -> None:
    queue = pd.read_csv(queue_path, dtype=str).fillna("")
    if preserve_existing:
        queue = apply_existing_recovery_edits(queue, read_existing_recovery_edits(output_dir))
    packets = make_recovery_packets(queue, batch_size=batch_size)
    output_dir.mkdir(parents=True, exist_ok=True)
    if html_dir:
        html_dir.mkdir(parents=True, exist_ok=True)
    for batch_id, packet in packets:
        filename = f"insufficient_text_recovery_batch_{batch_id}.csv"
        packet.to_csv(output_dir / filename, index=False)
        if html_dir:
            (html_dir / filename.replace(".csv", ".html")).write_text(
                recovery_form_html(packet, title=f"Insufficient Text Recovery {batch_id}"),
                encoding="utf-8",
            )
    summary = batch_summary(packets)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(summary_output, index=False)
    print(f"batches={len(packets)}")
    print(f"summary={summary_output}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", default="outputs/tables/enriched/insufficient_text_recovery_queue.csv")
    parser.add_argument("--output-dir", default="data/intermediate/insufficient_text_recovery_batches")
    parser.add_argument("--html-dir", default="data/intermediate/insufficient_text_recovery_forms")
    parser.add_argument("--summary-output", default="outputs/tables/enriched/insufficient_text_recovery_batch_summary.csv")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--no-html", action="store_true")
    parser.add_argument("--overwrite-existing", action="store_true")
    args = parser.parse_args()
    write_recovery_batches(
        queue_path=Path(args.queue),
        output_dir=Path(args.output_dir),
        html_dir=None if args.no_html else Path(args.html_dir),
        summary_output=Path(args.summary_output),
        batch_size=args.batch_size,
        preserve_existing=not args.overwrite_existing,
    )


if __name__ == "__main__":
    main()
