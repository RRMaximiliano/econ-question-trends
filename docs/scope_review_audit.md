# Scope Review Audit

This is a non-mutating audit. It does not change `causal_predictive_category`, manual validation labels, or source article files.

- Candidate rows: 7
- Unique candidate articles: 7

## By Dataset

| dataset      | candidate_rows |
| ------------ | -------------- |
| active_batch | 7              |

## By Proposed Scope

| proposed_article_scope  | candidate_rows |
| ----------------------- | -------------- |
| review_erratum_paratext | 7              |

## By Recovery Batch

| recovery_batch | candidate_rows |
| -------------- | -------------- |
| R001           | 7              |

## Summary Detail

| dataset      | proposed_article_scope  | proposed_scope_reason                 | journal_short | decade | recovery_batch | candidate_rows |
| ------------ | ----------------------- | ------------------------------------- | ------------- | ------ | -------------- | -------------- |
| active_batch | review_erratum_paratext | title_pattern=\ba correction$         | restud        | 1970   | R001           | 2              |
| active_batch | review_erratum_paratext | title_pattern=\belection of fellows\b | ecta          | 2000   | R001           | 1              |
| active_batch | review_erratum_paratext | title_pattern=\breferees? [0-9]{4}    | ecta          | 2000   | R001           | 1              |
| active_batch | review_erratum_paratext | title_pattern=^supplement to\b        | ecta          | 2000   | R001           | 1              |
| active_batch | review_erratum_paratext | title_pattern=: erratum$              | restud        | 1970   | R001           | 1              |
| active_batch | review_erratum_paratext | title_pattern=\ba correction$         | restud        | 1980   | R001           | 1              |

## Candidate Preview

| dataset      | article_id           | journal_short | publication_year | title                                                                                       | doi                  | current_article_scope | proposed_article_scope  | proposed_scope_reason                 | recovery_batch | recovery_rank |
| ------------ | -------------------- | ------------- | ---------------- | ------------------------------------------------------------------------------------------- | -------------------- | --------------------- | ----------------------- | ------------------------------------- | -------------- | ------------- |
| active_batch | eqt_cfafc0b726238522 | restud        | 1978             | Money in a Sequence Economy: A Correction                                                   | 10.2307/2297356      |                       | review_erratum_paratext | title_pattern=\ba correction$         | R001           | 6             |
| active_batch | eqt_01610bafe13f66bf | restud        | 1978             | More on Prices vs. Quantities: Erratum                                                      | 10.2307/2297098      |                       | review_erratum_paratext | title_pattern=: erratum$              | R001           | 7             |
| active_batch | eqt_b91731167d1a0908 | restud        | 1979             | On the Consistency of Libertarian Claims: A Correction                                      | 10.2307/2297041      |                       | review_erratum_paratext | title_pattern=\ba correction$         | R001           | 11            |
| active_batch | eqt_93d1a55d1bd5e496 | restud        | 1983             | Spatial Competition and Spatial Price Discrimination: A Correction                          | 10.2307/2297774      |                       | review_erratum_paratext | title_pattern=\ba correction$         | R001           | 12            |
| active_batch | eqt_ce64edb007bbe04b | ecta          | 2008             | Supplement to Best Nonparametric Bounds on Demand Responses-Guide to Data Files and Program | 10.3982/ecta6096supp |                       | review_erratum_paratext | title_pattern=^supplement to\b        | R001           | 35            |
| active_batch | eqt_a6bef25ef2ad3854 | ecta          | 2009             | 2008 Election of Fellows to the Econometric Society                                         | 10.3982/ecta772fes   |                       | review_erratum_paratext | title_pattern=\belection of fellows\b | R001           | 36            |
| active_batch | eqt_6c95a1e1053a8348 | ecta          | 2009             | Econometrica Referees 2007-2008                                                             | 10.3982/ecta771ref   |                       | review_erratum_paratext | title_pattern=\breferees? [0-9]{4}    | R001           | 38            |

## Next Command

After human scope decisions are resolved, rerun:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_project_status.py
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_batch_workplan.py
```
