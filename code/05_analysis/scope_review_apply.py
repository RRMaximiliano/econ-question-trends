from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd

LIB_DIR = Path(__file__).resolve().parents[1] / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.append(str(LIB_DIR))

from econqt_common import clean_text  # noqa: E402
from scope_review_audit import SCOPE_DECISIONS, scope_review_completion_summary  # noqa: E402


ERROR_COLUMNS = ["scope_review_id", "article_id", "field", "value", "error"]
CHANGE_COLUMNS = [
    "scope_review_id",
    "article_id",
    "human_scope_decision",
    "old_article_scope",
    "old_article_scope_reason",
    "new_article_scope",
    "new_article_scope_reason",
    "scope_review_notes",
    "reviewer_id",
    "review_date",
    "change_status",
]
SUMMARY_COLUMNS = ["metric", "value"]
METADATA_COLUMNS = ["scope_review_decision", "scope_review_notes", "scope_reviewer_id", "scope_review_date"]


def decided_rows(packet: pd.DataFrame) -> pd.DataFrame:
    if packet.empty or "human_scope_decision" not in packet.columns:
        return pd.DataFrame(columns=packet.columns)
    decision = packet["human_scope_decision"].astype(str).str.strip()
    return packet[decision.ne("")].copy()


def validate_scope_review_packet(packet: pd.DataFrame, target_ids: set[str]) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    required = ["scope_review_id", "article_id", "human_scope_decision", "proposed_article_scope", "reviewer_id", "review_date"]
    missing_columns = [column for column in required if column not in packet.columns]
    for column in missing_columns:
        rows.append({"scope_review_id": "", "article_id": "", "field": column, "value": "", "error": "missing_required_column"})
    if missing_columns:
        return pd.DataFrame(rows, columns=ERROR_COLUMNS)

    decided = decided_rows(packet).fillna("")
    scope_ids = decided["scope_review_id"].astype(str).str.strip() if "scope_review_id" in decided.columns else pd.Series(dtype=str)
    article_ids = decided["article_id"].astype(str).str.strip() if "article_id" in decided.columns else pd.Series(dtype=str)
    duplicate_scope_ids = {value for value in scope_ids[scope_ids.ne("") & scope_ids.duplicated(keep=False)].tolist()}
    duplicate_article_ids = {value for value in article_ids[article_ids.ne("") & article_ids.duplicated(keep=False)].tolist()}

    for _, row in decided.iterrows():
        scope_review_id = clean_text(row.get("scope_review_id"))
        article_id = clean_text(row.get("article_id"))
        decision = clean_text(row.get("human_scope_decision"))
        proposed_scope = clean_text(row.get("proposed_article_scope"))
        reviewer = clean_text(row.get("reviewer_id"))
        review_date = clean_text(row.get("review_date"))

        def add_error(field: str, value: Any, error: str) -> None:
            rows.append(
                {
                    "scope_review_id": scope_review_id,
                    "article_id": article_id,
                    "field": field,
                    "value": clean_text(value),
                    "error": error,
                }
            )

        if not scope_review_id:
            add_error("scope_review_id", scope_review_id, "missing_scope_review_id")
        elif scope_review_id in duplicate_scope_ids:
            add_error("scope_review_id", scope_review_id, "duplicate_scope_review_id")
        if not article_id:
            add_error("article_id", article_id, "missing_article_id")
        elif article_id not in target_ids:
            add_error("article_id", article_id, "article_id_not_in_target_files")
        elif article_id in duplicate_article_ids:
            add_error("article_id", article_id, "duplicate_scope_article_id")
        if decision not in SCOPE_DECISIONS:
            add_error("human_scope_decision", decision, "invalid_scope_decision")
        if decision == "exclude_nonresearch" and not proposed_scope:
            add_error("proposed_article_scope", proposed_scope, "missing_proposed_scope")
        if not reviewer:
            add_error("reviewer_id", reviewer, "missing_reviewer_id")
        if not review_date:
            add_error("review_date", review_date, "missing_review_date")
        elif not re.match(r"^\d{4}-\d{2}-\d{2}$", review_date):
            add_error("review_date", review_date, "invalid_review_date")

    return pd.DataFrame(rows, columns=ERROR_COLUMNS)


def valid_decision_lookup(packet: pd.DataFrame, errors: pd.DataFrame) -> dict[str, dict[str, str]]:
    if packet.empty:
        return {}
    error_ids = set(errors["article_id"].astype(str)) if not errors.empty and "article_id" in errors.columns else set()
    out: dict[str, dict[str, str]] = {}
    for _, row in decided_rows(packet).fillna("").iterrows():
        article_id = clean_text(row.get("article_id"))
        if not article_id or article_id in error_ids:
            continue
        out[article_id] = {column: clean_text(row.get(column, "")) for column in packet.columns}
    return out


