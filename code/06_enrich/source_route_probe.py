from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "lib"))
sys.path.append(str(Path(__file__).resolve().parent))

from econqt_common import clean_text, request_headers  # noqa: E402
from text_enrichment import extract_econpapers_abstract, extract_publisher_metadata_abstract, extract_publisher_metadata_pdf_url  # noqa: E402


PROBE_COLUMNS = [
    "probe_rank",
    "decision_unit",
    "doi_prefix",
    "investigation_type",
    "article_id",
    "journal_short",
    "publication_year",
    "title",
    "doi",
    "probe_source",
    "probe_url",
    "final_url",
    "status_code",
    "content_type",
    "result_status",
    "abstract_chars",
    "pdf_url",
    "parser_used",
    "access_challenge_signal",
    "not_found_signal",
    "note",
]

HTML_URL_COLUMNS = ["article_url", "doi_url", "attempt_url"]
SKIP_URL_MARKERS = ["/api.", "api.openalex.org", "api.crossref.org", "semanticscholar.org/graph/"]


def looks_like_html_probe_url(url: Any) -> bool:
    cleaned = clean_text(url)
    if not cleaned.startswith(("http://", "https://")):
        return False
    lower = cleaned.lower()
    if lower.endswith(".pdf"):
        return False
    return not any(marker in lower for marker in SKIP_URL_MARKERS)


def probe_source_for_url(url: str) -> str:
    lower = clean_text(url).lower()
    if "ideas.repec.org" in lower or "econpapers" in lower:
        return "repec_landing"
    if "doi.org/" in lower:
        return "doi_landing"
    if "aeaweb.org" in lower:
        return "aea_landing"
    if "journals.uchicago.edu" in lower:
        return "uchicago_landing"
    if "onlinelibrary.wiley.com" in lower:
        return "wiley_landing"
    if "jstor.org" in lower:
        return "jstor_landing"
    if "academic.oup.com" in lower:
        return "oup_landing"
    if "econometricsociety.org" in lower:
        return "econometric_society_landing"
    return "html_landing"


def source_route_probe_candidates(packet: pd.DataFrame, *, max_urls_per_decision: int = 6) -> pd.DataFrame:
    if packet.empty:
        return pd.DataFrame(columns=PROBE_COLUMNS)
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    work = packet.copy().fillna("")
    work["_rank"] = pd.to_numeric(work.get("investigation_rank", ""), errors="coerce").fillna(999999).astype(int)
    work = work.sort_values(["_rank", "decision_unit", "article_id"])
    for decision_unit, group in work.groupby("decision_unit", dropna=False):
        added = 0
        for _, row in group.iterrows():
            for column in HTML_URL_COLUMNS:
                url = clean_text(row.get(column, ""))
                if not looks_like_html_probe_url(url):
                    continue
                key = (clean_text(decision_unit), url)
                if key in seen:
                    continue
                seen.add(key)
                added += 1
                rows.append(
                    {
                        "probe_rank": len(rows) + 1,
                        "decision_unit": clean_text(row.get("decision_unit", "")),
                        "doi_prefix": clean_text(row.get("doi_prefix", "")),
                        "investigation_type": clean_text(row.get("investigation_type", "")),
                        "article_id": clean_text(row.get("article_id", "")),
                        "journal_short": clean_text(row.get("journal_short", "")),
                        "publication_year": clean_text(row.get("publication_year", "")),
                        "title": clean_text(row.get("title", "")),
                        "doi": clean_text(row.get("doi", "")),
                        "probe_source": probe_source_for_url(url),
                        "probe_url": url,
                    }
                )
                if added >= max_urls_per_decision:
                    break
            if added >= max_urls_per_decision:
                break
    return pd.DataFrame(rows, columns=[column for column in PROBE_COLUMNS if column in rows[0]] if rows else PROBE_COLUMNS)


def has_access_challenge(text: str) -> bool:
    lower = clean_text(text).lower()
    patterns = [
        "access denied",
        "access challenge",
        "captcha",
        "enable javascript",
        "institutional access",
        "you do not have access",
        "your access has been blocked",
        "checking your browser",
        "cloudflare",
        "request unsuccessful",
    ]
    return any(pattern in lower for pattern in patterns)


def has_not_found_signal(text: str, status_code: int | str = "") -> bool:
    lower = clean_text(text).lower()
    status = clean_text(status_code)
    patterns = [
        "404 not found",
        "page not found",
        "not found",
        "the page you were looking for",
        "sorry, the page",
        "does not exist",
    ]
    return status == "404" or any(pattern in lower for pattern in patterns)


def classify_probe_payload(
    *,
    url: str,
    final_url: str,
    status_code: int | str,
    content_type: str,
    text: str,
    title: Any = "",
) -> dict[str, Any]:
    source = probe_source_for_url(final_url or url)
    abstract = ""
    parser_used = ""
    if source == "repec_landing":
        abstract = extract_econpapers_abstract(text)
        parser_used = "extract_econpapers_abstract"
    else:
        abstract = extract_publisher_metadata_abstract(text, title=title)
        parser_used = "extract_publisher_metadata_abstract"

    pdf_url = extract_publisher_metadata_pdf_url(text, base_url=final_url or url)
    access_challenge = has_access_challenge(text)
    not_found = has_not_found_signal(text, status_code)
    status_text = clean_text(status_code)
    if abstract:
        result_status = "abstract_found"
    elif pdf_url:
        result_status = "pdf_candidate"
    elif not_found:
        result_status = "not_found"
    elif access_challenge:
        result_status = "access_challenge"
    elif status_text and status_text not in {"200", "201", "202"}:
        result_status = "http_error"
    else:
        result_status = "no_metadata_found"

    return {
        "final_url": clean_text(final_url or url),
        "status_code": status_text,
        "content_type": clean_text(content_type),
        "result_status": result_status,
        "abstract_chars": len(clean_text(abstract)),
        "pdf_url": pdf_url,
        "parser_used": parser_used,
        "access_challenge_signal": access_challenge,
        "not_found_signal": not_found,
        "note": "bounded_landing_page_probe",
    }


