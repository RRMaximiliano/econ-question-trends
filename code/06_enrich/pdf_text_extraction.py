from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd
import requests

sys.path.append(str(Path(__file__).resolve().parents[1] / "lib"))
sys.path.append(str(Path(__file__).resolve().parent))

from econqt_common import clean_text, contact_email, load_yaml  # noqa: E402
from text_enrichment import apply_enrichment_to_articles, text_chars, write_summary  # noqa: E402


def safe_pdf_filename(article_id: str, url: str) -> str:
    digest = hashlib.sha1(f"{article_id}|{url}".encode("utf-8")).hexdigest()[:16]
    return f"{clean_text(article_id) or 'unknown'}_{digest}.pdf"


def pdf_result_key(article_id: Any, url: Any) -> str:
    return hashlib.sha1(f"{clean_text(article_id)}|{clean_text(url)}".encode("utf-8")).hexdigest()


def pdf_headers() -> dict[str, str]:
    email = contact_email()
    suffix = f" (mailto:{email})" if email else ""
    return {"User-Agent": f"econ-question-trends-pilot/0.1{suffix}", "Accept": "application/pdf,*/*"}


def download_pdf(url: str, path: Path, timeout: int) -> tuple[bool, str]:
    try:
        response = requests.get(url, headers=pdf_headers(), timeout=timeout, allow_redirects=True)
        if not response.ok:
            return False, f"http_status={response.status_code}"
        content = response.content
        content_type = response.headers.get("content-type", "")
        if not content.startswith(b"%PDF") and "pdf" not in content_type.lower():
            return False, f"not_pdf;content_type={content_type}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return True, response.url
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


def extract_pdf_text(pdf_path: Path, pages: int, pdftotext_path: str = "pdftotext") -> tuple[bool, str]:
    command = [pdftotext_path, "-f", "1", "-l", str(pages), "-layout", str(pdf_path), "-"]
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        return False, clean_text(result.stderr)
    return True, clean_text(result.stdout)


def ocr_pdf_text(
    pdf_path: Path,
    pages: int,
    *,
    dpi: int = 200,
    pdftoppm_path: str = "pdftoppm",
    tesseract_path: str = "tesseract",
) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        image_prefix = Path(tmp) / "page"
        render_command = [
            pdftoppm_path,
            "-f",
            "1",
            "-l",
            str(pages),
            "-r",
            str(dpi),
            "-png",
            str(pdf_path),
            str(image_prefix),
        ]
        render_result = subprocess.run(render_command, text=True, capture_output=True, check=False)
        if render_result.returncode != 0:
            return False, f"pdftoppm_error={clean_text(render_result.stderr)}"

        image_paths = sorted(Path(tmp).glob("page-*.png")) or sorted(Path(tmp).glob("page*.png"))
        if not image_paths:
            return False, "pdftoppm_no_images"

        texts: list[str] = []
        errors: list[str] = []
        for image_path in image_paths:
            ocr_command = [tesseract_path, str(image_path), "stdout", "-l", "eng", "--psm", "1"]
            ocr_result = subprocess.run(ocr_command, text=True, capture_output=True, check=False)
            if ocr_result.returncode != 0:
                errors.append(clean_text(ocr_result.stderr))
                continue
            texts.append(ocr_result.stdout)

        text = clean_text("\n".join(texts))
        if text:
            return True, text
        return False, "tesseract_empty_output" if not errors else f"tesseract_error={'; '.join(errors[:3])}"


def abstract_or_first_pages(text: str, max_chars: int = 4000) -> str:
    cleaned = clean_text(text)
    if not cleaned:
        return ""
    abstract_match = re.search(
        r"(?is)\babstract\b[:\s]*(.*?)(?=\b(?:1\.?\s+)?introduction\b|\bkeywords?\b|\bjel\b|\backnowledg|\breferences\b)",
        text,
    )
    if abstract_match:
        abstract_text = clean_text(abstract_match.group(1))
        if len(abstract_text) >= 150:
            return abstract_text[:max_chars]
    return cleaned[:max_chars]


