# Plan 010: Expand Insufficient Text With Evidence-Tiered Recovery

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report rather than improvising. When done, update the status row for this
> plan in `plans/README.md`.
>
> **Drift check (run first)**:
>
> ```bash
> test -f docs/recovery_impact_report.md \
>   && test -f docs/recovery_batch_R001_review_queue.md \
>   && test -f outputs/tables/enriched/insufficient_text_expansion_overview.csv \
>   && test -f outputs/tables/enriched/recovery_batch_R001_review_queue_summary.csv \
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
- **Effort**: M
- **Risk**: LOW
- **Depends on**: `plans/007-recover-remaining-insufficient-text.md`,
  `plans/008-add-scope-audit-and-recovery-decision-gate.md`,
  `plans/009-add-insufficient-text-recovery-experiments.md`
- **Category**: direction
- **Planned at**: no git repo detected, 2026-06-29

## Why This Matters

The project can now classify recent top-five economics journal articles, but
the historical expansion is still vulnerable to nonrandom missing text. The
current recovery universe has 3,806 scoped research rows marked
`insufficient_text`, with missingness concentrated in older AER,
Econometrica, and JPE cells. The goal of this plan is to expand classification
text only with auditable, source-confirmed evidence, then measure whether the
extra text changes category shares and validation risk.

This plan deliberately separates text recovery from causal/predictive labeling.
Recovered text may move rows out of `insufficient_text`; it must not become a
manual shortcut for assigning `causal`, `predictive`, or `other`.

## Current State

Relevant files and roles:

- `docs/recovery_impact_report.md` - non-mutating snapshot of the current
  insufficient-text universe, route units, and experiment queue.
- `docs/insufficient_text_expansion_plan.md` - lane-level expansion decisions
  and DOI-prefix route recommendations.
- `docs/recovery_batch_R001_review_queue.md` - ranked 71-row active manual
  recovery queue after twenty-two accepted R001 recovery-review imports; the static split still carries
  93 ready rows for audit context.
- `docs/recovery_batch_R001_tiered_packets.md` - five quick-win packet tiers
  for R001.
- `docs/recovery_batch_R001_cached_evidence.md` - non-mutating local-cache
  audit showing whether R001 rows already have usable cached/source-record
  metadata text.
- `docs/recovery_batch_R001_action_packet.md` - non-mutating reviewer action
  packet combining the recovery queue, source guide, cached-evidence audit, and
  automation audit.
- `docs/recovery_cell_targets.md` - balanced journal-decade recovery target
  table, including current insufficient-text shares, recoveries needed to reach
  the target share, R001 coverage, and the next recovery cell queue.
- `outputs/tables/enriched/recovery_batch_R001_action_packet_index.csv` -
  index of action-group reviewer packets and local browser forms.
- `outputs/tables/enriched/recovery_batch_R001_action_packets/` -
  action-group CSV packets compatible with the existing recovery staging flow.
- `data/intermediate/insufficient_text_recovery_review_forms/R001/actions/` -
  action-group browser forms that show reviewer action, source-to-avoid, cached
  evidence, cell-target priority, and candidate-source context.
- `docs/recovery_batch_R001_action_progress.md` - non-mutating progress report
  showing action-form exports, staged rows, stage errors, and preflight errors
  by action group.
- `data/intermediate/insufficient_text_recovery_review_forms/R001/recovery_batch_R001_action_dashboard.html` -
  local launch dashboard linking action forms, action packets, and progress
  reports.
- `docs/source_route_probe.md` - bounded public-source probe showing most
  sampled DOI landing pages return access challenges rather than abstracts.
- `outputs/tables/enriched/insufficient_text_expansion_overview.csv` -
  current lane overview.
- `outputs/tables/enriched/recovery_batch_R001_review_queue_summary.csv` -
  current R001 tier counts.
- `outputs/tables/enriched/recovery_batch_R001_staged_split_summary.csv` -
  current staged import readiness.

Current metrics from local artifacts:

- Remaining insufficient-text rows in the current snapshot: 3,806.
- Expansion lanes: 8.
- Highest-leverage manual lane: `partial_short_text_extension`, 466 rows, 372
  high-priority rows.
- R001 ready split work: 93 rows, including 38 partial-text-extension rows and
  55 manual-metadata rows. Twenty-two accepted R001 recovery-review rows have now
  been imported and are skipped from the active ranked review queue; seven
  scope-reviewed nonresearch rows are excluded from recovery, leaving 71
  actionable rows.
- R001 clean fastest active tier: 11 `tier_1_partial_near_threshold` rows
  needing a median of 43 characters to reach the 250-character usable-text
  threshold.
- R001 suspect partial tier: 2 `tier_2_partial_replace_suspect_text` rows
  needing a median of 179 characters after stripping boilerplate; current text
  must be replaced, not extended.
- R001 deeper partial tier: 3 `tier_3_partial_extension` rows needing a
  median of 167 characters.
- R001 manual metadata tiers: 41 rows with existing context and 14 rows where
  blocked/suspect PDF routes should not be retried unchanged.
- R001 cached-evidence audit: 71 active rows scanned locally, with no
  cached-import-candidate rows; 11 tier-1 rows only repeat existing short
  OpenAlex text, 2 tier-2 rows repeat suspect JSTOR boilerplate, 41 tier-4 rows
  have no cached text candidate, and 5 tier-5 rows expose only PDF candidates.
- R001 action packet: start with 11 `find_external_extension` rows, then 2
  `replace_boilerplate_from_new_source` rows, then the remaining
  `find_fuller_metadata`, `manual_metadata_search`, `verify_pdf_or_use_metadata`,
  and rate-limit/cache-avoidance groups.
- R001 action packet now carries balanced recovery context for every ready row:
  `cell_target_rank`, `cell_target_level`,
  `cell_recoveries_to_target_share`,
  `cell_projected_share_after_ready_r001`,
  `cell_ready_r001_target_coverage`, and
  `cell_recommended_next_step`.
- R001 action reviewer packets: 7 action-group packets covering all 71 active
  rows; completed exports go to
  `data/intermediate/insufficient_text_recovery_review_exports/R001/` and use
  the same staging and preflight commands as the tiered packets.
- R001 action progress: 7 action groups covering 71 active rows; current state has 0
  exported rows, 0 import-ready rows, 0 stage errors, and 0 preflight errors.
- Balanced recovery target table: 20 target cells, 100 queued example rows,
  1,375 recoveries needed across target cells to reach a 20% insufficient-text
  target share, and 71 active R001 rows inside those target cells.
- Classification now strips known source boilerplate before text-length
  counting and records `classification_text_quality_flags`; raw abstract fields
  remain unchanged for auditability.
- Text enrichment strips known source boilerplate before writing recovered
  abstracts to the article file and records `text_enrichment_quality_flags`.
- Source-route probe: 24 sampled public landing/metadata URLs, 22
  `access_challenge` and 2 `not_found`; no sampled abstracts or PDF
  candidates.
- Largest unresolved route units include `openalex_or_title_search` 1,474
  rows, `10.2307` 1,022 rows, `10.1086` 780 rows, `partial_short_text_extension`
  468 rows, `10.1257` 238 rows, and `10.1111` 138 rows.

Current working rules already documented in the repo:

- Minimum usable classification text is 250 characters.
- Completed recovery rows require `abstract`, `source`, and either
  `source_url` or `source_record_id`.
- Title-only suggestions are allowed for triage and sensitivity only, not final
  causal/predictive/other labels.
- Do not scrape restricted full text or scale routes whose probes only produce
  access challenges.

## Commands You Will Need

| Purpose | Command | Expected on success |
|---|---|---|
| Refresh the full human-review workboard | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_human_review_refresh.py` | exits 0 and refreshes calibration, recovery queue, cell targets, cached-evidence/action packets, staging/preflight status, validation gate, and workboard |
| Review R001 tiers | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_review_queue.py` | exits 0 and refreshes R001 tiered packets |
| Refresh balanced recovery targets | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_cell_targets.py` | exits 0 and writes `docs/recovery_cell_targets.md`, `outputs/tables/enriched/recovery_cell_targets.csv`, and `outputs/tables/enriched/recovery_cell_target_queue.csv` |
| Audit cached evidence and actions | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_cached_evidence.py` | exits 0 and writes `docs/recovery_batch_R001_cached_evidence.md`, `docs/recovery_batch_R001_action_packet.md`, `outputs/tables/enriched/recovery_batch_R001_action_packet_index.csv`, and action-group forms without network calls or imports |
| Stage completed exports | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_tiered_stage.py` | exits 0 and writes staged split summary |
| Preflight staged rows | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_split_preflight.py --split-summary outputs/tables/enriched/recovery_batch_R001_staged_split_summary.csv` | exits 0; completed rows have 0 preflight errors |
| Track action progress | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_action_progress.py` | exits 0 and writes action-group export/stage/preflight progress, target-cell priority rollups, and the local action dashboard without imports |
| Build first-session recovery packet | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_kickoff_packet.py` | exits 0 and writes `docs/recovery_batch_R001_kickoff_packet.md`, `outputs/tables/enriched/recovery_batch_R001_kickoff_packet.csv`, and `data/intermediate/insufficient_text_recovery_review_forms/R001/recovery_batch_R001_kickoff_packet.html` |
| Baseline impact | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_impact_report.py --snapshot-label before_R001 --write-snapshot` | exits 0 and writes a before snapshot |
| Dry-run partial import | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_import_abstract_backfill.py --input data/intermediate/insufficient_text_recovery_staged/R001/insufficient_text_recovery_batch_R001_ready_partial_text_extension.csv --skip-empty-abstracts --dry-run --require-source-metadata` | exits 0; no source/provenance errors |
| Apply partial import | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_import_abstract_backfill.py --input data/intermediate/insufficient_text_recovery_staged/R001/insufficient_text_recovery_batch_R001_ready_partial_text_extension.csv --skip-empty-abstracts --require-source-metadata --fail-on-errors` | exits 0 and imports completed rows |
| Dry-run manual metadata import | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_import_abstract_backfill.py --input data/intermediate/insufficient_text_recovery_staged/R001/insufficient_text_recovery_batch_R001_ready_manual_metadata.csv --skip-empty-abstracts --dry-run --require-source-metadata` | exits 0; no source/provenance errors |
| Apply manual metadata import | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_import_abstract_backfill.py --input data/intermediate/insufficient_text_recovery_staged/R001/insufficient_text_recovery_batch_R001_ready_manual_metadata.csv --skip-empty-abstracts --require-source-metadata --fail-on-errors` | exits 0 and imports completed rows |
| Reclassify | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_classification_pilot.py --input data/final/articles_enriched_pilot.csv --output data/final/articles_classified_enriched_pilot.csv` | exits 0 |
| Diagnostics | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_classification_diagnostics.py --classified data/final/articles_classified_enriched_pilot.csv --validation data/intermediate/manual_validation_sample.csv --output-dir outputs/tables/enriched --report docs/classification_diagnostics_enriched.md` | exits 0 |
| Compare impact | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_impact_report.py --snapshot-label after_R001 --write-snapshot --compare-to before_R001` | exits 0 and reports row movement |
| Gate | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_validation_gate.py` | exits 0; current expected gate remains `blocked_calibration` until calibration labels exist |
| Tests | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest discover -s tests` | exits 0; current baseline in `plans/README.md` is 292 tests |

Use `/usr/bin/python3` in this workspace.

## Scope

**In scope**:

- Existing recovery packets and forms under
  `data/intermediate/insufficient_text_recovery_review_forms/R001/`.
- Completed recovery exports under
  `data/intermediate/insufficient_text_recovery_review_exports/R001/`.
- Staged recovery files under
  `data/intermediate/insufficient_text_recovery_staged/R001/`.
- Existing recovery reports under `docs/` and `outputs/tables/enriched/`.
- Existing command wrappers:
  - `run_recovery_review_queue.py`
  - `run_recovery_cached_evidence.py`
  - `run_recovery_tiered_stage.py`
  - `run_recovery_split_preflight.py`
  - `run_import_abstract_backfill.py`
  - `run_classification_pilot.py`
  - `run_classification_diagnostics.py`
  - `run_recovery_impact_report.py`

**Out of scope**:

- Do not lower `minimum_usable_text_chars`.
- Do not convert title-only suggestions into final labels.
- Do not change `causal_predictive_category` by hand.
- Do not retry blocked PDF URLs unchanged.
- Do not scrape restricted publisher, JSTOR, Wiley, OUP, AEA, Chicago, or
  society full text.
- Do not recover rows in `waiting_scope_review` before scope decisions are
  complete.
- Do not regenerate the main validation sample solely because recovery imports
  changed text; use readiness and gate checks to detect drift.

## Git Workflow

- This workspace is not currently a git repository. If the executor is working
  in a git checkout, use a branch named
  `advisor/010-insufficient-text-evidence-tiers`.
- Do not push or open a PR unless the operator explicitly asks for it.

## Steps

### Step 1: Work R001 In Evidence Tiers

Start with rows that are both high payoff and low ambiguity:

1. Work `tier_1_partial_near_threshold` first: 13 active rows, median 43 characters
   needed.
2. Work `tier_2_partial_replace_suspect_text` second: 2 active rows, median 179
   characters needed after stripping boilerplate. Replace the current text
   from explicit source metadata; do not extend JSTOR/access/rights text.
3. Work `tier_3_partial_extension` third: 7 rows, median 170 characters
   needed.
4. Only then work `tier_4_manual_metadata_has_context`: 41 rows with source
   hints or partial context but no sufficient abstract.
5. Leave `tier_5_manual_metadata_pdf_blocked` until a reviewer can find an
   explicit metadata source that is not the blocked PDF route.

Within each tier, use the action forms' cell-target fields to prioritize rows
from weak journal-decade cells first. Rows with lower `cell_target_rank`, a
`critical` target level, and positive `cell_recoveries_to_target_share` should
take precedence over monitoring cells that are already below the target
insufficient-text share.

For each completed row, fill:

- `abstract`: source-confirmed abstract or source-confirmed short description.
- `source`: source family, for example `JSTOR metadata`, `EconPapers`,
  `publisher metadata`, `OpenAlex`, `EconLit`, or `library index`.
- `source_url` or `source_record_id`.
- reviewer notes when the evidence is a short source description rather than a
  formal abstract.

Do not complete a row if the only evidence is title, citation, access-challenge
page, search result snippet, or an inaccessible PDF.

**Verify**:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_cell_targets.py
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_cached_evidence.py
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_tiered_stage.py
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_split_preflight.py --split-summary outputs/tables/enriched/recovery_batch_R001_staged_split_summary.csv
```

