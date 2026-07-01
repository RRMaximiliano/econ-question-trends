# ScienceOn Recovery Scan

This scan checks ScienceOn public article metadata for exact DOI/title matches with `citation_abstract`. It does not use title-only snippets, access-challenge pages, or restricted full text.

- Scan rows: 21
- DOI prefixes: `10.2307`
- Accepted candidates: 0
- Skipped rows: 21
- Appended export rows: 0
- Candidates CSV: `outputs/tables/enriched/scienceon_recovery_R001_candidates.csv`
- Skipped CSV: `outputs/tables/enriched/scienceon_recovery_R001_skipped.csv`
- Confirmed-source export: `data/intermediate/insufficient_text_recovery_review_exports/R001/recovery_batch_R001_confirmed_source_rows.csv`

## Skip Summary

| status                      | rows |
| --------------------------- | ---- |
| doi_title_match_no_abstract | 19   |
| abstract_below_threshold    | 2    |

## Accepted Candidates

_No rows._
