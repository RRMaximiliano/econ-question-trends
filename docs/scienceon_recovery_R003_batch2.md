# ScienceOn Recovery Scan

This scan checks ScienceOn public article metadata for exact DOI/title matches with `citation_abstract`. It does not use title-only snippets, access-challenge pages, or restricted full text.

- Scan rows: 25
- DOI prefixes: `10.2307`
- Accepted candidates: 15
- Skipped rows: 25
- Appended export rows: 15
- Candidates CSV: `outputs/tables/enriched/scienceon_recovery_R003_batch2_candidates.csv`
- Skipped CSV: `outputs/tables/enriched/scienceon_recovery_R003_batch2_skipped.csv`
- Confirmed-source export: `data/intermediate/insufficient_text_recovery_review_exports/R003/recovery_batch_R003_confirmed_source_rows.csv`

## Skip Summary

| status                      | rows |
| --------------------------- | ---- |
| accepted                    | 15   |
| doi_title_match_no_abstract | 10   |

## Accepted Candidates

| article_id           | title                                                                      | doi             | nart_id      | usable_text_chars | source_url                                                                 |
| -------------------- | -------------------------------------------------------------------------- | --------------- | ------------ | ----------------- | -------------------------------------------------------------------------- |
| eqt_71ffe6da7c1a0ba5 | The Estimation of Linear Differential Equations with Constant Coefficients | 10.2307/1913441 | NART25365822 | 555               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365822 |
| eqt_93ac3f0fbf807988 | Testing for Serial Correlation in Dynamic Simultaneous Equation Models     | 10.2307/1911545 | NART25365858 | 611               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365858 |
| eqt_b9b534ec5181d643 | The Identification and Parameterization of Armax and State Space Forms     | 10.2307/1913438 | NART25365819 | 759               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365819 |
| eqt_b6c2dadb51372097 | Recursive Subaggregation and a Generalized Hypocycloidal Demand Model      | 10.2307/1914062 | NART25365996 | 409               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365996 |
| eqt_eae0182225bc9a76 | Some Generic Properties of Aggregate Excess Demand and an Application      | 10.2307/1911676 | NART25365943 | 432               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365943 |
| eqt_4c8b4773f0b3b47f | Personal Taxation and Portfolio Composition: An Econometric Analysis       | 10.2307/1913433 | NART25365814 | 581               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365814 |
| eqt_ae6114c838b09736 | The Incentives for Price-Taking Behavior in Large Exchange Economies       | 10.2307/1911385 | NART25365737 | 738               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365737 |
| eqt_d8ed8ce8f30ca271 | Estimation of Simultaneous Equation Models with Measurement Error          | 10.2307/1914070 | NART25366004 | 468               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366004 |
| eqt_935a86b4b6bac811 | Weak Priors and Sharp Posteriors in Simultaneous Equation Models           | 10.2307/1912729 | NART25365767 | 556               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365767 |
| eqt_2eb08f4b2796805e | Efficient Estimation and Inference in Large Econometric Systems            | 10.2307/1912314 | NART25366030 | 639               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366030 |
| eqt_d89063f13320a851 | Nonlinearity of Delivered Price Schedules and Predatory Pricing            | 10.2307/1914115 | NART25366067 | 542               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366067 |
| eqt_8f76a0de66a006d5 | Continuity of Equilibria for Production Economies: New Results             | 10.2307/1914110 | NART25366062 | 475               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366062 |
| eqt_ef81617bcc07f400 | Estimating the Returns to Schooling: Some Econometric Problems             | 10.2307/1913285 | NART25365888 | 751               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365888 |
| eqt_fac19e4e0e7f478b | Homogeneous Programming: Saddlepoint and Perturbation Function             | 10.2307/1911685 | NART25365952 | 378               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365952 |
| eqt_da4de11463a5bbb4 | Solutions of General Equilibrium Problems for a Trading World              | 10.2307/1913981 | NART25365793 | 603               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365793 |
