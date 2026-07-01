# Manual Validation Readiness

- Ready for blind review: `yes`
- Sample rows: 300
- Completed manual labels: 300
- Remaining manual labels: 0
- Drifted sample articles: 0
- Reviewer batches: 6
- Next incomplete batch: ``

## Review Materials

- Codebook: `docs/manual_validation_codebook.md`
- Batch CSVs: `data/intermediate/manual_validation_batches`
- Browser forms: `data/intermediate/manual_validation_forms`

## Summary

| metric                                       | value |
| -------------------------------------------- | ----- |
| sample_rows                                  | 300   |
| completed_manual_labels                      | 300   |
| remaining_manual_labels                      | 0     |
| drifted_articles                             | 0     |
| drifted_cells                                | 0     |
| sample_validation_category_causal            | 40    |
| sample_validation_category_insufficient_text | 99    |
| sample_validation_category_other             | 130   |
| sample_validation_category_predictive        | 31    |
| sample_article_scope_research_article        | 300   |
| sample_missing_abstract_rows                 | 85    |
| reviewer_batches                             | 6     |
| completed_reviewer_batches                   | 6     |
| started_reviewer_batches                     | 6     |
| next_incomplete_batch                        |       |
| ready_for_blind_review                       | yes   |

## Batch Progress

| batch_id | total_rows | completed_manual_labels | remaining_manual_labels | invalid_manual_label_rows | missing_manual_confidence_rows | reviewer_ids   | latest_review_date | manual_label_causal | manual_label_predictive | manual_label_other | manual_label_insufficient_text |
| -------- | ---------- | ----------------------- | ----------------------- | ------------------------- | ------------------------------ | -------------- | ------------------ | ------------------- | ----------------------- | ------------------ | ------------------------------ |
| B001     | 50         | 50                      | 0                       | 0                         | 0                              | codex_assisted | 2026-06-30         | 0                   | 0                       | 50                 | 0                              |
| B002     | 50         | 50                      | 0                       | 0                         | 0                              | codex_assisted | 2026-06-30         | 4                   | 15                      | 31                 | 0                              |
| B003     | 50         | 50                      | 0                       | 0                         | 0                              | codex_assisted | 2026-06-30         | 17                  | 5                       | 28                 | 0                              |
| B004     | 50         | 50                      | 0                       | 0                         | 0                              | codex_assisted | 2026-06-30         | 22                  | 15                      | 13                 | 0                              |
| B005     | 50         | 50                      | 0                       | 0                         | 0                              | codex_assisted | 2026-06-30         | 6                   | 1                       | 43                 | 0                              |
| B006     | 50         | 50                      | 0                       | 0                         | 0                              | codex_assisted | 2026-06-30         | 18                  | 1                       | 31                 | 0                              |

## Sample Drift

_No rows._
