# ScienceOn Recovery Scan

This scan checks ScienceOn public article metadata for exact DOI/title matches with `citation_abstract`. It does not use title-only snippets, access-challenge pages, or restricted full text.

- Scan rows: 25
- DOI prefixes: `10.2307`
- Accepted candidates: 14
- Skipped rows: 25
- Appended export rows: 14
- Candidates CSV: `outputs/tables/enriched/scienceon_recovery_R003_batch4_candidates.csv`
- Skipped CSV: `outputs/tables/enriched/scienceon_recovery_R003_batch4_skipped.csv`
- Confirmed-source export: `data/intermediate/insufficient_text_recovery_review_exports/R003/recovery_batch_R003_confirmed_source_rows.csv`

## Skip Summary

| status                      | rows |
| --------------------------- | ---- |
| accepted                    | 14   |
| doi_title_match_no_abstract | 10   |
| abstract_below_threshold    | 1    |

## Accepted Candidates

| article_id           | title                                          | doi             | nart_id      | usable_text_chars | source_url                                                                 |
| -------------------- | ---------------------------------------------- | --------------- | ------------ | ----------------- | -------------------------------------------------------------------------- |
| eqt_e0d5c336b24614a0 | A Recommendation for a Better Tariff Structure | 10.2307/1914114 | NART25366066 | 697               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366066 |
| eqt_c9f46789a6611444 | Disequilibrium Econometrics for Business Loans | 10.2307/1914067 | NART25366001 | 252               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366001 |
| eqt_b7ab9547b5910da3 | On the Theory of Layoffs and Unemployment      | 10.2307/1914058 | NART25365992 | 1182              | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365992 |
| eqt_fea453fdd4352a55 | The Welfare Loss from Price Distortions        | 10.2307/1914258 | NART25365874 | 346               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365874 |
| eqt_c6ade13cc0b34478 | Social Decision Functions and the Veto         | 10.2307/1912677 | NART25365970 | 844               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365970 |
| eqt_495e8bae6e0f2cb7 | Optimal Growth in a Putty-Clay Model           | 10.2307/1911533 | NART25365846 | 322               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365846 |
| eqt_9468363a0f0f3a02 | The Existence of Choice Functions              | 10.2307/1912679 | NART25365972 | 1277              | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365972 |
| eqt_0a9e83ab27a8d5be | Kernels of Preference Structures               | 10.2307/1913288 | NART25365891 | 400               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365891 |
| eqt_b27aff240f1c57d3 | Representable Choice Functions                 | 10.2307/1911543 | NART25365856 | 978               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365856 |
| eqt_0af8e493c4d7ae9d | A Logit Model of Homeownership                 | 10.2307/1914060 | NART25365994 | 273               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365994 |
| eqt_890321b404e2541f | Fisher's Tests Revisited                       | 10.2307/1912721 | NART25365759 | 522               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365759 |
| eqt_4aa6b039504f1368 | Price-Taking Behavior                          | 10.2307/1913957 | NART25366044 | 696               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25366044 |
| eqt_b5f64eec489eca27 | Turnpike Theory                                | 10.2307/1911532 | NART25365845 | 463               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365845 |
| eqt_09f9fa8c31922db8 | Power and Taxes                                | 10.2307/1914063 | NART25365997 | 541               | https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=NART25365997 |