def fetch_probe_url(url: str, *, timeout: int) -> dict[str, Any]:
    import requests

    headers = request_headers("source_route_probe")
    headers["Accept"] = "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8"
    response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    return {
        "final_url": response.url,
        "status_code": response.status_code,
        "content_type": response.headers.get("content-type", ""),
        "text": response.text if response.text else "",
    }


def run_source_route_probe(
    *,
    packet_path: Path,
    output_path: Path,
    report_path: Path,
    max_urls_per_decision: int,
    max_total_urls: int,
    timeout: int,
    sleep_seconds: float,
) -> pd.DataFrame:
    packet = pd.read_csv(packet_path, dtype=str).fillna("") if packet_path.exists() else pd.DataFrame()
    candidates = source_route_probe_candidates(packet, max_urls_per_decision=max_urls_per_decision)
    if max_total_urls > 0:
        candidates = candidates.head(max_total_urls).copy()
    rows: list[dict[str, Any]] = []
    for _, candidate in candidates.iterrows():
        base = {column: clean_text(candidate.get(column, "")) for column in PROBE_COLUMNS if column in candidate.index}
        try:
            payload = fetch_probe_url(clean_text(candidate.get("probe_url", "")), timeout=timeout)
            result = classify_probe_payload(
                url=clean_text(candidate.get("probe_url", "")),
                final_url=payload.get("final_url", ""),
                status_code=payload.get("status_code", ""),
                content_type=payload.get("content_type", ""),
                text=payload.get("text", ""),
                title=candidate.get("title", ""),
            )
        except Exception as exc:  # noqa: BLE001
            result = {
                "final_url": "",
                "status_code": "",
                "content_type": "",
                "result_status": "probe_error",
                "abstract_chars": 0,
                "pdf_url": "",
                "parser_used": "",
                "access_challenge_signal": False,
                "not_found_signal": False,
                "note": f"{type(exc).__name__}: {exc}",
            }
        rows.append({**base, **result})
        if sleep_seconds:
            time.sleep(sleep_seconds)

    output = pd.DataFrame(rows, columns=PROBE_COLUMNS)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(output_path, index=False)
    write_probe_report(report_path, output, packet_path)
    print(f"probe_rows={len(output)}")
    print(f"output={output_path}")
    print(f"report={report_path}")
    return output


def markdown_cell(value: Any) -> str:
    return str(value).replace("\r", " ").replace("\n", " ").replace("|", "\\|")


def df_to_markdown(df: pd.DataFrame, max_rows: int = 30) -> str:
    if df.empty:
        return "_No rows._"
    shown = df.head(max_rows).fillna("")
    headers = [markdown_cell(column) for column in shown.columns]
    rows = [headers] + [[markdown_cell(value) for value in row] for row in shown.astype(str).values.tolist()]
    widths = [max(len(row[i]) for row in rows) for i in range(len(headers))]
    header = "| " + " | ".join(headers[i].ljust(widths[i]) for i in range(len(headers))) + " |"
    separator = "| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |"
    body = ["| " + " | ".join(row[i].ljust(widths[i]) for i in range(len(headers))) + " |" for row in rows[1:]]
    suffix = f"\n\n_Only first {max_rows} rows shown._" if len(df) > max_rows else ""
    return "\n".join([header, separator] + body) + suffix


def write_probe_report(path: Path, output: pd.DataFrame, packet_path: Path) -> None:
    if output.empty:
        summary = pd.DataFrame(columns=["result_status", "probe_rows"])
        by_unit = pd.DataFrame(columns=["decision_unit", "result_status", "probe_rows"])
    else:
        summary = output.groupby("result_status", dropna=False).size().reset_index(name="probe_rows").sort_values(["probe_rows", "result_status"], ascending=[False, True])
        by_unit = output.groupby(["decision_unit", "result_status"], dropna=False).size().reset_index(name="probe_rows").sort_values(["decision_unit", "probe_rows"], ascending=[True, False])
    lines = [
        "# Source Route Probe",
        "",
        f"- Investigation packet: `{packet_path}`",
        f"- Probe rows: {len(output)}",
        "",
        "This bounded probe checks representative public landing/metadata pages only. It does not download restricted full text and does not update article classifications.",
        "",
        "## Status Summary",
        "",
        df_to_markdown(summary, max_rows=30),
        "",
        "## Status By Decision Unit",
        "",
        df_to_markdown(by_unit, max_rows=40),
        "",
        "## Probe Detail",
        "",
        df_to_markdown(output, max_rows=40),
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", default="outputs/tables/enriched/insufficient_text_source_investigation_packet.csv")
    parser.add_argument("--output", default="outputs/tables/enriched/source_route_probe_results.csv")
    parser.add_argument("--report", default="docs/source_route_probe.md")
    parser.add_argument("--max-urls-per-decision", type=int, default=4)
    parser.add_argument("--max-total-urls", type=int, default=24)
    parser.add_argument("--timeout", type=int, default=12)
    parser.add_argument("--sleep-seconds", type=float, default=0.2)
    args = parser.parse_args()
    run_source_route_probe(
        packet_path=Path(args.packet),
        output_path=Path(args.output),
        report_path=Path(args.report),
        max_urls_per_decision=args.max_urls_per_decision,
        max_total_urls=args.max_total_urls,
        timeout=args.timeout,
        sleep_seconds=args.sleep_seconds,
    )


if __name__ == "__main__":
    main()
