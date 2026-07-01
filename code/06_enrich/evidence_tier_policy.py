from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd


EVIDENCE_TIER_ROWS: list[dict[str, str]] = [
    {
        "evidence_tier": "tier_a_formal_abstract",
        "short_label": "A formal abstract",
        "importable": "yes",
        "definition": "A source-provided article abstract from a publisher, journal page, index, DOI record, or library metadata record.",
        "allowed_use": "May be imported as classification text when source provenance is present.",
        "minimum_provenance": "source plus source_url or source_record_id",
        "reject_when": "Reject if the text is title-only, citation-only, boilerplate, or not article-specific.",
    },
    {
        "evidence_tier": "tier_b_source_description",
        "short_label": "B source description",
        "importable": "yes",
        "definition": "A source-provided article description, summary, or metadata abstract that is not explicitly labeled as a formal abstract.",
        "allowed_use": "May be imported as classification text when source provenance is present and the text describes the article content.",
        "minimum_provenance": "source plus source_url or source_record_id",
        "reject_when": "Reject if the description only repeats the title, bibliographic citation, rights text, or access instructions.",
    },
    {
        "evidence_tier": "tier_c_first_page_abstract_or_intro",
        "short_label": "C first-page abstract/intro",
        "importable": "yes",
        "definition": "Abstract-like text, introduction opening text, or first-page summary text from a verified public article PDF or first-page source.",
        "allowed_use": "May be imported as classification text only when the source is public, article-specific, and not a previously blocked or suspect route.",
        "minimum_provenance": "source plus source_url or source_record_id",
        "reject_when": "Reject if the PDF route is blocked, paywalled, a challenge page, a table of contents, or not clearly the target article.",
    },
    {
        "evidence_tier": "tier_d_title_only_triage",
        "short_label": "D title-only triage",
        "importable": "no",
        "definition": "A reviewer or automation judgment based only on title text or title-level cues.",
        "allowed_use": "May guide prioritization and scope triage, but must not be imported as classification text.",
        "minimum_provenance": "not importable",
        "reject_when": "Always reject at import/preflight for recovered abstract text.",
    },
    {
        "evidence_tier": "tier_e_blocked",
        "short_label": "E blocked or ambiguous",
        "importable": "no",
        "definition": "Evidence is blocked, ambiguous, inaccessible, source-incomplete, or not usable for article-level classification text.",
        "allowed_use": "May document why a row remains unresolved.",
        "minimum_provenance": "not importable",
        "reject_when": "Always reject at import/preflight for recovered abstract text.",
    },
]

ACCEPTED_EVIDENCE_TIERS = {
    row["evidence_tier"] for row in EVIDENCE_TIER_ROWS if row["importable"] == "yes"
}
REJECTED_EVIDENCE_TIERS = {
    row["evidence_tier"] for row in EVIDENCE_TIER_ROWS if row["importable"] != "yes"
}
KNOWN_EVIDENCE_TIERS = ACCEPTED_EVIDENCE_TIERS | REJECTED_EVIDENCE_TIERS
EVIDENCE_TIER_OPTIONS = [{"value": "", "label": "Select evidence tier"}] + [
    {"value": row["evidence_tier"], "label": row["short_label"]} for row in EVIDENCE_TIER_ROWS
]

EVIDENCE_TIER_ERROR_DETAILS = {
    "missing_evidence_tier": "Filled abstract rows must record an evidence_tier.",
    "unimportable_evidence_tier": "Title-only, blocked, or ambiguous evidence tiers cannot be imported as classification text.",
    "invalid_evidence_tier": "Evidence tier must be one of the documented recovery evidence tiers.",
}


def clean_tier(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def evidence_tier_error_code(value: Any) -> str:
    evidence_tier = clean_tier(value)
    if not evidence_tier:
        return "missing_evidence_tier"
    if evidence_tier in REJECTED_EVIDENCE_TIERS:
        return "unimportable_evidence_tier"
    if evidence_tier not in KNOWN_EVIDENCE_TIERS:
        return "invalid_evidence_tier"
    return ""


def evidence_tier_error_detail(error_code: str) -> str:
    return EVIDENCE_TIER_ERROR_DETAILS.get(error_code, "")


def evidence_tier_policy_frame() -> pd.DataFrame:
    return pd.DataFrame(EVIDENCE_TIER_ROWS)


def df_to_markdown(df: pd.DataFrame) -> str:
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


def write_evidence_tier_policy(*, output_csv: Path, report_path: Path) -> pd.DataFrame:
    policy = evidence_tier_policy_frame()
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    policy.to_csv(output_csv, index=False)
    accepted = ", ".join(sorted(ACCEPTED_EVIDENCE_TIERS))
    rejected = ", ".join(sorted(REJECTED_EVIDENCE_TIERS))
    lines = [
        "# Evidence Tier Policy",
        "",
        "This is the shared policy for insufficient-text recovery imports. Recovery staging, split preflight, action-progress readiness, and abstract-backfill import should all treat the same tiers as importable.",
        "",
        f"- Machine-readable policy: `{output_csv}`",
        f"- Importable tiers: `{accepted}`",
        f"- Non-importable tiers: `{rejected}`",
        "",
        "## Policy Table",
        "",
        df_to_markdown(policy),
    ]
    report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return policy


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="outputs/tables/enriched/evidence_tier_policy.csv")
    parser.add_argument("--report", default="docs/evidence_tier_policy.md")
    args = parser.parse_args()
    policy = write_evidence_tier_policy(output_csv=Path(args.output), report_path=Path(args.report))
    print(f"evidence_tiers={len(policy)}")
    print(f"importable_tiers={len(ACCEPTED_EVIDENCE_TIERS)}")
    print(f"output={args.output}")
    print(f"report={args.report}")


if __name__ == "__main__":
    main()
