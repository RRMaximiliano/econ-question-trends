# ScienceOn Recovery Scan

This scan checks ScienceOn public article metadata for exact DOI/title matches with `citation_abstract`. It does not use title-only snippets, access-challenge pages, or restricted full text.

- Scan rows: 14
- DOI prefixes: `10.2307`
- Accepted candidates: 6
- Skipped rows: 14
- Appended export rows: 6
- Candidates CSV: `outputs/tables/enriched/scienceon_recovery_R002_batch4_candidates.csv`
- Skipped CSV: `outputs/tables/enriched/scienceon_recovery_R002_batch4_skipped.csv`
- Confirmed-source export: `data/intermediate/insufficient_text_recovery_review_exports/R002/recovery_batch_R002_confirmed_source_rows.csv`

## Skip Summary

| status                      | rows |
| --------------------------- | ---- |
| doi_title_match_no_abstract | 7    |
| accepted                    | 6    |
| abstract_below_threshold    | 1    |

## Accepted Candidates

| article_id           | title                                       | doi             | nart_id      | usable_text_chars | source_url                                                                 |
| -------------------- | ------------------------------------------- | --------------- | ------------ | ----------------- | -------------------------------------------------------------------------- |
| eqt_5890546cd6321a5b | A Function for Size Distribution of Incomes | 10.2307/1911538 | NART25365851 | 829               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365851 |
| eqt_bdd47b8665d44340 | Pareto Optimality in Non-Convex Economies   | 10.2307/1913410 | NART25365622 | 644               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365622 |
| eqt_6212edc0c359dcb8 | An Interactive Market-Planning Procedure    | 10.2307/1914251 | NART25365867 | 448               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365867 |
| eqt_ef641deac1bf3107 | A Theorem on Decentralized Exchange         | 10.2307/1913444 | NART25365825 | 583               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365825 |
| eqt_eee3f52799030505 | Samuelson's Self-Dual Preferences           | 10.2307/1913411 | NART25365623 | 956               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365623 |
| eqt_9eb9be3ff70e0bda | Voting Majority Sizes                       | 10.2307/1913586 | NART25365651 | 474               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365651 |
