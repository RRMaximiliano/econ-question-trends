from __future__ import annotations

import argparse
import html
import json
import os
import re
from pathlib import Path
from typing import Any

import pandas as pd


MANUAL_COLUMNS = ["manual_label", "manual_confidence", "manual_notes", "reviewer_id", "review_date"]
ALLOWED_MANUAL_LABELS = ["causal", "predictive", "other", "insufficient_text"]
ALLOWED_MANUAL_CONFIDENCE = ["high", "medium", "low"]
VALIDATION_ERROR_COLUMNS = ["validation_id", "article_id", "row_number", "field", "value", "error"]
DEFAULT_EXCLUDED_SCOPES = ["review_erratum_paratext", "comment_reply", "lecture_address"]
DEFAULT_VALIDATION_DRIFT_COLUMNS = [
    "causal_predictive_category",
    "classification_confidence",
    "classification_text_chars",
    "text_enrichment_status",
    "text_enrichment_source",
    "abstract",
    "article_scope",
]
OVERLAP_DISAGREEMENT_COLUMNS = [
    "overlap_id",
    "validation_id",
    "article_id",
    "title",
    "primary_manual_label",
    "primary_manual_confidence",
    "primary_reviewer_id",
    "overlap_manual_label",
    "overlap_manual_confidence",
    "overlap_reviewer_id",
    "primary_manual_notes",
    "overlap_manual_notes",
    "adjudicated_label",
    "adjudication_notes",
    "adjudicator_id",
    "adjudication_date",
]
CALIBRATION_DISAGREEMENT_COLUMNS = [
    "calibration_id",
    "validation_id",
    "article_id",
    "title",
    "reviewer_labels",
    "reviewer_confidences",
    "reviewer_notes",
    "label_set",
    "adjudicated_label",
    "adjudication_notes",
    "adjudicator_id",
    "adjudication_date",
]
BLIND_REVIEWER_COLUMNS = [
    "validation_id",
    "article_id",
    "title",
    "abstract",
    "manual_label",
    "manual_confidence",
    "manual_notes",
    "reviewer_id",
    "review_date",
]
AUDIT_REVIEWER_COLUMNS = [
    "validation_id",
    "article_id",
    "journal_short",
    "publication_year",
    "title",
    "abstract",
    "validation_category",
    "validation_confidence",
    "classification_reason",
    "causal_language_terms",
    "predictive_language_terms",
    "manual_label",
    "manual_confidence",
    "manual_notes",
    "reviewer_id",
    "review_date",
]


def nonempty(series: pd.Series) -> pd.Series:
    return series.notna() & (series.astype(str).str.strip() != "")


def numeric_series(series: pd.Series, default: int = 0) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(default)


