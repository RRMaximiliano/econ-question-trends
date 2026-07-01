# Plan 012: Finish R002 ScienceOn Recovery And Decide Scale-Up Gates

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report rather than improvising. When done, update the status row for this
> plan in `plans/README.md`.
>
> **Drift check (run first)**:
>
> ```bash
> test -f run_scienceon_recovery_scan.py \
>   && test -f code/06_enrich/scienceon_recovery_scan.py \
>   && test -f outputs/tables/enriched/scienceon_recovery_R002_batch3_candidates.csv \
>   && test -f data/intermediate/insufficient_text_recovery_review_exports/R002/recovery_batch_R002_confirmed_source_rows.csv \
>   && test -f data/intermediate/abstract_backfill_import_history.csv \
>   && echo no-git-repo-r002-scienceon-files-present
> ```
>
> Expected result in the current workspace:
> `no-git-repo-r002-scienceon-files-present`. This workspace is not currently a
> git repository, so no commit SHA is available for drift comparison. If the
> workspace has become a git repo, run `git status --short` and inspect changes
> under all in-scope paths before proceeding.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: `plans/011-scale-insufficient-text-recovery-beyond-r001.md`
- **Category**: direction
- **Planned at**: no git repo detected, 2026-06-30

## Why This Matters

R002 has produced a high-yield public-metadata route for legacy `10.2307`
articles: ScienceOn exact DOI/title matches with `citation_abstract` metadata.
That can reduce `insufficient_text`, but only if the accepted rows move through
the same staging, preflight, import, reclassification, diagnostics, and impact
gates as manual recovery rows. The current classified file is stale relative to
R002 imports, so no causal/predictive/other counts should be interpreted until
R002 batch3 is imported and the classifier is rerun.

This plan finishes the current R002 ScienceOn batch, refreshes the analysis
state, and defines scale/stop rules before applying the route to broader
1975-2025 recovery.

## Current State

Relevant files and roles:

- `run_scienceon_recovery_scan.py` - CLI wrapper for the ScienceOn recovery
  scanner.
- `code/06_enrich/scienceon_recovery_scan.py` - scanner implementation. It
  accepts only exact DOI/title matches with `citation_abstract` and at least
  250 usable text characters.
- `outputs/tables/enriched/scienceon_recovery_R002_candidates.csv` - R002
  ScienceOn batch1 candidates.
- `outputs/tables/enriched/scienceon_recovery_R002_batch2_candidates.csv` -
  R002 ScienceOn batch2 candidates.
- `outputs/tables/enriched/scienceon_recovery_R002_batch3_candidates.csv` -
  R002 ScienceOn batch3 candidates, not yet imported.
- `data/intermediate/insufficient_text_recovery_review_exports/R002/recovery_batch_R002_confirmed_source_rows.csv`
  - cumulative R002 confirmed-source export; currently 32 rows.
- `data/intermediate/abstract_backfill_import_history.csv` - cumulative import
  history; currently 80 rows, including 22 imported R002 rows.
- `outputs/tables/enriched/recovery_batch_R002_split_summary.csv` - active
  R002 split packet summary used by staging and preflight.
- `data/final/articles_enriched_pilot.csv` - enriched article text file updated
  by imports.
- `data/final/articles_classified_enriched_pilot.csv` - classified enriched
  file. Current counts are stale relative to R002 batch2/batch3 work until
  reclassification runs.

Current measured facts from local artifacts:

- R002 ScienceOn batch1 scanned 25 rows, accepted 7 tier-A formal abstracts.
- R002 ScienceOn batch2 scanned 25 rows, accepted 15 tier-A formal abstracts.
- R002 ScienceOn batch3 scanned 25 rows, accepted 10 tier-A formal abstracts.
- Combined R002 ScienceOn acceptance so far is 32 / 75 scanned rows.
- Batch3 candidates are all `ready_manual_metadata`,
  `tier_4_manual_metadata_has_context`, and `tier_a_formal_abstract`.
- Batch3 candidate article IDs are:
  `eqt_6857a60bc23e1976`, `eqt_9dc2bb88954c4d79`,
  `eqt_f54e6fcd8b100165`, `eqt_d46f38e7cc649120`,
  `eqt_c000e5d2f2316eba`, `eqt_ac97ac70e424edf5`,
  `eqt_90e13af513237937`, `eqt_0d1e901d475012b4`,
  `eqt_f57bfd754c3dff82`, and `eqt_72edf44782eb867d`.
- Batch3 skipped rows are 10 `accepted` and 15
  `doi_title_match_no_abstract`.
- Current `data/final/articles_classified_enriched_pilot.csv` counts are
  stale: `causal=3960`, `predictive=1219`, `other=12286`,
  `insufficient_text=6438`.
