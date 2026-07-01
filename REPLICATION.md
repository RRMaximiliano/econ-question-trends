# Replication Guide

This project builds an article-level panel for five top economics journals and classifies each article into causal, predictive, other, or insufficient-text categories.

## Scope

- Journals: American Economic Review, Quarterly Journal of Economics, Journal of Political Economy, Econometrica, Review of Economic Studies.
- Years: 1975-2025 in the current enriched working dataset.
- Unit of observation: article-level record identified by deterministic `article_id`.
- Main classified file: `data/final/articles_classified_enriched_pilot.csv`.
- Main validation file: `data/intermediate/manual_validation_sample.csv`.

## Software

Required:

- Python 3.9 or newer.
- Python packages in `requirements.txt`.

Optional for PDF text recovery:

- Poppler command-line tools: `pdftotext`, `pdftoppm`.
- Tesseract OCR: `tesseract`.

Optional API keys:

- `OPENAI_API_KEY` for LLM classification experiments.
- `SEMANTIC_SCHOLAR_API_KEY` for higher Semantic Scholar rate limits.

Polite API contact variables:

- `CONTACT_EMAIL`
- `OPENALEX_MAILTO`
- `CROSSREF_MAILTO`

## Data Availability Boundary

The GitHub repository should commit source code, configuration, tests, prompts, and human-readable documentation. It should not commit the full local `data/` or `outputs/` trees by default.

Current local artifact sizes are large:

- `data/raw/`: public API response cache.
- `data/intermediate/`: enrichment caches, reviewer packets, PDF cache, and staging files.
- `data/final/`: analysis-ready article datasets.
- `outputs/`: generated tables, logs, and reports.

For a public replication package, archive these artifacts separately and restore them under the same paths before running status, diagnostics, or trend commands.

## Environment Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Set optional contact metadata before collection or enrichment:

```bash
export CONTACT_EMAIL="you@example.com"
export OPENALEX_MAILTO="you@example.com"
export CROSSREF_MAILTO="you@example.com"
```

## Run Path

### 1. Test The Code

```bash
make test
```

If the default `python3` points to an environment without `PyYAML`, `pandas`, or `requests`, activate the project virtual environment or run:

```bash
make PYTHON=/usr/bin/python3 test
```

### 2. Rebuild From Saved Raw Responses

Use this when `data/raw/crossref/1975_2025_yearly_crossref_20260628T/` and matching OpenAlex raw files are already present:

```bash
make reproduce-offline
```

### 3. Recollect Public Metadata

Use this only when regenerating raw API responses:

```bash
python3 run_phase1_pilot.py --start-year 1975 --end-year 2025
```

### 4. Rebuild Enriched Classification

```bash
python3 run_text_enrichment.py --cached-only --no-merge-existing
python3 run_pdf_text_enrichment.py
python3 run_classification_pilot.py --input data/final/articles_enriched_pilot.csv --output data/final/articles_classified_enriched_pilot.csv
```

Network enrichment commands are intentionally bounded in the workflow reference because external services rate-limit and vary over time.

### 5. Refresh Validation Diagnostics

```bash
make diagnostics
make validation-gate
make status
```

The gate writes:

- `docs/manual_validation_gate.md`
- `outputs/tables/enriched/manual_validation_gate.csv`
- `outputs/tables/enriched/manual_validation_gate_checks.csv`

Trend outputs should be treated as publishable descriptive outputs only when `validation_gate=proceed`.

### 6. Produce Trend Tables

```bash
make trends
```

Trend tables are written under `outputs/tables/enriched/`, with the report at `docs/recent_trend_summary_enriched.md`.

## Validation Protocol

The project has a manual-validation framework:

- 20-row calibration packet.
- 300-row main validation sample.
- 30-row overlap review packet.
- Adjudication packet for classifier-reviewer disagreements.

Current local status:

- Calibration: complete.
- Main validation: complete.
- Overlap review: complete.
- Adjudication: complete.
- Validation gate: proceed.

Caveat: the latest main validation, overlap completion for non-calibration rows, and diagnostic adjudication were completed by Codex as an AI-assisted pass. This is appropriate for pipeline debugging and exploratory trend inspection. For publication, either describe the validation as AI-assisted or complete a human audit subset and report that audit separately.

## Output Map

Primary data artifacts:

- `data/final/articles_pilot.csv`: cleaned article panel before enrichment.
- `data/final/articles_enriched_pilot.csv`: enriched article panel.
- `data/final/articles_classified_enriched_pilot.csv`: enriched article panel with classification fields.
- `data/intermediate/manual_validation_sample.csv`: validation sample and adjudication fields.

Primary reports:

- `docs/project_status.md`: current project dashboard.
- `docs/manual_validation_gate.md`: validation gate status.
- `docs/classification_diagnostics_enriched.md`: validation metrics and disagreement packets.
- `docs/evidence_tier_policy.md`: rules for importable recovered text.
- `docs/workflow_reference.md`: detailed operational notes preserved from the original README.

Primary tables:

- `outputs/tables/enriched/category_shares_by_year.csv`
- `outputs/tables/enriched/category_shares_by_journal_year.csv`
- `outputs/tables/enriched/validation_metrics.csv`
- `outputs/tables/enriched/validation_category_metrics.csv`
- `outputs/tables/enriched/manual_validation_gate.csv`

## Reproducibility Notes

- API-based metadata collection is not bit-for-bit stable over time because public metadata sources update records.
- The offline run path is the preferred computational replication route when raw API response caches are archived.
- PDF/OCR recovery depends on local command-line tools and may vary by tool version.
- Do not manually edit `causal_predictive_category`; use classification, validation, and adjudication workflows.
- Recovered abstracts require source provenance and importable evidence tiers.