def current_category_and_confidence(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if {"llm_category", "llm_confidence", "llm_status"}.issubset(out.columns):
        llm_ok = (out["llm_status"].astype(str) == "ok") & nonempty(out["llm_category"])
    else:
        llm_ok = pd.Series(False, index=out.index)

    out["validation_category"] = out.get("causal_predictive_category", "").astype(str)
    out["validation_confidence"] = out.get("classification_confidence", "").astype(str)
    if llm_ok.any():
        out.loc[llm_ok, "validation_category"] = out.loc[llm_ok, "llm_category"].astype(str)
        out.loc[llm_ok, "validation_confidence"] = out.loc[llm_ok, "llm_confidence"].astype(str)
    out["validation_category"] = out["validation_category"].replace("", "missing")
    out["validation_confidence"] = out["validation_confidence"].replace("", "missing")
    return out


def assign_validation_strata(df: pd.DataFrame) -> pd.DataFrame:
    out = current_category_and_confidence(df)
    abstract = out["abstract"] if "abstract" in out else pd.Series("", index=out.index)
    out["has_abstract"] = nonempty(abstract)
    out["abstract_chars"] = abstract.fillna("").astype(str).str.len()
    out["publication_year_num"] = numeric_series(out["publication_year"], default=0) if "publication_year" in out else 0
    out["validation_decade"] = ((out["publication_year_num"].astype(int) // 10) * 10).astype(str)
    out.loc[out["publication_year_num"] <= 0, "validation_decade"] = "missing"

    causal_score = (
        numeric_series(out["causal_language_indicator"], default=0)
        if "causal_language_indicator" in out
        else pd.Series(0, index=out.index)
    )
    predictive_score = (
        numeric_series(out["predictive_language_indicator"], default=0)
        if "predictive_language_indicator" in out
        else pd.Series(0, index=out.index)
    )
    out["causal_score_bin"] = pd.cut(
        causal_score,
        bins=[-1, 0, 1, 3, float("inf")],
        labels=["none", "low", "medium", "high"],
    ).astype(str)
    out["predictive_score_bin"] = pd.cut(
        predictive_score,
        bins=[-1, 0, 1, 3, float("inf")],
        labels=["none", "low", "medium", "high"],
    ).astype(str)
    out["validation_ambiguous"] = (
        ((causal_score > 0) & (predictive_score > 0))
        | (out["validation_confidence"].astype(str) == "low")
        | (out["validation_category"].astype(str) == "insufficient_text")
    )
    out["validation_stratum"] = (
        out["journal_short"].astype(str)
        + "|"
        + out["validation_decade"].astype(str)
        + "|"
        + out["validation_category"].astype(str)
        + "|"
        + out["validation_confidence"].astype(str)
        + "|abstract="
        + out["has_abstract"].astype(str)
        + "|ambiguous="
        + out["validation_ambiguous"].astype(str)
    )
    return out


def unique_concat(frames: list[pd.DataFrame]) -> pd.DataFrame:
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, axis=0)
    return combined.loc[~combined["article_id"].duplicated()].copy()


def sample_validation_rows(df: pd.DataFrame, sample_size: int, seed: int) -> pd.DataFrame:
    if sample_size <= 0:
        raise ValueError("sample_size must be positive")

    out = assign_validation_strata(df)
    shuffled = out.sample(frac=1, random_state=seed).reset_index(drop=True)
    selected_parts: list[pd.DataFrame] = []

    insufficient_cap = max(1, int(sample_size * 0.20))
    ambiguous_cap = max(1, int(sample_size * 0.35))

    insufficient = shuffled[shuffled["validation_category"] == "insufficient_text"].head(insufficient_cap)
    ambiguous = shuffled[shuffled["validation_ambiguous"]].head(ambiguous_cap)
    coverage = (
        shuffled.groupby(["journal_short", "validation_decade", "validation_category"], dropna=False)
        .head(1)
        .reset_index(drop=True)
    )
    selected_parts.extend([insufficient, ambiguous, coverage])
    selected = unique_concat(selected_parts)

    if len(selected) > sample_size:
        selected = selected.sample(n=sample_size, random_state=seed).reset_index(drop=True)
    elif len(selected) < sample_size:
        remaining = shuffled[~shuffled["article_id"].isin(selected["article_id"])]
        fill = remaining.head(sample_size - len(selected))
        selected = unique_concat([selected, fill]).reset_index(drop=True)
    else:
        selected = selected.reset_index(drop=True)

    return selected.head(sample_size).copy()


def filter_validation_scope(df: pd.DataFrame, excluded_scopes: list[str] | None) -> pd.DataFrame:
    excluded = {scope for scope in excluded_scopes or [] if scope}
    if not excluded or "article_scope" not in df.columns:
        return df.copy()
    scope = df["article_scope"].replace("", "missing").astype(str)
    return df[~scope.isin(excluded)].copy()


def make_label_template(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy().reset_index(drop=True)
    out.insert(0, "validation_id", [f"VAL{i:04d}" for i in range(1, len(out) + 1)])
    for column in MANUAL_COLUMNS:
        out[column] = ""
    return out


def completed_manual_label_count(path: Path) -> int:
    if not path.exists():
        return 0
    sample = pd.read_csv(path, dtype=str).fillna("")
    if "manual_label" not in sample.columns:
        return 0
    return int(sample["manual_label"].astype(str).str.strip().ne("").sum())


def guard_against_overwriting_completed_labels(path: Path, *, overwrite_labeled: bool = False) -> None:
    completed = completed_manual_label_count(path)
    if completed and not overwrite_labeled:
        raise SystemExit(
            f"Refusing to overwrite {path}: {completed} completed manual labels found. "
            "Use --overwrite-labeled only after exporting/backing up existing labels."
        )


def reviewer_columns_for_mode(mode: str) -> list[str]:
    if mode == "blind":
        return BLIND_REVIEWER_COLUMNS
    if mode == "audit":
        return AUDIT_REVIEWER_COLUMNS
    raise ValueError("reviewer packet mode must be 'blind' or 'audit'")


def make_reviewer_packet(df: pd.DataFrame, mode: str = "blind") -> pd.DataFrame:
    out = df.copy().fillna("")
    columns = reviewer_columns_for_mode(mode)
    for column in columns:
        if column not in out.columns:
            out[column] = ""
    return out[columns].copy()


def make_reviewer_batches(packet_df: pd.DataFrame, batch_size: int) -> list[tuple[str, pd.DataFrame]]:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    packet = packet_df.copy().fillna("").reset_index(drop=True)
    batches: list[tuple[str, pd.DataFrame]] = []
    for start in range(0, len(packet), batch_size):
        batch_number = len(batches) + 1
        batch = packet.iloc[start : start + batch_size].copy().reset_index(drop=True)
        batch.insert(0, "batch_row", [f"{i:03d}" for i in range(1, len(batch) + 1)])
        batch.insert(0, "batch_id", f"B{batch_number:03d}")
        batches.append((f"manual_validation_review_packet_batch_{batch_number:03d}.csv", batch))
    return batches


def write_reviewer_batches(packet_df: pd.DataFrame, output_dir: Path, batch_size: int) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for filename, batch in make_reviewer_batches(packet_df, batch_size):
        path = output_dir / filename
        batch.to_csv(path, index=False)
        written.append(path)
    return written


def reviewer_form_html(packet_df: pd.DataFrame, *, title: str) -> str:
    packet = packet_df.copy().fillna("")
    columns = list(packet.columns)
    rows = packet.to_dict(orient="records")
    payload = json.dumps({"columns": columns, "rows": rows}, ensure_ascii=False)
    title_text = html.escape(title)
    label_options = "".join(f'<option value="{html.escape(label)}">{html.escape(label)}</option>' for label in ALLOWED_MANUAL_LABELS)
    confidence_options = "".join(f'<option value="{html.escape(level)}">{html.escape(level)}</option>' for level in ALLOWED_MANUAL_CONFIDENCE)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title_text}</title>
  <style>
    :root {{
      color-scheme: light;
      --text: #1f2933;
      --muted: #667085;
      --line: #d7dce2;
      --panel: #f7f8fa;
      --accent: #215c5c;
    }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background: #ffffff;
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 3;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 14px 20px;
      border-bottom: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.96);
    }}
    h1 {{
      margin: 0;
      font-size: 18px;
      font-weight: 650;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 18px 20px 48px;
    }}
    .actions {{
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }}
    button {{
      border: 1px solid var(--accent);
      background: var(--accent);
      color: white;
      padding: 8px 12px;
      border-radius: 6px;
      font-size: 14px;
      cursor: pointer;
    }}
    button.secondary {{
      background: white;
      color: var(--accent);
    }}
    .bulk-input {{
      width: 120px;
    }}
    .status {{
      font-size: 13px;
      color: var(--muted);
    }}
    .status.warning {{
      color: #9a3412;
    }}
    .rubric {{
      display: grid;
      gap: 8px;
      margin: 0 0 16px;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfd;
      font-size: 13px;
      line-height: 1.4;
      color: #334155;
    }}
    .rubric-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 8px;
    }}
    .rubric strong {{
      color: var(--text);
      font-weight: 650;
    }}
    .row {{
      border: 1px solid var(--line);
      border-radius: 8px;
      margin: 14px 0;
      overflow: hidden;
    }}
    .row.issue {{
      border-color: #d97706;
    }}
    .row-head {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 10px 12px;
      background: var(--panel);
      border-bottom: 1px solid var(--line);
      font-size: 13px;
      color: var(--muted);
    }}
    .row-body {{
      padding: 12px;
    }}
    .title {{
      font-size: 16px;
      font-weight: 650;
      margin-bottom: 8px;
    }}
    .abstract {{
      white-space: pre-wrap;
      line-height: 1.45;
      color: #334155;
      margin-bottom: 12px;
    }}
    .empty {{
      color: #98a2b3;
      font-style: italic;
    }}
    .guide {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 8px;
      margin: 0 0 12px;
      padding: 9px 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fbfcfd;
      color: #334155;
      font-size: 13px;
      line-height: 1.35;
    }}
    .guide div:last-child {{
      grid-column: 1 / -1;
    }}
    .guide strong {{
      color: var(--muted);
      font-weight: 650;
    }}
    .fields {{
      display: grid;
      grid-template-columns: 180px 150px 1fr 110px 130px;
      gap: 10px;
      align-items: start;
    }}
    label {{
      display: block;
      font-size: 12px;
      color: var(--muted);
      margin-bottom: 4px;
    }}
    select, input, textarea {{
      box-sizing: border-box;
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 7px 8px;
      font: inherit;
      font-size: 14px;
      background: white;
    }}
    textarea {{
      min-height: 36px;
      resize: vertical;
    }}
    @media (max-width: 900px) {{
      header {{
        align-items: flex-start;
        flex-direction: column;
      }}
      .fields {{
        grid-template-columns: 1fr;
      }}
    }}
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
      <button type="button" onclick="exportCsv()">Export CSV</button>
      <button type="button" class="secondary" onclick="saveLocal()">Save In Browser</button>
      <button type="button" class="secondary" onclick="loadLocal()">Load Saved</button>
    </div>
  </header>
  <main>
    <section class="rubric" aria-label="Manual label rubric">
      <div><strong>Primary focus rule:</strong> choose the label that best describes the paper's main research objective from title and abstract only. If causal and predictive language both appear, label the main objective.</div>
      <div><strong>Before export:</strong> every completed label needs manual_confidence, reviewer_id, and review_date in YYYY-MM-DD format. Use manual_notes for title-only judgments, ambiguous main focus, or low-confidence calls.</div>
      <div class="rubric-grid">
        <div><strong>causal:</strong> estimating, identifying, or interpreting causal effects.</div>
        <div><strong>predictive:</strong> prediction, forecasting, classification, nowcasting, predictive performance, or out-of-sample accuracy.</div>
        <div><strong>other:</strong> neither causal nor predictive as the main objective.</div>
        <div><strong>insufficient_text:</strong> title and abstract are missing, too short, or too vague to classify reliably.</div>
      </div>
    </section>
    <div id="rows"></div>
  </main>
  <script>
    const DATA = {payload};
    const LABEL_OPTIONS = `{label_options}`;
    const CONFIDENCE_OPTIONS = `{confidence_options}`;
    const STORAGE_KEY = "econqt-validation-" + location.pathname.split("/").pop();

    function escapeHtml(value) {{
      return String(value || "").replace(/[&<>"']/g, c => ({{"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#39;"}}[c]));
    }}

    function fieldId(rowIndex, field) {{
      return `${{field}}_${{rowIndex}}`;
    }}

    function guideLine(label, value) {{
      if (!String(value || "").trim()) return "";
      return `<div><strong>${{escapeHtml(label)}}:</strong> ${{escapeHtml(value)}}</div>`;
    }}

    function guideBlock(row) {{
      const lines = [
        guideLine("Calibration status", row.calibration_row_status),
        guideLine("Calibration next step", row.calibration_next_step),
        guideLine("Text status", row.text_status),
        guideLine("Cue profile", row.cue_profile),
        guideLine("Difficulty", row.review_difficulty),
        guideLine("Text chars", row.classification_text_chars),
        guideLine("Causal cues", row.causal_cue_terms),
        guideLine("Predictive cues", row.predictive_cue_terms),
        guideLine("Reviewer focus", row.reviewer_focus)
      ].join("");
      return lines ? `<div class="guide">${{lines}}</div>` : "";
    }}

    function render() {{
      const container = document.getElementById("rows");
      container.innerHTML = DATA.rows.map((row, index) => {{
        const title = escapeHtml(row.title || "");
        const abstract = row.abstract ? escapeHtml(row.abstract) : '<span class="empty">No abstract provided.</span>';
        const locator = [row.batch_id, row.batch_row, row.validation_id].filter(Boolean).map(escapeHtml).join(" / ");
        return `
          <section class="row" id="${{fieldId(index, "row")}}">
            <div class="row-head">
              <span>${{locator}}</span>
              <span>${{escapeHtml(row.article_id || "")}}</span>
            </div>
            <div class="row-body">
              <div class="title">${{title}}</div>
              <div class="abstract">${{abstract}}</div>
              ${{guideBlock(row)}}
              <div class="fields">
                <div>
                  <label for="${{fieldId(index, "manual_label")}}">manual_label</label>
                  <select id="${{fieldId(index, "manual_label")}}" data-row="${{index}}" data-field="manual_label">
                    <option value=""></option>${{LABEL_OPTIONS}}
                  </select>
                </div>
                <div>
                  <label for="${{fieldId(index, "manual_confidence")}}">manual_confidence</label>
                  <select id="${{fieldId(index, "manual_confidence")}}" data-row="${{index}}" data-field="manual_confidence">
                    <option value=""></option>${{CONFIDENCE_OPTIONS}}
                  </select>
                </div>
                <div>
                  <label for="${{fieldId(index, "manual_notes")}}">manual_notes</label>
                  <textarea id="${{fieldId(index, "manual_notes")}}" data-row="${{index}}" data-field="manual_notes"></textarea>
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
          </section>`;
      }}).join("");
      document.querySelectorAll("[data-field]").forEach(el => el.addEventListener("input", updateStatus));
      applyRowValues(DATA.rows);
      loadLocal();
      updateStatus();
    }}

    function collectRows() {{
      return DATA.rows.map((row, index) => {{
        const out = {{...row}};
        ["manual_label", "manual_confidence", "manual_notes", "reviewer_id", "review_date"].forEach(field => {{
          const el = document.getElementById(fieldId(index, field));
          out[field] = el ? el.value.trim() : "";
      }});
      return out;
      }});
    }}

    function applyRowValues(rows) {{
      rows.forEach((row, index) => {{
        ["manual_label", "manual_confidence", "manual_notes", "reviewer_id", "review_date"].forEach(field => {{
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
        const label = row.manual_label || "";
        const confidence = row.manual_confidence || "";
        const reviewer = row.reviewer_id || "";
        const reviewDate = row.review_date || "";
        if (label && !confidence) issues.push({{index, field: "manual_confidence", issue: "missing confidence"}});
        if (confidence && !label) issues.push({{index, field: "manual_label", issue: "missing label"}});
        if (label && !reviewer) issues.push({{index, field: "reviewer_id", issue: "missing reviewer"}});
        if (label && !reviewDate) issues.push({{index, field: "review_date", issue: "missing review date"}});
        if (reviewDate && !/^\\d{{4}}-\\d{{2}}-\\d{{2}}$/.test(reviewDate)) {{
          issues.push({{index, field: "review_date", issue: "date must be YYYY-MM-DD"}});
        }}
      }});
      return issues;
    }}

    function exportCsv() {{
      const rows = collectRows();
      const issues = formIssues(rows);
      if (issues.length) {{
        const proceed = window.confirm(`${{issues.length}} QA issues remain. Export anyway? The import command will reject completed labels missing confidence, reviewer ID, or ISO review date.`);
        if (!proceed) return;
      }}
      const csvRows = [DATA.columns.join(",")].concat(rows.map(row => DATA.columns.map(col => csvEscape(row[col] || "")).join(",")));
      const blob = new Blob([csvRows.join("\\n") + "\\n"], {{type: "text/csv;charset=utf-8"}});
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = location.pathname.split("/").pop().replace(/\\.html$/, ".csv");
      link.click();
      URL.revokeObjectURL(link.href);
    }}

    function saveLocal() {{
      localStorage.setItem(STORAGE_KEY, JSON.stringify(collectRows()));
      updateStatus();
    }}

    function loadLocal() {{
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const saved = JSON.parse(raw);
      applyRowValues(saved);
      updateStatus();
    }}

    function fillReviewer() {{
      const value = document.getElementById("bulk_reviewer").value.trim();
      if (!value) return;
      DATA.rows.forEach((row, index) => {{
        const labelEl = document.getElementById(fieldId(index, "manual_label"));
        const reviewerEl = document.getElementById(fieldId(index, "reviewer_id"));
        if (labelEl && labelEl.value && reviewerEl && !reviewerEl.value) {{
          reviewerEl.value = value;
        }}
      }});
      updateStatus();
    }}

    function fillToday() {{
      const today = new Date().toISOString().slice(0, 10);
      DATA.rows.forEach((row, index) => {{
        const labelEl = document.getElementById(fieldId(index, "manual_label"));
        const dateEl = document.getElementById(fieldId(index, "review_date"));
        if (labelEl && labelEl.value && dateEl && !dateEl.value) {{
          dateEl.value = today;
        }}
      }});
      updateStatus();
    }}

    function updateStatus() {{
      const rows = collectRows();
      const completed = rows.filter(row => row.manual_label).length;
      const issues = formIssues(rows);
      const issueRows = new Set(issues.map(issue => issue.index));
      rows.forEach((row, index) => {{
        const rowEl = document.getElementById(fieldId(index, "row"));
        if (rowEl) rowEl.classList.toggle("issue", issueRows.has(index));
      }});
      const status = document.getElementById("status");
      status.classList.toggle("warning", issues.length > 0);
      status.textContent = `${{completed}} / ${{rows.length}} labels completed; ${{issues.length}} QA issues`;
    }}

    render();
  </script>
</body>
</html>
"""


def write_reviewer_html_forms(packet_df: pd.DataFrame, output_dir: Path, batch_size: int) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for csv_filename, batch in make_reviewer_batches(packet_df, batch_size):
        html_filename = csv_filename.replace(".csv", ".html")
        path = output_dir / html_filename
        path.write_text(reviewer_form_html(batch, title=html_filename.replace(".html", "")), encoding="utf-8")
        written.append(path)
    return written


def completed_manual_label_mask(df: pd.DataFrame) -> pd.Series:
    if "manual_label" not in df.columns:
        return pd.Series(False, index=df.index)
    return nonempty(df["manual_label"])


def validation_row_key(df: pd.DataFrame) -> pd.Series:
    if not {"validation_id", "article_id"}.issubset(df.columns):
        missing = sorted({"validation_id", "article_id"} - set(df.columns))
        raise ValueError(f"Missing required validation key columns: {', '.join(missing)}")
    return df["validation_id"].astype(str).str.strip() + "|" + df["article_id"].astype(str).str.strip()


def validate_manual_label_values(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy().fillna("")
    for column in MANUAL_COLUMNS:
        if column not in work.columns:
            work[column] = ""
    errors: list[dict[str, Any]] = []
    labels = work["manual_label"].astype(str).str.strip()
    confidences = work["manual_confidence"].astype(str).str.strip()
    reviewer_ids = work["reviewer_id"].astype(str).str.strip()
    dates = work["review_date"].astype(str).str.strip()

    for idx, row in work.iterrows():
        label = labels.loc[idx]
        confidence = confidences.loc[idx]
        reviewer_id = reviewer_ids.loc[idx]
        date = dates.loc[idx]
        base = {
            "validation_id": row.get("validation_id", ""),
            "article_id": row.get("article_id", ""),
            "row_number": idx + 2,
        }
        if label and label not in ALLOWED_MANUAL_LABELS:
            errors.append({**base, "field": "manual_label", "value": label, "error": "invalid_manual_label"})
        if label and not confidence:
            errors.append({**base, "field": "manual_confidence", "value": confidence, "error": "missing_manual_confidence"})
        if confidence and confidence not in ALLOWED_MANUAL_CONFIDENCE:
            errors.append({**base, "field": "manual_confidence", "value": confidence, "error": "invalid_manual_confidence"})
        if confidence and not label:
            errors.append({**base, "field": "manual_label", "value": label, "error": "missing_manual_label"})
        if label and not reviewer_id:
            errors.append({**base, "field": "reviewer_id", "value": reviewer_id, "error": "missing_reviewer_id"})
        if label and not date:
            errors.append({**base, "field": "review_date", "value": date, "error": "missing_review_date"})
        if date and re.match(r"^\d{4}-\d{2}-\d{2}$", date) is None:
            errors.append({**base, "field": "review_date", "value": date, "error": "review_date_must_be_iso_yyyy_mm_dd"})

    return pd.DataFrame(errors, columns=VALIDATION_ERROR_COLUMNS)


def merge_manual_labels(sample_df: pd.DataFrame, reviewer_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    sample = sample_df.copy().fillna("")
    reviewer = reviewer_df.copy().fillna("")
    for column in MANUAL_COLUMNS:
        if column not in sample.columns:
            sample[column] = ""
        if column not in reviewer.columns:
            reviewer[column] = ""

    errors = validate_manual_label_values(reviewer)
    sample_keys = validation_row_key(sample)
    reviewer_keys = validation_row_key(reviewer)
    duplicate_mask = reviewer_keys.duplicated(keep=False)
    if duplicate_mask.any():
        duplicate_errors = reviewer.loc[duplicate_mask, ["validation_id", "article_id"]].copy()
        duplicate_errors["row_number"] = duplicate_errors.index + 2
        duplicate_errors["field"] = "validation_id|article_id"
        duplicate_errors["value"] = reviewer_keys.loc[duplicate_mask].values
        duplicate_errors["error"] = "duplicate_reviewer_row"
        errors = pd.concat([errors, duplicate_errors.reindex(columns=VALIDATION_ERROR_COLUMNS)], ignore_index=True)

    unknown_mask = ~reviewer_keys.isin(set(sample_keys))
    if unknown_mask.any():
        unknown_errors = reviewer.loc[unknown_mask, ["validation_id", "article_id"]].copy()
        unknown_errors["row_number"] = unknown_errors.index + 2
        unknown_errors["field"] = "validation_id|article_id"
        unknown_errors["value"] = reviewer_keys.loc[unknown_mask].values
        unknown_errors["error"] = "reviewer_row_not_in_sample"
        errors = pd.concat([errors, unknown_errors.reindex(columns=VALIDATION_ERROR_COLUMNS)], ignore_index=True)

    if not errors.empty:
        return sample, errors.reset_index(drop=True), validation_completion_summary(sample)

    reviewer_lookup = reviewer.assign(_validation_key=reviewer_keys).set_index("_validation_key", drop=False)
    merged = sample.copy()
    for idx, key in sample_keys.items():
        if key not in reviewer_lookup.index:
            continue
        reviewer_row = reviewer_lookup.loc[key]
        if isinstance(reviewer_row, pd.DataFrame):
            reviewer_row = reviewer_row.iloc[0]
        for column in MANUAL_COLUMNS:
            merged.at[idx, column] = str(reviewer_row.get(column, "")).strip()
    return merged, pd.DataFrame(columns=VALIDATION_ERROR_COLUMNS), validation_completion_summary(merged)


def validation_completion_summary(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy().fillna("")
    labeled_mask = completed_manual_label_mask(work)
    labeled = work[labeled_mask].copy()
    rows: list[dict[str, Any]] = [
        {
            "metric": "total_rows",
            "value": len(work),
        },
        {
            "metric": "completed_manual_labels",
            "value": int(labeled_mask.sum()),
        },
        {
            "metric": "remaining_manual_labels",
            "value": int((~labeled_mask).sum()),
        },
    ]
    for label in ALLOWED_MANUAL_LABELS:
        rows.append({"metric": f"manual_label_{label}", "value": int((labeled["manual_label"] == label).sum()) if not labeled.empty else 0})
    return pd.DataFrame(rows)


def validation_batch_completion_summary(reviewer_df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "batch_id",
        "total_rows",
        "completed_manual_labels",
        "remaining_manual_labels",
        "invalid_manual_label_rows",
        "missing_manual_confidence_rows",
        "reviewer_ids",
        "latest_review_date",
    ] + [f"manual_label_{label}" for label in ALLOWED_MANUAL_LABELS]
    if reviewer_df.empty:
        return pd.DataFrame(columns=columns)

    work = reviewer_df.copy().fillna("")
    for column in MANUAL_COLUMNS:
        if column not in work.columns:
            work[column] = ""
    if "batch_id" not in work.columns:
        work["batch_id"] = "unbatched"
    work["batch_id"] = work["batch_id"].astype(str).str.strip().replace("", "unbatched")
    work["_manual_label"] = work["manual_label"].astype(str).str.strip()
    work["_manual_confidence"] = work["manual_confidence"].astype(str).str.strip()
    work["_reviewer_id"] = work["reviewer_id"].astype(str).str.strip()
    work["_review_date"] = work["review_date"].astype(str).str.strip()

    rows: list[dict[str, Any]] = []
    for batch_id, group in work.groupby("batch_id", dropna=False):
        labeled = group[group["_manual_label"] != ""].copy()
        valid_label_mask = group["_manual_label"].isin(ALLOWED_MANUAL_LABELS) | group["_manual_label"].eq("")
        missing_confidence_mask = group["_manual_label"].ne("") & group["_manual_confidence"].eq("")
        reviewer_ids = sorted(set(group.loc[group["_reviewer_id"].ne(""), "_reviewer_id"]))
        review_dates = sorted(set(group.loc[group["_review_date"].ne(""), "_review_date"]))
        row = {
            "batch_id": batch_id,
            "total_rows": len(group),
            "completed_manual_labels": len(labeled),
            "remaining_manual_labels": int(group["_manual_label"].eq("").sum()),
            "invalid_manual_label_rows": int((~valid_label_mask).sum()),
            "missing_manual_confidence_rows": int(missing_confidence_mask.sum()),
            "reviewer_ids": "|".join(reviewer_ids),
            "latest_review_date": review_dates[-1] if review_dates else "",
        }
        for label in ALLOWED_MANUAL_LABELS:
            row[f"manual_label_{label}"] = int(group["_manual_label"].eq(label).sum())
        rows.append(row)
    return pd.DataFrame(rows, columns=columns).sort_values("batch_id").reset_index(drop=True)


def validation_sample_drift(
    sample_df: pd.DataFrame,
    current_df: pd.DataFrame,
    columns: list[str] | None = None,
) -> pd.DataFrame:
    drift_columns = columns or DEFAULT_VALIDATION_DRIFT_COLUMNS
    sample = sample_df.copy().fillna("")
    current = current_df.copy().fillna("")
    output_columns = ["validation_id", "article_id", "field", "sample_value", "current_value"]
    if "article_id" not in sample.columns or "article_id" not in current.columns:
        return pd.DataFrame(columns=output_columns)

    current_lookup = current.drop_duplicates("article_id").set_index("article_id", drop=False)
    rows: list[dict[str, Any]] = []
    for _, sample_row in sample.iterrows():
        article_id = str(sample_row.get("article_id", "")).strip()
        validation_id = str(sample_row.get("validation_id", "")).strip()
        if article_id not in current_lookup.index:
            rows.append(
                {
                    "validation_id": validation_id,
                    "article_id": article_id,
                    "field": "article_id",
                    "sample_value": article_id,
                    "current_value": "missing_current",
                }
            )
            continue
        current_row = current_lookup.loc[article_id]
        for column in drift_columns:
            if column not in sample.columns or column not in current.columns:
                continue
            sample_value = str(sample_row.get(column, "")).strip()
            current_value = str(current_row.get(column, "")).strip()
            if sample_value != current_value:
                rows.append(
                    {
                        "validation_id": validation_id,
                        "article_id": article_id,
                        "field": column,
                        "sample_value": sample_value,
                        "current_value": current_value,
                    }
                )
    return pd.DataFrame(rows, columns=output_columns)


def manual_validation_readiness_summary(
    sample_df: pd.DataFrame,
    batch_summary: pd.DataFrame | None = None,
    drift: pd.DataFrame | None = None,
) -> pd.DataFrame:
    sample = sample_df.copy().fillna("")
    completion = validation_completion_summary(sample)
    lookup = dict(zip(completion["metric"].astype(str), completion["value"]))
    drift_rows = 0 if drift is None or drift.empty else drift["article_id"].nunique()
    drift_cells = 0 if drift is None else len(drift)

    rows: list[dict[str, Any]] = [
        {"metric": "sample_rows", "value": len(sample)},
        {"metric": "completed_manual_labels", "value": lookup.get("completed_manual_labels", 0)},
        {"metric": "remaining_manual_labels", "value": lookup.get("remaining_manual_labels", len(sample))},
        {"metric": "drifted_articles", "value": drift_rows},
        {"metric": "drifted_cells", "value": drift_cells},
    ]

    if "validation_category" in sample.columns:
        for category, count in sample["validation_category"].astype(str).value_counts(dropna=False).sort_index().items():
            rows.append({"metric": f"sample_validation_category_{category}", "value": int(count)})
    if "article_scope" in sample.columns:
        for scope, count in sample["article_scope"].astype(str).value_counts(dropna=False).sort_index().items():
            rows.append({"metric": f"sample_article_scope_{scope}", "value": int(count)})
    if "abstract" in sample.columns:
        rows.append({"metric": "sample_missing_abstract_rows", "value": int(sample["abstract"].astype(str).str.strip().eq("").sum())})

    if batch_summary is not None and not batch_summary.empty:
        work = batch_summary.copy().fillna("")
        remaining = pd.to_numeric(work.get("remaining_manual_labels", 0), errors="coerce").fillna(0)
        completed = pd.to_numeric(work.get("completed_manual_labels", 0), errors="coerce").fillna(0)
        rows.extend(
            [
                {"metric": "reviewer_batches", "value": len(work)},
                {"metric": "completed_reviewer_batches", "value": int((remaining == 0).sum())},
                {"metric": "started_reviewer_batches", "value": int((completed > 0).sum())},
            ]
        )
        next_batch = ""
        if (remaining > 0).any() and "batch_id" in work.columns:
            next_batch = str(work.loc[remaining > 0, "batch_id"].iloc[0])
        rows.append({"metric": "next_incomplete_batch", "value": next_batch})
    else:
        rows.extend(
            [
                {"metric": "reviewer_batches", "value": 0},
                {"metric": "completed_reviewer_batches", "value": 0},
                {"metric": "started_reviewer_batches", "value": 0},
                {"metric": "next_incomplete_batch", "value": ""},
            ]
        )

    ready = len(sample) > 0 and drift_rows == 0
    rows.append({"metric": "ready_for_blind_review", "value": "yes" if ready else "no"})
    return pd.DataFrame(rows, columns=["metric", "value"])


def write_manual_validation_readiness_report(
    path: Path,
    summary: pd.DataFrame,
    batch_summary: pd.DataFrame,
    drift: pd.DataFrame,
    *,
    codebook_path: str,
    batch_dir: str,
    html_dir: str,
) -> None:
    def lookup(metric: str, default: Any = "") -> Any:
        rows = summary.loc[summary["metric"].astype(str).eq(metric), "value"]
        return rows.iloc[0] if not rows.empty else default

    def markdown_table(df: pd.DataFrame) -> str:
        if df.empty:
            return "_No rows._"
        shown = df.fillna("").astype(str)
        headers = list(shown.columns)
        rows = [headers] + shown.values.tolist()
        widths = [max(len(row[i]) for row in rows) for i in range(len(headers))]
        header = "| " + " | ".join(headers[i].ljust(widths[i]) for i in range(len(headers))) + " |"
        sep = "| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |"
        body = ["| " + " | ".join(row[i].ljust(widths[i]) for i in range(len(headers))) + " |" for row in rows[1:]]
        return "\n".join([header, sep] + body)

    lines = [
        "# Manual Validation Readiness",
        "",
        f"- Ready for blind review: `{lookup('ready_for_blind_review')}`",
        f"- Sample rows: {lookup('sample_rows')}",
        f"- Completed manual labels: {lookup('completed_manual_labels')}",
        f"- Remaining manual labels: {lookup('remaining_manual_labels')}",
        f"- Drifted sample articles: {lookup('drifted_articles')}",
        f"- Reviewer batches: {lookup('reviewer_batches')}",
        f"- Next incomplete batch: `{lookup('next_incomplete_batch')}`",
        "",
        "## Review Materials",
        "",
        f"- Codebook: `{codebook_path}`",
        f"- Batch CSVs: `{batch_dir}`",
        f"- Browser forms: `{html_dir}`",
        "",
        "## Summary",
        "",
        markdown_table(summary),
        "",
        "## Batch Progress",
        "",
        markdown_table(batch_summary),
        "",
        "## Sample Drift",
        "",
        markdown_table(drift.head(50)),
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def relative_href(from_path: Path, target: str) -> str:
    target_path = Path(target)
    if target_path.is_absolute():
        rel = os.path.relpath(target_path, from_path.parent)
    else:
        rel = os.path.relpath(Path.cwd() / target_path, from_path.parent)
    return rel.replace(os.sep, "/")


def write_manual_validation_portal(
    path: Path,
    readiness_summary: pd.DataFrame,
    batch_summary: pd.DataFrame,
    *,
    codebook_path: str,
    readiness_report: str,
    status_report: str,
    overlap_report: str,
    main_forms_dir: str,
    overlap_forms_dir: str,
    human_review_workboard_report: str = "docs/human_review_workboard.md",
    adjudication_report: str = "docs/manual_validation_adjudication_status.md",
    calibration_report: str = "docs/manual_validation_calibration.md",
    calibration_kickoff_report: str = "docs/manual_validation_calibration_kickoff.md",
    calibration_guide_report: str = "docs/manual_validation_calibration_guide.md",
    calibration_remaining_report: str = "docs/manual_validation_calibration_remaining.md",
    calibration_remaining_template: str = "data/intermediate/manual_validation_calibration/manual_validation_calibration_remaining_submission_template.csv",
    calibration_forms_dir: str = "data/intermediate/manual_validation_calibration_forms",
    calibration_summary: pd.DataFrame | None = None,
    overlap_summary: pd.DataFrame | None = None,
    adjudication_summary: pd.DataFrame | None = None,
    scope_review_report: str = "docs/scope_review_packet.md",
    scope_review_guide_report: str = "docs/scope_review_guide.md",
    scope_review_form: str = "data/intermediate/scope_review_forms/scope_review_packet.html",
    scope_review_apply_report: str = "docs/scope_review_apply.md",
    scope_review_completion: pd.DataFrame | None = None,
) -> None:
    lookup = dict(zip(readiness_summary["metric"].astype(str), readiness_summary["value"])) if not readiness_summary.empty else {}
    calibration_lookup = dict(zip(calibration_summary["metric"].astype(str), calibration_summary["value"])) if calibration_summary is not None and not calibration_summary.empty else {}
    overlap_lookup = dict(zip(overlap_summary["metric"].astype(str), overlap_summary["value"])) if overlap_summary is not None and not overlap_summary.empty else {}
    adjudication_lookup = dict(zip(adjudication_summary["metric"].astype(str), adjudication_summary["value"])) if adjudication_summary is not None and not adjudication_summary.empty else {}
    scope_lookup = dict(zip(scope_review_completion["metric"].astype(str), scope_review_completion["value"])) if scope_review_completion is not None and not scope_review_completion.empty else {}

    def link(label: str, target: str) -> str:
        return f'<a href="{html.escape(relative_href(path, target))}">{html.escape(label)}</a>'

    def form_links(directory: str) -> list[str]:
        dir_path = Path(directory)
        if not dir_path.exists():
            return []
        return [str(item) for item in sorted(dir_path.glob("*.html")) if item.name != path.name]

    batch_rows: list[str] = []
    batch_lookup = batch_summary.copy().fillna("") if batch_summary is not None else pd.DataFrame()
    for form_path in form_links(main_forms_dir):
        batch_id = ""
        filename = Path(form_path).stem
        match = re.search(r"batch_(\d+)", filename)
        if match:
            batch_id = f"B{int(match.group(1)):03d}"
        row = batch_lookup[batch_lookup.get("batch_id", pd.Series(dtype=str)).astype(str).eq(batch_id)] if not batch_lookup.empty and batch_id else pd.DataFrame()
        completed = row.iloc[0].get("completed_manual_labels", "") if not row.empty else ""
        remaining = row.iloc[0].get("remaining_manual_labels", "") if not row.empty else ""
        batch_rows.append(
            "<tr>"
            f"<td>{html.escape(batch_id or filename)}</td>"
            f"<td>{link(Path(form_path).name, form_path)}</td>"
            f"<td>{html.escape(str(completed))}</td>"
            f"<td>{html.escape(str(remaining))}</td>"
            "</tr>"
        )

    overlap_links = form_links(overlap_forms_dir)
    overlap_items = "\n".join(f"<li>{link(Path(item).name, item)}</li>" for item in overlap_links) or "<li>No overlap forms found.</li>"
    calibration_links = form_links(calibration_forms_dir)
    calibration_items = "\n".join(f"<li>{link(Path(item).name, item)}</li>" for item in calibration_links) or "<li>No calibration forms found.</li>"
    batch_table = "\n".join(batch_rows) or '<tr><td colspan="4">No batch forms found.</td></tr>'

    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Manual Validation Portal</title>
  <style>
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #1f2933;
      background: #ffffff;
    }}
    main {{
      max-width: 980px;
      margin: 0 auto;
      padding: 28px 20px 48px;
    }}
    h1 {{
      margin: 0 0 16px;
      font-size: 26px;
    }}
    h2 {{
      margin-top: 28px;
      font-size: 18px;
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 10px;
      margin: 18px 0;
    }}
    .metric {{
      border: 1px solid #d7dce2;
      border-radius: 8px;
      padding: 12px;
      background: #f7f8fa;
    }}
    .metric span {{
      display: block;
      color: #667085;
      font-size: 12px;
      margin-bottom: 4px;
    }}
    .metric strong {{
      font-size: 18px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 10px;
    }}
    th, td {{
      border-bottom: 1px solid #d7dce2;
      padding: 9px 8px;
      text-align: left;
      font-size: 14px;
    }}
    th {{
      color: #667085;
      font-weight: 650;
    }}
    a {{
      color: #215c5c;
    }}
  </style>
</head>
<body>
  <main>
    <h1>Manual Validation Portal</h1>
    <div class="summary">
      <div class="metric"><span>Ready</span><strong>{html.escape(str(lookup.get("ready_for_blind_review", "")))}</strong></div>
      <div class="metric"><span>Main labels</span><strong>{html.escape(str(lookup.get("completed_manual_labels", 0)))} / {html.escape(str(lookup.get("sample_rows", 0)))}</strong></div>
      <div class="metric"><span>Remaining</span><strong>{html.escape(str(lookup.get("remaining_manual_labels", 0)))}</strong></div>
      <div class="metric"><span>Next batch</span><strong>{html.escape(str(lookup.get("next_incomplete_batch", "")))}</strong></div>
      <div class="metric"><span>Drifted articles</span><strong>{html.escape(str(lookup.get("drifted_articles", 0)))}</strong></div>
      <div class="metric"><span>Calibration labels</span><strong>{html.escape(str(calibration_lookup.get("completed_calibration_labels", 0)))} / {html.escape(str(calibration_lookup.get("calibration_rows", 0)))}</strong></div>
      <div class="metric"><span>Overlap labels</span><strong>{html.escape(str(overlap_lookup.get("completed_overlap_labels", 0)))} / {html.escape(str(overlap_lookup.get("overlap_rows", 0)))}</strong></div>
      <div class="metric"><span>Adjudications</span><strong>{html.escape(str(adjudication_lookup.get("completed_adjudications", 0)))}</strong></div>
      <div class="metric"><span>Scope review</span><strong>{html.escape(str(scope_lookup.get("completed_scope_review_decisions", 0)))} / {html.escape(str(scope_lookup.get("scope_review_rows", 0)))}</strong></div>
    </div>

    <h2>Start Here</h2>
    <ul>
      <li>{link("Manual validation codebook", codebook_path)}</li>
      <li>{link("Human review workboard", human_review_workboard_report)}</li>
      <li>{link("Readiness report", readiness_report)}</li>
      <li>{link("Manual validation status", status_report)}</li>
      <li>{link("Overlap QA report", overlap_report)}</li>
      <li>{link("Calibration kickoff checklist", calibration_kickoff_report)}</li>
      <li>{link("Calibration guide", calibration_guide_report)}</li>
      <li>{link("Calibration remaining rows", calibration_remaining_report)}</li>
      <li>{link("Calibration spreadsheet template", calibration_remaining_template)}</li>
      <li>{link("Calibration report", calibration_report)}</li>
      <li>{link("Adjudication status", adjudication_report)}</li>
      <li>{link("Scope review packet", scope_review_report)}</li>
      <li>{link("Scope review guide", scope_review_guide_report)}</li>
      <li>{link("Scope review apply dry run", scope_review_apply_report)}</li>
    </ul>

    <h2>Main Reviewer Batches</h2>
    <table>
      <thead><tr><th>Batch</th><th>Form</th><th>Completed</th><th>Remaining</th></tr></thead>
      <tbody>{batch_table}</tbody>
    </table>

    <h2>Overlap QA Forms</h2>
    <ul>
      {overlap_items}
    </ul>

    <h2>Calibration Forms</h2>
    <ul>
      {calibration_items}
    </ul>

    <h2>Scope Review</h2>
    <ul>
      <li>{link("Scope review form", scope_review_form)}</li>
      <li>{link("Scope review packet report", scope_review_report)}</li>
      <li>{link("Scope review guide", scope_review_guide_report)}</li>
      <li>{link("Scope review apply dry run", scope_review_apply_report)}</li>
    </ul>
  </main>
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html_text, encoding="utf-8")


def make_calibration_packet(sample_df: pd.DataFrame, sample_size: int, seed: int) -> pd.DataFrame:
    if sample_size <= 0:
        raise ValueError("sample_size must be positive")
    sample = sample_df.copy().fillna("")
    if sample.empty:
        packet = make_reviewer_packet(sample, mode="blind")
        packet.insert(0, "calibration_id", [])
        return packet

    shuffled = sample.sample(frac=1, random_state=seed).reset_index(drop=True)
    selected_parts: list[pd.DataFrame] = []
    if "validation_category" in shuffled.columns:
        category_count = max(1, shuffled["validation_category"].nunique(dropna=False))
        per_category = max(1, sample_size // category_count)
        selected_parts.append(shuffled.groupby("validation_category", dropna=False).head(per_category).reset_index(drop=True))
    if "validation_ambiguous" in shuffled.columns:
        ambiguous = shuffled[shuffled["validation_ambiguous"].astype(str).str.lower().eq("true")].head(max(1, sample_size // 4))
        selected_parts.append(ambiguous)

    selected = unique_concat(selected_parts)
    if len(selected) > sample_size:
        selected = selected.sample(n=sample_size, random_state=seed).reset_index(drop=True)
    elif len(selected) < sample_size:
        remaining = shuffled[~shuffled["article_id"].isin(selected.get("article_id", pd.Series(dtype=str)))]
        selected = unique_concat([selected, remaining.head(sample_size - len(selected))]).reset_index(drop=True)

    packet = make_reviewer_packet(selected.head(sample_size), mode="blind").reset_index(drop=True)
    packet.insert(0, "calibration_id", [f"CAL{i:04d}" for i in range(1, len(packet) + 1)])
    return packet


def calibration_agreement_summary(submissions_df: pd.DataFrame) -> pd.DataFrame:
    submissions = submissions_df.copy().fillna("")
    if submissions.empty:
        return pd.DataFrame(
            [
                {"metric": "calibration_rows", "value": 0},
                {"metric": "completed_calibration_labels", "value": 0},
                {"metric": "completed_calibration_rows", "value": 0},
                {"metric": "remaining_calibration_rows", "value": 0},
                {"metric": "calibration_reviewers", "value": 0},
                {"metric": "rows_with_multiple_reviewers", "value": 0},
                {"metric": "unanimous_rows", "value": 0},
                {"metric": "disagreement_rows", "value": 0},
                {"metric": "agreement_rate", "value": ""},
            ]
        )

    for column in MANUAL_COLUMNS:
        if column not in submissions.columns:
            submissions[column] = ""
    if "calibration_id" not in submissions.columns:
        submissions["calibration_id"] = ""

    completed = submissions[submissions["manual_label"].astype(str).str.strip().ne("")].copy()
    reviewers = completed["reviewer_id"].astype(str).str.strip()
    calibration_rows = submissions[["calibration_id", "validation_id", "article_id"]].drop_duplicates().shape[0]
    completed_rows = completed[["calibration_id", "validation_id", "article_id"]].drop_duplicates().shape[0]
    grouped = completed.groupby(["calibration_id", "validation_id", "article_id"], dropna=False)
    comparable = 0
    unanimous = 0
    disagreements = 0
    for _, group in grouped:
        labels = {label for label in group["manual_label"].astype(str).str.strip() if label}
        reviewer_count = len({rid for rid in group["reviewer_id"].astype(str).str.strip() if rid})
        if len(group) < 2 and reviewer_count < 2:
            continue
        comparable += 1
        if len(labels) == 1:
            unanimous += 1
        else:
            disagreements += 1
    agreement_rate = round(unanimous / comparable, 4) if comparable else ""
    return pd.DataFrame(
        [
            {"metric": "calibration_rows", "value": calibration_rows},
            {"metric": "completed_calibration_labels", "value": len(completed)},
            {"metric": "completed_calibration_rows", "value": completed_rows},
            {"metric": "remaining_calibration_rows", "value": max(0, calibration_rows - completed_rows)},
            {"metric": "calibration_reviewers", "value": len({rid for rid in reviewers if rid})},
            {"metric": "rows_with_multiple_reviewers", "value": comparable},
            {"metric": "unanimous_rows", "value": unanimous},
            {"metric": "disagreement_rows", "value": disagreements},
            {"metric": "agreement_rate", "value": agreement_rate},
        ]
    )


def calibration_disagreement_packet(submissions_df: pd.DataFrame) -> pd.DataFrame:
    submissions = submissions_df.copy().fillna("")
    if submissions.empty:
        return pd.DataFrame(columns=CALIBRATION_DISAGREEMENT_COLUMNS)
    for column in MANUAL_COLUMNS:
        if column not in submissions.columns:
            submissions[column] = ""
    if "calibration_id" not in submissions.columns:
        submissions["calibration_id"] = ""
    rows: list[dict[str, Any]] = []
    completed = submissions[submissions["manual_label"].astype(str).str.strip().ne("")].copy()
    for _, group in completed.groupby(["calibration_id", "validation_id", "article_id"], dropna=False):
        labels = sorted({label for label in group["manual_label"].astype(str).str.strip() if label})
        if len(labels) <= 1:
            continue
        reviewers = group["reviewer_id"].astype(str).str.strip()
        reviewer_labels = [
            f"{reviewer or 'missing_reviewer'}={label}"
            for reviewer, label in zip(reviewers, group["manual_label"].astype(str).str.strip())
            if label
        ]
        reviewer_confidences = [
            f"{reviewer or 'missing_reviewer'}={confidence}"
            for reviewer, confidence in zip(reviewers, group["manual_confidence"].astype(str).str.strip())
            if confidence
        ]
        reviewer_notes = [
            f"{reviewer or 'missing_reviewer'}={note}"
            for reviewer, note in zip(reviewers, group["manual_notes"].astype(str).str.strip())
            if note
        ]
        first = group.iloc[0]
        rows.append(
            {
                "calibration_id": first.get("calibration_id", ""),
                "validation_id": first.get("validation_id", ""),
                "article_id": first.get("article_id", ""),
                "title": first.get("title", ""),
                "reviewer_labels": " | ".join(reviewer_labels),
                "reviewer_confidences": " | ".join(reviewer_confidences),
                "reviewer_notes": " | ".join(reviewer_notes),
                "label_set": "|".join(labels),
                "adjudicated_label": "",
                "adjudication_notes": "",
                "adjudicator_id": "",
                "adjudication_date": "",
            }
        )
    return pd.DataFrame(rows, columns=CALIBRATION_DISAGREEMENT_COLUMNS)


def make_overlap_packet(sample_df: pd.DataFrame, sample_size: int, seed: int) -> pd.DataFrame:
    if sample_size <= 0:
        raise ValueError("sample_size must be positive")
    sample = sample_df.copy().fillna("")
    if sample.empty:
        packet = make_reviewer_packet(sample, mode="blind")
        packet.insert(0, "overlap_id", [])
        return packet

    shuffled = sample.sample(frac=1, random_state=seed).reset_index(drop=True)
    if len(shuffled) <= sample_size:
        selected = shuffled.copy()
    elif "validation_category" in shuffled.columns:
        per_category = max(1, sample_size // max(1, shuffled["validation_category"].nunique(dropna=False)))
        coverage = shuffled.groupby("validation_category", dropna=False).head(per_category).reset_index(drop=True)
        if len(coverage) > sample_size:
            selected = coverage.sample(n=sample_size, random_state=seed).reset_index(drop=True)
        else:
            remaining = shuffled[~shuffled["article_id"].isin(coverage["article_id"])]
            selected = unique_concat([coverage, remaining.head(sample_size - len(coverage))]).reset_index(drop=True)
    else:
        selected = shuffled.head(sample_size).copy()

    packet = make_reviewer_packet(selected.head(sample_size), mode="blind").reset_index(drop=True)
    packet.insert(0, "overlap_id", [f"OV{i:04d}" for i in range(1, len(packet) + 1)])
    return packet


def overlap_agreement_summary(sample_df: pd.DataFrame, overlap_df: pd.DataFrame) -> pd.DataFrame:
    sample = sample_df.copy().fillna("")
    overlap = overlap_df.copy().fillna("")
    if overlap.empty:
        return pd.DataFrame(
            [
                {"metric": "overlap_rows", "value": 0},
                {"metric": "completed_overlap_labels", "value": 0},
                {"metric": "comparable_overlap_labels", "value": 0},
                {"metric": "overlap_agreements", "value": 0},
                {"metric": "overlap_disagreements", "value": 0},
                {"metric": "missing_primary_labels", "value": 0},
                {"metric": "overlap_agreement_rate", "value": ""},
            ]
        )

    for column in MANUAL_COLUMNS:
        if column not in sample.columns:
            sample[column] = ""
        if column not in overlap.columns:
            overlap[column] = ""

    sample_lookup = sample.assign(_validation_key=validation_row_key(sample)).set_index("_validation_key", drop=False)
    overlap_keys = validation_row_key(overlap)
    completed_mask = overlap["manual_label"].astype(str).str.strip().ne("")
    completed = overlap.loc[completed_mask].copy()
    completed_keys = overlap_keys.loc[completed_mask]

    comparable_rows = 0
    agreements = 0
    missing_primary = 0
    for idx, overlap_row in completed.iterrows():
        key = completed_keys.loc[idx]
        if key not in sample_lookup.index:
            missing_primary += 1
            continue
        sample_row = sample_lookup.loc[key]
        primary_label = str(sample_row.get("manual_label", "")).strip()
        if not primary_label:
            missing_primary += 1
            continue
        comparable_rows += 1
        if primary_label == str(overlap_row.get("manual_label", "")).strip():
            agreements += 1

    disagreements = comparable_rows - agreements
    agreement_rate = round(agreements / comparable_rows, 4) if comparable_rows else ""
    return pd.DataFrame(
        [
            {"metric": "overlap_rows", "value": len(overlap)},
            {"metric": "completed_overlap_labels", "value": int(completed_mask.sum())},
            {"metric": "comparable_overlap_labels", "value": comparable_rows},
            {"metric": "overlap_agreements", "value": agreements},
            {"metric": "overlap_disagreements", "value": disagreements},
            {"metric": "missing_primary_labels", "value": missing_primary},
            {"metric": "overlap_agreement_rate", "value": agreement_rate},
        ]
    )


def overlap_disagreement_packet(sample_df: pd.DataFrame, overlap_df: pd.DataFrame) -> pd.DataFrame:
    sample = sample_df.copy().fillna("")
    overlap = overlap_df.copy().fillna("")
    if sample.empty or overlap.empty:
        return pd.DataFrame(columns=OVERLAP_DISAGREEMENT_COLUMNS)
    for column in MANUAL_COLUMNS:
        if column not in sample.columns:
            sample[column] = ""
        if column not in overlap.columns:
            overlap[column] = ""
    if "overlap_id" not in overlap.columns:
        overlap["overlap_id"] = ""

    sample_lookup = sample.assign(_validation_key=validation_row_key(sample)).set_index("_validation_key", drop=False)
    overlap_keys = validation_row_key(overlap)
    rows: list[dict[str, Any]] = []
    for idx, overlap_row in overlap.iterrows():
        overlap_label = str(overlap_row.get("manual_label", "")).strip()
        if not overlap_label:
            continue
        key = overlap_keys.loc[idx]
        if key not in sample_lookup.index:
            continue
        sample_row = sample_lookup.loc[key]
        primary_label = str(sample_row.get("manual_label", "")).strip()
        if not primary_label or primary_label == overlap_label:
            continue
        rows.append(
            {
                "overlap_id": overlap_row.get("overlap_id", ""),
                "validation_id": overlap_row.get("validation_id", sample_row.get("validation_id", "")),
                "article_id": overlap_row.get("article_id", sample_row.get("article_id", "")),
                "title": overlap_row.get("title", sample_row.get("title", "")),
                "primary_manual_label": primary_label,
                "primary_manual_confidence": sample_row.get("manual_confidence", ""),
                "primary_reviewer_id": sample_row.get("reviewer_id", ""),
                "overlap_manual_label": overlap_label,
                "overlap_manual_confidence": overlap_row.get("manual_confidence", ""),
                "overlap_reviewer_id": overlap_row.get("reviewer_id", ""),
                "primary_manual_notes": sample_row.get("manual_notes", ""),
                "overlap_manual_notes": overlap_row.get("manual_notes", ""),
                "adjudicated_label": "",
                "adjudication_notes": "",
                "adjudicator_id": "",
                "adjudication_date": "",
            }
        )
    return pd.DataFrame(rows, columns=OVERLAP_DISAGREEMENT_COLUMNS)


def write_validation_status_report(
    path: Path,
    summary: pd.DataFrame,
    errors: pd.DataFrame,
    batch_summary: pd.DataFrame | None = None,
    title: str = "Manual Validation Status",
) -> None:
    def markdown_table(df: pd.DataFrame) -> str:
        if df.empty:
            return "_No rows._"
        shown = df.fillna("").astype(str)
        headers = list(shown.columns)
        rows = [headers] + shown.values.tolist()
        widths = [max(len(row[i]) for row in rows) for i in range(len(headers))]
        header = "| " + " | ".join(headers[i].ljust(widths[i]) for i in range(len(headers))) + " |"
        sep = "| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |"
        body = ["| " + " | ".join(row[i].ljust(widths[i]) for i in range(len(headers))) + " |" for row in rows[1:]]
        return "\n".join([header, sep] + body)

    lines = [
        f"# {title}",
        "",
        "## Completion",
        "",
        markdown_table(summary),
        "",
        "## Import Errors",
        "",
        markdown_table(errors),
    ]
    if batch_summary is not None:
        lines.extend(
            [
                "",
                "## Batch Completion",
                "",
                markdown_table(batch_summary),
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parse_excluded_scopes(value: str) -> list[str]:
    if value.strip() == "":
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default="data/intermediate/manual_validation_sample.csv")
    parser.add_argument("--reviewer-output", default="")
    parser.add_argument("--reviewer-mode", choices=["blind", "audit"], default="blind")
    parser.add_argument("--reviewer-batch-dir", default="")
    parser.add_argument("--reviewer-batch-size", type=int, default=50)
    parser.add_argument("--reviewer-html-dir", default="")
    parser.add_argument("--sample-size", type=int, default=300)
    parser.add_argument("--seed", type=int, default=20260628)
    parser.add_argument("--exclude-scopes", default=",".join(DEFAULT_EXCLUDED_SCOPES))
    parser.add_argument("--overwrite-labeled", action="store_true")
    args = parser.parse_args()

    data = pd.read_csv(args.input, dtype=str).fillna("")
    data = filter_validation_scope(data, parse_excluded_scopes(args.exclude_scopes))
    sample = sample_validation_rows(data, args.sample_size, args.seed)
    template = make_label_template(sample)
    output = Path(args.output)
    guard_against_overwriting_completed_labels(output, overwrite_labeled=args.overwrite_labeled)
    output.parent.mkdir(parents=True, exist_ok=True)
    template.to_csv(output, index=False)
    if args.reviewer_output:
        reviewer_output = Path(args.reviewer_output)
        reviewer_output.parent.mkdir(parents=True, exist_ok=True)
        reviewer_packet = make_reviewer_packet(template, mode=args.reviewer_mode)
        reviewer_packet.to_csv(reviewer_output, index=False)
        if args.reviewer_batch_dir:
            written = write_reviewer_batches(reviewer_packet, Path(args.reviewer_batch_dir), args.reviewer_batch_size)
            print(f"reviewer_batches={len(written)}")
        if args.reviewer_html_dir:
            written = write_reviewer_html_forms(reviewer_packet, Path(args.reviewer_html_dir), args.reviewer_batch_size)
            print(f"reviewer_html_forms={len(written)}")
    print(f"rows={len(template)}")
    print(template["validation_category"].value_counts(dropna=False).to_string())
    if args.reviewer_output:
        print(f"reviewer_output={args.reviewer_output}")


if __name__ == "__main__":
    main()