Expected result: action packets include nonempty cell-target context for R001
rows, and completed rows have 0 preflight errors. Empty rows are ignored or
remain unready; they should not create import errors.

### Step 2: Import Only Source-Ready Rows

Write a `before_R001` impact snapshot before importing. Then dry-run and apply
the partial-extension staged file before the manual-metadata staged file.

Partial extensions should usually go first because they are less ambiguous:
they extend already-present text rather than finding text from scratch.

**Verify**:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_impact_report.py --snapshot-label before_R001 --write-snapshot
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_import_abstract_backfill.py --input data/intermediate/insufficient_text_recovery_staged/R001/insufficient_text_recovery_batch_R001_ready_partial_text_extension.csv --skip-empty-abstracts --dry-run --require-source-metadata
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_import_abstract_backfill.py --input data/intermediate/insufficient_text_recovery_staged/R001/insufficient_text_recovery_batch_R001_ready_partial_text_extension.csv --skip-empty-abstracts --require-source-metadata --fail-on-errors
```

Expected result: dry run and import exit 0. If no rows were completed, the
commands should skip empty abstracts rather than importing placeholders.

### Step 3: Reclassify And Measure What Changed

After any import, rerun classification, diagnostics, progress, and impact
comparison. The unit of success is not just "more text imported"; it is rows
moving from `insufficient_text` into an auditable category without creating
validation drift.

Measure at least:

- number of imported rows;
- number of rows crossing the 250-character threshold;
- number of rows leaving `insufficient_text`;
- category movement into `causal`, `predictive`, or `other`;
- change in insufficient-text share by journal and decade;
- whether any manual validation sample drift appears.

**Verify**:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_classification_pilot.py --input data/final/articles_enriched_pilot.csv --output data/final/articles_classified_enriched_pilot.csv
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_classification_diagnostics.py --classified data/final/articles_classified_enriched_pilot.csv --validation data/intermediate/manual_validation_sample.csv --output-dir outputs/tables/enriched --report docs/classification_diagnostics_enriched.md
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_impact_report.py --snapshot-label after_R001 --write-snapshot --compare-to before_R001
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_manual_validation_readiness.py
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_validation_gate.py
```

