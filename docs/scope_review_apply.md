# Scope Review Decision Import

- Mode: `dry-run`

This command validates completed scope-review packet rows. It does not change causal/predictive labels.
Completed rows must have unique `scope_review_id` and `article_id` values, a valid decision, reviewer ID, and ISO review date before scope metadata can be applied.

## Summary

| metric                           | value |
| -------------------------------- | ----- |
| scope_review_rows                | 7     |
| completed_scope_review_decisions | 7     |
| remaining_scope_review_decisions | 0     |
| error_rows                       | 0     |
| valid_decisions                  | 7     |
| scope_changes                    | 0     |
| metadata_only_changes            | 7     |
| applied                          | no    |

## Validation Errors

_No rows._

## Proposed/Applied Changes

| scope_review_id | article_id           | human_scope_decision | old_article_scope       | old_article_scope_reason                                                        | new_article_scope       | new_article_scope_reason                                                        | scope_review_notes                                                                              | reviewer_id | review_date | change_status |
| --------------- | -------------------- | -------------------- | ----------------------- | ------------------------------------------------------------------------------- | ----------------------- | ------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- | ----------- | ----------- | ------------- |
| SR0005          | eqt_ce64edb007bbe04b | exclude_nonresearch  | review_erratum_paratext | scope_review_decision=exclude_nonresearch;title_pattern=^supplement to\b        | review_erratum_paratext | scope_review_decision=exclude_nonresearch;title_pattern=^supplement to\b        | Title identifies this as a supplement/data-file guide, not a standalone research article.       | codex       | 2026-06-29  | metadata_only |
| SR0006          | eqt_a6bef25ef2ad3854 | exclude_nonresearch  | review_erratum_paratext | scope_review_decision=exclude_nonresearch;title_pattern=\belection of fellows\b | review_erratum_paratext | scope_review_decision=exclude_nonresearch;title_pattern=\belection of fellows\b | Title identifies this as a society-election notice, not a standalone research article.          | codex       | 2026-06-29  | metadata_only |
| SR0007          | eqt_6c95a1e1053a8348 | exclude_nonresearch  | review_erratum_paratext | scope_review_decision=exclude_nonresearch;title_pattern=\breferees? [0-9]{4}    | review_erratum_paratext | scope_review_decision=exclude_nonresearch;title_pattern=\breferees? [0-9]{4}    | Title identifies this as a referee list/acknowledgment, not a standalone research article.      | codex       | 2026-06-29  | metadata_only |
| SR0002          | eqt_01610bafe13f66bf | exclude_nonresearch  | review_erratum_paratext | scope_review_decision=exclude_nonresearch;title_pattern=: erratum$              | review_erratum_paratext | scope_review_decision=exclude_nonresearch;title_pattern=: erratum$              | Title identifies this as a correction/erratum to prior work, not a standalone research article. | codex       | 2026-06-29  | metadata_only |
| SR0001          | eqt_cfafc0b726238522 | exclude_nonresearch  | review_erratum_paratext | scope_review_decision=exclude_nonresearch;title_pattern=\ba correction$         | review_erratum_paratext | scope_review_decision=exclude_nonresearch;title_pattern=\ba correction$         | Title identifies this as a correction/erratum to prior work, not a standalone research article. | codex       | 2026-06-29  | metadata_only |
| SR0003          | eqt_b91731167d1a0908 | exclude_nonresearch  | review_erratum_paratext | scope_review_decision=exclude_nonresearch;title_pattern=\ba correction$         | review_erratum_paratext | scope_review_decision=exclude_nonresearch;title_pattern=\ba correction$         | Title identifies this as a correction/erratum to prior work, not a standalone research article. | codex       | 2026-06-29  | metadata_only |
| SR0004          | eqt_93d1a55d1bd5e496 | exclude_nonresearch  | review_erratum_paratext | scope_review_decision=exclude_nonresearch;title_pattern=\ba correction$         | review_erratum_paratext | scope_review_decision=exclude_nonresearch;title_pattern=\ba correction$         | Title identifies this as a correction/erratum to prior work, not a standalone research article. | codex       | 2026-06-29  | metadata_only |
