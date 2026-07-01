# Recovery Batch R004 Split Preflight

This report is non-mutating. It validates ready split packets with the same matching, source-metadata, and evidence-tier checks used by `run_import_abstract_backfill.py --skip-empty-abstracts --require-source-metadata`, but it does not update enrichment histories or final article files.

- Ready split groups checked: 1
- Import-ready rows: 14
- Error rows: 0
- Skipped empty abstract rows: 86

## Preflight Summary

| recovery_batch | split_group           | preflight_status | input_csv                                                                                                                | total_rows | skipped_empty_abstract_rows | candidate_rows_after_skip | import_ready_rows | error_rows | source_ready_backfill_abstracts | source_incomplete_backfill_abstracts | recommended_next_step                                                                                                                                            |
| -------------- | --------------------- | ---------------- | ------------------------------------------------------------------------------------------------------------------------ | ---------- | --------------------------- | ------------------------- | ----------------- | ---------- | ------------------------------- | ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| R004           | ready_manual_metadata | pass_ready       | data/intermediate/insufficient_text_recovery_staged/R004/insufficient_text_recovery_batch_R004_ready_manual_metadata.csv | 100        | 86                          | 14                        | 14                | 0          | 14                              | 0                                    | Recover only source-confirmed abstracts from DOI, publisher, index, or title-match metadata; record evidence_tier and do not retry blocked PDF routes unchanged. |

## Errors

_No rows._
