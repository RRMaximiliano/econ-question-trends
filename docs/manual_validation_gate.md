# Manual Validation Gate

- Gate: `proceed`
- First blocking check: ``
- Blocking checks: 0
- Next action: Validation gate passed. Trend outputs can be used with documented caveats.

This gate is the project stoplight for using classification trend outputs as evidence. A descriptive trend report can exist while this gate is blocked, but it should not be treated as final analysis.

## Overview

| metric                        | value                                                                      |
| ----------------------------- | -------------------------------------------------------------------------- |
| validation_gate               | proceed                                                                    |
| first_blocking_check          |                                                                            |
| blocking_checks               | 0                                                                          |
| next_action                   | Validation gate passed. Trend outputs can be used with documented caveats. |
| ready_for_blind_review        | yes                                                                        |
| drifted_articles              | 0                                                                          |
| calibration_rows              | 20                                                                         |
| completed_calibration_labels  | 20                                                                         |
| completed_calibration_rows    | 20                                                                         |
| manual_validation_total_rows  | 300                                                                        |
| completed_manual_labels       | 300                                                                        |
| remaining_manual_labels       | 0                                                                          |
| overlap_rows                  | 30                                                                         |
| completed_overlap_labels      | 30                                                                         |
| pending_adjudication_rows     | 145                                                                        |
| completed_adjudications       | 145                                                                        |
| classification_recommendation | proceed                                                                    |
| validation_status             | available                                                                  |

## Checks

| check                         | status | observed                                                                            | required                                               | next_action       |
| ----------------------------- | ------ | ----------------------------------------------------------------------------------- | ------------------------------------------------------ | ----------------- |
| sample_readiness              | pass   | ready_for_blind_review=yes; drifted_articles=0                                      | ready_for_blind_review=yes; drifted_articles=0         | No action needed. |
| calibration                   | pass   | completed_calibration_rows=20; completed_calibration_labels=20; calibration_rows=20 | completed_calibration_rows>=20                         | No action needed. |
| manual_validation             | pass   | completed_manual_labels=300; total_rows=300; remaining_manual_labels=0              | completed_manual_labels=300; remaining_manual_labels=0 | No action needed. |
| overlap_review                | pass   | completed_overlap_labels=30; overlap_rows=30                                        | completed_overlap_labels>=30                           | No action needed. |
| adjudication                  | pass   | completed_adjudications=145; pending_adjudication_rows=145                          | completed_adjudications=145                            | No action needed. |
| classification_recommendation | pass   | recommendation=proceed                                                              | recommendation=proceed                                 | No action needed. |
