# Manual Validation Calibration Kickoff

- Calibration packet: `data/intermediate/manual_validation_calibration/manual_validation_calibration_packet.csv`
- Calibration guide: `docs/manual_validation_calibration_guide.md`
- Remaining-row guide: `docs/manual_validation_calibration_remaining.md`
- Remaining-row form: `data/intermediate/manual_validation_calibration_forms/manual_validation_calibration_remaining.html`
- Spreadsheet template: `data/intermediate/manual_validation_calibration/manual_validation_calibration_remaining_submission_template.csv`
- Browser forms: `data/intermediate/manual_validation_calibration_forms`
- Submission directory: `data/intermediate/manual_validation_calibration_submissions`

Use this as the handoff for the required 20-row calibration step. Do not edit model labels here; reviewers fill only manual fields.

## Label Decision Cheat Sheet

- Use only the provided title and abstract; ignore model predictions, journal, authors, year, DOI, and outside knowledge.
- Apply the primary-focus rule: choose the label that best describes the paper's main research objective.
- Choose insufficient_text only when the title and abstract are missing, too short, or too vague for a defensible label.
- Choose causal when the main objective is estimating, identifying, or interpreting causal effects.
- Choose predictive when the main objective is prediction, forecasting, classification, nowcasting, or out-of-sample performance.
- Choose other for theory, measurement, institutional narrative, or methods papers that are not primarily causal or predictive.
- When causal and predictive cues both appear, label the main objective and use manual_notes for the ambiguity.

## After Export Commands

After adding reviewer CSV exports to the submissions directory, run these non-importing refresh checks. The validation gate should remain blocked until all 20 calibration rows are complete and disagreements are resolved.

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_manual_validation_calibration.py
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_validation_gate.py
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_human_review_workboard.py
```

## Checklist

| step_order | step                                | status         | action                                                                                        | path_or_command                                                                                                 | note                                                                                                    |
| ---------- | ----------------------------------- | -------------- | --------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| 1          | Read the codebook                   | ready          | Review label definitions and borderline-case guidance before labeling.                        | docs/manual_validation_codebook.md                                                                              | Use only title and abstract for calibration labels.                                                     |
| 2          | Read the calibration guide          | ready          | Review text-status and cue-profile flags without treating them as labels.                     | docs/manual_validation_calibration_guide.md                                                                     | The guide is blind to model predictions and uses only title/abstract text.                              |
| 3          | Open the remaining calibration form | ready          | Open the filtered HTML form and label only rows still needing calibration work.               | data/intermediate/manual_validation_calibration_forms/manual_validation_calibration_remaining.html              | Filtered packet report: docs/manual_validation_calibration_remaining.md                                 |
| 4          | Use spreadsheet template if needed  | ready          | Use this CSV only if labeling in a spreadsheet instead of the browser form.                   | data/intermediate/manual_validation_calibration/manual_validation_calibration_remaining_submission_template.csv | Save a completed copy in the submissions directory; keep the blank template outside submissions.        |
| 5          | Open the full calibration form      | ready          | Use the full HTML form when you need all calibration rows in one view.                        | data/intermediate/manual_validation_calibration_forms/manual_validation_review_packet_batch_001.html            | Packet source: data/intermediate/manual_validation_calibration/manual_validation_calibration_packet.csv |
| 6          | Complete calibration labels         | done           | Fill manual_label, manual_confidence, reviewer_id, and review_date for every calibration row. | data/intermediate/manual_validation_calibration_forms/manual_validation_calibration_remaining.html              | 20 / 20 completed labels recorded.                                                                      |
| 7          | Export reviewer CSV                 | ready          | Use Export CSV from the form and put each reviewer export in the submissions directory.       | data/intermediate/manual_validation_calibration_submissions                                                     | 1 submission CSV files currently found.                                                                 |
| 8          | Refresh calibration summary         | ready          | Rerun the calibration command after adding reviewer submissions.                              | /usr/bin/python3 run_manual_validation_calibration.py                                                           | This updates the agreement summary and disagreement packet.                                             |
| 9          | Resolve calibration disagreements   | not_applicable | Discuss disagreements before assigning the full validation sample.                            | outputs/tables/enriched/manual_validation_calibration_disagreements.csv                                         | 0 disagreement rows currently listed.                                                                   |
| 10         | Recheck validation gate             | ready          | Rerun the validation gate after calibration is complete.                                      | /usr/bin/python3 run_validation_gate.py                                                                         | The gate will remain blocked until calibration labels are complete.                                     |

## Packet Profile

| metric                | value |
| --------------------- | ----- |
| packet_rows           | 20    |
| rows_with_abstract    | 16    |
| rows_without_abstract | 4     |
| min_abstract_chars    | 0     |
| median_abstract_chars | 682   |
| max_abstract_chars    | 1482  |