def extract_pdf_candidates(
    pdf_candidates: pd.DataFrame,
    *,
    pdf_dir: Path,
    pages: int,
    timeout: int,
    limit: int | None,
    existing_results: pd.DataFrame | None = None,
    retry_existing: bool = False,
    ocr_fallback: bool = False,
    ocr_pages: int | None = None,
    ocr_dpi: int = 200,
    pdftotext_path: str = "pdftotext",
    pdftoppm_path: str = "pdftoppm",
    tesseract_path: str = "tesseract",
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    existing_lookup: dict[str, pd.Series] = {}
    if existing_results is not None and not existing_results.empty:
        existing = existing_results.copy().fillna("")
        for _, existing_row in existing.iterrows():
            existing_lookup[pdf_result_key(existing_row.get("article_id"), existing_row.get("oa_pdf_url"))] = existing_row
    iterator = pdf_candidates.head(limit).to_dict(orient="records") if limit else pdf_candidates.to_dict(orient="records")
    for row in iterator:
        article_id = clean_text(row.get("article_id"))
        url = clean_text(row.get("oa_pdf_url"))
        title = clean_text(row.get("title"))
        pdf_path = pdf_dir / safe_pdf_filename(article_id, url)
        base = {
            "article_id": article_id,
            "journal_short": clean_text(row.get("journal_short")),
            "publication_year": clean_text(row.get("publication_year")),
            "title": title,
            "oa_pdf_url": url,
            "pdf_path": str(pdf_path),
        }
        key = pdf_result_key(article_id, url)
        if not retry_existing and key in existing_lookup:
            existing_row = existing_lookup[key]
            rows.append(
                {
                    **base,
                    "pdf_text_status": clean_text(existing_row.get("pdf_text_status")),
                    "pdf_text": clean_text(existing_row.get("pdf_text")),
                    "pdf_text_chars": clean_text(existing_row.get("pdf_text_chars")),
                    "pdf_detail": clean_text(existing_row.get("pdf_detail")),
                }
            )
            continue
        if not url:
            rows.append({**base, "pdf_text_status": "skipped_missing_url", "pdf_text": "", "pdf_text_chars": 0, "pdf_detail": ""})
            continue
        if pdf_path.exists():
            downloaded = True
            detail = "cached_pdf"
        else:
            downloaded, detail = download_pdf(url, pdf_path, timeout)
        if not downloaded:
            rows.append({**base, "pdf_text_status": "download_error", "pdf_text": "", "pdf_text_chars": 0, "pdf_detail": detail})
            continue
        ok, raw_text_or_error = extract_pdf_text(pdf_path, pages, pdftotext_path=pdftotext_path)
        if not ok:
            if not ocr_fallback:
                rows.append({**base, "pdf_text_status": "extract_error", "pdf_text": "", "pdf_text_chars": 0, "pdf_detail": raw_text_or_error})
                continue
            ocr_ok, ocr_text_or_error = ocr_pdf_text(
                pdf_path,
                ocr_pages or pages,
                dpi=ocr_dpi,
                pdftoppm_path=pdftoppm_path,
                tesseract_path=tesseract_path,
            )
            if not ocr_ok:
                rows.append(
                    {
                        **base,
                        "pdf_text_status": "extract_error",
                        "pdf_text": "",
                        "pdf_text_chars": 0,
                        "pdf_detail": f"{raw_text_or_error};ocr_error={ocr_text_or_error}",
                    }
                )
                continue
            selected_text = abstract_or_first_pages(ocr_text_or_error)
            detail = f"{detail};pdftotext_error={raw_text_or_error};ocr_fallback"
        else:
            selected_text = abstract_or_first_pages(raw_text_or_error)
            detail = clean_text(detail)
            if ocr_fallback and text_chars(title, selected_text) < 250:
                ocr_ok, ocr_text_or_error = ocr_pdf_text(
                    pdf_path,
                    ocr_pages or pages,
                    dpi=ocr_dpi,
                    pdftoppm_path=pdftoppm_path,
                    tesseract_path=tesseract_path,
                )
                if ocr_ok:
                    ocr_selected = abstract_or_first_pages(ocr_text_or_error)
                    if text_chars(title, ocr_selected) > text_chars(title, selected_text):
                        selected_text = ocr_selected
                        detail = f"{detail};ocr_fallback" if detail else "ocr_fallback"
                else:
                    detail = f"{detail};ocr_error={ocr_text_or_error}" if detail else f"ocr_error={ocr_text_or_error}"
        if text_chars(title, selected_text) < 250:
            rows.append(
                {
                    **base,
                    "pdf_text_status": "too_short",
                    "pdf_text": selected_text,
                    "pdf_text_chars": text_chars(title, selected_text),
                    "pdf_detail": detail,
                }
            )
            continue
        rows.append(
            {
                **base,
                "pdf_text_status": "extracted",
                "pdf_text": selected_text,
                "pdf_text_chars": text_chars(title, selected_text),
                "pdf_detail": detail,
            }
        )
    return pd.DataFrame(rows)


def merge_pdf_text_into_enrichment(enrichment: pd.DataFrame, pdf_text: pd.DataFrame) -> pd.DataFrame:
    if enrichment.empty or pdf_text.empty:
        return enrichment.copy()
    out = enrichment.copy().fillna("")
    text_lookup = pdf_text[pdf_text["pdf_text_status"].eq("extracted")].set_index("article_id", drop=False)
    for idx, row in out.iterrows():
        article_id = clean_text(row.get("article_id"))
        if article_id not in text_lookup.index:
            continue
        if clean_text(row.get("enrichment_status")) == "enriched":
            continue
        text_row = text_lookup.loc[article_id]
        if isinstance(text_row, pd.DataFrame):
            text_row = text_row.iloc[0]
        out.at[idx, "enrichment_status"] = "enriched"
        out.at[idx, "enrichment_source"] = "oa_pdf_first_pages"
        out.at[idx, "enriched_abstract"] = clean_text(text_row.get("pdf_text"))
        out.at[idx, "enriched_text_chars"] = clean_text(text_row.get("pdf_text_chars"))
        out.at[idx, "enrichment_url"] = clean_text(text_row.get("oa_pdf_url"))
        out.at[idx, "oa_pdf_url"] = clean_text(text_row.get("oa_pdf_url"))
        out.at[idx, "enrichment_detail"] = "pdf_text_first_pages"
        sources = [source for source in str(row.get("attempted_sources", "")).split("|") if source]
        if "oa_pdf_first_pages" not in sources:
            sources.append("oa_pdf_first_pages")
        out.at[idx, "attempted_sources"] = "|".join(sources)
    return out


def write_report(path: Path, pdf_text: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    status = pdf_text["pdf_text_status"].value_counts(dropna=False).rename_axis("status").reset_index(name="rows") if not pdf_text.empty else pd.DataFrame()
    lines = ["# PDF Text Extraction Report", "", f"- Rows: {len(pdf_text)}", "", "## Status", ""]
    if status.empty:
        lines.append("_No rows._")
    else:
        headers = list(status.columns)
        rows = [headers] + status.astype(str).values.tolist()
        widths = [max(len(row[i]) for row in rows) for i in range(len(headers))]
        lines.append("| " + " | ".join(headers[i].ljust(widths[i]) for i in range(len(headers))) + " |")
        lines.append("| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |")
        lines.extend("| " + " | ".join(row[i].ljust(widths[i]) for i in range(len(headers))) + " |" for row in rows[1:])
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def run_pdf_text_enrichment(
    *,
    pdf_candidates_path: Path,
    enrichment_candidates_path: Path,
    attempts_path: Path,
    articles_input: Path,
    config_path: Path,
    output_pdf_text: Path,
    output_candidates: Path,
    output_articles: Path,
    report_path: Path,
    enrichment_report_path: Path,
    pdf_dir: Path,
    pages: int,
    timeout: int,
    limit: int | None,
    report_only: bool,
    retry_existing: bool,
    ocr_fallback: bool,
    ocr_pages: int | None,
    ocr_dpi: int,
    pdftotext_path: str,
    pdftoppm_path: str,
    tesseract_path: str,
) -> None:
    config = load_yaml(config_path)
    minimum_chars = int(config.get("minimum_usable_text_chars", 250))
    pdf_candidates = pd.read_csv(pdf_candidates_path, dtype=str).fillna("")
    enrichment = pd.read_csv(enrichment_candidates_path, dtype=str).fillna("")
    attempts = pd.read_csv(attempts_path, dtype=str).fillna("") if attempts_path.exists() else pd.DataFrame()
    if report_only:
        pdf_text = pd.read_csv(output_pdf_text, dtype=str).fillna("") if output_pdf_text.exists() else pd.DataFrame()
        merged = enrichment
    else:
        articles = pd.read_csv(articles_input, dtype=str).fillna("")
        existing_pdf_text = pd.read_csv(output_pdf_text, dtype=str).fillna("") if output_pdf_text.exists() else pd.DataFrame()
        pdf_text = extract_pdf_candidates(
            pdf_candidates,
            pdf_dir=pdf_dir,
            pages=pages,
            timeout=timeout,
            limit=limit,
            existing_results=existing_pdf_text,
            retry_existing=retry_existing,
            ocr_fallback=ocr_fallback,
            ocr_pages=ocr_pages,
            ocr_dpi=ocr_dpi,
            pdftotext_path=pdftotext_path,
            pdftoppm_path=pdftoppm_path,
            tesseract_path=tesseract_path,
        )
        merged = merge_pdf_text_into_enrichment(enrichment, pdf_text)
        enriched_articles = apply_enrichment_to_articles(
            articles,
            merged,
            minimum_chars=minimum_chars,
            scope_patterns=config.get("article_scope_patterns", {}) or {},
        )
        for path, frame in [(output_pdf_text, pdf_text), (output_candidates, merged), (output_articles, enriched_articles)]:
            path.parent.mkdir(parents=True, exist_ok=True)
            frame.to_csv(path, index=False)
    write_report(report_path, pdf_text)
    pdf_candidates_updated = merged[merged["oa_pdf_url"].astype(str).str.strip() != ""].copy() if not merged.empty else pd.DataFrame()
    write_summary(enrichment_report_path, merged, attempts, pdf_candidates_updated)
    print(f"pdf_rows={len(pdf_text)}")
    if not pdf_text.empty:
        print(pdf_text["pdf_text_status"].value_counts(dropna=False).to_string())
    print(f"updated_candidates={output_candidates}")
    print(f"updated_articles={output_articles}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf-candidates", default="data/intermediate/text_enrichment_pdf_candidates.csv")
    parser.add_argument("--enrichment-candidates", default="data/intermediate/text_enrichment_candidates.csv")
    parser.add_argument("--attempts", default="data/intermediate/text_enrichment_attempts.csv")
    parser.add_argument("--articles-input", default="data/final/articles_pilot.csv")
    parser.add_argument("--config", default="config/text_enrichment.yml")
    parser.add_argument("--output-pdf-text", default="data/intermediate/text_enrichment_pdf_text.csv")
    parser.add_argument("--output-candidates", default="data/intermediate/text_enrichment_candidates.csv")
    parser.add_argument("--output-articles", default="data/final/articles_enriched_pilot.csv")
    parser.add_argument("--report", default="docs/pdf_text_extraction_report.md")
    parser.add_argument("--enrichment-report", default="docs/text_enrichment_report.md")
    parser.add_argument("--pdf-dir", default="data/intermediate/pdf_cache")
    parser.add_argument("--pages", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--retry-existing", action="store_true")
    parser.add_argument("--ocr-fallback", action="store_true")
    parser.add_argument("--ocr-pages", type=int, default=None)
    parser.add_argument("--ocr-dpi", type=int, default=200)
    parser.add_argument("--pdftotext-path", default="pdftotext")
    parser.add_argument("--pdftoppm-path", default="pdftoppm")
    parser.add_argument("--tesseract-path", default="tesseract")
    args = parser.parse_args()
    run_pdf_text_enrichment(
        pdf_candidates_path=Path(args.pdf_candidates),
        enrichment_candidates_path=Path(args.enrichment_candidates),
        attempts_path=Path(args.attempts),
        articles_input=Path(args.articles_input),
        config_path=Path(args.config),
        output_pdf_text=Path(args.output_pdf_text),
        output_candidates=Path(args.output_candidates),
        output_articles=Path(args.output_articles),
        report_path=Path(args.report),
        enrichment_report_path=Path(args.enrichment_report),
        pdf_dir=Path(args.pdf_dir),
        pages=args.pages,
        timeout=args.timeout,
        limit=args.limit,
        report_only=args.report_only,
        retry_existing=args.retry_existing,
        ocr_fallback=args.ocr_fallback,
        ocr_pages=args.ocr_pages,
        ocr_dpi=args.ocr_dpi,
        pdftotext_path=args.pdftotext_path,
        pdftoppm_path=args.pdftoppm_path,
        tesseract_path=args.tesseract_path,
    )


if __name__ == "__main__":
    main()