Expected result: diagnostics and impact reports update. The validation gate is
still expected to remain `blocked_calibration` until the 20-row calibration
packet is labeled.

### Step 4: Decide Whether To Scale Manual Recovery Or Source Templates

Use the R001 after/before impact report to choose the next branch.

Choose **manual scale-up** if:

- partial-extension rows produce a high share of usable text;
- import errors are rare;
- recovered rows move out of `insufficient_text` cleanly;
- the work is concentrated in old journal-decade cells that matter for the
  1975 expansion.

Choose **source-template spike** if:

- many unresolved rows share the same DOI/source family;
- a bounded public source can expose explicit abstracts or source-confirmed
  descriptions;
- the probe yields at least one accepted abstract or PDF candidate without
  access challenges.

Do **not** scale a route if the first 10 representative URLs return only access
challenges, not-found pages, citation-only metadata, or title-only snippets.

**Verify**:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_impact_report.py
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_insufficient_text_expansion_plan.py
```

Expected result: `docs/recovery_impact_report.md` and
`docs/insufficient_text_expansion_plan.md` identify the next route or recovery
batch without requiring broad blocked-source retries.

### Step 5: Add A Conservative Evidence Tier To Reviewer Notes

For manual work, use the following evidence tiers in reviewer notes or source
fields so later analysis can separate high-trust and weaker-but-source-confirmed
recoveries:

- `tier_a_formal_abstract`: source explicitly labels the text as an abstract.
- `tier_b_source_description`: source gives a description/summary but not a
  formal abstract.
- `tier_c_first_page_abstract_or_intro`: reachable OA first-page text exposes
  abstract/intro-like text.
- `tier_d_title_only_triage`: title-only evidence; never import as final
  classification text.
- `tier_e_blocked`: access challenge, restricted full text, paywall-only, or
  ambiguous source; leave unresolved.

Only tiers A, B, and carefully documented C may be imported as classification
text. Tier D can be used for sensitivity analysis or reviewer prioritization
only.

**Verify**: Spot-check completed staged rows before import. Every completed row
must have a source and locator. Rows marked title-only or blocked must remain
unimported.

### Step 6: Keep Sensitivity Outputs Separate From Main Labels

If the team wants to understand how much missing text could affect trends, add
or use a separate sensitivity artifact that keeps title-only or weak-evidence
suggestions outside the main classification file. The sensitivity artifact can
rank rows for review or compute lower/upper trend bounds, but it must not write
to `causal_predictive_category`.

**Verify**: After sensitivity work, confirm that
`data/final/articles_classified_enriched_pilot.csv` categories changed only
through accepted backfilled text and reclassification, not through title-only
manual overrides.

## Test Plan

- If this plan is executed using only existing commands and manual packet work,
  run the full suite after imports:

  ```bash
  PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest discover -s tests
  ```

- If any helper code is added for evidence tiers or sensitivity artifacts, add
  focused tests proving:
  - title-only evidence is never imported as final classification text;
  - completed rows without source provenance fail preflight;
  - evidence-tier values are preserved in generated artifacts;
  - reclassification is driven by accepted text, not direct category edits.

## Done Criteria

All must hold:

- [ ] R001 tiered packets have been worked in order or explicitly deferred.
- [ ] Completed recovery rows pass staging and split preflight with 0 errors.
- [ ] Backfill imports were run with `--require-source-metadata`.
- [ ] Classification, diagnostics, recovery impact, readiness, and validation
      gate reports were refreshed after imports.
- [ ] The after/before impact report states how many rows left
      `insufficient_text`.
- [ ] Title-only or blocked rows remain outside the final classification file.
- [ ] `plans/README.md` status row is updated.

## Current Run Notes

- Evidence-tier tooling is now implemented in the recovery flow. Recovery CSVs
  and HTML forms include `evidence_tier`; tiered staging, split preflight, and
  `run_import_abstract_backfill.py --require-source-metadata` reject missing,
  title-only, blocked, ambiguous, or unknown evidence tiers.
- Importable evidence tiers are `tier_a_formal_abstract`,
  `tier_b_source_description`, and
  `tier_c_first_page_abstract_or_intro`. `tier_d_title_only_triage` and
  `tier_e_blocked` remain review/sensitivity signals only.
- R001 packets were regenerated after adding the field and after separating
  boilerplate-contaminated current text. After twenty-two accepted R001
  recovery-review imports, the active ranked queue is 71 rows, staged completed
  rows are 0, and preflight errors are 0. The static split still carries 93
  ready rows for audit context.
- The latest accepted row is Fehr, Gaechter, and Kirchsteiger, "Reciprocity as a
  Contract Enforcement Device: Experimental Evidence" (`eqt_58f354a1f4c952aa`),
  imported from public RePEc/IDEAS metadata as `tier_b_source_description`; it
  moved from `insufficient_text` to `causal` after reclassification.
- Tiered staging now skips reviewer rows whose `article_id` already appears in
  `data/intermediate/abstract_backfill_import_history.csv`, preventing accepted
  recovery-review rows from reappearing as import-ready duplicates when static
  split exports still contain them.
- R001 action-group reviewer packets were added after the cached-evidence audit.
  The action index lists 7 packets covering all 71 active rows; each generated
  form includes the action group, reviewer action, source-to-avoid guidance,
  suggested evidence tier, cached-evidence status, cell-target priority, and
  candidate-source context. These forms export ordinary recovery rows and stage
  through the existing `run_recovery_tiered_stage.py` path.
- R001 action-progress reporting now tracks each action group across reviewer
  exports, staging, and split preflight. Current status is 0 exported rows, 0
  import-ready rows, and no stage/preflight errors.
- R001 action dashboard now provides one local launch page for the 7 action
  groups, linking each group to its form, CSV packet, and supporting reports.
  The dashboard and `docs/recovery_batch_R001_action_progress.md` also show
  target-cell rollups: 60 current R001 rows are in cells still above the 20%
  insufficient-text target share, and 61 rows are in critical target cells.
- R001 kickoff packet now provides a smaller first-session handoff at
  `docs/recovery_batch_R001_kickoff_packet.md` and
  `data/intermediate/insufficient_text_recovery_review_forms/R001/recovery_batch_R001_kickoff_packet.html`.
  It currently contains 20 rows: 19 priority-cell rows, 19 critical-cell rows,
  11 `find_external_extension` rows, 2
  `replace_boilerplate_from_new_source` rows, and 5 deeper/manual rows. Exports from
  this form stage through the same `run_recovery_tiered_stage.py` path as the
  full action packets.
- The kickoff report now includes a reviewer checklist, acceptable importable
  evidence tiers, and the non-importing stage/preflight/progress commands to
  run after reviewer exports. Its summary also records suggested evidence tiers
  and candidate source families for the 20-row first session.
- The calibration kickoff report now embeds the primary-focus label decision
  cheat sheet and the post-export refresh commands. This keeps the blocking
  20-row calibration handoff self-contained while preserving blind review:
  reviewers still use only title and abstract, not model predictions.
- The shared validation HTML form now shows a pre-export QA reminder next to
  the label rubric: completed labels require `manual_confidence`,
  `reviewer_id`, and ISO `review_date`, and reviewers should use
  `manual_notes` for title-only, ambiguous, or low-confidence calls. This
  appears in the calibration remaining form, full calibration form, and main
  validation batch forms after refresh.
- The scope-review packet and browser form now include a decision rubric for
  `exclude_nonresearch`, `keep_research`, and `unsure`, plus reviewer/date
  requirements. This makes the pattern-family bulk-fill workflow safer before
  likely paratext rows are excluded from recovery work or retained in the trend
  denominator.
- Scope-review application is now documented as dry-run first in the packet
  report, browser form, and workboard. `run_human_review_refresh.py` reruns the
  non-mutating `run_apply_scope_review_decisions.py` step immediately after
  generating the packet, so `docs/scope_review_apply.md` stays current before
  anyone uses `--apply`.
- The recent 2023-2025 top-5 pilot now has its own handoff at
  `docs/recent_2023_2025_recovery_pilot.md`, with a browser form at
  `data/intermediate/insufficient_text_recovery_review_forms/recent_2023_2025/recent_2023_2025_recovery_packet.html`.
  After the first 2023-2025 pass, the recent queue is empty:
  `recent_queue_rows=0`, `recent_scope_review_first_rows=0`, and
  `recent_recover_text_rows=0`.
- Two 2024 JPE rows were recovered from source-confirmed public NBER working
  paper PDFs and imported with
  `evidence_tier=tier_c_first_page_abstract_or_intro`: `Online Business
  Models, Digital Ads, and User Welfare` and `Rent Guarantee Insurance`.
  Reclassification moved both out of `insufficient_text` into `other` with
  medium confidence.
- Three R001 rows were recovered from article-specific IDEAS/RePEc source
  descriptions and imported with `evidence_tier=tier_b_source_description`:
  `Estimating Dynamic Random Effects Models from Panel Data Covering Short Time
  Periods`, `The Exact Distribution of the Wald Statistic`, and `Taxation,
  Human Capital, and Uncertainty`. Reclassification moved all three out of
  `insufficient_text`: two into `other` and one into `causal`, all with medium
  confidence.
- Three more R001 rows were imported in the next measured mini-batch:
  `Efficient Estimation and Identification of Simultaneous Equation Models with
  Covariance Restrictions` from an IDEAS/RePEc source description, plus
  `An Econometric Analysis of Residential Electric Appliance Holdings and
  Consumption` and `Rationalizable Strategic Behavior and the Problem of
  Perfection` from public first-page PDF abstract blocks. Reclassification
  moved all three out of `insufficient_text`: the first into `causal` with high
  confidence and the other two into `other` with medium confidence.
- Two additional R001 rows were recovered from public first-page PDF abstract
  blocks in the next measured mini-batch: `Pareto Superiority of Unegalitarian
  Equilibria in Stiglitz' Model of Wealth Distribution with Convex Saving
  Function` and `Resource-Constrained versus Demand-Constrained Systems`.
  Reclassification moved both out of `insufficient_text` into `other` with
  medium confidence.
- Three additional R001 rows were recovered from public article PDFs in the
  next measured mini-batch: `Regression Quantiles`, `The Nonparametric
  Approach to Demand Analysis`, and `Prediction, Optimization, and Learning in
  Repeated Games`. Reclassification moved all three out of
  `insufficient_text`: `Regression Quantiles` into `other`, and the other two
  into `predictive`, all with medium confidence.
- Five additional R001 rows were recovered in the next measured mini-batch:
  `Congestion of Production Factors` from a public DTIC report PDF,
  `A Comparison of Two Consistent Estimators in the Choice-Based Sampling
  Qualitative Response Model` from a public Stanford technical report PDF,
  `Fixed Costs and Labor Supply` and `Inflation, Tax Rules and Investment:
  Some Econometric Evidence` from NBER working paper metadata, and `Optimal
  Search for the Best Alternative` from Semantic Scholar metadata.
  Reclassification moved all five out of `insufficient_text`: the fixed-costs
  and inflation/tax rows into `causal`, and the other three into `other`, all
  with medium confidence.
- Three additional R001 rows were recovered in the next measured mini-batch:
  `Limit Pricing, Uncertain Entry, and the Entry Lag` from a public KU
  Leuven/Lirias report PDF, `Monotonic Solutions to General Cooperative Games`
  from a public Northwestern/Kellogg discussion paper PDF, and
  `The Distribution of Inventory Holdings in a Pure Exchange Barter Search
  Economy` from a public MIT DSpace working paper PDF. Reclassification moved
  all three out of `insufficient_text` into `other` with medium confidence.
- One additional R001 row was recovered in the next measured mini-batch:
  `An Axiomatization of Harsanyi's Nontransferable Utility Solution` from a
  public Sergiu Hart author abstract page. Reclassification moved it out of
  `insufficient_text` into `other` with medium confidence.
