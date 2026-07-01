# Plan 011: Scale Insufficient-Text Recovery Beyond R001 With Source-Route Experiments

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report rather than improvising. When done, update the status row for this
> plan in `plans/README.md`.
>
> **Drift check (run first)**:
>
> ```bash
> test -f plans/010-expand-insufficient-text-with-evidence-tiers.md \
>   && test -f docs/evidence_tier_policy.md \
>   && test -f docs/recovery_impact_report.md \
>   && test -f outputs/tables/enriched/recovery_source_experiments.csv \
>   && test -f outputs/tables/enriched/insufficient_text_source_route_matrix.csv \
>   && echo no-git-repo-current-files-present
> ```
>
> Expected result in the current workspace: `no-git-repo-current-files-present`.
> This workspace is not currently a git repository, so no commit SHA is
> available for drift comparison. If the workspace has become a git repo, run
> `git status --short` and inspect any changes under the in-scope paths before
> proceeding.

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: MED
- **Depends on**: `plans/010-expand-insufficient-text-with-evidence-tiers.md`
- **Category**: direction
- **Planned at**: no git repo detected, 2026-06-30

## Why This Matters

The remaining `insufficient_text` rows are not random. They are concentrated
in older journal-decade cells, especially older AER, Econometrica, and JPE
records, so expanding the sample mechanically can distort the historical trend
the project is trying to measure. The next step is not a broad 1975-2025 scrape;
it is a sequence of small source-route experiments with explicit stop rules,
evidence tiers, and before/after impact measurement.

The target is to improve classification coverage while preserving the audit
trail: recovered text can move a row out of `insufficient_text`, but no reviewer
or script should directly assign `causal`, `predictive`, or `other`.

## Current State

Relevant files and roles:

- `plans/010-expand-insufficient-text-with-evidence-tiers.md` - current R001
  execution plan for evidence-tiered recovery.
- `docs/evidence_tier_policy.md` - shared policy defining importable tiers:
  `tier_a_formal_abstract`, `tier_b_source_description`, and
  `tier_c_first_page_abstract_or_intro`.
- `docs/recovery_batch_R001_kickoff_packet.md` - 20-row first-session R001
  recovery handoff.
- `outputs/tables/enriched/recovery_batch_R001_review_queue_summary.csv` -
  active R001 tier counts after first imports.
- `outputs/tables/enriched/recovery_source_experiments.csv` - ranked experiment
  queue for R001, source-template spikes, and credentialed API passes.
- `outputs/tables/enriched/insufficient_text_source_route_matrix.csv` -
  source-route status by lane and DOI prefix.
- `outputs/tables/enriched/recovery_cell_targets.csv` - journal-decade cells
  ranked by remaining missingness and recovery need.
- `outputs/tables/enriched/evidence_tier_sensitivity_overall.csv` - robustness
  table showing how current labels change under formal-abstract-only and
  no-recovered-text scenarios.

Current metrics from local artifacts:

- Remaining recovery queue: 3,806 rows.
- Current validation gate: `blocked_calibration`; calibration progress is
  `0 / 20`, so trend outputs remain descriptive until calibration is complete.
- Recent 2023-2025 top-five queue: already resolved; current recent queue is 0.
- R001 active ranked queue: 71 rows after twenty-two accepted R001 recovery-review
  imports.
- R001 active quick-win tiers: 11 near-threshold partial rows, 2 suspect
  boilerplate replacement rows, 3 deeper partial-extension rows, 41 manual
  metadata rows, and 14 blocked/suspect PDF metadata rows.
- Current staged R001 rows: 0 import-ready rows and 0 preflight errors.
- Current recovered-tier sensitivity: 184 rows have recovered text tiers; the
  formal-abstract-only cut demotes 82 non-tier-A rows and raises scoped
  `insufficient_text` share from 18.7027% to 19.1057%.
- Largest route units: `openalex_or_title_search` 1,474 rows, `10.2307` 1,022
  rows, `10.1086` 780 rows, `partial_short_text_extension` 468 rows,
  `10.1257` 238 rows, and `10.1111` 138 rows.
