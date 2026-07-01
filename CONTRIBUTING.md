# Contributing

This is a research-code repository. Contributions should preserve reproducibility and auditability.

## Expectations

- Run `make test` before submitting changes.
- Use top-level `run_*.py` scripts for workflow entry points.
- Keep raw, intermediate, final, and output data artifacts out of git unless a specific replication release requires them.
- Do not manually edit classification outcome columns in final datasets.
- Preserve source provenance for recovered abstracts.
- Document changes that alter scope, classification rules, validation thresholds, or trend outputs.

## Suggested Checks

```bash
make test
make diagnostics
make validation-gate
```

If data artifacts are not available locally, run the test suite and describe which data-dependent commands could not be run.
