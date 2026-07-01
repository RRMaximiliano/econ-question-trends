# Manual Validation Calibration Guide

This guide is blind to model predictions. It uses only the calibration packet title and abstract to flag text length and keyword cues that reviewers should consider while applying the codebook.

- Rules file for cue extraction: `config/classification_rules.yml`
- Minimum usable classification text: 250

Do not treat cue flags as labels. Reviewers still choose `causal`, `predictive`, `other`, or `insufficient_text` from the primary-focus rule.

## Summary

| section           | value                      | rows |
| ----------------- | -------------------------- | ---- |
| text_status       | usable_text                | 15   |
| text_status       | no_abstract                | 4    |
| text_status       | short_text                 | 1    |
| cue_profile       | no_keyword_cues            | 9    |
| cue_profile       | causal_cues                | 5    |
| cue_profile       | predictive_cues            | 5    |
| cue_profile       | causal_and_predictive_cues | 1    |
| review_difficulty | routine                    | 14   |
| review_difficulty | high                       | 5    |
| review_difficulty | medium                     | 1    |

## Row Guide

| calibration_id | title                                                                                                      | abstract_chars | text_status | cue_profile                | review_difficulty | reviewer_focus                                                                                              |
| -------------- | ---------------------------------------------------------------------------------------------------------- | -------------- | ----------- | -------------------------- | ----------------- | ----------------------------------------------------------------------------------------------------------- |
| CAL0001        | American Inequality: A Macroeconomic History . Jeffrey G. Williamson , Peter Lindert                       | 0              | no_abstract | no_keyword_cues            | high              | Likely insufficient_text unless the title alone is decisive; explain any title-only judgment in notes.      |
| CAL0002        | Real Effects of Academic Research                                                                          | 569            | usable_text | causal_cues                | routine           | Check whether causal effect estimation or interpretation is the main objective, not only motivation.        |
| CAL0003        | Existence of a Continuous Utility Function: An Elementary Proof                                            | 0              | no_abstract | no_keyword_cues            | high              | Likely insufficient_text unless the title alone is decisive; explain any title-only judgment in notes.      |
| CAL0004        | Limited-Purpose Banking—Moving from “Trust Me” to “Show Me” Banking                                        | 676            | usable_text | no_keyword_cues            | routine           | Usually other unless the title or abstract makes causal or predictive focus explicit.                       |
| CAL0005        | Econometric Analysis of Aggregation in the Context of Linear Prediction Models                             | 1482           | usable_text | predictive_cues            | routine           | Check whether prediction, forecasting, classification, or out-of-sample performance is the main objective.  |
| CAL0006        | Ownership Structure, Institutional Organization and Measured X-Efficiency                                  | 906            | usable_text | no_keyword_cues            | routine           | Usually other unless the title or abstract makes causal or predictive focus explicit.                       |
| CAL0007        | The Price Adjustment Mechanism for Rental Housing in the United States                                     | 69             | short_text  | no_keyword_cues            | medium            | Check whether title plus short abstract are enough for a defensible label; otherwise use insufficient_text. |
| CAL0008        | Uncertainty and Shopping Behaviour: An Experimental Analysis                                               | 766            | usable_text | predictive_cues            | routine           | Check whether prediction, forecasting, classification, or out-of-sample performance is the main objective.  |
| CAL0009        | Progress: A Bumpy Road                                                                                     | 0              | no_abstract | no_keyword_cues            | high              | Likely insufficient_text unless the title alone is decisive; explain any title-only judgment in notes.      |
| CAL0010        | Health Care Technologies and Health Care Choices                                                           | 0              | no_abstract | no_keyword_cues            | high              | Likely insufficient_text unless the title alone is decisive; explain any title-only judgment in notes.      |
| CAL0011        | Efficient Tests for General Persistent Time Variation in Regression Coefficients                           | 852            | usable_text | no_keyword_cues            | routine           | Usually other unless the title or abstract makes causal or predictive focus explicit.                       |
| CAL0012        | Making Moves Matter: Experimental Evidence on Incentivizing Bureaucrats through Performance-Based Postings | 790            | usable_text | causal_and_predictive_cues | high              | Apply the primary-focus rule; decide whether causal, predictive, or neither is the main objective.          |
| CAL0013        | The Missing Motivation in Macroeconomics                                                                   | 645            | usable_text | no_keyword_cues            | routine           | Usually other unless the title or abstract makes causal or predictive focus explicit.                       |
| CAL0014        | The Impact of the Transatlantic Slave Trade on Ethnic Stratification in Africa                             | 665            | usable_text | causal_cues                | routine           | Check whether causal effect estimation or interpretation is the main objective, not only motivation.        |
| CAL0015        | Consumer Search and Price Competition                                                                      | 696            | usable_text | causal_cues                | routine           | Check whether causal effect estimation or interpretation is the main objective, not only motivation.        |
| CAL0016        | The Economic Effects of Mafia: Firm Level Evidence                                                         | 689            | usable_text | causal_cues                | routine           | Check whether causal effect estimation or interpretation is the main objective, not only motivation.        |
| CAL0017        | Corporate Financial Policy and Taxation in a Growing Economy                                               | 235            | usable_text | causal_cues                | routine           | Check whether causal effect estimation or interpretation is the main objective, not only motivation.        |
| CAL0018        | Rent Seeking with Bounded Rationality: An Analysis of the All‐Pay Auction                                  | 688            | usable_text | predictive_cues            | routine           | Check whether prediction, forecasting, classification, or out-of-sample performance is the main objective.  |
| CAL0019        | Leasing and Secondary Markets: Theory and Evidence from Commercial Aircraft                                | 1099           | usable_text | predictive_cues            | routine           | Check whether prediction, forecasting, classification, or out-of-sample performance is the main objective.  |
| CAL0020        | Belief Distortions and Macroeconomic Fluctuations                                                          | 877            | usable_text | predictive_cues            | routine           | Check whether prediction, forecasting, classification, or out-of-sample performance is the main objective.  |
