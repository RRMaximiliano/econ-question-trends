# ScienceOn Recovery Scan

This scan checks ScienceOn public article metadata for exact DOI/title matches with `citation_abstract`. It does not use title-only snippets, access-challenge pages, or restricted full text.

- Scan rows: 25
- DOI prefixes: `10.2307`
- Accepted candidates: 15
- Skipped rows: 25
- Appended export rows: 15
- Candidates CSV: `outputs/tables/enriched/scienceon_recovery_R002_batch2_candidates.csv`
- Skipped CSV: `outputs/tables/enriched/scienceon_recovery_R002_batch2_skipped.csv`
- Confirmed-source export: `data/intermediate/insufficient_text_recovery_review_exports/R002/recovery_batch_R002_confirmed_source_rows.csv`

## Skip Summary

| status                      | rows |
| --------------------------- | ---- |
| accepted                    | 15   |
| doi_title_match_no_abstract | 10   |

## Accepted Candidates

| article_id           | title                                                                      | doi             | nart_id      | usable_text_chars | source_url                                                                 |
| -------------------- | -------------------------------------------------------------------------- | --------------- | ------------ | ----------------- | -------------------------------------------------------------------------- |
| eqt_0c01de10ead5190c | Estimation of the Earnings Profile from Optimal Human Capital Accumulation | 10.2307/1914256 | NART25365872 | 658               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365872 |
| eqt_874f54e84cab73d9 | Bayesian Limited Information Analysis of the Simultaneous Equations Model  | 10.2307/1911544 | NART25365857 | 911               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365857 |
| eqt_31ad809fcc5009fc | Observations on the Shape and Relevance of the Spatial Demand Function     | 10.2307/1913076 | NART25365679 | 930               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365679 |
| eqt_c8693a695da4372a | Comparative Advantage and the Distributions of Earnings and Abilities      | 10.2307/1914276 | NART25365665 | 422               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365665 |
| eqt_0178246ab9b3447d | Estimating Regression Models with Multiplicative Heteroscedasticity        | 10.2307/1913974 | NART25365786 | 341               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365786 |
| eqt_9ddf159af64bf49d | Social Choice with Continuous Expression of Individual Preferences         | 10.2307/1913077 | NART25365680 | 362               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365680 |
| eqt_a4c66b0234858612 | A Social Choice Interpretation of the Von Neumann-Morgenstern Game         | 10.2307/1911384 | NART25365736 | 448               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365736 |
| eqt_3d695d0aeb23c114 | An Indirect Test of Complementarity in a Family Labor Supply Model         | 10.2307/1913434 | NART25365815 | 450               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365815 |
| eqt_4bf846df25d96881 | Linear Cross-Equation Constraints and the Identification Problem           | 10.2307/1913418 | NART25365630 | 451               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365630 |
| eqt_be726e4230be4cba | A Small Open Economy with More Produced Commodities than Factors           | 10.2307/1913982 | NART25365794 | 466               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365794 |
| eqt_2aecc52ba0ed5a27 | An Indirect Least Squares Estimator for Overidentified Equations           | 10.2307/1913440 | NART25365821 | 748               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365821 |
| eqt_8d1e028b2b83b229 | Capital Aggregation in a General Equilibrium Model of Production           | 10.2307/1914254 | NART25365870 | 1587              | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365870 |
| eqt_ff1ff05480c0945e | A Stochastic Decentralized Resource Allocation Process: Part II            | 10.2307/1914272 | NART25365661 | 833               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365661 |
| eqt_f0f5ec2daf9360e5 | A Stochastic Decentralized Resource Allocation Process: Part I             | 10.2307/1913581 | NART25365646 | 820               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365646 |
| eqt_74e3c378d69409f2 | Coalitional Fairness of Allocations in Pure Exchange Economies             | 10.2307/1913075 | NART25365678 | 395               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365678 |