- The scope-review packet now adds a `scope_review_priority` column and a
  browser-form priority filter, but the current refreshed packet has no
  remaining `P1_recent_2023_2025_top5` rows. It has 7 active-batch R001
  scope-review candidates, all requiring dry-run review before any
  `--apply` scope changes.
- The scope audit now refreshes before the scope-review packet in
  `run_human_review_refresh.py`, and the scope-pattern config catches recent
  paratext titles such as back covers, acknowledgments of referees, addenda,
  Lucas Prize announcements, online corrigenda, retractions, and Robert E.
  Lucas Jr. memorial/parataxt titles. Recent likely-nonresearch rows are now
  filtered before they consume recovery effort; the remaining human scope
  packet is the 7-row active R001 set.
- The generated human-review workboard now starts with a first-session
  checklist and includes machine-readable `gate_rule` and
  `first_session_action` columns. Calibration is marked as the blocker for main
  validation, scope review and R001 recovery are marked as parallel researcher
  work, and recovery imports remain gated on tiered staging plus split
  preflight.
- Balanced recovery targets now refresh before cached-evidence/action packets
  in `run_human_review_refresh.py`, so reviewer packets show each row's
  journal-decade target rank, target level, recoveries needed to reach the 20%
  target share, and recommended next step.
- Evidence-tier robustness diagnostics now refresh with
  `run_classification_diagnostics.py`. The enriched diagnostics write
  `outputs/tables/enriched/evidence_tier_category_shares.csv`,
  `outputs/tables/enriched/evidence_tier_sensitivity_overall.csv`,
  `outputs/tables/enriched/evidence_tier_sensitivity_by_year.csv`, and
  `outputs/tables/enriched/evidence_tier_sensitivity_by_journal.csv`. In the
  current scoped pilot, 102 tier-A, 8 tier-B, and 74 tier-C rows enter the
  analysis; the formal-abstract-only cut demotes the 82 non-tier-A rows and
  raises scoped `insufficient_text` share from 18.7027% to 19.1057%.
