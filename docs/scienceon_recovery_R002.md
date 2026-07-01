# ScienceOn Recovery Scan

This scan checks ScienceOn public article metadata for exact DOI/title matches with `citation_abstract`. It does not use title-only snippets, access-challenge pages, or restricted full text.

- Scan rows: 25
- DOI prefixes: `10.2307`
- Accepted candidates: 7
- Skipped rows: 25
- Appended export rows: 7
- Candidates CSV: `outputs/tables/enriched/scienceon_recovery_R002_candidates.csv`
- Skipped CSV: `outputs/tables/enriched/scienceon_recovery_R002_skipped.csv`
- Confirmed-source export: `data/intermediate/insufficient_text_recovery_review_exports/R002/recovery_batch_R002_confirmed_source_rows.csv`

## Skip Summary

| status                      | rows |
| --------------------------- | ---- |
| doi_title_match_no_abstract | 14   |
| accepted                    | 7    |
| abstract_below_threshold    | 4    |

## Accepted Candidates

| article_id           | title                                                                                                      | doi             | nart_id      | usable_text_chars | source_url                                                                 |
| -------------------- | ---------------------------------------------------------------------------------------------------------- | --------------- | ------------ | ----------------- | -------------------------------------------------------------------------- |
| eqt_57328c9df2d920d1 | Incomplete Contracts and Renegotiation                                                                     | 10.2307/1912698 | NART25367703 | 1450              | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25367703 |
| eqt_d22389f2e355278e | Certainty Equivalence, First Order Certainty Equivalence, Stochastic Control, and the Covariance Structure | 10.2307/1914274 | NART25365663 | 480               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365663 |
| eqt_addb3513801c4fca | Efficient Estimation of the Lorenz Curve and Associated Inequality Measures from Grouped Observations      | 10.2307/1911387 | NART25365739 | 674               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365739 |
| eqt_9489ee196c80cd75 | Estimation of Models with Jointly Dependent Qualitative Variables: A Simultaneous Logit Approach           | 10.2307/1913083 | NART25365686 | 475               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365686 |
| eqt_f5a6f2cfb5c8df01 | Optimal Consumption over Time when Prices and Interest Rates Follow a Markovian Process                    | 10.2307/1913584 | NART25365649 | 848               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365649 |
| eqt_16b7d3bd591ec5ac | Analysis of Models for Commercial Fishing: Mathematical and Economical Aspects                             | 10.2307/1912725 | NART25365763 | 406               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365763 |
| eqt_3b7ed4bd4e26ac5b | Asymmetric Policymaker Utility Functions and Optimal Policy under Uncertainty                              | 10.2307/1911380 | NART25365732 | 590               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365732 |
