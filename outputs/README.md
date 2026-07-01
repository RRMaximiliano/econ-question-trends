# Outputs Directory

This directory contains generated tables, logs, and figures. It is ignored by git by default.

Expected subdirectories:

- `tables/`: generated CSV outputs.
- `tables/enriched/`: enriched-pipeline tables, diagnostics, validation metrics, and trend summaries.
- `logs/`: collection and refresh logs.
- `figures/`: generated figures when available.

Regenerate outputs with:

```bash
make diagnostics
make validation-gate
make status
make trends
```

