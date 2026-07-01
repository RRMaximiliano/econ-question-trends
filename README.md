# Economics Question Trends

This repository builds a reproducible article-level dataset for studying how the focus of top economics journal articles has shifted across three research-question categories:

- `causal`: papers primarily focused on estimating, identifying, or interpreting causal effects.
- `predictive`: papers primarily focused on prediction, forecasting, classification, predictive performance, or out-of-sample accuracy.
- `other`: papers that do not clearly fit the causal or predictive definitions.

The current working scope is 1975-2025 for five general-interest economics journals: American Economic Review, Quarterly Journal of Economics, Journal of Political Economy, Econometrica, and Review of Economic Studies.

## Current Status

The enriched validation gate currently passes:

- `validation_gate=proceed`
- `completed_manual_labels=300`
- `completed_overlap_labels=30`
- `completed_adjudications=145`
- `classification_recommendation=proceed`

Important caveat: the latest validation pass is AI-assisted and should be described that way unless a human audit is later completed. See [REPLICATION.md](REPLICATION.md) for the validation protocol and reproducibility notes.

## Repository Layout

```text
code/       Source modules grouped by workflow stage.
config/     Journal metadata, source policy, classification rules, and thresholds.
data/       Local data artifacts. Ignored by git by default.
docs/       Protocols, generated reports, workflow notes, and reviewer guides.
outputs/    Generated tables, logs, and figures. Ignored by git by default.
plans/      Implementation plans and project roadmap notes.
prompts/    LLM classification prompts.
tests/      Unit tests for collection, cleaning, classification, enrichment, and validation.
```

## Quick Start

Create an environment and install Python dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Run the test suite:

```bash
make test
```

If your shell's default `python3` does not have the required packages, either activate the virtual environment above or pass an interpreter explicitly:

```bash
make PYTHON=/usr/bin/python3 test
```

Refresh the current validation/status reports from existing local data:

```bash
make status
```

Rebuild the main pilot from saved raw API responses, if those raw artifacts are present locally:

```bash
make reproduce-offline
```

Run the enriched trend tables after the validation gate passes:

```bash
make trends
```

Build the static trend dashboard data:

```bash
make site-data
```

Then open [site/index.html](site/index.html), or serve it locally:

```bash
python3 -m http.server 8765 --directory site
```

## Public Website

The repository includes a static website under [site/](site/) and a GitHub Pages workflow at
[.github/workflows/pages.yml](.github/workflows/pages.yml). The workflow runs the test suite,
packages the dashboard plus selected public documentation, and deploys through GitHub Pages on
pushes to `main`.

First-time publishing steps are documented in [docs/github_pages.md](docs/github_pages.md).

## Replication

Use [REPLICATION.md](REPLICATION.md) as the main replication guide. It documents software requirements, data inputs, environment variables, expected outputs, and the exact command order for:

1. Rebuilding the article panel.
2. Enriching insufficient text.
3. Running classification.
4. Running validation diagnostics and the validation gate.
5. Producing trend tables.

Large raw/intermediate files, PDF caches, API caches, reviewer exports, and generated outputs are intentionally excluded from git. If a public replication package is released, place archived data artifacts under the documented `data/` paths before running the commands.

## Key Reports

- [Project status](docs/project_status.md)
- [Validation gate](docs/manual_validation_gate.md)
- [Classification diagnostics](docs/classification_diagnostics_enriched.md)
- [Manual validation codebook](docs/manual_validation_codebook.md)
- [Evidence tier policy](docs/evidence_tier_policy.md)
- [Trend dashboard](site/index.html)
- [Detailed workflow reference](docs/workflow_reference.md)

## Development

Common commands are available through `make`:

```bash
make help
make test
make diagnostics
make validation-gate
make status
make trends
make site-data
```

Before posting publicly, choose and add a license, archive or document access to replication data artifacts, and decide whether to run a human audit of the AI-assisted validation labels.
