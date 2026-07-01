# ScienceOn Recovery Scan

This scan checks ScienceOn public article metadata for exact DOI/title matches with `citation_abstract`. It does not use title-only snippets, access-challenge pages, or restricted full text.

- Scan rows: 25
- DOI prefixes: `10.2307`
- Accepted candidates: 14
- Skipped rows: 25
- Appended export rows: 14
- Candidates CSV: `outputs/tables/enriched/scienceon_recovery_R004_batch2_candidates.csv`
- Skipped CSV: `outputs/tables/enriched/scienceon_recovery_R004_batch2_skipped.csv`
- Confirmed-source export: `data/intermediate/insufficient_text_recovery_review_exports/R004/recovery_batch_R004_confirmed_source_rows.csv`

## Skip Summary

| status                      | rows |
| --------------------------- | ---- |
| accepted                    | 14   |
| doi_title_match_no_abstract | 11   |

## Accepted Candidates

| article_id           | title                                                                      | doi             | nart_id      | usable_text_chars | source_url                                                                 |
| -------------------- | -------------------------------------------------------------------------- | --------------- | ------------ | ----------------- | -------------------------------------------------------------------------- |
| eqt_f2c52c9cd80ace0c | Capital Accumulation on the Transition Path in a Monetary Optimizing Model | 10.2307/1914010 | NART25366394 | 550               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366394 |
| eqt_5ee3cd4b892015db | Functional Forms, Estimation Techniques and the Distribution of Income     | 10.2307/1914015 | NART25366399 | 623               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366399 |
| eqt_cfe5feffad67684c | General Conditions for Global Intransitivities in Formal Voting Models     | 10.2307/1911951 | NART25366364 | 1427              | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366364 |
| eqt_e3f17f6de00cd691 | Admissible Sets of Utility Functions in Expected Utility Maximization      | 10.2307/1913655 | NART25366100 | 613               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366100 |
| eqt_4e11815068a112a4 | Testing Price Equations for Stability Across Spectral Frequency Bands      | 10.2307/1909754 | NART25366186 | 952               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366186 |
| eqt_5a3f9226ade305ae | A Method for Computing Optimal Decision Rules for a Competitive Firm       | 10.2307/1914236 | NART25366166 | 1004              | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366166 |
| eqt_8a7cb24ebf76da83 | Transversality Condition in a Multi-Sector Economy under Uncertainty       | 10.2307/1914228 | NART25366158 | 625               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366158 |
| eqt_e40d7268fe2c0ad4 | The Estimation of a Simultaneous Equation Generalized Probit Model         | 10.2307/1911443 | NART25366211 | 569               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366211 |
| eqt_4afdc7216f7e920e | On the Time Consistency of Optimal Policy in a Monetary Economy            | 10.2307/1913836 | NART25366235 | 466               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366235 |
| eqt_47754d05267a9acd | An Equilibrium Existence Theorem without Convexity Assumptions             | 10.2307/1914230 | NART25366160 | 592               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366160 |
| eqt_2d7851dcb7ecc8f9 | Double k-Class Estimators of Coefficients in Linear Regression             | 10.2307/1914242 | NART25366172 | 510               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366172 |
| eqt_84147f4a9cf39011 | The Heteroscedastic Linear Model: Exact Finite Sample Results              | 10.2307/1914239 | NART25366169 | 484               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366169 |
| eqt_94176bfbbc5bf661 | A Theory of Competitive Equilibrium in Stock Market Economies              | 10.2307/1914186 | NART25366285 | 949               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366285 |
| eqt_fd8f056a407f2989 | Economic Equilibrium and Catastrophe Theory: An Introduction               | 10.2307/1914231 | NART25366161 | 597               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366161 |