- Project status remains `validation_gate=blocked_calibration`; calibration
  progress is 0 / 20. Recovered text can improve labels, but trend claims stay
  descriptive until calibration passes.

## Commands You Will Need

Use `/usr/bin/python3` in this workspace. Prefix Python commands with
`PYTHONDONTWRITEBYTECODE=1`.

| Purpose | Command | Expected on success |
|---|---|---|
| Focused ScienceOn tests | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_scienceon_recovery_scan` | exits 0 |
| Full tests | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest discover -s tests` | exits 0 |
| R002 staging | see Step 2 | current expected `staged_rows=10`, `stage_errors=0` |
| R002 preflight | see Step 2 | current expected `import_ready_rows=10`, `error_rows=0` |
| Dry-run import | see Step 3 | current expected `imported_rows=10`, `error_rows=0`, `dry_run=true` |
| Actual import | see Step 3 | exits 0, `state_update=written` |
| Reclassify | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_classification_pilot.py --input data/final/articles_enriched_pilot.csv --output data/final/articles_classified_enriched_pilot.csv` | exits 0 |
| Diagnostics | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_classification_diagnostics.py --classified data/final/articles_classified_enriched_pilot.csv --validation data/intermediate/manual_validation_sample.csv --output-dir outputs/tables/enriched --report docs/classification_diagnostics_enriched.md` | exits 0 |
| Validation gate | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_validation_gate.py` | exits 0; expected gate remains `blocked_calibration` until calibration labels exist |
| Project status | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_project_status.py` | exits 0 and refreshes `docs/project_status.md` |

## Scope

**In scope**:

- R002 ScienceOn candidate, skipped, export, staged, preflight, import,
  classification, diagnostics, recovery-progress, and impact artifacts.
- A bounded next ScienceOn scan for R002, using exact DOI/title matching and
  the existing evidence-tier policy.
- Documentation and plan-index updates under `plans/`.

**Out of scope**:

- Do not hand-edit `causal_predictive_category`.
- Do not import title-only snippets, access-challenge pages, restricted full
  text, or ambiguous duplicate-title matches.
- Do not lower the 250 usable-character threshold.
- Do not expand to a full 1975-2025 source sweep until this plan's scale/stop
  thresholds are evaluated.
- Do not treat trend outputs as analysis-ready while
  `validation_gate=blocked_calibration`.

## Git Workflow

- This workspace is not currently a git repository. If the executor is working
  in a git checkout, use a branch named
  `advisor/012-finish-r002-scienceon-recovery`.
- Do not push or open a PR unless the operator explicitly asks for it.

## Steps

### Step 1: Confirm The Current R002 State

Run this read-only count check before staging:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 - <<'PY'
from pathlib import Path
import csv
from collections import Counter

root = Path("/Users/ifyou/Documents/Projects/econ-question-trends")
paths = {
    "confirmed_export": root / "data/intermediate/insufficient_text_recovery_review_exports/R002/recovery_batch_R002_confirmed_source_rows.csv",
    "batch3_candidates": root / "outputs/tables/enriched/scienceon_recovery_R002_batch3_candidates.csv",
    "batch3_skipped": root / "outputs/tables/enriched/scienceon_recovery_R002_batch3_skipped.csv",
    "import_history": root / "data/intermediate/abstract_backfill_import_history.csv",
}
for label, path in paths.items():
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    print(label, len(rows))
    if label == "batch3_candidates":
        print("split_group", dict(Counter(r.get("split_group", "") for r in rows)))
        print("evidence_tier", dict(Counter(r.get("evidence_tier", "") for r in rows)))
    if label == "batch3_skipped":
        print("status", dict(Counter(r.get("status", "") for r in rows)))
PY
```

Expected current result:

- `confirmed_export 32`
- `batch3_candidates 10`
- `split_group {'ready_manual_metadata': 10}`
- `evidence_tier {'tier_a_formal_abstract': 10}`
- `batch3_skipped 25`
- `status {'accepted': 10, 'doi_title_match_no_abstract': 15}`
- `import_history 80`

If the counts differ because another run already imported batch3, inspect
`data/intermediate/abstract_backfill_import_history.csv` before continuing.

### Step 2: Stage And Preflight The 10 New Batch3 Rows

Stage R002 exports against the active split summary and import history:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_tiered_stage.py \
  --split-summary outputs/tables/enriched/recovery_batch_R002_split_summary.csv \
  --reviewer-input data/intermediate/insufficient_text_recovery_review_exports/R002 \
  --imported-history data/intermediate/abstract_backfill_import_history.csv \
  --output-dir data/intermediate/insufficient_text_recovery_staged/R002 \
  --output-summary outputs/tables/enriched/recovery_batch_R002_staged_split_summary.csv \
  --output-changes outputs/tables/enriched/recovery_batch_R002_tiered_stage_changes.csv \
  --output-errors outputs/tables/enriched/recovery_batch_R002_tiered_stage_errors.csv \
  --report docs/recovery_batch_R002_tiered_stage.md \
  --batch-id R002
```