- Highest target cells include AER 1980, Econometrica 1980, AER 1990,
  Econometrica 1970, JPE 1980, AER 1970, JPE 1970, and QJE 1970.

## Commands You Will Need

| Purpose | Command | Expected on success |
|---|---|---|
| Full handoff refresh | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_human_review_refresh.py` | exits 0 and refreshes calibration, recovery, staging, preflight, project status, and workboard artifacts |
| Recovery source experiments | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_impact_report.py` | exits 0 and refreshes `docs/recovery_impact_report.md` plus `outputs/tables/enriched/recovery_source_experiments.csv` |
| Source-route matrix | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_insufficient_text_expansion_plan.py` | exits 0 and refreshes expansion lanes, DOI-prefix decisions, and attempt summaries |
| R001 review queue | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_review_queue.py` | exits 0 and refreshes tiered packets |
| Stage completed exports | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_tiered_stage.py` | exits 0 and writes staged split summary |
| Preflight staged rows | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_split_preflight.py --split-summary outputs/tables/enriched/recovery_batch_R001_staged_split_summary.csv` | exits 0; completed rows have 0 preflight errors |
| Import completed partial rows | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_import_abstract_backfill.py --input data/intermediate/insufficient_text_recovery_staged/R001/insufficient_text_recovery_batch_R001_ready_partial_text_extension.csv --skip-empty-abstracts --require-source-metadata --fail-on-errors` | exits 0 after a dry run has passed |
| Reclassify | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_classification_pilot.py --input data/final/articles_enriched_pilot.csv --output data/final/articles_classified_enriched_pilot.csv` | exits 0 |
| Diagnostics | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_classification_diagnostics.py --classified data/final/articles_classified_enriched_pilot.csv --validation data/intermediate/manual_validation_sample.csv --output-dir outputs/tables/enriched --report docs/classification_diagnostics_enriched.md` | exits 0 |
| Validation gate | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_validation_gate.py` | exits 0; expected gate remains `blocked_calibration` until calibration labels exist |
| Tests | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest discover -s tests` | exits 0; current baseline is 293 tests |

Use `/usr/bin/python3` in this workspace.

## Scope

**In scope**:

- Existing R001 recovery review exports, staged files, reports, and output
  tables.
- Bounded source-route experiments that inspect public metadata, source records,
  public article PDFs, or API metadata.
- Recovery and diagnostics reports under `docs/` and `outputs/tables/enriched/`.
- Evidence-tier and route-yield decisions used to decide whether to scale.

**Out of scope**:

- Do not lower the 250-character usable-text threshold to make rows pass.
- Do not classify from title-only evidence.
- Do not hand-edit `causal_predictive_category`.
- Do not scrape restricted full text or bypass JSTOR, publisher, or society
  access challenges.
- Do not scale a DOI/source route before a bounded probe produces accepted
  importable evidence.
- Do not start the full 1975-2025 recovery sweep until R001 yield, calibration,
  and source-route stop rules are reviewed.

## Git Workflow

- This workspace is not currently a git repository. If the executor is working
  in a git checkout, use a branch named
  `advisor/011-scale-insufficient-text-recovery`.
- Do not push or open a PR unless the operator explicitly asks for it.

## Steps

### Step 1: Lock The Evidence And Validation Gates

Before expanding recovery, confirm the rules that protect the analysis:

1. Only tiers A, B, and C are importable as classification text.
2. Tier D title-only evidence can guide triage but cannot enter the final
   classification file.
3. Every completed row needs source provenance: `source` plus `source_url` or
   `source_record_id`.
4. The 20-row calibration packet remains the blocker for analysis-ready trend
   claims, even if more text is recovered.

**Verify**:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_evidence_tier_policy.py
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_project_status.py
```

Expected result: evidence policy still lists tiers A/B/C as importable, tiers
D/E as non-importable, and project status still identifies calibration as the
blocking validation gate unless reviewers have completed calibration.

### Step 2: Finish A Measured R001 Mini-Batch Before Scaling

Use the current 20-row R001 kickoff packet as the next measured unit. Work rows
in this order:

1. `tier_1_partial_near_threshold` rows, because these need the least new text.
2. `tier_2_partial_replace_suspect_text` rows, but replace boilerplate rather
   than extending it.
