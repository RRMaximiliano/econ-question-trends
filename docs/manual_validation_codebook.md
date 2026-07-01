# Manual Validation Codebook

Use this codebook to manually review the validation sample for causal, predictive, other, and insufficient-text classification.

## Review Inputs

Use only the article title and abstract for the main validation label. Do not use journal prestige, authors, affiliations, DOI, publication year, or outside knowledge of the paper.

The one-file labeling packet is `data/intermediate/manual_validation_review_packet.csv`. The same rows are also split into 50-row reviewer batches under `data/intermediate/manual_validation_batches/`. Local dropdown-based HTML forms are under `data/intermediate/manual_validation_forms/`.

These reviewer files are blind: they include only IDs, title, abstract, and manual-label fields, not the model prediction or rule-matching explanation.

Prediction metadata remains in `data/intermediate/manual_validation_sample.csv` for post-label audit, not for reviewer labeling.

For browser-based labeling, open one of the `.html` batch files, fill the dropdown fields, and use **Export CSV**. The form shows the primary-focus label rubric and a QA count for missing confidence, reviewer IDs, review dates, and invalid dates; use **Set Reviewer** and **Set Today** to fill those fields for labeled rows. Completed labels without confidence, reviewer ID, or ISO review date are rejected by the import/preflight commands. Replace the corresponding batch CSV in `data/intermediate/manual_validation_batches/` with the exported file before running the import command.

After filling the manual fields, run:

```bash
python3 run_apply_validation_labels.py --reviewer-input data/intermediate/manual_validation_batches --dry-run
python3 run_apply_validation_labels.py --reviewer-input data/intermediate/manual_validation_batches
python3 run_classification_diagnostics.py --classified data/final/articles_classified_enriched_pilot.csv --validation data/intermediate/manual_validation_sample.csv --output-dir outputs/tables/enriched --report docs/classification_diagnostics_enriched.md
python3 run_validation_gate.py
```

`run_apply_validation_labels.py` accepts either the one-file packet or a directory of batch CSVs. It rejects invalid labels, invalid confidence values, duplicate reviewer rows, and rows that do not match the validation sample.
Calibration exports are checked against the active `calibration_id`, `validation_id`, and `article_id` packet keys. Multiple reviewers may label the same calibration row, but duplicate completed rows from the same reviewer are rejected.
Use `--dry-run` first to write dry-run status files without modifying `data/intermediate/manual_validation_sample.csv`.

The import command writes `docs/manual_validation_status.md`, `outputs/tables/enriched/manual_validation_completion.csv`, and `outputs/tables/enriched/manual_validation_import_errors.csv`.
The gate command writes `docs/manual_validation_gate.md` and machine-readable gate outputs under `outputs/tables/enriched/`. Treat trend outputs as evidence only when `validation_gate` is `proceed`; otherwise follow the reported `next_action`.

After diagnostics writes `outputs/tables/enriched/validation_adjudication_packet.csv`, fill `adjudicated_label`, `adjudication_notes`, `adjudicator_id`, and `adjudication_date` for any rows requiring resolution. Then run:

```bash
python3 run_apply_adjudication_labels.py --dry-run
python3 run_apply_adjudication_labels.py
python3 run_classification_diagnostics.py --classified data/final/articles_classified_enriched_pilot.csv --validation data/intermediate/manual_validation_sample.csv --output-dir outputs/tables/enriched --report docs/classification_diagnostics_enriched.md
python3 run_validation_gate.py
```

Diagnostics treats `adjudicated_label` as the effective human label when it is present. Completed adjudication rows must include notes, adjudicator ID, ISO adjudication date, and disagreement context from either diagnostics (`manual_label` plus `predicted_label`) or overlap QA (`primary_manual_label` plus `overlap_manual_label`).

Before labeling, run:

```bash
python3 run_manual_validation_readiness.py
```

The readiness report confirms whether the current sample has drifted from `data/final/articles_classified_enriched_pilot.csv` and identifies the next incomplete batch.
It also writes `docs/manual_validation_portal.html`, which is the fastest local start page for reviewers because it links the codebook, status reports, main batch forms, calibration form, and overlap QA form. The portal also shows current completion counts for main labeling, calibration, overlap, adjudication, and drift checks.

For reviewer calibration before the full sample, run:

```bash
python3 run_manual_validation_calibration.py
```

This also writes `docs/manual_validation_calibration_guide.md`, a blind title/abstract-only guide that flags no-abstract rows, competing causal/predictive cue rows, and other calibration difficulty markers. The same guide flags appear inside the calibration HTML form alongside the primary-focus label rubric. Use them to focus attention, not as a source of labels. Each reviewer should export their completed calibration CSV to `data/intermediate/manual_validation_calibration_submissions/`. Rerun the same command to update `docs/manual_validation_calibration.md`, validate submitted packet keys, and refresh the calibration disagreement rows. Discuss those disagreements before assigning the full 300-row sample.

