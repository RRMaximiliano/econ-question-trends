# Recovery Batch R001 Tiered Stage

This report stages completed tiered recovery-form exports into split-packet copies. It does not update final article files, enrichment histories, or the original split packets.

- Reviewer input: `data/intermediate/insufficient_text_recovery_review_exports/R001`
- Staged split summary: `outputs/tables/enriched/recovery_batch_R001_staged_split_summary.csv`
- Staged rows: 0
- Error rows: 0

Run preflight against the staged summary before importing:

```bash
python3 run_recovery_split_preflight.py --split-summary outputs/tables/enriched/recovery_batch_R001_staged_split_summary.csv
```

## Staged Summary

| recovery_batch | split_group                  | rows | completed_backfill_abstracts | source_ready_backfill_abstracts | source_incomplete_backfill_abstracts | remaining_backfill_abstracts | output_csv                                                                                                                      | output_html | recommended_next_step                                                                                                                                            |
| -------------- | ---------------------------- | ---- | ---------------------------- | ------------------------------- | ------------------------------------ | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------- | ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| R001           | ready_partial_text_extension | 38   | 0                            | 0                               | 0                                    | 38                           | data/intermediate/insufficient_text_recovery_staged/R001/insufficient_text_recovery_batch_R001_ready_partial_text_extension.csv |             | Extend partial text from explicit source metadata, record source details and evidence_tier, then import completed rows with --skip-empty-abstracts.              |
| R001           | ready_manual_metadata        | 55   | 0                            | 0                               | 0                                    | 55                           | data/intermediate/insufficient_text_recovery_staged/R001/insufficient_text_recovery_batch_R001_ready_manual_metadata.csv        |             | Recover only source-confirmed abstracts from DOI, publisher, index, or title-match metadata; record evidence_tier and do not retry blocked PDF routes unchanged. |
| R001           | ready_autofill_or_completed  | 0    | 0                            | 0                               | 0                                    | 0                            |                                                                                                                                 |             | Preserve already-filled rows or autofill accepted PDF text before importing completed rows.                                                                      |
| R001           | waiting_scope_review         | 0    | 0                            | 0                               | 0                                    | 0                            |                                                                                                                                 |             | Do not spend abstract-recovery time until the scope-review packet has a keep/exclude/unsure decision.                                                            |
| R001           | excluded_nonresearch         | 7    | 0                            | 0                               | 0                                    | 7                            | data/intermediate/insufficient_text_recovery_staged/R001/insufficient_text_recovery_batch_R001_excluded_nonresearch.csv         |             | Do not recover abstract text unless the scope decision changes; this row is outside the research denominator.                                                    |
| R001           | other_manual_review          | 0    | 0                            | 0                               | 0                                    | 0                            |                                                                                                                                 |             | Inspect the workplan notes before choosing a recovery route.                                                                                                     |

## Staged Changes

_No rows._

## Errors

_No rows._