3. `tier_3_partial_extension` rows from explicit source metadata.
4. Manual metadata rows only when a source gives article-specific content, not
   only a citation.

For each accepted row, record the evidence tier and exact source. For each
rejected row, record why it remains unresolved: no abstract available,
citation-only record, access challenge, blocked PDF, title-only snippet, or
ambiguous match.

**Verify**:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_tiered_stage.py
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_split_preflight.py --split-summary outputs/tables/enriched/recovery_batch_R001_staged_split_summary.csv
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_action_progress.py
```

Expected result: any completed rows are import-ready with 0 stage/preflight
errors. Empty rows are skipped, not imported.

### Step 3: Import, Reclassify, And Measure R001 Yield

Before import, write a `before_R001_scale_check` snapshot. Dry-run each staged
CSV before applying it. After import, reclassify and write an
`after_R001_scale_check` snapshot.

**Verify**:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_impact_report.py --snapshot-label before_R001_scale_check --write-snapshot
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_import_abstract_backfill.py --input data/intermediate/insufficient_text_recovery_staged/R001/insufficient_text_recovery_batch_R001_ready_partial_text_extension.csv --skip-empty-abstracts --dry-run --require-source-metadata
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_import_abstract_backfill.py --input data/intermediate/insufficient_text_recovery_staged/R001/insufficient_text_recovery_batch_R001_ready_partial_text_extension.csv --skip-empty-abstracts --require-source-metadata --fail-on-errors
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_import_abstract_backfill.py --input data/intermediate/insufficient_text_recovery_staged/R001/insufficient_text_recovery_batch_R001_ready_manual_metadata.csv --skip-empty-abstracts --dry-run --require-source-metadata
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_import_abstract_backfill.py --input data/intermediate/insufficient_text_recovery_staged/R001/insufficient_text_recovery_batch_R001_ready_manual_metadata.csv --skip-empty-abstracts --require-source-metadata --fail-on-errors
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_classification_pilot.py --input data/final/articles_enriched_pilot.csv --output data/final/articles_classified_enriched_pilot.csv
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_classification_diagnostics.py --classified data/final/articles_classified_enriched_pilot.csv --validation data/intermediate/manual_validation_sample.csv --output-dir outputs/tables/enriched --report docs/classification_diagnostics_enriched.md
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_impact_report.py --snapshot-label after_R001_scale_check --write-snapshot --compare-to before_R001_scale_check
```

Expected result: the impact report records how many rows were imported, how
many left `insufficient_text`, and which categories they entered after
reclassification.

### Step 4: Choose The Next Source Route By Yield, Not Size

After the R001 mini-batch, choose one next route at a time. Use this order
unless the measured yield says otherwise:

1. **Partial short text extension**: highest-confidence manual route because
   rows already have some article text. Prioritize weak target cells, especially
   Econometrica 1980, Econometrica 1970, QJE 1970, and older AER cells.
2. **Reachable public OA PDF first pages**: use only public, verified PDFs and
   import only formal abstracts or first-page abstract/intro text.
3. **Exact source-description probes**: for legacy DOI families such as
   `10.2307` and `10.1086`, test deterministic public metadata pages or
   source-record pages in small samples. Accept only article-specific
   descriptions, and record explicit "no abstract available" pages as blocked.
4. **Credentialed API passes**: use Semantic Scholar or Unpaywall only in
   bounded batches and only after required keys/contact metadata are available.
5. **Publisher/source templates**: add or scale a route only after a bounded
   sample proves that it returns article-specific abstract text without access
   challenges.

Do not pick a route only because it has many rows. A 1,022-row unsupported
route is lower priority than a smaller route with repeatable import-ready
evidence.