Expected current result: `staged_rows=10` and `stage_errors=0`.

Then preflight the staged split summary:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_split_preflight.py \
  --split-summary outputs/tables/enriched/recovery_batch_R002_staged_split_summary.csv \
  --output-summary outputs/tables/enriched/recovery_batch_R002_preflight_summary.csv \
  --output-errors outputs/tables/enriched/recovery_batch_R002_preflight_errors.csv \
  --report docs/recovery_batch_R002_preflight.md
```

Expected current result: `import_ready_rows=10` and `error_rows=0`.

Open `outputs/tables/enriched/recovery_batch_R002_preflight_summary.csv` after
preflight. In the current state, the 10 import-ready rows should be in
`ready_manual_metadata`.

### Step 3: Import Batch3, Reclassify, And Measure Impact

Write a before snapshot:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_impact_report.py \
  --snapshot-label before_R002_batch3 \
  --write-snapshot
```

Dry-run the staged manual metadata import:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_import_abstract_backfill.py \
  --input data/intermediate/insufficient_text_recovery_staged/R002/insufficient_text_recovery_batch_R002_ready_manual_metadata.csv \
  --skip-empty-abstracts \
  --dry-run \
  --require-source-metadata
```

Expected current result: `imported_rows=10`, `error_rows=0`,
`dry_run=true`.

Apply the import only after the dry run passes:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_import_abstract_backfill.py \
  --input data/intermediate/insufficient_text_recovery_staged/R002/insufficient_text_recovery_batch_R002_ready_manual_metadata.csv \
  --skip-empty-abstracts \
  --require-source-metadata \
  --fail-on-errors
```

Expected current result: `imported_rows=10`, `error_rows=0`,
`state_update=written`.

Refresh classification, diagnostics, validation gate, and impact:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_classification_pilot.py \
  --input data/final/articles_enriched_pilot.csv \
  --output data/final/articles_classified_enriched_pilot.csv

PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_classification_diagnostics.py \
  --classified data/final/articles_classified_enriched_pilot.csv \
  --validation data/intermediate/manual_validation_sample.csv \
  --output-dir outputs/tables/enriched \
  --report docs/classification_diagnostics_enriched.md

PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_validation_gate.py

PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_impact_report.py \
  --snapshot-label after_R002_batch3 \
  --write-snapshot \
  --compare-to before_R002_batch3
```

Expected result: the classified counts change only through the rule-based
classifier operating on imported text. The validation gate is still expected to
be `blocked_calibration` unless calibration labels have been completed.

### Step 4: Refresh Recovery Planning Artifacts

After import and reclassification, refresh the reports used to decide the next
batch:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_progress.py

PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_insufficient_text_expansion_plan.py

PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_cell_targets.py

PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_project_status.py

PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_human_review_workboard.py
```

Expected result: remaining recovery counts, source-route decisions, target
cells, project status, and workboard all reflect the imported R002 batch3 rows.

### Step 5: Decide Whether To Continue ScienceOn Within R002

Continue one more bounded R002 ScienceOn batch if the updated reports still show
eligible unimported R002 `10.2307` rows. The current route has 32 accepted
tier-A rows out of 75 scanned, which is high enough to justify another 25-row
bounded pass.

Before scanning, combine all previous R002 ScienceOn skipped-audit files into a
single scanned-ID file:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 - <<'PY'
from pathlib import Path
import csv

root = Path("/Users/ifyou/Documents/Projects/econ-question-trends")
inputs = [
    root / "outputs/tables/enriched/scienceon_recovery_R002_skipped.csv",
    root / "outputs/tables/enriched/scienceon_recovery_R002_batch2_skipped.csv",
    root / "outputs/tables/enriched/scienceon_recovery_R002_batch3_skipped.csv",
]
output = root / "outputs/tables/enriched/scienceon_recovery_R002_scanned_ids.csv"
seen = {}
for path in inputs:
    if not path.exists():
        continue
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            article_id = (row.get("article_id") or "").strip()
            if article_id and article_id not in seen:
                seen[article_id] = row
fieldnames = ["article_id", "title", "doi", "status", "nart_id", "abstract_chars", "usable_text_chars", "source_url", "detail"]
output.parent.mkdir(parents=True, exist_ok=True)
with output.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for row in seen.values():
        writer.writerow({field: row.get(field, "") for field in fieldnames})
