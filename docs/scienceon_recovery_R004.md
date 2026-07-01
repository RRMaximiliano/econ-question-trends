# ScienceOn Recovery Scan

This scan checks ScienceOn public article metadata for exact DOI/title matches with `citation_abstract`. It does not use title-only snippets, access-challenge pages, or restricted full text.

- Scan rows: 25
- DOI prefixes: `10.2307`
- Accepted candidates: 15
- Skipped rows: 25
- Appended export rows: 15
- Candidates CSV: `outputs/tables/enriched/scienceon_recovery_R004_candidates.csv`
- Skipped CSV: `outputs/tables/enriched/scienceon_recovery_R004_skipped.csv`
- Confirmed-source export: `data/intermediate/insufficient_text_recovery_review_exports/R004/recovery_batch_R004_confirmed_source_rows.csv`

## Skip Summary

| status                      | rows |
| --------------------------- | ---- |
| accepted                    | 15   |
| doi_title_match_no_abstract | 10   |

## Accepted Candidates

| article_id           | title                                                                                                                           | doi             | nart_id      | usable_text_chars | source_url                                                                 |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------- | --------------- | ------------ | ----------------- | -------------------------------------------------------------------------- |
| eqt_2d779f3cdf06283f | A New Representation of Preferences over "Certain x Uncertain" Consumption Pairs: The "Ordinal Certainty Equivalent" Hypothesis | 10.2307/1911435 | NART25366203 | 841               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366203 |
| eqt_294a58c073871316 | Testing for Higher Order Serial Correlation in Regression Equations when the Regressors Include Lagged Dependent Variables      | 10.2307/1913830 | NART25366229 | 763               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366229 |
| eqt_725c54ae185d4f79 | Linear Models with Autocorrelated Errors: Structural Identifiability in the Absence of Minimality Assumptions                   | 10.2307/1914195 | NART25366294 | 470               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366294 |
| eqt_5de82aa3b8b0ba05 | The Bilinear Complementarity Problem and Competitive Equilibria of Piecewise Linear Economic Models                             | 10.2307/1913647 | NART25366092 | 317               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366092 |
| eqt_316e06d10fe536b3 | Examination of Environmental Policies Using Production and Pollution Microparameter Distributions                               | 10.2307/1909747 | NART25366179 | 814               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366179 |
| eqt_433c56ae53834170 | Measurement Error in a Dynamic Simultaneous Equations Model with Stationary Disturbances                                        | 10.2307/1914194 | NART25366293 | 701               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366293 |
| eqt_64ae3099401975bb | The Linear Logarithmic Expenditure System: An Application to Consumption-Leisure Choice                                         | 10.2307/1909753 | NART25366185 | 847               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366185 |
| eqt_b426374f65c8be40 | Discrete Parameter Variation: Efficient Estimation of a Switching Regression Model                                              | 10.2307/1913910 | NART25366134 | 477               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366134 |
| eqt_4add5e99b98f1c6e | Extermination of Self-Reproducible Natural Resources under Competitive Conditions                                               | 10.2307/1913658 | NART25366103 | 420               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366103 |
| eqt_8531d74b244c0730 | Household Bequests, Perfect Expectations, and the National Distribution of Wealth                                               | 10.2307/1911957 | NART25366370 | 1038              | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366370 |
| eqt_9b14ddbfbcf2f184 | Comparisons of Normal and Logistic Models in the Bivariate Dichotomous Analysis                                                 | 10.2307/1914141 | NART25366350 | 754               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366350 |
| eqt_67c744fbb8f4e87c | A Note on the Characterization of Mechanisms for the Revelation of Preferences                                                  | 10.2307/1913651 | NART25366096 | 613               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366096 |
| eqt_2999a3686473d8be | A Procedure for Generating Pareto-Efficient Egalitarian-Equivalent Allocations                                                  | 10.2307/1912345 | NART25366253 | 673               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366253 |
| eqt_ebf7bc22adb4a842 | Iterative Aggregation--A New Approach to the Solution of Large-Scale Problems                                                   | 10.2307/1914133 | NART25366342 | 954               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366342 |
| eqt_9e96130949947c5d | Components of Variation in Panel Earnings Data: American Scientists 1960-70                                                     | 10.2307/1914192 | NART25366291 | 774               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366291 |
