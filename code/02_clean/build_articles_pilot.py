from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "lib"))

from econqt_common import (  # noqa: E402
    SOURCE_PRIORITY,
    as_json_string,
    author_name_from_crossref,
    clean_text,
    crossref_date,
    ensure_dirs,
    first_nonempty,
    load_journals,
    make_article_id,
    normalize_doi,
    normalize_title,
    parse_pages,
    project_root_from_arg,
    read_json,
    reconstruct_openalex_abstract,
    source_key,
)


SOURCE_COLUMNS = [
    "source",
    "source_record_id",
    "source_file",
    "source_query_url",
    "journal_short",
    "journal",
    "title",
    "abstract",
    "publication_year",
    "publication_date",
    "doi",
    "volume",
    "issue",
    "first_page",
    "last_page",
    "pages_raw",
    "article_type",
    "article_url",
    "authors_raw",
    "author_names",
    "author_affiliations_raw",
    "num_authors",
    "jel_codes",
    "keywords",
    "field_jel_primary",
    "field_jel_broad",
    "openalex_id",
    "crossref_id",
    "jstor_id",
    "repec_handle",
    "publisher_record_id",
]


FINAL_COLUMNS = [
    "article_id",
    "title",
    "abstract",
    "journal",
    "journal_short",
    "publication_year",
    "publication_date",
    "doi",
    "volume",
    "issue",
    "first_page",
    "last_page",
    "pages_raw",
    "article_type",
    "article_type_source",
    "article_url",
    "primary_source",
    "authors_raw",
    "author_names",
    "author_affiliations_raw",
    "num_authors",
    "jel_codes",
    "keywords",
    "field_jel_primary",
    "field_jel_broad",
    "openalex_id",
    "crossref_id",
    "jstor_id",
    "repec_handle",
    "publisher_record_id",
    "title_source",
    "abstract_source",
    "doi_source",
    "bibliographic_source",
    "authors_source",
    "affiliations_source",
    "jel_source",
    "keywords_source",
    "field_source",
    "source_record_count",
    "duplicate_resolution_rule",
    "metadata_warning",
]


def crossref_rows(project_root: Path, run_id: str, start_year: int, end_year: int) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    raw_dir = project_root / "data" / "raw" / "crossref" / run_id
    for path in sorted(raw_dir.glob("*_page_*.json")):
        if path.name.endswith("_error.json"):
            continue
        wrapper = read_json(path)
        metadata = wrapper.get("metadata", {})
        response = wrapper.get("response", {})
        journal_short = metadata.get("journal_short", "")
        journal = metadata.get("journal", "")
        query_url = metadata.get("query_url", "")

        for item in response.get("message", {}).get("items", []):
            publication_date, publication_year = crossref_date(item)
            if publication_year is not None and not (start_year <= publication_year <= end_year):
                continue

            doi = normalize_doi(item.get("DOI"))
            title = clean_text(first_nonempty(item.get("title", [])))
            abstract = clean_text(item.get("abstract"))
            first_page, last_page = parse_pages(item.get("page"))
            authors = item.get("author", []) or []
            author_names = [author_name_from_crossref(author) for author in authors]
            author_names = [name for name in author_names if name]
            affiliations = []
            for author in authors:
                for affil in author.get("affiliation", []) or []:
                    name = clean_text(affil.get("name"))
                    if name:
                        affiliations.append(
                            {
                                "author": author_name_from_crossref(author),
                                "affiliation": name,
                            }
                        )

            subjects = [clean_text(value) for value in item.get("subject", []) if clean_text(value)]
            article_type = clean_text(item.get("subtype")) or clean_text(item.get("type"))

            rows.append(
                {
                    "source": "crossref",
                    "source_record_id": f"crossref:{doi}" if doi else clean_text(item.get("URL")),
                    "source_file": str(path.relative_to(project_root)),
                    "source_query_url": query_url,
                    "journal_short": journal_short,
                    "journal": journal,
                    "title": title,
                    "abstract": abstract,
                    "publication_year": publication_year or "",
                    "publication_date": publication_date,
                    "doi": doi,
                    "volume": clean_text(item.get("volume")),
                    "issue": clean_text(item.get("issue")),
                    "first_page": first_page,
                    "last_page": last_page,
                    "pages_raw": clean_text(item.get("page")),
                    "article_type": article_type,
                    "article_url": clean_text(item.get("URL")),
                    "authors_raw": as_json_string(authors),
                    "author_names": "|".join(author_names),
                    "author_affiliations_raw": as_json_string(affiliations),
                    "num_authors": len(author_names) if author_names else "",
                    "jel_codes": "",
                    "keywords": "|".join(subjects),
                    "field_jel_primary": "",
                    "field_jel_broad": "",
                    "openalex_id": "",
                    "crossref_id": doi,
                    "jstor_id": "",
                    "repec_handle": "",
                    "publisher_record_id": "",
                }
            )
    return rows


