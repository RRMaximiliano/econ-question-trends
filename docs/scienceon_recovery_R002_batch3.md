# ScienceOn Recovery Scan

This scan checks ScienceOn public article metadata for exact DOI/title matches with `citation_abstract`. It does not use title-only snippets, access-challenge pages, or restricted full text.

- Scan rows: 25
- DOI prefixes: `10.2307`
- Accepted candidates: 10
- Skipped rows: 25
- Appended export rows: 10
- Candidates CSV: `outputs/tables/enriched/scienceon_recovery_R002_batch3_candidates.csv`
- Skipped CSV: `outputs/tables/enriched/scienceon_recovery_R002_batch3_skipped.csv`
- Confirmed-source export: `data/intermediate/insufficient_text_recovery_review_exports/R002/recovery_batch_R002_confirmed_source_rows.csv`

## Skip Summary

| status                      | rows |
| --------------------------- | ---- |
| doi_title_match_no_abstract | 15   |
| accepted                    | 10   |

## Accepted Candidates

| article_id           | title                                                        | doi             | nart_id      | usable_text_chars | source_url                                                                 |
| -------------------- | ------------------------------------------------------------ | --------------- | ------------ | ----------------- | -------------------------------------------------------------------------- |
| eqt_6857a60bc23e1976 | Estimation in the Presence of Stochastic Parameter Variation | 10.2307/1911389 | NART25365741 | 336               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365741 |
| eqt_9dc2bb88954c4d79 | Optimal Cropping of Self-Reproducible Natural Resources      | 10.2307/1913086 | NART25365689 | 618               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365689 |
| eqt_f54e6fcd8b100165 | Testing the Error Specification in Nonlinear Regression      | 10.2307/1913080 | NART25365683 | 508               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365683 |
| eqt_d46f38e7cc649120 | A Non-Tatonnement Model with Production and Consumption      | 10.2307/1911535 | NART25365848 | 682               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365848 |
| eqt_c000e5d2f2316eba | A Price Characterization of Efficient Random Variables       | 10.2307/1913585 | NART25365650 | 535               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365650 |
| eqt_ac97ac70e424edf5 | Some Estimation Methods for a Random Coefficient Model       | 10.2307/1913588 | NART25365653 | 436               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365653 |
| eqt_90e13af513237937 | Econometric Estimators and the Edgeworth Approximation       | 10.2307/1913972 | NART25365784 | 630               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365784 |
| eqt_0d1e901d475012b4 | Community Preferences and the Representative Consumer        | 10.2307/1911540 | NART25365853 | 649               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365853 |
| eqt_f57bfd754c3dff82 | Factor Prices, Expectations, and Demand for Labor            | 10.2307/1913084 | NART25365687 | 840               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365687 |
| eqt_72edf44782eb867d | Wealth Effects and Slutsky Equations for Assets              | 10.2307/1913587 | NART25365652 | 278               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365652 |
