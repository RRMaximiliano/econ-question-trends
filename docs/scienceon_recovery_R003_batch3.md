# ScienceOn Recovery Scan

This scan checks ScienceOn public article metadata for exact DOI/title matches with `citation_abstract`. It does not use title-only snippets, access-challenge pages, or restricted full text.

- Scan rows: 25
- DOI prefixes: `10.2307`
- Accepted candidates: 12
- Skipped rows: 25
- Appended export rows: 12
- Candidates CSV: `outputs/tables/enriched/scienceon_recovery_R003_batch3_candidates.csv`
- Skipped CSV: `outputs/tables/enriched/scienceon_recovery_R003_batch3_skipped.csv`
- Confirmed-source export: `data/intermediate/insufficient_text_recovery_review_exports/R003/recovery_batch_R003_confirmed_source_rows.csv`

## Skip Summary

| status                      | rows |
| --------------------------- | ---- |
| doi_title_match_no_abstract | 13   |
| accepted                    | 12   |

## Accepted Candidates

| article_id           | title                                                         | doi             | nart_id      | usable_text_chars | source_url                                                                 |
| -------------------- | ------------------------------------------------------------- | --------------- | ------------ | ----------------- | -------------------------------------------------------------------------- |
| eqt_fac346a10a3f2dda | Application of Pre-Test and Stein Estimators to Economic Data | 10.2307/1914073 | NART25366007 | 546               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366007 |
| eqt_5ffb52149e21fcfb | Towards a Theory of Elections with Probabilistic Preferences  | 10.2307/1914118 | NART25366070 | 1041              | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366070 |
| eqt_ea3d40fff6a8041e | The Systems of Consumer Demand Functions Approach: A Review   | 10.2307/1913286 | NART25365889 | 634               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365889 |
| eqt_1d57d8605e98bc88 | Linear Quadratic Control Theory for Models with Long Lags     | 10.2307/1912681 | NART25365974 | 831               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365974 |
| eqt_cce16f97e41b8856 | A Convergent Adjustment Process for Firms in Competition      | 10.2307/1912304 | NART25366020 | 678               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366020 |
| eqt_7acdce8781a83940 | Input-Output Analysis with Scale-Dependent Coefficients       | 10.2307/1911537 | NART25365850 | 1072              | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365850 |
| eqt_bd6a56178d80529b | Pricing under Spatial Competition and Spatial Monopoly        | 10.2307/1912302 | NART25366018 | 364               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366018 |
| eqt_6e8df2ed36112ea6 | Two-Person Bargaining Problems and Comparable Utility         | 10.2307/1913955 | NART25366042 | 549               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366042 |
| eqt_6fb30ae816056a58 | A Generalization of the Open Expanding Economy Model          | 10.2307/1914109 | NART25366061 | 336               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366061 |
| eqt_142bd0925ec3da49 | Error Components and Seemingly Unrelated Regressions          | 10.2307/1913296 | NART25365899 | 548               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365899 |
| eqt_889191f1d98bae28 | Optimum Trade Restrictions and Their Consequences             | 10.2307/1913443 | NART25365824 | 518               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365824 |
| eqt_6389b2328d05b64c | A Model of Borrowing and Lending with Bankruptcy              | 10.2307/1914117 | NART25366069 | 444               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366069 |