def openalex_rows(project_root: Path, run_id: str, start_year: int, end_year: int) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    raw_dir = project_root / "data" / "raw" / "openalex" / run_id
    for path in sorted(raw_dir.glob("*_page_*.json")):
        if path.name.endswith("_error.json"):
            continue
        wrapper = read_json(path)
        metadata = wrapper.get("metadata", {})
        response = wrapper.get("response", {})
        journal_short = metadata.get("journal_short", "")
        journal = metadata.get("journal", "")
        query_url = metadata.get("query_url", "")

        for item in response.get("results", []):
            publication_year = item.get("publication_year") or ""
            if publication_year and not (start_year <= int(publication_year) <= end_year):
                continue

            doi = normalize_doi(item.get("doi"))
            primary_location = item.get("primary_location") or {}
            biblio = item.get("biblio") or {}
            authorships = item.get("authorships") or []
            author_names = []
            affiliations = []
            for authorship in authorships:
                author = authorship.get("author") or {}
                author_name = clean_text(author.get("display_name"))
                if author_name:
                    author_names.append(author_name)
                for raw_affil in authorship.get("raw_affiliation_strings") or []:
                    raw_affil_clean = clean_text(raw_affil)
                    if raw_affil_clean:
                        affiliations.append({"author": author_name, "affiliation": raw_affil_clean})
                for institution in authorship.get("institutions") or []:
                    institution_name = clean_text(institution.get("display_name"))
                    if institution_name:
                        affiliations.append({"author": author_name, "institution": institution_name})

            keyword_values = []
            for keyword in item.get("keywords") or []:
                name = clean_text(keyword.get("display_name") or keyword.get("keyword"))
                if name:
                    keyword_values.append(name)
            for topic in item.get("topics") or []:
                name = clean_text(topic.get("display_name"))
                if name:
                    keyword_values.append(name)
            keyword_values = sorted(set(keyword_values))

            first_page = clean_text(biblio.get("first_page"))
            last_page = clean_text(biblio.get("last_page"))
            pages_raw = "-".join(part for part in [first_page, last_page] if part)
            article_type = clean_text(item.get("type_crossref")) or clean_text(item.get("type"))

            rows.append(
                {
                    "source": "openalex",
                    "source_record_id": item.get("id", ""),
                    "source_file": str(path.relative_to(project_root)),
                    "source_query_url": query_url,
                    "journal_short": journal_short,
                    "journal": journal,
                    "title": clean_text(item.get("title") or item.get("display_name")),
                    "abstract": reconstruct_openalex_abstract(item.get("abstract_inverted_index")),
                    "publication_year": publication_year,
                    "publication_date": clean_text(item.get("publication_date")),
                    "doi": doi,
                    "volume": clean_text(biblio.get("volume")),
                    "issue": clean_text(biblio.get("issue")),
                    "first_page": first_page,
                    "last_page": last_page,
                    "pages_raw": pages_raw,
                    "article_type": article_type,
                    "article_url": clean_text(primary_location.get("landing_page_url") or item.get("doi")),
                    "authors_raw": as_json_string(authorships),
                    "author_names": "|".join(author_names),
                    "author_affiliations_raw": as_json_string(affiliations),
                    "num_authors": len(author_names) if author_names else "",
                    "jel_codes": "",
                    "keywords": "|".join(keyword_values),
                    "field_jel_primary": "",
                    "field_jel_broad": "",
                    "openalex_id": item.get("id", ""),
                    "crossref_id": doi,
                    "jstor_id": "",
                    "repec_handle": "",
                    "publisher_record_id": "",
                }
            )
    return rows


def nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, float) and pd.isna(value):
        return False
    return str(value).strip() != ""


def choose_value(records: List[Dict[str, Any]], field: str, priority: List[str]) -> Tuple[str, str]:
    for source in priority:
        for record in records:
            if record.get("source") != source:
                continue
            value = record.get(field, "")
            if nonempty(value):
                return str(value), source
    for record in records:
        value = record.get(field, "")
        if nonempty(value):
            return str(value), str(record.get("source", ""))
    return "", ""


def conflict_warning(records: List[Dict[str, Any]], field: str, normalized: bool = False) -> Optional[str]:
    values = []
    for record in records:
        value = record.get(field, "")
        if not nonempty(value):
            continue
        value_text = normalize_title(value) if normalized else str(value).strip().lower()
        if field == "article_type" and value_text in ["article", "journal-article"]:
            value_text = "article"
        values.append(value_text)
    if len(set(values)) > 1:
        return f"conflicting_{field}"
    return None


def build_articles(source_records: List[Dict[str, Any]], project_root: Path) -> pd.DataFrame:
    journal_lookup = {journal["journal_short"]: journal["journal"] for journal in load_journals(project_root)}
    grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for record in source_records:
        key = source_key(
            str(record.get("doi", "")),
            str(record.get("journal_short", "")),
            record.get("publication_year", ""),
            str(record.get("title", "")),
        )
        grouped[key].append(record)

    articles = []
    bibliographic_fields = [
        "title",
        "publication_year",
        "publication_date",
        "doi",
        "volume",
        "issue",
        "first_page",
        "last_page",
        "pages_raw",
        "article_type",
        "article_url",
    ]

    for (rule, _key_value), records in sorted(grouped.items()):
        article: Dict[str, Any] = {}
        field_sources: Dict[str, str] = {}

        for field in bibliographic_fields:
            value, source = choose_value(records, field, SOURCE_PRIORITY["bibliographic"])
            article[field] = value
            field_sources[field] = source

        article["abstract"], field_sources["abstract"] = choose_value(
            records, "abstract", SOURCE_PRIORITY["abstract"]
        )
        for field in ["authors_raw", "author_names", "num_authors"]:
            article[field], field_sources[field] = choose_value(records, field, SOURCE_PRIORITY["authors"])
        article["author_affiliations_raw"], field_sources["author_affiliations_raw"] = choose_value(
            records, "author_affiliations_raw", SOURCE_PRIORITY["affiliations"]
        )
        article["keywords"], field_sources["keywords"] = choose_value(
            records, "keywords", SOURCE_PRIORITY["keywords"]
        )

        for field in [
            "jel_codes",
            "field_jel_primary",
            "field_jel_broad",
            "openalex_id",
            "crossref_id",
            "jstor_id",
            "repec_handle",
            "publisher_record_id",
        ]:
            article[field], field_sources[field] = choose_value(records, field, ["crossref", "openalex"])

        journal_short, journal_short_source = choose_value(
            records, "journal_short", SOURCE_PRIORITY["bibliographic"]
        )
        article["journal_short"] = journal_short
        article["journal"] = journal_lookup.get(journal_short, records[0].get("journal", ""))
        article["article_id"] = make_article_id(
            str(article.get("doi", "")),
            str(article.get("journal_short", "")),
            article.get("publication_year", ""),
            str(article.get("title", "")),
        )
        article["primary_source"] = "crossref" if any(r["source"] == "crossref" for r in records) else records[0][
            "source"
        ]
        article["article_type_source"] = field_sources.get("article_type", "")
        article["title_source"] = field_sources.get("title", "")
        article["abstract_source"] = field_sources.get("abstract", "")
        article["doi_source"] = field_sources.get("doi", "")
        article["bibliographic_source"] = field_sources.get("volume") or field_sources.get("publication_year", "")
        article["authors_source"] = field_sources.get("author_names", "")
        article["affiliations_source"] = field_sources.get("author_affiliations_raw", "")
        article["jel_source"] = field_sources.get("jel_codes", "")
        article["keywords_source"] = field_sources.get("keywords", "")
        article["field_source"] = field_sources.get("field_jel_primary", "")
        article["source_record_count"] = len(records)
        article["duplicate_resolution_rule"] = rule

        warnings = []
        for warning in [
            conflict_warning(records, "doi"),
            conflict_warning(records, "title", normalized=True),
            conflict_warning(records, "publication_year"),
            conflict_warning(records, "volume"),
            conflict_warning(records, "issue"),
            conflict_warning(records, "article_type"),
        ]:
            if warning:
                warnings.append(warning)
        if not nonempty(article.get("abstract")):
            warnings.append("missing_abstract")
        if not nonempty(article.get("doi")):
            warnings.append("missing_doi")
        if not nonempty(article.get("article_type")):
            warnings.append("missing_article_type")
        if nonempty(article.get("article_type")) and article.get("article_type") not in [
            "article",
            "journal-article",
        ]:
            warnings.append("nonstandard_article_type")
        if not nonempty(article.get("jel_codes")):
            warnings.append("missing_jel_codes")
        article["metadata_warning"] = ";".join(sorted(set(warnings)))

        for column in FINAL_COLUMNS:
            article.setdefault(column, "")
        articles.append(article)

    df = pd.DataFrame(articles, columns=FINAL_COLUMNS)
    if not df.empty:
        df["publication_year"] = pd.to_numeric(df["publication_year"], errors="coerce").astype("Int64")
        df = df.sort_values(["journal_short", "publication_year", "publication_date", "title"], na_position="last")
    return df


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--start-year", type=int, required=True)
    parser.add_argument("--end-year", type=int, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    project_root = project_root_from_arg(args.project_root)
    ensure_dirs(project_root)

    rows = []
    rows.extend(crossref_rows(project_root, args.run_id, args.start_year, args.end_year))
    rows.extend(openalex_rows(project_root, args.run_id, args.start_year, args.end_year))
    source_df = pd.DataFrame(rows, columns=SOURCE_COLUMNS)
    source_df.to_csv(project_root / "data" / "intermediate" / "source_records.csv", index=False)

    articles = build_articles(rows, project_root)
    articles.to_csv(project_root / "data" / "final" / "articles_pilot.csv", index=False)

    source_overlap_rows = []
    grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for record in rows:
        grouped[
            source_key(
                str(record.get("doi", "")),
                str(record.get("journal_short", "")),
                record.get("publication_year", ""),
                str(record.get("title", "")),
            )
        ].append(record)
    for (rule, value), records_in_group in grouped.items():
        source_overlap_rows.append(
            {
                "duplicate_resolution_rule": rule,
                "match_value": value,
                "journal_short": records_in_group[0].get("journal_short", ""),
                "publication_year": records_in_group[0].get("publication_year", ""),
                "source_record_count": len(records_in_group),
                "sources": "|".join(sorted({record.get("source", "") for record in records_in_group})),
            }
        )
    pd.DataFrame(source_overlap_rows).to_csv(
        project_root / "outputs" / "tables" / "source_overlap_by_article.csv", index=False
    )

    duplicate_groups = (
        source_df[source_df["doi"].fillna("").astype(str).str.strip() != ""]
        .groupby(["source", "journal_short", "doi"], dropna=False)
        .size()
        .reset_index(name="source_records")
        .query("source_records > 1")
    )
    duplicate_groups.to_csv(project_root / "outputs" / "tables" / "duplicate_groups.csv", index=False)

    print(f"source_records={len(source_df)}")
    print(f"articles={len(articles)}")


if __name__ == "__main__":
    main()
