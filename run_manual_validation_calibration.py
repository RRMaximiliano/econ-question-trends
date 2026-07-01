from __future__ import annotations

import argparse
import html
import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT / "code" / "04_classify"))

from validation_sample import (  # noqa: E402
    calibration_agreement_summary,
    calibration_disagreement_packet,
    completed_manual_label_mask,
    completed_manual_label_count,
    MANUAL_COLUMNS,
    make_calibration_packet,
    reviewer_form_html,
    VALIDATION_ERROR_COLUMNS,
    validate_manual_label_values,
    write_reviewer_html_forms,
)
from rule_based import build_classification_text, load_rules, score_text  # noqa: E402


CALIBRATION_GUIDE_COLUMNS = [
    "calibration_id",
    "validation_id",
    "article_id",
    "title",
    "abstract_chars",
    "classification_text_chars",
    "text_status",
    "cue_profile",
    "review_difficulty",
    "reviewer_focus",
    "causal_cue_terms",
    "predictive_cue_terms",
    "abstract_preview",
]
CALIBRATION_GUIDE_SUMMARY_COLUMNS = ["section", "value", "rows"]
CALIBRATION_KEY_COLUMNS = ["calibration_id", "validation_id", "article_id"]
CALIBRATION_PROGRESS_COLUMNS = [
    "calibration_id",
    "validation_id",
    "article_id",
    "title",
    "text_status",
    "review_difficulty",
    "completed_labels",
    "completed_reviewers",
    "reviewer_labels",
    "label_set",
    "error_rows",
    "row_status",
    "next_step",
]
REMAINING_CALIBRATION_STATUSES = {"needs_label", "disagreement", "fix_errors"}
REMAINING_CALIBRATION_SUMMARY_COLUMNS = ["metric", "value"]
CALIBRATION_SUBMISSION_AUDIT_COLUMNS = [
    "file",
    "rows",
    "completed_labels",
    "completed_rows",
    "reviewer_ids",
    "missing_required_columns",
    "status",
    "note",
]
CALIBRATION_SUBMISSION_REQUIRED_COLUMNS = CALIBRATION_KEY_COLUMNS + MANUAL_COLUMNS
CALIBRATION_SUBMISSION_TEMPLATE_COLUMNS = (
    CALIBRATION_KEY_COLUMNS
    + [
        "title",
        "abstract",
        *MANUAL_COLUMNS,
        "calibration_row_status",
        "calibration_next_step",
        "text_status",
        "cue_profile",
        "review_difficulty",
        "reviewer_focus",
    ]
)


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


def relative_href(from_path: Path, target: str) -> str:
    target_text = str(target or "").strip()
    if not target_text:
        return ""
    if target_text.startswith(("http://", "https://", "mailto:")):
        return target_text
    try:
        return os.path.relpath(target_text, start=str(from_path.parent))
    except ValueError:
        return target_text


def html_link(from_path: Path, label: str, target: str) -> str:
    target_text = str(target or "").strip()
    if not target_text:
        return ""
    return f'<a href="{html.escape(relative_href(from_path, target_text), quote=True)}">{html.escape(label)}</a>'


def html_open_target(from_path: Path, target: str) -> str:
    target_text = str(target or "").strip()
    if not target_text:
        return ""
    if " " in target_text and not Path(target_text).exists():
        return f"<code>{html.escape(target_text)}</code>"
    return html_link(from_path, "Open", target_text)


def calibration_packet_profile(packet: pd.DataFrame) -> pd.DataFrame:
    work = packet.copy().fillna("")
    abstract_chars = work["abstract"].astype(str).str.len() if "abstract" in work.columns else pd.Series(0, index=work.index)
    rows = [
        {"metric": "packet_rows", "value": len(work)},
        {"metric": "rows_with_abstract", "value": int(abstract_chars.gt(0).sum())},
        {"metric": "rows_without_abstract", "value": int(abstract_chars.eq(0).sum())},
        {"metric": "min_abstract_chars", "value": int(abstract_chars.min()) if len(abstract_chars) else 0},
        {"metric": "median_abstract_chars", "value": int(abstract_chars.median()) if len(abstract_chars) else 0},
        {"metric": "max_abstract_chars", "value": int(abstract_chars.max()) if len(abstract_chars) else 0},
    ]
    return pd.DataFrame(rows)


def truncate_text(value: Any, limit: int = 220) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def cue_profile(causal_score: int, predictive_score: int) -> str:
    if causal_score > 0 and predictive_score > 0:
        return "causal_and_predictive_cues"
    if causal_score > 0:
        return "causal_cues"
    if predictive_score > 0:
        return "predictive_cues"
    return "no_keyword_cues"


def calibration_text_status(text_chars: int, abstract_chars: int, minimum_chars: int) -> str:
    if abstract_chars == 0:
        return "no_abstract"
    if text_chars < minimum_chars:
        return "short_text"
    return "usable_text"


def calibration_review_difficulty(text_status: str, profile: str) -> str:
    if text_status == "no_abstract":
        return "high"
    if profile == "causal_and_predictive_cues":
        return "high"
    if text_status == "short_text":
        return "medium"
    return "routine"


def calibration_reviewer_focus(text_status: str, profile: str) -> str:
    if text_status == "no_abstract":
        return "Likely insufficient_text unless the title alone is decisive; explain any title-only judgment in notes."
    if text_status == "short_text":
        return "Check whether title plus short abstract are enough for a defensible label; otherwise use insufficient_text."
    if profile == "causal_and_predictive_cues":
        return "Apply the primary-focus rule; decide whether causal, predictive, or neither is the main objective."
    if profile == "causal_cues":
        return "Check whether causal effect estimation or interpretation is the main objective, not only motivation."
    if profile == "predictive_cues":
        return "Check whether prediction, forecasting, classification, or out-of-sample performance is the main objective."
    return "Usually other unless the title or abstract makes causal or predictive focus explicit."


