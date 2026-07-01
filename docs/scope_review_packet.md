# Scope Review Packet

Use this packet to decide whether candidate rows belong in the research-analysis denominator. Do not edit causal/predictive labels here.

- Packet CSV: `data/intermediate/scope_review/scope_review_packet.csv`
- Browser form: `data/intermediate/scope_review_forms/scope_review_packet.html`
- Completed decisions: 7 / 7
- Remaining decisions: 0
- First incomplete row: ``

Allowed decisions: `exclude_nonresearch`, `keep_research`, `unsure`.

## Decision Rubric

- `exclude_nonresearch`: use for corrections, errata, retractions, referee lists, society-election notices, supplements, data/code appendices, or other paratext that is not a standalone research article.
- `keep_research`: use only when the row contains substantive standalone research and should remain in the trend denominator.
- `unsure`: use when the title or metadata are not enough to decide; leave a note describing the ambiguity.
- Completed decisions require `reviewer_id` and ISO `review_date`. Do not change causal/predictive labels in this packet.

## Decision Counts

| metric                       | value |
| ---------------------------- | ----- |
| decision_exclude_nonresearch | 7     |
| decision_keep_research       | 0     |
| decision_unsure              | 0     |

## Review Priority

| scope_review_priority   | candidate_rows |
| ----------------------- | -------------- |
| P2_scope_review_backlog | 7              |

## After Export Commands

- Place the exported CSV at `data/intermediate/scope_review/scope_review_packet.csv`.
- Run the dry-run validator: `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_apply_scope_review_decisions.py`.
- Review `docs/scope_review_apply.md`, `outputs/tables/enriched/scope_review_apply_errors.csv`, and `outputs/tables/enriched/scope_review_apply_changes.csv`; continue only when `error_rows=0` and the proposed changes match the reviewed packet.
- Apply only after the dry-run is clean: `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_apply_scope_review_decisions.py --apply`.
- Refresh handoff status: `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_human_review_refresh.py`.

## Review Pattern Guide

| scope_pattern_family     | proposed_article_scope  | review_lens                                                                                            | pattern_group_rows | completed_decisions | remaining_decisions | review_focus                                                                                                                                                              |
| ------------------------ | ----------------------- | ------------------------------------------------------------------------------------------------------ | ------------------ | ------------------- | ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| correction_erratum       | review_erratum_paratext | Usually exclude if it only corrects a prior article.                                                   | 4                  | 4                   | 0                   | Confirm whether this row is only a correction, erratum, corrigendum, or retraction. Exclude nonresearch paratext; keep only if it contains substantive original research. |
| referee_list             | review_erratum_paratext | Usually exclude as editorial paratext.                                                                 | 1                  | 1                   | 0                   | Confirm it is a referee acknowledgement/list. These are editorial paratext and should not consume abstract-recovery time.                                                 |
| society_election         | review_erratum_paratext | Usually exclude as society paratext.                                                                   | 1                  | 1                   | 0                   | Confirm it is an election/fellows notice rather than a research article. These repeated society notices should generally leave the research denominator.                  |
| supplement_or_data_files | review_erratum_paratext | Usually exclude if it is supplementary files, data, code, or a guide rather than a standalone article. | 1                  | 1                   | 0                   | Confirm whether this is a supplement, data-file guide, code/program note, or appendix-only material. Exclude if it is not a standalone research article.                  |

Full guide: `docs/scope_review_guide.md`

## Packet Preview

| scope_review_id | scope_review_priority   | article_id           | journal_short | publication_year | title                                                                                       | proposed_article_scope  | proposed_scope_reason                 | recovery_batches | human_scope_decision |
| --------------- | ----------------------- | -------------------- | ------------- | ---------------- | ------------------------------------------------------------------------------------------- | ----------------------- | ------------------------------------- | ---------------- | -------------------- |
| SR0001          | P2_scope_review_backlog | eqt_cfafc0b726238522 | restud        | 1978             | Money in a Sequence Economy: A Correction                                                   | review_erratum_paratext | title_pattern=\ba correction$         | R001             | exclude_nonresearch  |
| SR0002          | P2_scope_review_backlog | eqt_01610bafe13f66bf | restud        | 1978             | More on Prices vs. Quantities: Erratum                                                      | review_erratum_paratext | title_pattern=: erratum$              | R001             | exclude_nonresearch  |
| SR0003          | P2_scope_review_backlog | eqt_b91731167d1a0908 | restud        | 1979             | On the Consistency of Libertarian Claims: A Correction                                      | review_erratum_paratext | title_pattern=\ba correction$         | R001             | exclude_nonresearch  |
| SR0004          | P2_scope_review_backlog | eqt_93d1a55d1bd5e496 | restud        | 1983             | Spatial Competition and Spatial Price Discrimination: A Correction                          | review_erratum_paratext | title_pattern=\ba correction$         | R001             | exclude_nonresearch  |
| SR0005          | P2_scope_review_backlog | eqt_ce64edb007bbe04b | ecta          | 2008             | Supplement to Best Nonparametric Bounds on Demand Responses-Guide to Data Files and Program | review_erratum_paratext | title_pattern=^supplement to\b        | R001             | exclude_nonresearch  |
| SR0006          | P2_scope_review_backlog | eqt_a6bef25ef2ad3854 | ecta          | 2009             | 2008 Election of Fellows to the Econometric Society                                         | review_erratum_paratext | title_pattern=\belection of fellows\b | R001             | exclude_nonresearch  |
| SR0007          | P2_scope_review_backlog | eqt_6c95a1e1053a8348 | ecta          | 2009             | Econometrica Referees 2007-2008                                                             | review_erratum_paratext | title_pattern=\breferees? [0-9]{4}    | R001             | exclude_nonresearch  |