For inter-reviewer quality control, run:

```bash
python3 run_manual_validation_overlap.py
```

The overlap packet is a separate blind second-review packet. Do not import it with `run_apply_validation_labels.py`; use the overlap command to summarize agreement and write disagreement rows for adjudication. The overlap command checks the packet against the active validation sample and rejects stale sample rows, duplicate `overlap_id` values, duplicate validation rows, and row-count drift.

## Labels

Apply a primary-focus rule. Choose the label that best describes the paper's main research objective as stated in the title and abstract, not every method or motivation mentioned.

Use this decision order:

1. If the title and abstract are missing, too short, or too vague to support a defensible label, choose `insufficient_text`.
2. If the main objective is estimating, identifying, or interpreting a causal effect, choose `causal`.
3. If the main objective is prediction, forecasting, classification, nowcasting, or out-of-sample performance, choose `predictive`.
4. Otherwise choose `other`.

When a paper contains both causal and predictive language, label the main objective. For example, a forecasting paper that uses treatment effects only as background is `predictive`; an impact-evaluation paper that reports out-of-sample fit as a robustness check is `causal`.

### `causal`

Use `causal` when the paper is primarily focused on estimating, identifying, or interpreting causal effects.

Examples:

- Estimates treatment effects.
- Uses randomized assignment, a natural experiment, difference-in-differences, regression discontinuity, instrumental variables, or another identification strategy.
- Interprets a policy, shock, intervention, or treatment as causing an outcome.

### `predictive`

Use `predictive` when the paper is primarily focused on prediction, forecasting, classification, predictive performance, or out-of-sample accuracy.

Examples:

- Forecasts macroeconomic, financial, or other outcomes.
- Compares predictive accuracy or out-of-sample performance.
- Builds or evaluates classification, machine-learning, or nowcasting methods.

### `other`

Use `other` when the paper does not clearly fit causal or predictive.

Examples:

- Pure theory.
- Descriptive measurement.
- Institutional or historical narrative without a primary causal or predictive question.
- Methodological work where the abstract does not make causal estimation or prediction the primary focus.

### `insufficient_text`

Use `insufficient_text` when the title and abstract are missing, too short, or too vague to classify reliably.

If the title alone is clearly decisive, note that in `manual_notes`; the project owner should decide whether title-only labels are acceptable before using them in final analysis.

Do not use `insufficient_text` merely because the paper is unfamiliar, technical, or not in your field. Use it only when the provided title and abstract do not contain enough information to apply the primary-focus rule.

## Reviewer Fields

Fill these fields in the validation CSV:

- `manual_label`: one of `causal`, `predictive`, `other`, or `insufficient_text`.
- `manual_confidence`: one of `high`, `medium`, or `low`.
- `manual_notes`: short explanation, especially for ambiguous cases.
- `reviewer_id`: reviewer initials or identifier.
- `review_date`: ISO date, such as `2026-06-28`.

Confidence guidance:

- `high`: the main objective is explicit in the title or abstract.
- `medium`: the label is defensible, but the abstract is broad or contains competing signals.
- `low`: the label is a best judgment from limited or ambiguous text. Use `manual_notes` to explain the ambiguity.

## Disagreements

If multiple reviewers label the same article and disagree, adjudicate the article explicitly. Do not average labels.

The overlap QA report writes disagreement rows to `outputs/tables/enriched/manual_validation_overlap_disagreements.csv`. Fill `adjudicated_label`, `adjudication_notes`, `adjudicator_id`, and `adjudication_date` for those rows before using them as adjudicated evidence.

## Borderline Cases

- Empirical estimate of a treatment effect: usually `causal`.
- Forecasting or out-of-sample performance comparison: usually `predictive`.
- Machine learning used to estimate heterogeneous treatment effects: usually `causal` if treatment-effect interpretation is the main objective.
- Machine learning used to forecast outcomes, classify observations, or optimize predictive accuracy: usually `predictive`.
- A theory paper about causal mechanisms without empirical causal estimation: usually `other`, unless the abstract makes causal interpretation the primary question.
- A macro or finance model with forecasts: `predictive` only if forecasting or predictive performance is a primary objective.
- Structural estimation, calibration, or simulation: usually `other` unless the abstract frames the main result as a causal effect or forecasting exercise.
- Descriptive measurement, data construction, decomposition, or accounting: usually `other` unless it is primarily causal or predictive.
- Missing abstract: usually `insufficient_text`.