- Regenerating the unlabeled manual validation sample, calibration packet, and
  overlap packet cleared the post-import drift created by recovery and scope
  updates. Current readiness is `ready_for_blind_review=yes` with
  `drifted_articles=0`; the validation gate remains
  `blocked_calibration` until the 20-row calibration packet is completed.
- Further human review is still required before additional R001 rows can be
  imported and measured against explicit before/after impact snapshots.

## STOP Conditions

Stop and report back if:

- A completed row lacks `source` and either `source_url` or
  `source_record_id`.
- A row's only evidence is a title, citation-only record, access-challenge
  page, search result snippet, or blocked PDF.
- Preflight reports source/provenance errors for completed rows.
- Rerunning classification causes unexpected validation sample drift that the
  readiness report flags.
- A source-template spike requires scraping restricted full text or bypassing an
  access challenge.
- The user decides first-page text, source descriptions, or title-only
  sensitivity should be treated differently from the evidence-tier rules above.

## Maintenance Notes

- Keep recovery impact snapshots around. They are the audit trail for whether
  each recovery batch improved the analysis enough to justify more manual work.
- When reporting trends, stratify or footnote remaining `insufficient_text` by
  journal and decade. The missingness is concentrated in older cells, so a
  single overall missingness share can hide historical bias.
- Do not let the recovery workflow outrun calibration. The validation gate
  remains blocked until calibration labels exist, regardless of how much text is
  recovered.
