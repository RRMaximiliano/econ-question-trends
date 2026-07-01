# Data Documentation

Generated UTC: 2026-06-28T21:00:32+00:00
Run ID: `1975_2025_yearly_crossref_20260628T`

## Data Sources Used

- Crossref REST API: DOI-centered bibliographic metadata.
- OpenAlex Works API: work discovery, abstracts where available, authorships, institutions, keywords, concepts, topics, and DOI links.

## Output Datasets

- `data/intermediate/source_records.csv`: standardized source-level records before deduplication.
- `data/final/articles_pilot.csv`: deduplicated article-level pilot file.

## Deduplication

Records are grouped by normalized DOI when available. Records without DOI are grouped by normalized title, journal, and publication year. Fuzzy title matching is not used for automatic deduplication.

## Variable Provenance

The final article file includes source columns such as `title_source`, `abstract_source`, `bibliographic_source`, `authors_source`, `affiliations_source`, `jel_source`, and `keywords_source`.

## Missingness

| variable                | nonmissing_count | missing_count | nonmissing_share |
| ----------------------- | ---------------- | ------------- | ---------------- |
| title                   | 23612            | 291           | 0.9878           |
| abstract                | 17929            | 5974          | 0.7501           |
| journal                 | 23903            | 0             | 1.0              |
| publication_year        | 23903            | 0             | 1.0              |
| doi                     | 20357            | 3546          | 0.8517           |
| volume                  | 23707            | 196           | 0.9918           |
| issue                   | 23675            | 228           | 0.9905           |
| pages_raw               | 22885            | 1018          | 0.9574           |
| article_type            | 23903            | 0             | 1.0              |
| author_names            | 21561            | 2342          | 0.902            |
| author_affiliations_raw | 14037            | 9866          | 0.5872           |
| num_authors             | 21561            | 2342          | 0.902            |
| jel_codes               | 0                | 23903         | 0.0              |
| keywords                | 23844            | 59            | 0.9975           |
| field_jel_primary       | 0                | 23903         | 0.0              |
| field_jel_broad         | 0                | 23903         | 0.0              |

## Known Limitations

- This is a public-source metadata pilot, not a final archival article database.
- Article type/category coverage is incomplete and source-provided only.
- Source-provided article type is too coarse for full research-article restrictions in this batch. Crossref mostly returns `journal-article`, while OpenAlex may return `article`, `preprint`, `report`, `paratext`, or `erratum`.
- JEL code coverage is currently missing because neither Crossref nor OpenAlex reliably supplies JEL metadata in this workflow.
- Affiliation metadata should be interpreted cautiously; OpenAlex institutions and raw affiliation strings may not always represent publication-time affiliations cleanly.
- Abstract missingness must be accounted for before any classification exercise.

## Next Expansion Options

- Add publisher table-of-contents scraping or APIs for article type validation.
- Add JSTOR support for historical coverage, subject to access terms.
- Add EconLit exports for JEL codes, keywords, article types, and abstracts where institutional terms allow.
- Add RePEc as an economics-specific supplemental source.
