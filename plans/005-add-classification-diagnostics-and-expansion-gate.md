# Plan 005: Add classification diagnostics and expansion gate

> **Executor instructions**: Follow this plan step by step. Run every verification command and confirm the expected result before moving to the next step. If anything in the "STOP conditions" section occurs, stop and report; do not improvise. When done, update the status row for this plan in `plans/README.md`.
>
> **Drift check (run first)**: `test ! -d .git && echo no-git-repo || git status --short`
> Expected result in the current workspace: `no-git-repo`. If this has become a git repo, inspect changes to the in-scope files before proceeding.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW
- **Depends on**: `plans/001-establish-verification-baseline.md`, `plans/002-add-rule-based-classification-indicators.md`, `plans/003-add-auditable-llm-classification.md`, `plans/004-add-manual-validation-workflow.md`
- **Category**: docs
- **Planned at**: no git repository detected, 2026-06-28

## Why this matters

The project should not expand back to 1975 until the pilot classification is credible. The expansion decision needs a reproducible report that combines metadata coverage, classification shares, confidence, insufficient-text rates, and manual validation accuracy. This plan creates that gate so the project can stop, enrich metadata, or expand in chunks based on evidence.

## Current state

Current diagnostics exist for metadata only:

```python
# code/03_diagnostics/make_phase1_reports.py:134-140
source_coverage = coverage_by_source(source_df)
missingness = missingness_table(articles)
counts = article_counts(articles)

source_coverage.to_csv(project_root / "outputs" / "tables" / "source_coverage_by_journal_year.csv", index=False)
missingness.to_csv(project_root / "outputs" / "tables" / "missingness_by_variable.csv", index=False)
counts.to_csv(project_root / "outputs" / "tables" / "article_counts_by_journal_year.csv", index=False)
```

Current report limitation:

```markdown
# docs/coverage_report.md
Use these diagnostics to decide whether public metadata coverage is adequate for exploratory work before adding restricted or publisher-specific sources.
```

Current data limitation:

```text
Pilot rows: 1,610
Abstract nonmissing share: 0.7702
JEL nonmissing share: 0.0
```

Repo conventions:

- Reports are markdown files under `docs/`.
- Machine-readable tables are CSV files under `outputs/tables/`.
- Generated outputs should be reproducible from scripts.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Unit tests | `python3 -m unittest discover -s tests` | exits 0 |
| Build diagnostics | `python3 run_classification_diagnostics.py --classified data/final/articles_classified_llm_pilot.csv --validation data/intermediate/manual_validation_sample_labeled.csv --output-dir outputs/tables --report docs/classification_diagnostics.md` | exits 0 if labeled validation exists |
| Build diagnostics without labels | `python3 run_classification_diagnostics.py --classified data/final/articles_classified_pilot.csv --output-dir outputs/tables --report docs/classification_diagnostics.md` | exits 0 and marks validation metrics unavailable |
| Report check | `test -f docs/classification_diagnostics.md && test -f outputs/tables/category_shares_by_journal_year.csv && echo diagnostics ok` | prints `diagnostics ok` |

## Scope

**In scope**:

- Create `code/05_analysis/classification_diagnostics.py`.
- Create `run_classification_diagnostics.py`.
- Create `tests/test_classification_diagnostics.py`.
- Create generated tables under `outputs/tables/`.
- Create `docs/classification_diagnostics.md`.
- Update `README.md` with diagnostics command.

**Out of scope**:

- Do not expand metadata collection to earlier years.
- Do not change classifier labels.
- Do not fill manual validation labels.
- Do not create final paper figures beyond basic diagnostic tables.

## Git workflow

If git exists by execution time, use branch `advisor/005-classification-diagnostics`. Do not push or open a PR unless instructed.

## Steps

### Step 1: Implement diagnostics calculations

Create `code/05_analysis/classification_diagnostics.py`.

Required functions:

- `category_column(df)` - prefer final/hybrid category if present, otherwise LLM category with ok status, otherwise rule-based category.
- `confidence_column(df)` - same priority logic for confidence.
- `category_shares(df, group_cols)` - returns counts and shares.
- `insufficient_text_rates(df, group_cols)` - returns rates.
- `confidence_distribution(df, group_cols)` - returns high/medium/low counts and shares.
- `validation_metrics(classified_df, validation_df)` - if manual labels exist, returns confusion matrix and agreement rates.
- `expansion_recommendation(metrics)` - returns `proceed`, `pause_for_metadata_enrichment`, or `pause_for_classifier_revision` plus reasons.

Default expansion gate:

- Pause for metadata enrichment if abstract coverage among classified rows is below 80% overall or below 60% for any journal.
- Pause for classifier revision if high-confidence manual agreement is below 85%, if available.
- Pause if `insufficient_text` share is above 20% overall.
- Proceed only if no pause rule triggers.

Make thresholds configurable in `config/classification_diagnostics.yml`.

**Verify**: `python3 -m unittest discover -s tests` -> exits 0.

### Step 2: Add diagnostics runner

Create `run_classification_diagnostics.py`.

Arguments:

- `--classified`, required
- `--validation`, optional
- `--output-dir`, default `outputs/tables`
- `--report`, default `docs/classification_diagnostics.md`
- `--config`, default `config/classification_diagnostics.yml`

Tables to write:

- `outputs/tables/category_shares_by_year.csv`
- `outputs/tables/category_shares_by_journal.csv`
- `outputs/tables/category_shares_by_journal_year.csv`
- `outputs/tables/category_shares_by_article_type.csv`
- `outputs/tables/confidence_distribution.csv`
- `outputs/tables/insufficient_text_rates.csv`
- `outputs/tables/validation_confusion_matrix.csv` if validation labels exist
- `outputs/tables/validation_metrics.csv` if validation labels exist

Report sections:

- Scope and input files.
- Category shares.
- Confidence distribution.
- Insufficient-text rates.
- Abstract coverage caveats.
- Manual validation metrics, or clear statement that labels are not available yet.
- Expansion recommendation with reasons.
- Specific next action: expand, enrich metadata, revise prompt/rules, or label validation sample.

**Verify**: run one of the diagnostics commands above depending on available inputs.

### Step 3: Add tests

Create `tests/test_classification_diagnostics.py`.

Test cases:

- Category share sums equal 1 within each group.
- Category column selection prefers LLM ok labels over rule labels when available.
- Rows with `llm_status != ok` fall back to rule labels.
- Validation confusion matrix includes all expected categories.
- Expansion recommendation pauses when insufficient-text share is too high.
- Expansion recommendation says validation unavailable when no manual labels are present.

**Verify**: `python3 -m unittest discover -s tests` -> exits 0.

### Step 4: Document the expansion gate

Update `README.md` with the diagnostics command.

Create or update `docs/classification_diagnostics.md` by running the diagnostics script. Ensure the report clearly states whether the recommendation is based on rule-only, LLM, or manually validated labels.

**Verify**: `sed -n '1,260p' docs/classification_diagnostics.md` -> includes an expansion recommendation and the input file names.

## Test plan

- Unit tests in `tests/test_classification_diagnostics.py`.
- Existing tests remain passing.
- Diagnostics runner works with no validation labels and marks validation metrics unavailable.
- Diagnostics runner works with a labeled validation file once available.

## Done criteria

- [ ] `python3 -m unittest discover -s tests` exits 0.
- [ ] Diagnostics runner exits 0 on the best available classified input.
- [ ] `docs/classification_diagnostics.md` exists.
- [ ] Required diagnostic CSVs exist under `outputs/tables/`.
- [ ] Report contains one of: `proceed`, `pause_for_metadata_enrichment`, or `pause_for_classifier_revision`.
- [ ] No earlier-year collection has been started in this plan.
- [ ] `plans/README.md` row for 005 is updated.

## STOP conditions

Stop and report if:

- No classified input exists.
- Category/confidence columns cannot be resolved unambiguously.
- Manual validation file exists but lacks `manual_label`.
- The computed recommendation would require changing thresholds without user approval.
- You need to modify collection scripts to complete diagnostics.

## Maintenance notes

This report is the checkpoint before going back to 1975. Reviewers should not accept historical expansion until this report names the current label source, validation status, missing-text rates, and the reason for the recommendation.