def scope_change_for_row(row: pd.Series, decision_row: dict[str, str]) -> dict[str, str]:
    decision = clean_text(decision_row.get("human_scope_decision"))
    old_scope = clean_text(row.get("article_scope"))
    old_reason = clean_text(row.get("article_scope_reason"))
    proposed_scope = clean_text(decision_row.get("proposed_article_scope"))
    proposed_reason = clean_text(decision_row.get("proposed_scope_reason"))
    if decision == "exclude_nonresearch":
        new_scope = proposed_scope
        new_reason = f"scope_review_decision=exclude_nonresearch;{proposed_reason}".rstrip(";")
        change_status = "scope_updated"
    elif decision == "keep_research":
        new_scope = "research_article"
        new_reason = "scope_review_decision=keep_research"
        change_status = "scope_updated"
    else:
        new_scope = old_scope
        new_reason = old_reason
        change_status = "metadata_only"
    if new_scope == old_scope and new_reason == old_reason:
        change_status = "metadata_only"
    return {
        "old_article_scope": old_scope,
        "old_article_scope_reason": old_reason,
        "new_article_scope": new_scope,
        "new_article_scope_reason": new_reason,
        "change_status": change_status,
    }


def apply_scope_decisions_to_frame(frame: pd.DataFrame, packet: pd.DataFrame, errors: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    out = frame.copy().fillna("")
    if out.empty:
        return out, pd.DataFrame(columns=CHANGE_COLUMNS)
    for column in ["article_scope", "article_scope_reason"] + METADATA_COLUMNS:
        if column not in out.columns:
            out[column] = ""
    decisions = valid_decision_lookup(packet, errors)
    changes: list[dict[str, str]] = []
    if not decisions or "article_id" not in out.columns:
        return out, pd.DataFrame(columns=CHANGE_COLUMNS)

    for idx, row in out.iterrows():
        article_id = clean_text(row.get("article_id"))
        decision = decisions.get(article_id)
        if not decision:
            continue
        change = scope_change_for_row(row, decision)
        out.at[idx, "article_scope"] = change["new_article_scope"]
        out.at[idx, "article_scope_reason"] = change["new_article_scope_reason"]
        out.at[idx, "scope_review_decision"] = clean_text(decision.get("human_scope_decision"))
        out.at[idx, "scope_review_notes"] = clean_text(decision.get("scope_review_notes"))
        out.at[idx, "scope_reviewer_id"] = clean_text(decision.get("reviewer_id"))
        out.at[idx, "scope_review_date"] = clean_text(decision.get("review_date"))
        changes.append(
            {
                "scope_review_id": clean_text(decision.get("scope_review_id")),
                "article_id": article_id,
                "human_scope_decision": clean_text(decision.get("human_scope_decision")),
                **change,
                "scope_review_notes": clean_text(decision.get("scope_review_notes")),
                "reviewer_id": clean_text(decision.get("reviewer_id")),
                "review_date": clean_text(decision.get("review_date")),
            }
        )
    return out, pd.DataFrame(changes, columns=CHANGE_COLUMNS)


def scope_apply_summary(packet: pd.DataFrame, errors: pd.DataFrame, changes: pd.DataFrame, *, apply: bool) -> pd.DataFrame:
    completion = scope_review_completion_summary(packet)
    lookup = dict(zip(completion["metric"], completion["value"])) if not completion.empty else {}
    scope_changes = int(changes["change_status"].eq("scope_updated").sum()) if not changes.empty else 0
    metadata_only = int(changes["change_status"].eq("metadata_only").sum()) if not changes.empty else 0
    rows = [
        {"metric": "scope_review_rows", "value": lookup.get("scope_review_rows", "0")},
        {"metric": "completed_scope_review_decisions", "value": lookup.get("completed_scope_review_decisions", "0")},
        {"metric": "remaining_scope_review_decisions", "value": lookup.get("remaining_scope_review_decisions", "0")},
        {"metric": "error_rows", "value": str(len(errors))},
        {"metric": "valid_decisions", "value": str(len(changes))},
        {"metric": "scope_changes", "value": str(scope_changes)},
        {"metric": "metadata_only_changes", "value": str(metadata_only)},
        {"metric": "applied", "value": "yes" if apply else "no"},
    ]
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


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


def write_scope_apply_report(path: Path, summary: pd.DataFrame, errors: pd.DataFrame, changes: pd.DataFrame, *, apply: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "apply" if apply else "dry-run"
    lines = [
        "# Scope Review Decision Import",
        "",
        f"- Mode: `{mode}`",
        "",
        "This command validates completed scope-review packet rows. It does not change causal/predictive labels.",
        "Completed rows must have unique `scope_review_id` and `article_id` values, a valid decision, reviewer ID, and ISO review date before scope metadata can be applied.",
        "",
        "## Summary",
        "",
        df_to_markdown(summary, max_rows=20),
        "",
        "## Validation Errors",
        "",
        df_to_markdown(errors, max_rows=40),
        "",
        "## Proposed/Applied Changes",
        "",
        df_to_markdown(changes, max_rows=40),
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("") if path.exists() else pd.DataFrame()


def run_apply_scope_review_decisions(
    *,
    packet_path: Path,
    articles_input: Path,
    classified_input: Path,
    output_articles: Path,
    output_classified: Path,
    output_summary: Path,
    output_errors: Path,
    output_changes: Path,
    report_path: Path,
    apply: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    packet = read_csv_if_exists(packet_path)
    articles = read_csv_if_exists(articles_input)
    classified = read_csv_if_exists(classified_input)
    target_ids = set()
    for frame in [articles, classified]:
        if not frame.empty and "article_id" in frame.columns:
            target_ids.update(frame["article_id"].astype(str))
    errors = validate_scope_review_packet(packet, target_ids)
    updated_articles, article_changes = apply_scope_decisions_to_frame(articles, packet, errors)
    updated_classified, classified_changes = apply_scope_decisions_to_frame(classified, packet, errors)
    changes = article_changes if not article_changes.empty else classified_changes
    if article_changes.empty and not classified_changes.empty:
        changes = classified_changes
    elif not article_changes.empty:
        changes = article_changes
    else:
        changes = pd.DataFrame(columns=CHANGE_COLUMNS)
    apply_effective = apply and errors.empty
    summary = scope_apply_summary(packet, errors, changes, apply=apply_effective)

    for path, frame in [(output_summary, summary), (output_errors, errors), (output_changes, changes)]:
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)
    write_scope_apply_report(report_path, summary, errors, changes, apply=apply_effective)

    if apply:
        if not errors.empty:
            raise SystemExit(f"Refusing to apply scope decisions: {len(errors)} validation errors. See {output_errors}.")
        output_articles.parent.mkdir(parents=True, exist_ok=True)
        output_classified.parent.mkdir(parents=True, exist_ok=True)
        updated_articles.to_csv(output_articles, index=False)
        updated_classified.to_csv(output_classified, index=False)

    print(f"scope_review_rows={dict(zip(summary['metric'], summary['value'])).get('scope_review_rows', '0')}")
    print(f"completed_scope_review_decisions={dict(zip(summary['metric'], summary['value'])).get('completed_scope_review_decisions', '0')}")
    print(f"error_rows={len(errors)}")
    print(f"scope_changes={dict(zip(summary['metric'], summary['value'])).get('scope_changes', '0')}")
    print(f"applied={'yes' if apply else 'no'}")
    print(f"summary={output_summary}")
    print(f"errors={output_errors}")
    print(f"changes={output_changes}")
    print(f"report={report_path}")
    return summary, errors, changes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", default="data/intermediate/scope_review/scope_review_packet.csv")
    parser.add_argument("--articles-input", default="data/final/articles_enriched_pilot.csv")
    parser.add_argument("--classified-input", default="data/final/articles_classified_enriched_pilot.csv")
    parser.add_argument("--output-articles", default="data/final/articles_enriched_pilot.csv")
    parser.add_argument("--output-classified", default="data/final/articles_classified_enriched_pilot.csv")
    parser.add_argument("--output-summary", default="outputs/tables/enriched/scope_review_apply_summary.csv")
    parser.add_argument("--output-errors", default="outputs/tables/enriched/scope_review_apply_errors.csv")
    parser.add_argument("--output-changes", default="outputs/tables/enriched/scope_review_apply_changes.csv")
    parser.add_argument("--report", default="docs/scope_review_apply.md")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    run_apply_scope_review_decisions(
        packet_path=Path(args.packet),
        articles_input=Path(args.articles_input),
        classified_input=Path(args.classified_input),
        output_articles=Path(args.output_articles),
        output_classified=Path(args.output_classified),
        output_summary=Path(args.output_summary),
        output_errors=Path(args.output_errors),
        output_changes=Path(args.output_changes),
        report_path=Path(args.report),
        apply=args.apply,
    )


if __name__ == "__main__":
    main()
