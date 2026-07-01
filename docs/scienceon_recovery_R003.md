# ScienceOn Recovery Scan

This scan checks ScienceOn public article metadata for exact DOI/title matches with `citation_abstract`. It does not use title-only snippets, access-challenge pages, or restricted full text.

- Scan rows: 25
- DOI prefixes: `10.2307`
- Accepted candidates: 16
- Skipped rows: 25
- Appended export rows: 16
- Candidates CSV: `outputs/tables/enriched/scienceon_recovery_R003_candidates.csv`
- Skipped CSV: `outputs/tables/enriched/scienceon_recovery_R003_skipped.csv`
- Confirmed-source export: `data/intermediate/insufficient_text_recovery_review_exports/R003/recovery_batch_R003_confirmed_source_rows.csv`

## Skip Summary

| status                      | rows |
| --------------------------- | ---- |
| accepted                    | 16   |
| doi_title_match_no_abstract | 9    |

## Accepted Candidates

| article_id           | title                                                                                                                                     | doi             | nart_id      | usable_text_chars | source_url                                                                 |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- | --------------- | ------------ | ----------------- | -------------------------------------------------------------------------- |
| eqt_0ac4921f00b13618 | Bounds for the Bias of the Least Squares Estimator of @s^2 in the Case of a First-Order Autoregressive Process (Positive Autocorrelation) | 10.2307/1914071 | NART25366005 | 572               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366005 |
| eqt_b19f0b5cb1d6494e | Extensions of the Le Chatelier-Samuelson Principle and Their Application to Analytical Economics--Constraints and Economic Analysis       | 10.2307/1913979 | NART25365791 | 1376              | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365791 |
| eqt_a99de6a1f8d50cc6 | The Robustness of Some Standard Tests for Autocorrelation and Heteroskedasticity when Both Problems Are Present                           | 10.2307/1911687 | NART25365954 | 447               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365954 |
| eqt_a089f350a312e391 | Stability Conditions for Linear Constant Coefficient Difference Equations in Generalized Differenced Form                                 | 10.2307/1913983 | NART25365795 | 461               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365795 |
| eqt_486d389cfbde127c | Keynes and Econometrics: On the Interaction between the Macroeconomic Revolutions of the Interwar Period                                  | 10.2307/1914249 | NART25365865 | 844               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365865 |
| eqt_8e80954ab15a528a | Efficient Investment and Growth Consistency in the Input-Output Frame: An Analytical Contribution                                         | 10.2307/1914112 | NART25366064 | 1758              | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366064 |
| eqt_be48f5ae13f4b0a8 | The United Kingdom Tax System 1968-1970: Some Fixed Point Indications of Its Economic Impact                                              | 10.2307/1914113 | NART25366065 | 512               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366065 |
| eqt_886408931fb1a730 | The Ratio Equilibria and the Core of the Voting Game G(N, W) in a Public Goods Economy                                                    | 10.2307/1913951 | NART25366038 | 476               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366038 |
| eqt_71bc1035c52947a8 | The Specification of Adaptive Expectations in Continuous Time Dynamic Economic Models                                                     | 10.2307/1911534 | NART25365847 | 956               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365847 |
| eqt_00d898ba329a717a | Integrability and Mathematical Programming Models: A Survey and a Parametric Approach                                                     | 10.2307/1914120 | NART25366072 | 770               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366072 |
| eqt_55c76b0dbeb758bd | Proportional Solutions to Bargaining Situations: Interpersonal Utility Comparisons                                                        | 10.2307/1913954 | NART25366041 | 620               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366041 |
| eqt_b3a2606a17b33acc | Rational Expectations and the Natural Rate Hypothesis: Some Consistent Estimates                                                          | 10.2307/1911379 | NART25365731 | 445               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365731 |
| eqt_bc523a4a2254a64b | A Stochastic Optimal Control Technique for Models with Estimated Coefficients                                                             | 10.2307/1912689 | NART25365982 | 570               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365982 |
| eqt_919cce36ec80b723 | On Weights and Measures: Informational Constraints in Social Welfare Analysis                                                             | 10.2307/1913949 | NART25366036 | 789               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366036 |
| eqt_70bcc9c24b8c098c | A Quantity-Quantity Algorithm for Planning under Increasing Returns to Scale                                                              | 10.2307/1912303 | NART25366019 | 426               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366019 |
| eqt_73a5f362fed20535 | Some Finite Sample Properties of Spectral Estimators of a Linear Regression                                                               | 10.2307/1911388 | NART25365740 | 774               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365740 |