**Verify**:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_impact_report.py
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_insufficient_text_expansion_plan.py
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_cell_targets.py
```

Expected result: the chosen next route appears in the experiment queue or
expansion plan, and target-cell context explains why that route is next.

### Step 5: Apply Scale/Stop Thresholds To Every Route

For each route experiment, start with 10-20 representative rows from the target
cells. Record attempted rows, import-ready rows, evidence tier mix, stage errors,
preflight errors, rows leaving `insufficient_text`, and classification movement.

Scale a route only if all of these hold:

- At least 30% of attempted rows produce import-ready evidence in the first
  10-20 row sample, or the route has a compelling target-cell reason to keep
  testing.
- Stage and preflight error rates are 0 after ordinary reviewer corrections.
- At least half of imported rows leave `insufficient_text` after
  reclassification.
- The route's accepted text is mostly tier A or B. Tier C can remain in the main
  file only if the formal-abstract-only robustness output is refreshed and
  reported.

Stop or pause a route if any of these hold:

- 10 representative URLs produce 0 abstracts/PDF candidates.
- Most responses are access challenges, citation-only records, no-abstract
  pages, title-only snippets, or blocked PDFs.
- The route requires scraping restricted full text.
- Accepted rows cluster in cells that are already below the 20% missingness
  target while worse cells remain untouched.

**Verify**:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_impact_report.py
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_classification_diagnostics.py --classified data/final/articles_classified_enriched_pilot.csv --validation data/intermediate/manual_validation_sample.csv --output-dir outputs/tables/enriched --report docs/classification_diagnostics_enriched.md
```

Expected result: the after/before impact report and evidence-tier sensitivity
tables give enough information to continue, pause, or stop the route.

### Step 6: Gate The Full 1975-2025 Expansion

Do not launch a broad historical recovery pass until all of these are true:

- Calibration packet is complete and the validation gate no longer blocks on
  calibration.
- At least one R001 before/after impact comparison exists.
- Source-route yield has been measured for the first R001 mini-batch and at
  least one non-R001 route or source-template sample.
- The next batch is selected by target-cell need, not just by source
  convenience.
- `evidence_tier_sensitivity_overall.csv` and the by-year/by-journal sensitivity
  outputs have been refreshed.

**Verify**:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_validation_gate.py
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_project_status.py
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_human_review_workboard.py
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest discover -s tests
```

Expected result: the workboard identifies the next human/recovery task, tests
pass, and project status no longer treats calibration as unresolved before the
team uses trend outputs as analysis-ready.

## Test Plan

- Run the full suite after any import, helper-code change, or classification
  refresh:

  ```bash
  PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest discover -s tests
  ```

- If new route-yield code is added, add focused tests proving:
  - title-only evidence never becomes importable recovered text;
  - route experiments record stopped routes without importing them;
  - evidence tiers survive staging, import, reclassification, and diagnostics;
  - formal-abstract-only sensitivity demotes non-tier-A rows without altering
    the baseline article file.

## Done Criteria

All must hold:

- [ ] R001 mini-batch has a before/after impact report.
- [ ] At least one next route is selected from measured yield plus target-cell
      need.
- [ ] Every imported row has source provenance and importable evidence tier.
- [ ] Title-only and blocked evidence remains outside the final classification
      file.
- [ ] Classification diagnostics and evidence-tier sensitivity outputs are
      refreshed after imports.
- [ ] The validation gate and human-review workboard are refreshed before using
      trend outputs.
- [ ] `plans/README.md` status row is updated.

## STOP Conditions

Stop and report back if:

- The user decides tier B source descriptions or tier C public first-page text
  should move from the main classification file to sensitivity-only analysis.
- A proposed route requires restricted full-text scraping or access-challenge
  bypassing.
- A source route produces title-only, citation-only, or no-abstract records but
  no importable text in the first 10 representative rows.
- Preflight reports provenance or evidence-tier errors for completed rows.
- Reclassification creates validation sample drift that readiness reports as
  unresolved.
- The next expansion route would mostly recover already-low-missingness cells
  while critical older cells remain untreated.

## Maintenance Notes

- Keep source-route yield results visible in reports. Without route-level yield,
  the project can accidentally spend most effort on the largest but least
  productive DOI prefix.
- Report trend results with recovered-tier sensitivity. The main labels can use
  tiers A/B/C under the current policy, but formal-abstract-only and
  no-recovered-text scenarios should be shown whenever historical trends are
  discussed.
- Treat calibration as a separate gate from text recovery. More text improves
  coverage, but it does not by itself validate the causal/predictive/other
  classifier.
