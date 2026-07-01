# Classification Diagnostics

## Scope

- Classified input: `data/final/articles_classified_pilot.csv`
- Validation input: `data/intermediate/manual_validation_sample.csv`
- Label source: `rule_based`
- Rows: 23903

## Expansion Recommendation

Recommendation: `pause_for_metadata_enrichment`

Reasons:

- Overall abstract coverage is 75.0%, below the 80% threshold.
- Insufficient-text share is 27.8%, above the 20% threshold.
- Manual validation labels are not available yet.

## Key Coverage Metrics

- Overall abstract coverage: 75.0%
- Minimum journal abstract coverage: 62.8%
- Insufficient-text share: 27.8%

## Category Shares By Journal

| journal_short | category          | article_count | group_total | category_share |
| ------------- | ----------------- | ------------- | ----------- | -------------- |
| aer           | causal            | 1679          | 9042        | 0.185689       |
| aer           | insufficient_text | 2534          | 9042        | 0.280248       |
| aer           | other             | 4389          | 9042        | 0.485401       |
| aer           | predictive        | 440           | 9042        | 0.048662       |
| ecta          | causal            | 486           | 4622        | 0.105149       |
| ecta          | insufficient_text | 1832          | 4622        | 0.396365       |
| ecta          | other             | 2131          | 4622        | 0.461056       |
| ecta          | predictive        | 173           | 4622        | 0.03743        |
| jpe           | causal            | 594           | 4507        | 0.131795       |
| jpe           | insufficient_text | 1616          | 4507        | 0.358553       |
| jpe           | other             | 2070          | 4507        | 0.459286       |
| jpe           | predictive        | 227           | 4507        | 0.050366       |
| qje           | causal            | 569           | 2698        | 0.210897       |
| qje           | insufficient_text | 378           | 2698        | 0.140104       |
| qje           | other             | 1575          | 2698        | 0.583766       |
| qje           | predictive        | 176           | 2698        | 0.065234       |
| restud        | causal            | 567           | 3034        | 0.186882       |
| restud        | insufficient_text | 290           | 3034        | 0.095583       |
| restud        | other             | 1989          | 3034        | 0.65557        |
| restud        | predictive        | 188           | 3034        | 0.061964       |

## Category Shares By Year

| publication_year | category          | article_count | group_total | category_share |
| ---------------- | ----------------- | ------------- | ----------- | -------------- |
| 1975             | causal            | 24            | 460         | 0.052174       |
| 1975             | insufficient_text | 262           | 460         | 0.569565       |
| 1975             | other             | 166           | 460         | 0.36087        |
| 1975             | predictive        | 8             | 460         | 0.017391       |
| 1976             | causal            | 23            | 512         | 0.044922       |
| 1976             | insufficient_text | 298           | 512         | 0.582031       |
| 1976             | other             | 183           | 512         | 0.357422       |
| 1976             | predictive        | 8             | 512         | 0.015625       |
| 1977             | causal            | 36            | 487         | 0.073922       |
| 1977             | insufficient_text | 244           | 487         | 0.501027       |
| 1977             | other             | 192           | 487         | 0.394251       |
| 1977             | predictive        | 15            | 487         | 0.030801       |
| 1978             | causal            | 26            | 464         | 0.056034       |
| 1978             | insufficient_text | 222           | 464         | 0.478448       |
| 1978             | other             | 204           | 464         | 0.439655       |
| 1978             | predictive        | 12            | 464         | 0.025862       |
| 1979             | causal            | 47            | 470         | 0.1            |
| 1979             | insufficient_text | 215           | 470         | 0.457447       |
| 1979             | other             | 196           | 470         | 0.417021       |
| 1979             | predictive        | 12            | 470         | 0.025532       |
| 1980             | causal            | 49            | 542         | 0.090406       |
| 1980             | insufficient_text | 226           | 542         | 0.416974       |
| 1980             | other             | 250           | 542         | 0.461255       |
| 1980             | predictive        | 17            | 542         | 0.031365       |
| 1981             | causal            | 38            | 440         | 0.086364       |
| 1981             | insufficient_text | 209           | 440         | 0.475          |
| 1981             | other             | 183           | 440         | 0.415909       |
| 1981             | predictive        | 10            | 440         | 0.022727       |
| 1982             | causal            | 38            | 436         | 0.087156       |
| 1982             | insufficient_text | 167           | 436         | 0.383028       |
| 1982             | other             | 218           | 436         | 0.5            |
| 1982             | predictive        | 13            | 436         | 0.029817       |
| 1983             | causal            | 53            | 435         | 0.121839       |
| 1983             | insufficient_text | 172           | 435         | 0.395402       |
| 1983             | other             | 195           | 435         | 0.448276       |
| 1983             | predictive        | 15            | 435         | 0.034483       |
| 1984             | causal            | 43            | 416         | 0.103365       |
| 1984             | insufficient_text | 175           | 416         | 0.420673       |
| 1984             | other             | 183           | 416         | 0.439904       |
| 1984             | predictive        | 15            | 416         | 0.036058       |

_Only first 40 rows shown._

## Confidence Distribution

| confidence | article_count | group_total | confidence_share |
| ---------- | ------------- | ----------- | ---------------- |
| high       | 729           | 23903       | 0.030498         |
| low        | 7071          | 23903       | 0.295821         |
| medium     | 16103         | 23903       | 0.673681         |

## Insufficient Text Rates

| journal_short | insufficient_text_count | group_total | insufficient_text_share |
| ------------- | ----------------------- | ----------- | ----------------------- |
| aer           | 2534                    | 9042        | 0.280248                |
| ecta          | 1832                    | 4622        | 0.396365                |
| jpe           | 1616                    | 4507        | 0.358553                |
| qje           | 378                     | 2698        | 0.140104                |
| restud        | 290                     | 3034        | 0.095583                |

## Manual Validation

| validation_status | reason                                                |
| ----------------- | ----------------------------------------------------- |
| unavailable       | Validation file has no completed manual_label values. |

## Next Action

Prioritize abstract enrichment and manual validation before using historical classification trends as substantive evidence.