print(f"combined_rows={len(seen)}")
print(f"output={output}")
PY
```

Expected current result after batch3: `combined_rows=75`.

Then run one more bounded scan:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_scienceon_recovery_scan.py \
  --action-packet outputs/tables/enriched/recovery_batch_R002_review_queue.csv \
  --split-summary outputs/tables/enriched/recovery_batch_R002_split_summary.csv \
  --confirmed-export data/intermediate/insufficient_text_recovery_review_exports/R002/recovery_batch_R002_confirmed_source_rows.csv \
  --previous-skipped outputs/tables/enriched/scienceon_recovery_R002_scanned_ids.csv \
  --output-candidates outputs/tables/enriched/scienceon_recovery_R002_batch4_candidates.csv \
  --output-skipped outputs/tables/enriched/scienceon_recovery_R002_batch4_skipped.csv \
  --report docs/scienceon_recovery_R002_batch4.md \
  --append-export \
  --timeout-seconds 5 \
  --sleep-seconds 0.05 \
  --max-rows 25 \
  --cache-dir data/intermediate/scienceon_cache/R002
```

Scale rule: import batch4 only if candidates pass the same stage/preflight gates
as batch3. Stop the ScienceOn route for R002 if batch4 accepts fewer than 5
rows out of 25, if exact DOI/title matches mostly lack abstracts, or if network
responses become access challenges rather than public metadata.

### Step 6: Decide Whether To Generalize The Route Beyond R002

Do not jump directly to all 1975-2025 rows. After R002 is exhausted or stopped,
choose one of these paths:

1. **If R002 final ScienceOn yield stays at or above 30%**: run the same
   bounded ScienceOn process on R003, prioritizing weak journal-decade target
   cells from `outputs/tables/enriched/recovery_cell_targets.csv`.
2. **If R002 final ScienceOn yield falls below 30% but remains above 10%**:
   keep ScienceOn as a manual-assist route for `10.2307`, but do not automate a
   broad sweep.
3. **If R002 final ScienceOn yield falls below 10% or begins returning
   access-challenge/error pages**: stop the route and work
   `partial_short_text_extension`, reachable OA PDFs, or source-specific
   `10.1086`/`10.1257` probes instead.

For any R003+ run, preserve the same artifact pattern:

- `outputs/tables/enriched/scienceon_recovery_R003_candidates.csv`
- `outputs/tables/enriched/scienceon_recovery_R003_skipped.csv`
- `docs/scienceon_recovery_R003.md`
- `data/intermediate/insufficient_text_recovery_review_exports/R003/recovery_batch_R003_confirmed_source_rows.csv`

Generate the R003 workplan/split/review queue first if those artifacts do not
already exist.

## Test Plan

Run these after batch3 import and any scanner changes:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_scienceon_recovery_scan

PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest discover -s tests
```

Expected result: both commands exit 0. `pytest` is not available in the current
workspace, so use `unittest`.

## Done Criteria

All must hold:

- [ ] R002 batch3 rows are staged with `stage_errors=0`.
- [ ] R002 batch3 preflight has `import_ready_rows=10` and `error_rows=0`, or
      the plan is updated with the reason counts changed.
- [ ] R002 batch3 import is applied only after a successful dry run.
- [ ] `data/intermediate/abstract_backfill_import_history.csv` includes the 10
      batch3 article IDs.
- [ ] `data/final/articles_classified_enriched_pilot.csv` has been regenerated
      after import.
- [ ] `docs/classification_diagnostics_enriched.md`,
      `docs/manual_validation_gate.md`, `docs/recovery_impact_report.md`,
      `docs/insufficient_text_expansion_plan.md`, and `docs/project_status.md`
      are refreshed after import.
- [ ] The ScienceOn route has a recorded continue/stop decision for R002.
- [ ] `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest discover -s tests`
      exits 0.
- [ ] `plans/README.md` status row for plan 012 is updated.

## STOP Conditions

Stop and report back if:

- Stage or preflight returns any error rows.
- Batch3 stages fewer or more than 10 rows and import history does not explain
  the difference.
- Dry-run import returns any validation errors.
- Any accepted ScienceOn row lacks exact DOI/title match, `citation_abstract`,
  source URL/record ID, or an importable evidence tier.
- Running the classifier after import increases `insufficient_text` for the
  imported article IDs.
- A step requires scraping restricted full text or bypassing access controls.
- Calibration is still blocked and someone asks for final trend claims rather
  than descriptive pilot counts.

## Maintenance Notes

ScienceOn should remain an evidence source, not a label source. Its abstracts
can enter the classification text when they satisfy the tier-A metadata rules,
but the causal/predictive/other label must still be produced by the classifier
and validated through the manual calibration workflow. If this route is later
generalized, keep per-batch candidates/skipped reports so yield and failure
modes remain auditable by journal-decade cell.