def calibration_guide(packet: pd.DataFrame, rules: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    work = packet.copy().fillna("")
    minimum_chars = int(rules.get("minimum_usable_text_chars", 250))
    rows: list[dict[str, Any]] = []
    for _, row in work.iterrows():
        text = build_classification_text(row.to_dict(), rules.get("text_fields", ["title", "abstract"]))
        scores = score_text(text, rules)
        causal_score = int(scores["causal"]["score"])
        predictive_score = int(scores["predictive"]["score"])
        profile = cue_profile(causal_score, predictive_score)
        abstract = str(row.get("abstract", ""))
        abstract_chars = len(abstract.strip())
        text_chars = len(text)
        text_status = calibration_text_status(text_chars, abstract_chars, minimum_chars)
        rows.append(
            {
                "calibration_id": row.get("calibration_id", ""),
                "validation_id": row.get("validation_id", ""),
                "article_id": row.get("article_id", ""),
                "title": row.get("title", ""),
                "abstract_chars": abstract_chars,
                "classification_text_chars": text_chars,
                "text_status": text_status,
                "cue_profile": profile,
                "review_difficulty": calibration_review_difficulty(text_status, profile),
                "reviewer_focus": calibration_reviewer_focus(text_status, profile),
                "causal_cue_terms": "|".join(scores["causal"]["terms"]),
                "predictive_cue_terms": "|".join(scores["predictive"]["terms"]),
                "abstract_preview": truncate_text(abstract),
            }
        )
    guide = pd.DataFrame(rows, columns=CALIBRATION_GUIDE_COLUMNS)
    summary_parts: list[pd.DataFrame] = []
    for section, column in [
        ("text_status", "text_status"),
        ("cue_profile", "cue_profile"),
        ("review_difficulty", "review_difficulty"),
    ]:
        if guide.empty:
            continue
        counts = guide[column].value_counts(dropna=False).rename_axis("value").reset_index(name="rows")
        counts.insert(0, "section", section)
        summary_parts.append(counts)
    summary = pd.concat(summary_parts, ignore_index=True) if summary_parts else pd.DataFrame(columns=CALIBRATION_GUIDE_SUMMARY_COLUMNS)
    return guide, summary[CALIBRATION_GUIDE_SUMMARY_COLUMNS]


def write_calibration_guide_report(path: Path, guide: pd.DataFrame, summary: pd.DataFrame, *, rules_path: str, minimum_chars: int) -> None:
    preview_columns = [
        "calibration_id",
        "title",
        "abstract_chars",
        "text_status",
        "cue_profile",
        "review_difficulty",
        "reviewer_focus",
    ]
    preview = guide[[column for column in preview_columns if column in guide.columns]].copy()
    lines = [
        "# Manual Validation Calibration Guide",
        "",
        "This guide is blind to model predictions. It uses only the calibration packet title and abstract to flag text length and keyword cues that reviewers should consider while applying the codebook.",
        "",
        f"- Rules file for cue extraction: `{rules_path}`",
        f"- Minimum usable classification text: {minimum_chars}",
        "",
        "Do not treat cue flags as labels. Reviewers still choose `causal`, `predictive`, `other`, or `insufficient_text` from the primary-focus rule.",
        "",
        "## Summary",
        "",
        markdown_table(summary),
        "",
        "## Row Guide",
        "",
        markdown_table(preview),
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def packet_with_calibration_guide(packet: pd.DataFrame, guide: pd.DataFrame) -> pd.DataFrame:
    if packet.empty or guide.empty:
        return packet.copy()
    join_keys = [key for key in ["calibration_id", "validation_id", "article_id"] if key in packet.columns and key in guide.columns]
    if not join_keys:
        return packet.copy()
    guide_columns = [
        "calibration_id",
        "validation_id",
        "article_id",
        "abstract_chars",
        "classification_text_chars",
        "text_status",
        "cue_profile",
        "review_difficulty",
        "reviewer_focus",
        "causal_cue_terms",
        "predictive_cue_terms",
    ]
    guide_view = guide[[column for column in guide_columns if column in guide.columns]].drop_duplicates(join_keys, keep="first")
    merged = packet.copy().fillna("").merge(guide_view, on=join_keys, how="left")
    return merged.fillna("")


def calibration_submission_count(submissions_dir: Path) -> int:
    if not submissions_dir.exists():
        return 0
    return len([path for path in submissions_dir.glob("*.csv") if path.is_file()])


def calibration_form_paths(html_dir: Path) -> list[Path]:
    if not html_dir.exists():
        return []
    return sorted(
        path
        for path in html_dir.glob("*.html")
        if path.is_file() and "dashboard" not in path.name and "remaining" not in path.name
    )


def guide_summary_value(summary: pd.DataFrame, section: str, value: str) -> str:
    if summary.empty or not {"section", "value", "rows"}.issubset(summary.columns):
        return "0"
    rows = summary[
        summary["section"].astype(str).eq(section)
        & summary["value"].astype(str).eq(value)
    ]
    if rows.empty:
        return "0"
    return str(rows.iloc[0].get("rows", "0"))


CALIBRATION_LABEL_DECISION_RULES = [
    "Use only the provided title and abstract; ignore model predictions, journal, authors, year, DOI, and outside knowledge.",
    "Apply the primary-focus rule: choose the label that best describes the paper's main research objective.",
    "Choose insufficient_text only when the title and abstract are missing, too short, or too vague for a defensible label.",
    "Choose causal when the main objective is estimating, identifying, or interpreting causal effects.",
    "Choose predictive when the main objective is prediction, forecasting, classification, nowcasting, or out-of-sample performance.",
    "Choose other for theory, measurement, institutional narrative, or methods papers that are not primarily causal or predictive.",
    "When causal and predictive cues both appear, label the main objective and use manual_notes for the ambiguity.",
]

CALIBRATION_AFTER_EXPORT_COMMANDS = [
    "PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_manual_validation_calibration.py",
    "PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_validation_gate.py",
    "PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_human_review_workboard.py",
]


def calibration_kickoff_checklist(
    *,
    summary: pd.DataFrame,
    errors: pd.DataFrame,
    disagreements: pd.DataFrame,
    packet_path: Path,
    html_dir: Path,
    submissions_dir: Path,
    codebook_path: Path,
    guide_path: Path | None = None,
    remaining_form_path: Path | None = None,
    remaining_report_path: Path | None = None,
    remaining_template_path: Path | None = None,
) -> pd.DataFrame:
    lookup = dict(zip(summary["metric"].astype(str), summary["value"])) if not summary.empty else {}
    calibration_rows = int(lookup.get("calibration_rows", 0) or 0)
    completed_labels = int(lookup.get("completed_calibration_labels", 0) or 0)
    form_paths = calibration_form_paths(html_dir)
    submission_count = calibration_submission_count(submissions_dir)
    rows = [
        {
            "step_order": 1,
            "step": "Read the codebook",
            "status": "ready" if codebook_path.exists() else "missing",
            "action": "Review label definitions and borderline-case guidance before labeling.",
            "path_or_command": str(codebook_path),
            "note": "Use only title and abstract for calibration labels.",
        },
        {
            "step_order": 2,
            "step": "Read the calibration guide",
            "status": "ready" if guide_path is not None and guide_path.exists() else "missing",
            "action": "Review text-status and cue-profile flags without treating them as labels.",
            "path_or_command": str(guide_path) if guide_path is not None else "",
            "note": "The guide is blind to model predictions and uses only title/abstract text.",
        },
        {
            "step_order": 3,
            "step": "Open the remaining calibration form",
            "status": "ready" if remaining_form_path is not None and remaining_form_path.exists() else "missing",
            "action": "Open the filtered HTML form and label only rows still needing calibration work.",
            "path_or_command": str(remaining_form_path) if remaining_form_path is not None else str(html_dir),
            "note": f"Filtered packet report: {remaining_report_path}" if remaining_report_path is not None else "Filtered packet shows unresolved rows only.",
        },
        {
            "step_order": 4,
            "step": "Use spreadsheet template if needed",
            "status": "ready" if remaining_template_path is not None and remaining_template_path.exists() else "missing",
            "action": "Use this CSV only if labeling in a spreadsheet instead of the browser form.",
            "path_or_command": str(remaining_template_path) if remaining_template_path is not None else "",
            "note": "Save a completed copy in the submissions directory; keep the blank template outside submissions.",
        },
        {
            "step_order": 5,
            "step": "Open the full calibration form",
            "status": "ready" if form_paths else "missing",
            "action": "Use the full HTML form when you need all calibration rows in one view.",
            "path_or_command": str(form_paths[0]) if form_paths else str(html_dir),
            "note": f"Packet source: {packet_path}",
        },
        {
            "step_order": 6,
            "step": "Complete calibration labels",
            "status": "done" if calibration_rows and completed_labels >= calibration_rows else "pending",
            "action": "Fill manual_label, manual_confidence, reviewer_id, and review_date for every calibration row.",
            "path_or_command": str(remaining_form_path) if remaining_form_path is not None else str(form_paths[0]) if form_paths else str(packet_path),
            "note": f"{completed_labels} / {calibration_rows} completed labels recorded.",
        },
        {
            "step_order": 7,
            "step": "Export reviewer CSV",
            "status": "ready" if submissions_dir.exists() else "missing",
            "action": "Use Export CSV from the form and put each reviewer export in the submissions directory.",
            "path_or_command": str(submissions_dir),
            "note": f"{submission_count} submission CSV files currently found.",
        },
        {
            "step_order": 8,
            "step": "Refresh calibration summary",
            "status": "ready",
            "action": "Rerun the calibration command after adding reviewer submissions.",
            "path_or_command": "/usr/bin/python3 run_manual_validation_calibration.py",
            "note": "This updates the agreement summary and disagreement packet.",
        },
        {
            "step_order": 9,
            "step": "Resolve calibration disagreements",
            "status": "pending" if not disagreements.empty else "not_applicable",
            "action": "Discuss disagreements before assigning the full validation sample.",
            "path_or_command": "outputs/tables/enriched/manual_validation_calibration_disagreements.csv",
            "note": f"{len(disagreements)} disagreement rows currently listed.",
        },
        {
            "step_order": 10,
            "step": "Recheck validation gate",
            "status": "blocked" if completed_labels < calibration_rows else "ready",
            "action": "Rerun the validation gate after calibration is complete.",
            "path_or_command": "/usr/bin/python3 run_validation_gate.py",
            "note": "The gate will remain blocked until calibration labels are complete.",
        },
    ]
    if not errors.empty:
        rows.append(
            {
                "step_order": 11,
                "step": "Fix submission errors",
                "status": "blocked",
                "action": "Correct invalid labels, confidence values, duplicate rows, or malformed dates.",
                "path_or_command": "outputs/tables/enriched/manual_validation_calibration_errors.csv",
                "note": f"{len(errors)} submission errors currently listed.",
            }
        )
    return pd.DataFrame(rows)


def write_calibration_kickoff_report(
    path: Path,
    checklist: pd.DataFrame,
    packet_profile: pd.DataFrame,
    *,
    packet_path: str,
    html_dir: str,
    submissions_dir: str,
    guide_path: str | None = None,
    remaining_report_path: str | None = None,
    remaining_form_path: str | None = None,
    remaining_template_path: str | None = None,
) -> None:
    lines = [
        "# Manual Validation Calibration Kickoff",
        "",
        f"- Calibration packet: `{packet_path}`",
        f"- Calibration guide: `{guide_path}`" if guide_path else "- Calibration guide: _not configured_",
        f"- Remaining-row guide: `{remaining_report_path}`" if remaining_report_path else "- Remaining-row guide: _not configured_",
        f"- Remaining-row form: `{remaining_form_path}`" if remaining_form_path else "- Remaining-row form: _not configured_",
        f"- Spreadsheet template: `{remaining_template_path}`" if remaining_template_path else "- Spreadsheet template: _not configured_",
        f"- Browser forms: `{html_dir}`",
        f"- Submission directory: `{submissions_dir}`",
        "",
        "Use this as the handoff for the required 20-row calibration step. Do not edit model labels here; reviewers fill only manual fields.",
        "",
        "## Label Decision Cheat Sheet",
        "",
        *[f"- {item}" for item in CALIBRATION_LABEL_DECISION_RULES],
        "",
        "## After Export Commands",
        "",
        "After adding reviewer CSV exports to the submissions directory, run these non-importing refresh checks. The validation gate should remain blocked until all 20 calibration rows are complete and disagreements are resolved.",
        "",
        "```bash",
        *CALIBRATION_AFTER_EXPORT_COMMANDS,
        "```",
        "",
        "## Checklist",
        "",
        markdown_table(checklist),
        "",
        "## Packet Profile",
        "",
        markdown_table(packet_profile),
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def calibration_submission_file_error(file_path: Path, field: str, error: str, value: str = "") -> dict[str, Any]:
    return {
        "validation_id": "",
        "article_id": "",
        "row_number": 0,
        "field": field,
        "value": value or str(file_path),
        "error": error,
    }


def load_calibration_submissions(submissions_dir: Path, packet: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    files = sorted(item for item in submissions_dir.glob("*.csv") if item.is_file()) if submissions_dir.exists() else []
    if not files:
        audit = pd.DataFrame(
            [
                {
                    "file": "",
                    "rows": 0,
                    "completed_labels": 0,
                    "completed_rows": 0,
                    "reviewer_ids": "",
                    "missing_required_columns": "",
                    "status": "no_submission_files",
                    "note": "No reviewer CSV files found; using the blank calibration packet for progress.",
                }
            ],
            columns=CALIBRATION_SUBMISSION_AUDIT_COLUMNS,
        )
        return packet.copy().fillna(""), audit, pd.DataFrame(columns=VALIDATION_ERROR_COLUMNS)

    frames: list[pd.DataFrame] = []
    audit_rows: list[dict[str, Any]] = []
    error_rows: list[dict[str, Any]] = []
    for file_path in files:
        try:
            raw = pd.read_csv(file_path, dtype=str).fillna("")
        except Exception as exc:  # pragma: no cover - parser errors vary by pandas engine
            audit_rows.append(
                {
                    "file": str(file_path),
                    "rows": 0,
                    "completed_labels": 0,
                    "completed_rows": 0,
                    "reviewer_ids": "",
                    "missing_required_columns": "",
                    "status": "read_error",
                    "note": f"Could not read CSV: {exc}",
                }
            )
            error_rows.append(calibration_submission_file_error(file_path, "submission_file", "calibration_submission_file_read_error"))
            continue

        frames.append(raw)
        missing_columns = [column for column in CALIBRATION_SUBMISSION_REQUIRED_COLUMNS if column not in raw.columns]
        work = raw.copy().fillna("")
        for column in CALIBRATION_SUBMISSION_REQUIRED_COLUMNS:
            if column not in work.columns:
                work[column] = ""
        completed = work[completed_manual_label_mask(work)].copy()
        completed_rows = (
            completed[CALIBRATION_KEY_COLUMNS].drop_duplicates().shape[0]
            if not completed.empty and set(CALIBRATION_KEY_COLUMNS).issubset(completed.columns)
            else 0
        )
        reviewer_ids = sorted({value for value in completed["reviewer_id"].astype(str).str.strip() if value})
        completed_labels = int(len(completed))

        if len(raw) == 0:
            status = "empty_file"
            note = "CSV has headers but no rows."
            error_rows.append(calibration_submission_file_error(file_path, "submission_file", "calibration_submission_file_empty"))
        elif missing_columns:
            status = "missing_required_columns"
            note = "Submission file is missing required columns."
            for column in missing_columns:
                error_rows.append(calibration_submission_file_error(file_path, column, "calibration_submission_file_missing_column"))
        elif completed_labels == 0:
            status = "blank_no_completed_labels"
            note = "CSV has rows but no completed manual_label values; remove blank templates from the submissions directory."
            error_rows.append(calibration_submission_file_error(file_path, "manual_label", "calibration_submission_file_has_no_completed_labels"))
        else:
            status = "ready_for_calibration_refresh"
            note = "Submission file has completed labels and will be included in calibration summaries."

        audit_rows.append(
            {
                "file": str(file_path),
                "rows": len(raw),
                "completed_labels": completed_labels,
                "completed_rows": completed_rows,
                "reviewer_ids": "|".join(reviewer_ids),
                "missing_required_columns": "|".join(missing_columns),
                "status": status,
                "note": note,
            }
        )

    submissions = pd.concat(frames, ignore_index=True) if frames else packet.copy().fillna("")
    audit = pd.DataFrame(audit_rows, columns=CALIBRATION_SUBMISSION_AUDIT_COLUMNS)
    file_errors = pd.DataFrame(error_rows, columns=VALIDATION_ERROR_COLUMNS)
    return submissions.fillna(""), audit.fillna(""), file_errors.fillna("")


def calibration_submission_key(df: pd.DataFrame) -> pd.Series:
    work = df.copy().fillna("")
    return work["calibration_id"].astype(str).str.strip() + "|" + work["validation_id"].astype(str).str.strip() + "|" + work["article_id"].astype(str).str.strip()


def calibration_sample_key(df: pd.DataFrame) -> pd.Series:
    work = df.copy().fillna("")
    return work["validation_id"].astype(str).str.strip() + "|" + work["article_id"].astype(str).str.strip()


def calibration_packet_identity_errors(sample: pd.DataFrame, packet: pd.DataFrame, *, expected_rows: int) -> pd.DataFrame:
    sample_work = sample.copy().fillna("")
    packet_work = packet.copy().fillna("")
    errors: list[dict[str, Any]] = []

    missing_packet_columns = [column for column in CALIBRATION_KEY_COLUMNS if column not in packet_work.columns]
    for column in missing_packet_columns:
        errors.append(
            {
                "validation_id": "",
                "article_id": "",
                "row_number": 0,
                "field": column,
                "value": "",
                "error": "missing_calibration_packet_key_column",
            }
        )
    missing_sample_columns = [column for column in ["validation_id", "article_id"] if column not in sample_work.columns]
    for column in missing_sample_columns:
        errors.append(
            {
                "validation_id": "",
                "article_id": "",
                "row_number": 0,
                "field": column,
                "value": "",
                "error": "missing_sample_key_column",
            }
        )
    if missing_packet_columns or missing_sample_columns:
        return pd.DataFrame(errors, columns=VALIDATION_ERROR_COLUMNS)

    if len(packet_work) != expected_rows:
        errors.append(
            {
                "validation_id": "",
                "article_id": "",
                "row_number": 0,
                "field": "calibration_rows",
                "value": str(len(packet_work)),
                "error": "calibration_packet_row_count_mismatch",
            }
        )

    sample_keys = set(calibration_sample_key(sample_work))
    packet_keys = calibration_sample_key(packet_work)
    calibration_ids = packet_work["calibration_id"].astype(str).str.strip()
    duplicate_calibration_mask = calibration_ids.ne("") & calibration_ids.duplicated(keep=False)
    duplicate_key_mask = packet_keys.ne("|") & packet_keys.duplicated(keep=False)
    unknown_mask = ~packet_keys.isin(sample_keys)
    missing_calibration_id_mask = calibration_ids.eq("")

    for idx, row in packet_work.iterrows():
        validation_id = row.get("validation_id", "")
        article_id = row.get("article_id", "")
        row_number = idx + 2
        if missing_calibration_id_mask.loc[idx]:
            errors.append(
                {
                    "validation_id": validation_id,
                    "article_id": article_id,
                    "row_number": row_number,
                    "field": "calibration_id",
                    "value": "",
                    "error": "missing_calibration_id",
                }
            )
        if duplicate_calibration_mask.loc[idx]:
            errors.append(
                {
                    "validation_id": validation_id,
                    "article_id": article_id,
                    "row_number": row_number,
                    "field": "calibration_id",
                    "value": calibration_ids.loc[idx],
                    "error": "duplicate_calibration_id",
                }
            )
        if duplicate_key_mask.loc[idx]:
            errors.append(
                {
                    "validation_id": validation_id,
                    "article_id": article_id,
                    "row_number": row_number,
                    "field": "validation_id|article_id",
                    "value": packet_keys.loc[idx],
                    "error": "duplicate_calibration_sample_row",
                }
            )
        if unknown_mask.loc[idx]:
            errors.append(
                {
                    "validation_id": validation_id,
                    "article_id": article_id,
                    "row_number": row_number,
                    "field": "validation_id|article_id",
                    "value": packet_keys.loc[idx],
                    "error": "calibration_row_not_in_sample",
                }
            )

    return pd.DataFrame(errors, columns=VALIDATION_ERROR_COLUMNS)


def calibration_submission_identity_errors(packet: pd.DataFrame, submissions: pd.DataFrame) -> pd.DataFrame:
    packet_work = packet.copy().fillna("")
    submission_work = submissions.copy().fillna("")
    errors: list[dict[str, Any]] = []

    missing_packet_columns = [column for column in CALIBRATION_KEY_COLUMNS if column not in packet_work.columns]
    for column in missing_packet_columns:
        errors.append(
            {
                "validation_id": "",
                "article_id": "",
                "row_number": 0,
                "field": column,
                "value": "",
                "error": "missing_calibration_packet_key_column",
            }
        )

    missing_submission_columns = [column for column in CALIBRATION_KEY_COLUMNS if column not in submission_work.columns]
    for column in missing_submission_columns:
        errors.append(
            {
                "validation_id": "",
                "article_id": "",
                "row_number": 0,
                "field": column,
                "value": "",
                "error": "missing_calibration_submission_key_column",
            }
        )

    if missing_packet_columns or missing_submission_columns:
        return pd.DataFrame(errors, columns=VALIDATION_ERROR_COLUMNS)

    packet_keys = set(calibration_submission_key(packet_work))
    submission_keys = calibration_submission_key(submission_work)
    unknown_mask = ~submission_keys.isin(packet_keys)
    if unknown_mask.any():
        for idx, row in submission_work.loc[unknown_mask].iterrows():
            errors.append(
                {
                    "validation_id": row.get("validation_id", ""),
                    "article_id": row.get("article_id", ""),
                    "row_number": idx + 2,
                    "field": "calibration_id|validation_id|article_id",
                    "value": submission_keys.loc[idx],
                    "error": "calibration_row_not_in_packet",
                }
            )

    completed_mask = completed_manual_label_mask(submission_work)
    if "reviewer_id" not in submission_work.columns:
        submission_work["reviewer_id"] = ""
    reviewer_keys = submission_keys + "|" + submission_work["reviewer_id"].astype(str).str.strip()
    duplicate_mask = completed_mask & reviewer_keys.duplicated(keep=False)
    if duplicate_mask.any():
        for idx, row in submission_work.loc[duplicate_mask].iterrows():
            errors.append(
                {
                    "validation_id": row.get("validation_id", ""),
                    "article_id": row.get("article_id", ""),
                    "row_number": idx + 2,
                    "field": "calibration_id|validation_id|article_id|reviewer_id",
                    "value": reviewer_keys.loc[idx],
                    "error": "duplicate_calibration_reviewer_row",
                }
            )

    return pd.DataFrame(errors, columns=VALIDATION_ERROR_COLUMNS)


def calibration_error_counts(errors: pd.DataFrame) -> dict[str, int]:
    if errors.empty or not {"validation_id", "article_id"}.issubset(errors.columns):
        return {}
    work = errors.copy().fillna("")
    work["_key"] = work["validation_id"].astype(str).str.strip() + "|" + work["article_id"].astype(str).str.strip()
    work = work[work["_key"].str.strip().ne("|")]
    if work.empty:
        return {}
    return work.groupby("_key", dropna=False).size().astype(int).to_dict()


def calibration_row_progress(
    *,
    packet: pd.DataFrame,
    submissions: pd.DataFrame,
    guide: pd.DataFrame,
    errors: pd.DataFrame,
) -> pd.DataFrame:
    if packet.empty:
        return pd.DataFrame(columns=CALIBRATION_PROGRESS_COLUMNS)
    packet_work = packet.copy().fillna("")
    submission_work = submissions.copy().fillna("")
    for column in ["manual_label", "reviewer_id", "manual_confidence", "manual_notes"]:
        if column not in submission_work.columns:
            submission_work[column] = ""
    guide_work = guide.copy().fillna("") if not guide.empty else pd.DataFrame()
    guide_cols = [column for column in ["calibration_id", "validation_id", "article_id", "text_status", "review_difficulty"] if column in guide_work.columns]
    if guide_cols:
        packet_work = packet_work.merge(guide_work[guide_cols].drop_duplicates(CALIBRATION_KEY_COLUMNS, keep="first"), on=CALIBRATION_KEY_COLUMNS, how="left").fillna("")
    error_counts = calibration_error_counts(errors)
    rows: list[dict[str, Any]] = []
    for _, packet_row in packet_work.iterrows():
        calibration_id = str(packet_row.get("calibration_id", "")).strip()
        validation_id = str(packet_row.get("validation_id", "")).strip()
        article_id = str(packet_row.get("article_id", "")).strip()
        matches = submission_work[
            submission_work.get("calibration_id", pd.Series("", index=submission_work.index)).astype(str).str.strip().eq(calibration_id)
            & submission_work.get("validation_id", pd.Series("", index=submission_work.index)).astype(str).str.strip().eq(validation_id)
            & submission_work.get("article_id", pd.Series("", index=submission_work.index)).astype(str).str.strip().eq(article_id)
        ].copy()
        completed = matches[matches["manual_label"].astype(str).str.strip().ne("")]
        reviewers = [reviewer for reviewer in completed["reviewer_id"].astype(str).str.strip().tolist() if reviewer]
        reviewer_labels = [
            f"{reviewer or 'missing_reviewer'}={label}"
            for reviewer, label in zip(completed["reviewer_id"].astype(str).str.strip(), completed["manual_label"].astype(str).str.strip())
            if label
        ]
        labels = sorted({label for label in completed["manual_label"].astype(str).str.strip() if label})
        error_rows = error_counts.get(f"{validation_id}|{article_id}", 0)
        if error_rows:
            row_status = "fix_errors"
            next_step = "Fix submission errors for this calibration row, then rerun calibration."
        elif len(labels) > 1:
            row_status = "disagreement"
            next_step = "Discuss reviewer disagreement before assigning the full validation sample."
        elif len(completed) == 0:
            row_status = "needs_label"
            next_step = "Complete manual_label, manual_confidence, reviewer_id, and review_date."
        elif len({reviewer for reviewer in reviewers if reviewer}) >= 2:
            row_status = "multi_reviewer_agreement"
            next_step = "No action needed unless calibration policy requires discussion."
        else:
            row_status = "labeled"
            next_step = "No action needed for this row."
        rows.append(
            {
                "calibration_id": calibration_id,
                "validation_id": validation_id,
                "article_id": article_id,
                "title": packet_row.get("title", ""),
                "text_status": packet_row.get("text_status", ""),
                "review_difficulty": packet_row.get("review_difficulty", ""),
                "completed_labels": len(completed),
                "completed_reviewers": len({reviewer for reviewer in reviewers if reviewer}),
                "reviewer_labels": " | ".join(reviewer_labels),
                "label_set": "|".join(labels),
                "error_rows": error_rows,
                "row_status": row_status,
                "next_step": next_step,
            }
        )
    return pd.DataFrame(rows, columns=CALIBRATION_PROGRESS_COLUMNS)


def remaining_calibration_packet(packet: pd.DataFrame, guide: pd.DataFrame, progress: pd.DataFrame) -> pd.DataFrame:
    if packet.empty or progress.empty:
        return pd.DataFrame(columns=packet.columns)
    form_packet = packet_with_calibration_guide(packet, guide)
    progress_cols = [
        column
        for column in [
            "calibration_id",
            "validation_id",
            "article_id",
            "completed_labels",
            "completed_reviewers",
            "reviewer_labels",
            "label_set",
            "error_rows",
            "row_status",
            "next_step",
        ]
        if column in progress.columns
    ]
    if not {"calibration_id", "validation_id", "article_id", "row_status"}.issubset(progress_cols):
        return pd.DataFrame(columns=form_packet.columns)
    remaining_progress = progress[progress["row_status"].astype(str).isin(REMAINING_CALIBRATION_STATUSES)].copy().fillna("")
    if remaining_progress.empty:
        return pd.DataFrame(columns=list(form_packet.columns) + ["calibration_row_status", "calibration_next_step"])
    merged = form_packet.merge(
        remaining_progress[progress_cols].drop_duplicates(CALIBRATION_KEY_COLUMNS, keep="first"),
        on=CALIBRATION_KEY_COLUMNS,
        how="inner",
        suffixes=("", "_progress"),
    ).fillna("")
    merged["calibration_row_status"] = merged.get("row_status", "")
    merged["calibration_next_step"] = merged.get("next_step", "")
    sort_order = {"fix_errors": 1, "disagreement": 2, "needs_label": 3}
    merged["_status_order"] = merged["calibration_row_status"].map(sort_order).fillna(99).astype(int)
    if "review_difficulty" in merged.columns:
        merged["_difficulty_order"] = merged["review_difficulty"].map({"high": 1, "medium": 2, "routine": 3}).fillna(99).astype(int)
    else:
        merged["_difficulty_order"] = 99
    merged["_calibration_order"] = pd.to_numeric(merged["calibration_id"].astype(str).str.extract(r"(\d+)", expand=False), errors="coerce").fillna(999999).astype(int)
    merged = merged.sort_values(["_status_order", "_difficulty_order", "_calibration_order", "calibration_id"]).drop(columns=["_status_order", "_difficulty_order", "_calibration_order"])
    return merged.reset_index(drop=True)


def remaining_calibration_summary(remaining: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = [{"metric": "remaining_rows", "value": len(remaining)}]
    if not remaining.empty and "calibration_row_status" in remaining.columns:
        counts = remaining["calibration_row_status"].astype(str).value_counts().sort_index()
        for status, count in counts.items():
            rows.append({"metric": f"status_{status}", "value": int(count)})
    if not remaining.empty and "review_difficulty" in remaining.columns:
        counts = remaining["review_difficulty"].astype(str).value_counts().sort_index()
        for difficulty, count in counts.items():
            rows.append({"metric": f"difficulty_{difficulty}", "value": int(count)})
    return pd.DataFrame(rows, columns=REMAINING_CALIBRATION_SUMMARY_COLUMNS)


def remaining_calibration_submission_template(remaining: pd.DataFrame) -> pd.DataFrame:
    work = remaining.copy().fillna("")
    for column in CALIBRATION_SUBMISSION_TEMPLATE_COLUMNS:
        if column not in work.columns:
            work[column] = ""
    out = work[CALIBRATION_SUBMISSION_TEMPLATE_COLUMNS].copy()
    for column in MANUAL_COLUMNS:
        out[column] = ""
    return out


def write_remaining_calibration_report(
    path: Path,
    remaining: pd.DataFrame,
    summary: pd.DataFrame,
    *,
    output_csv: str,
    output_form: str,
    output_template: str,
) -> None:
    preview_columns = [
        "calibration_id",
        "title",
        "calibration_row_status",
        "text_status",
        "cue_profile",
        "review_difficulty",
        "completed_labels",
        "reviewer_labels",
        "calibration_next_step",
    ]
    preview = remaining[[column for column in preview_columns if column in remaining.columns]].copy() if not remaining.empty else pd.DataFrame(columns=preview_columns)
    lines = [
        "# Manual Validation Calibration Remaining Packet",
        "",
        "This generated packet contains only calibration rows that still need a label, disagreement discussion, or submission-error fix. It is blind to model predictions and uses the same manual-label export schema as the full calibration form.",
        "",
        f"- Remaining CSV: `{output_csv}`",
        f"- Remaining form: `{output_form}`",
        f"- Spreadsheet template: `{output_template}`",
        "",
        "## Summary",
        "",
        markdown_table(summary),
        "",
        "## Rows",
        "",
        markdown_table(preview),
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_calibration_report(
    path: Path,
    summary: pd.DataFrame,
    disagreements: pd.DataFrame,
    errors: pd.DataFrame,
    submission_audit: pd.DataFrame,
    progress: pd.DataFrame,
    *,
    packet_path: str,
    html_dir: str,
    submissions_dir: str,
) -> None:
    lookup = dict(zip(summary["metric"].astype(str), summary["value"])) if not summary.empty else {}
    lines = [
        "# Manual Validation Calibration",
        "",
        f"- Calibration packet: `{packet_path}`",
        f"- Browser forms: `{html_dir}`",
        f"- Submissions directory: `{submissions_dir}`",
        f"- Calibration rows: {lookup.get('calibration_rows', 0)}",
        f"- Completed calibration rows: {lookup.get('completed_calibration_rows', lookup.get('completed_calibration_labels', 0))}",
        f"- Completed calibration labels: {lookup.get('completed_calibration_labels', 0)}",
        f"- Calibration reviewers: {lookup.get('calibration_reviewers', 0)}",
        f"- Rows with multiple reviewers: {lookup.get('rows_with_multiple_reviewers', 0)}",
        f"- Disagreement rows: {lookup.get('disagreement_rows', 0)}",
        f"- Agreement rate: `{lookup.get('agreement_rate', '')}`",
        "",
        "## Summary",
        "",
        markdown_table(summary),
        "",
        "## Submission Files",
        "",
        markdown_table(submission_audit),
        "",
        "## Submission Errors",
        "",
        markdown_table(errors),
        "",
        "## Disagreements For Discussion",
        "",
        markdown_table(disagreements),
        "",
        "## Row Progress",
        "",
        markdown_table(progress),
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_calibration_dashboard(
    path: Path,
    *,
    summary: pd.DataFrame,
    checklist: pd.DataFrame,
    packet_profile: pd.DataFrame,
    errors: pd.DataFrame,
    submission_audit: pd.DataFrame,
    disagreements: pd.DataFrame,
    guide_summary: pd.DataFrame,
    progress: pd.DataFrame,
    packet_path: str,
    html_dir: str,
    submissions_dir: str,
    codebook_path: str,
    report_path: str,
    kickoff_report_path: str,
    guide_report_path: str,
    remaining_report_path: str,
    remaining_form_path: str,
    remaining_template_path: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lookup = dict(zip(summary["metric"].astype(str), summary["value"])) if not summary.empty else {}
    profile_lookup = dict(zip(packet_profile["metric"].astype(str), packet_profile["value"])) if not packet_profile.empty else {}
    form_paths = [form for form in calibration_form_paths(Path(html_dir)) if form.name != path.name]
    form_path = str(form_paths[0]) if form_paths else html_dir
    submission_count = calibration_submission_count(Path(submissions_dir))
    calibration_rows = str(lookup.get("calibration_rows", 0))
    completed_rows = str(lookup.get("completed_calibration_rows", lookup.get("completed_calibration_labels", 0)))
    completed_labels = str(lookup.get("completed_calibration_labels", 0))
    audited_submission_files = int(
        submission_audit["file"].astype(str).str.strip().ne("").sum()
        if not submission_audit.empty and "file" in submission_audit.columns
        else 0
    )

    checklist_rows = []
    for _, row in checklist.copy().fillna("").iterrows():
        checklist_rows.append(
            "<tr>"
            f"<td>{html.escape(str(row.get('step_order', '')))}</td>"
            f"<td>{html.escape(str(row.get('step', '')))}</td>"
            f"<td><code>{html.escape(str(row.get('status', '')))}</code></td>"
            f"<td>{html.escape(str(row.get('action', '')))}<span>{html.escape(str(row.get('note', '')))}</span></td>"
            f"<td>{html_open_target(path, str(row.get('path_or_command', '')))}</td>"
            "</tr>"
        )
    checklist_table = "\n".join(checklist_rows) or '<tr><td colspan="5">No checklist rows found.</td></tr>'
    report_links = [
        ("Open remaining calibration form", remaining_form_path),
        ("Open spreadsheet template", remaining_template_path),
        ("Open calibration form", form_path),
        ("Codebook", codebook_path),
        ("Calibration guide", guide_report_path),
        ("Remaining rows report", remaining_report_path),
        ("Kickoff checklist", kickoff_report_path),
        ("Calibration report", report_path),
        ("Packet CSV", packet_path),
        ("Submission directory", submissions_dir),
    ]
    report_items = "\n".join(
        f"<li>{html_link(path, label, target)}</li>"
        for label, target in report_links
        if str(target or "").strip()
    )
    next_status = "complete" if str(completed_rows) == str(calibration_rows) and str(calibration_rows) != "0" else "blocked_calibration"
    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Calibration Dashboard</title>
  <style>
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #1f2933;
      background: #ffffff;
    }}
    main {{
      max-width: 1080px;
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
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 10px;
      margin: 18px 0;
    }}
    .metric {{
      border: 1px solid #d7dce2;
      border-radius: 8px;
      padding: 12px;
      background: #f7f8fa;
    }}
    .metric span, td span {{
      display: block;
      color: #667085;
      font-size: 12px;
      margin-top: 4px;
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
      padding: 10px 8px;
      text-align: left;
      vertical-align: top;
      font-size: 14px;
    }}
    th {{
      color: #667085;
      font-weight: 650;
    }}
    a {{
      color: #215c5c;
    }}
    code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 12px;
      background: #eef2f3;
      border-radius: 4px;
      padding: 2px 4px;
    }}
  </style>
</head>
<body>
  <main>
    <h1>Calibration Dashboard</h1>
    <div class="summary">
      <div class="metric"><span>Gate status</span><strong>{html.escape(next_status)}</strong></div>
      <div class="metric"><span>Completed rows</span><strong>{html.escape(completed_rows)} / {html.escape(calibration_rows)}</strong></div>
      <div class="metric"><span>Completed labels</span><strong>{html.escape(completed_labels)}</strong></div>
      <div class="metric"><span>Reviewers</span><strong>{html.escape(str(lookup.get("calibration_reviewers", 0)))}</strong></div>
      <div class="metric"><span>Submissions</span><strong>{html.escape(str(submission_count))}</strong></div>
      <div class="metric"><span>Audited files</span><strong>{html.escape(str(audited_submission_files))}</strong></div>
      <div class="metric"><span>Disagreements</span><strong>{html.escape(str(len(disagreements)))}</strong></div>
      <div class="metric"><span>Submission errors</span><strong>{html.escape(str(len(errors)))}</strong></div>
      <div class="metric"><span>Rows needing labels</span><strong>{html.escape(str(int(progress["row_status"].astype(str).eq("needs_label").sum()) if "row_status" in progress.columns else 0))}</strong></div>
      <div class="metric"><span>No abstract rows</span><strong>{html.escape(guide_summary_value(guide_summary, "text_status", "no_abstract"))}</strong></div>
      <div class="metric"><span>High difficulty</span><strong>{html.escape(guide_summary_value(guide_summary, "review_difficulty", "high"))}</strong></div>
      <div class="metric"><span>Packet rows</span><strong>{html.escape(str(profile_lookup.get("packet_rows", calibration_rows)))}</strong></div>
    </div>

    <h2>Start Here</h2>
    <ul>
      {report_items}
    </ul>

    <h2>Checklist</h2>
    <table>
      <thead><tr><th>#</th><th>Step</th><th>Status</th><th>Action</th><th>Open</th></tr></thead>
      <tbody>
        {checklist_table}
      </tbody>
    </table>

    <h2>Submission Files</h2>
    <table>
      <thead><tr><th>File</th><th>Status</th><th>Rows</th><th>Completed</th><th>Note</th></tr></thead>
      <tbody>
        {calibration_submission_audit_rows(submission_audit)}
      </tbody>
    </table>

    <h2>Row Progress</h2>
    <table>
      <thead><tr><th>ID</th><th>Title</th><th>Status</th><th>Labels</th><th>Next Step</th></tr></thead>
      <tbody>
        {calibration_progress_rows(progress)}
      </tbody>
    </table>
  </main>
</body>
</html>
"""
    path.write_text(html_text, encoding="utf-8")


def calibration_submission_audit_rows(submission_audit: pd.DataFrame) -> str:
    if submission_audit.empty:
        return '<tr><td colspan="5">No submission audit rows found.</td></tr>'
    rows: list[str] = []
    for _, row in submission_audit.copy().fillna("").iterrows():
        completed = f"{html.escape(str(row.get('completed_labels', '0')))} labels / {html.escape(str(row.get('completed_rows', '0')))} rows"
        detail = str(row.get("reviewer_ids", "")).strip()
        if detail:
            completed = f"{completed}<span>{html.escape(detail)}</span>"
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(row.get('file', '')) or '(none)')}</td>"
            f"<td><code>{html.escape(str(row.get('status', '')))}</code></td>"
            f"<td>{html.escape(str(row.get('rows', '0')))}</td>"
            f"<td>{completed}</td>"
            f"<td>{html.escape(str(row.get('note', '')))}<span>{html.escape(str(row.get('missing_required_columns', '')))}</span></td>"
            "</tr>"
        )
    return "\n".join(rows)


def calibration_progress_rows(progress: pd.DataFrame) -> str:
    if progress.empty:
        return '<tr><td colspan="5">No progress rows found.</td></tr>'
    rows: list[str] = []
    for _, row in progress.copy().fillna("").iterrows():
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(row.get('calibration_id', '')))}</td>"
            f"<td>{html.escape(str(row.get('title', '')))}<span>{html.escape(str(row.get('text_status', '')))} · {html.escape(str(row.get('review_difficulty', '')))}</span></td>"
            f"<td><code>{html.escape(str(row.get('row_status', '')))}</code></td>"
            f"<td>{html.escape(str(row.get('completed_labels', '0')))}<span>{html.escape(str(row.get('reviewer_labels', '')))}</span></td>"
            f"<td>{html.escape(str(row.get('next_step', '')))}</td>"
            "</tr>"
        )
    return "\n".join(rows)



def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", default="data/intermediate/manual_validation_sample.csv")
    parser.add_argument("--packet-output", default="data/intermediate/manual_validation_calibration/manual_validation_calibration_packet.csv")
    parser.add_argument("--html-dir", default="data/intermediate/manual_validation_calibration_forms")
    parser.add_argument("--submissions-dir", default="data/intermediate/manual_validation_calibration_submissions")
    parser.add_argument("--sample-size", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260629)
    parser.add_argument("--regenerate", action="store_true")
    parser.add_argument("--overwrite-labeled", action="store_true")
    parser.add_argument("--summary-output", default="outputs/tables/enriched/manual_validation_calibration_summary.csv")
    parser.add_argument("--progress-output", default="outputs/tables/enriched/manual_validation_calibration_progress.csv")
    parser.add_argument("--submission-audit-output", default="outputs/tables/enriched/manual_validation_calibration_submission_files.csv")
    parser.add_argument("--disagreement-output", default="outputs/tables/enriched/manual_validation_calibration_disagreements.csv")
    parser.add_argument("--error-output", default="outputs/tables/enriched/manual_validation_calibration_errors.csv")
    parser.add_argument("--report", default="docs/manual_validation_calibration.md")
    parser.add_argument("--kickoff-output", default="outputs/tables/enriched/manual_validation_calibration_kickoff.csv")
    parser.add_argument("--kickoff-report", default="docs/manual_validation_calibration_kickoff.md")
    parser.add_argument("--codebook", default="docs/manual_validation_codebook.md")
    parser.add_argument("--rules", default="config/classification_rules.yml")
    parser.add_argument("--guide-output", default="outputs/tables/enriched/manual_validation_calibration_guide.csv")
    parser.add_argument("--guide-summary-output", default="outputs/tables/enriched/manual_validation_calibration_guide_summary.csv")
    parser.add_argument("--guide-report", default="docs/manual_validation_calibration_guide.md")
    parser.add_argument("--remaining-output", default="outputs/tables/enriched/manual_validation_calibration_remaining_packet.csv")
    parser.add_argument("--remaining-summary-output", default="outputs/tables/enriched/manual_validation_calibration_remaining_summary.csv")
    parser.add_argument("--remaining-report", default="docs/manual_validation_calibration_remaining.md")
    parser.add_argument("--remaining-form", default="data/intermediate/manual_validation_calibration_forms/manual_validation_calibration_remaining.html")
    parser.add_argument("--remaining-template", default="data/intermediate/manual_validation_calibration/manual_validation_calibration_remaining_submission_template.csv")
    parser.add_argument("--dashboard", default="data/intermediate/manual_validation_calibration_forms/manual_validation_calibration_dashboard.html")
    args = parser.parse_args()

    sample = pd.read_csv(args.sample, dtype=str).fillna("")
    packet_path = Path(args.packet_output)
    should_create_packet = args.regenerate or not packet_path.exists()
    if should_create_packet:
        completed_existing = completed_manual_label_count(packet_path)
        if completed_existing and not args.overwrite_labeled:
            raise SystemExit(
                f"Refusing to overwrite {packet_path}: {completed_existing} completed calibration labels found. "
                "Use --overwrite-labeled only after exporting/backing up existing labels."
            )
        packet = make_calibration_packet(sample, args.sample_size, args.seed)
        packet_path.parent.mkdir(parents=True, exist_ok=True)
        packet.to_csv(packet_path, index=False)
    else:
        packet = pd.read_csv(packet_path, dtype=str).fillna("")

    submissions, submission_audit, file_errors = load_calibration_submissions(Path(args.submissions_dir), packet)
    errors = pd.concat(
        [
            file_errors,
            validate_manual_label_values(submissions),
            calibration_packet_identity_errors(sample, packet, expected_rows=min(args.sample_size, len(sample))),
            calibration_submission_identity_errors(packet, submissions),
        ],
        ignore_index=True,
    ).reindex(columns=VALIDATION_ERROR_COLUMNS)
    summary = calibration_agreement_summary(submissions)
    disagreements = calibration_disagreement_packet(submissions)
    packet_profile = calibration_packet_profile(packet)
    rules = load_rules(Path(args.rules))
    guide, guide_summary = calibration_guide(packet, rules)
    form_packet = packet_with_calibration_guide(packet, guide)
    progress = calibration_row_progress(packet=packet, submissions=submissions, guide=guide, errors=errors)
    remaining_packet = remaining_calibration_packet(packet, guide, progress)
    remaining_summary = remaining_calibration_summary(remaining_packet)
    remaining_template = remaining_calibration_submission_template(remaining_packet)

    Path(args.submissions_dir).mkdir(parents=True, exist_ok=True)
    write_reviewer_html_forms(form_packet, Path(args.html_dir), batch_size=args.sample_size)

    Path(args.summary_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.progress_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.submission_audit_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.disagreement_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.error_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.kickoff_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.guide_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.guide_summary_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.remaining_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.remaining_summary_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.remaining_template).parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.summary_output, index=False)
    progress.to_csv(args.progress_output, index=False)
    submission_audit.to_csv(args.submission_audit_output, index=False)
    disagreements.to_csv(args.disagreement_output, index=False)
    errors.to_csv(args.error_output, index=False)
    guide.to_csv(args.guide_output, index=False)
    guide_summary.to_csv(args.guide_summary_output, index=False)
    remaining_packet.to_csv(args.remaining_output, index=False)
    remaining_summary.to_csv(args.remaining_summary_output, index=False)
    remaining_template.to_csv(args.remaining_template, index=False)
    Path(args.remaining_form).parent.mkdir(parents=True, exist_ok=True)
    Path(args.remaining_form).write_text(reviewer_form_html(remaining_packet, title="Manual Validation Calibration Remaining Rows"), encoding="utf-8")
    write_calibration_guide_report(
        Path(args.guide_report),
        guide,
        guide_summary,
        rules_path=args.rules,
        minimum_chars=int(rules.get("minimum_usable_text_chars", 250)),
    )
    kickoff = calibration_kickoff_checklist(
        summary=summary,
        errors=errors,
        disagreements=disagreements,
        packet_path=packet_path,
        html_dir=Path(args.html_dir),
        submissions_dir=Path(args.submissions_dir),
        codebook_path=Path(args.codebook),
        guide_path=Path(args.guide_report),
        remaining_form_path=Path(args.remaining_form),
        remaining_report_path=Path(args.remaining_report),
        remaining_template_path=Path(args.remaining_template),
    )
    kickoff.to_csv(args.kickoff_output, index=False)
    write_calibration_report(
        Path(args.report),
        summary,
        disagreements,
        errors,
        submission_audit,
        progress,
        packet_path=args.packet_output,
        html_dir=args.html_dir,
        submissions_dir=args.submissions_dir,
    )
    write_calibration_kickoff_report(
        Path(args.kickoff_report),
        kickoff,
        packet_profile,
        packet_path=args.packet_output,
        html_dir=args.html_dir,
        submissions_dir=args.submissions_dir,
        guide_path=args.guide_report,
        remaining_report_path=args.remaining_report,
        remaining_form_path=args.remaining_form,
        remaining_template_path=args.remaining_template,
    )
    write_remaining_calibration_report(
        Path(args.remaining_report),
        remaining_packet,
        remaining_summary,
        output_csv=args.remaining_output,
        output_form=args.remaining_form,
        output_template=args.remaining_template,
    )
    write_calibration_dashboard(
        Path(args.dashboard),
        summary=summary,
        checklist=kickoff,
        packet_profile=packet_profile,
        errors=errors,
        submission_audit=submission_audit,
        disagreements=disagreements,
        guide_summary=guide_summary,
        progress=progress,
        packet_path=args.packet_output,
        html_dir=args.html_dir,
        submissions_dir=args.submissions_dir,
        codebook_path=args.codebook,
        report_path=args.report,
        kickoff_report_path=args.kickoff_report,
        guide_report_path=args.guide_report,
        remaining_report_path=args.remaining_report,
        remaining_form_path=args.remaining_form,
        remaining_template_path=args.remaining_template,
    )

    lookup = dict(zip(summary["metric"].astype(str), summary["value"]))
    print(f"calibration_rows={lookup.get('calibration_rows', 0)}")
    print(f"completed_calibration_rows={lookup.get('completed_calibration_rows', lookup.get('completed_calibration_labels', 0))}")
    print(f"completed_calibration_labels={lookup.get('completed_calibration_labels', 0)}")
    print(f"calibration_reviewers={lookup.get('calibration_reviewers', 0)}")
    print(f"disagreement_rows={lookup.get('disagreement_rows', 0)}")
    print(f"progress={args.progress_output}")
    print(f"submission_audit={args.submission_audit_output}")
    print(f"report={args.report}")
    print(f"kickoff_report={args.kickoff_report}")
    print(f"guide_report={args.guide_report}")
    print(f"remaining_rows={len(remaining_packet)}")
    print(f"remaining_report={args.remaining_report}")
    print(f"remaining_form={args.remaining_form}")
    print(f"remaining_template={args.remaining_template}")
    print(f"dashboard={args.dashboard}")

    if not errors.empty:
        print(f"calibration_errors={len(errors)}")
        print(f"error_output={args.error_output}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
