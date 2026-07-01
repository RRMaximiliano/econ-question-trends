# Manual Validation Adjudication Dry-Run Status

Completed adjudication rows must include a valid `adjudicated_label`, adjudication notes, adjudicator ID, ISO adjudication date, and disagreement context from either diagnostics (`manual_label` plus `predicted_label`) or overlap QA (`primary_manual_label` plus `overlap_manual_label`).

## Completion

| metric                              | value |
| ----------------------------------- | ----- |
| total_rows                          | 300   |
| completed_adjudications             | 145   |
| remaining_unadjudicated_rows        | 155   |
| adjudicated_label_causal            | 29    |
| adjudicated_label_predictive        | 15    |
| adjudicated_label_other             | 101   |
| adjudicated_label_insufficient_text | 0     |

## Import Errors

_No rows._
