# Recent 2023-2025 Recovery Pilot

This generated handoff keeps the user's requested recent top-5 pilot separate from the broader R001 backfill. It is non-mutating and does not change abstracts, labels, scope decisions, or final article files.

- Triage CSV: `outputs/tables/enriched/recent_2023_2025_insufficient_text_triage.csv`
- Recovery packet CSV: `outputs/tables/enriched/recent_2023_2025_recovery_packet.csv`
- Browser form: `data/intermediate/insufficient_text_recovery_review_forms/recent_2023_2025/recent_2023_2025_recovery_packet.html`
- Suggested export path: `data/intermediate/insufficient_text_recovery_review_exports/recent_2023_2025/recent_2023_2025_recovery_packet.csv`

## Summary

| metric                         | value                       |
| ------------------------------ | --------------------------- |
| recent_years                   | 2023\|2024\|2025            |
| recent_journals                | aer\|ecta\|jpe\|qje\|restud |
| recent_queue_rows              | 0                           |
| recent_scope_review_first_rows | 0                           |
| recent_recover_text_rows       | 0                           |
| recent_recovery_packet_rows    | 0                           |

## Reviewer Rule

- Work `recover_text` rows first; they remain in the recent analysis denominator and need source-confirmed text.
- Do not recover abstracts for `scope_review_first` rows until the scope packet marks them `keep_research` or `unsure` with notes.
- Completed recovery rows require `abstract`, `source`, either `source_url` or `source_record_id`, and an importable `evidence_tier`.
- Keep title-only, citation-only, search-snippet-only, blocked-PDF-only, and provenance-free evidence unresolved.

## After Export Commands

Run the dry-run first after saving completed browser-form exports to the suggested export path.

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_import_abstract_backfill.py --input data/intermediate/insufficient_text_recovery_review_exports/recent_2023_2025/recent_2023_2025_recovery_packet.csv --skip-empty-abstracts --dry-run --require-source-metadata
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_import_abstract_backfill.py --input data/intermediate/insufficient_text_recovery_review_exports/recent_2023_2025/recent_2023_2025_recovery_packet.csv --skip-empty-abstracts --require-source-metadata --fail-on-errors
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_text_enrichment.py
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_classification_pilot.py --input data/final/articles_enriched_pilot.csv --output data/final/articles_classified_enriched_pilot.csv
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_classification_diagnostics.py --classified data/final/articles_classified_enriched_pilot.csv --validation data/intermediate/manual_validation_sample.csv --output-dir outputs/tables/enriched --report docs/classification_diagnostics_enriched.md
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_human_review_refresh.py
```

## Recover-Text Rows

_No rows._

## Full Recent Triage

_No rows._
