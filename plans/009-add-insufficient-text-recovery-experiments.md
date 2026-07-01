# Plan 009: Add Insufficient-Text Recovery Experiments And Yield Tracking

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report rather than improvising. When done, update the status row for this
> plan in `plans/README.md`.
>
> **Drift check (run first)**:
>
> ```bash
> test -f outputs/tables/enriched/insufficient_text_recovery_queue.csv \
>   && test -f outputs/tables/enriched/insufficient_text_source_route_matrix.csv \
>   && test -f outputs/tables/enriched/recovery_batch_R001_review_queue.csv \
>   && test -f data/final/articles_classified_enriched_pilot.csv \
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
  `plans/008-add-scope-audit-and-recovery-decision-gate.md`
- **Category**: direction
- **Planned at**: no git repo detected, 2026-06-29

## Why This Matters

The project has a conservative recovery pipeline, but the next bottleneck is
decision quality: 3,912 scoped research rows still have insufficient
classification text, and manual recovery is expensive. The current reports tell
reviewers what to work on, but they do not yet measure the marginal effect of
each recovery route after imports. Before expanding beyond R001 or adding more
source templates, the project needs a recovery experiment layer that records
which routes, journals, decades, and source types actually move rows out of
`insufficient_text`.

This plan does not lower the 250-character text threshold, does not classify
from title-only evidence, and does not scrape restricted full text. It adds a
measurement and sequencing layer so abstract recovery can proceed in bounded,
auditable waves.

## Current State

Relevant files and roles:

- `outputs/tables/enriched/insufficient_text_recovery_queue.csv` - 3,912
  unresolved scoped research rows queued for recovery.
- `outputs/tables/enriched/remaining_insufficient_text_profile.csv` - current
  journal-decade missingness profile.
- `outputs/tables/enriched/insufficient_text_source_route_matrix.csv` -
  route-level decisions and stop rules.
- `outputs/tables/enriched/recovery_batch_R001_review_queue.csv` - ranked
  93-row reviewer queue for rows already ready to work.
- `outputs/tables/enriched/recovery_batch_R001_preflight_summary.csv` -
  combined split-packet import readiness summary.
- `data/intermediate/abstract_backfill_import_history.csv` - cumulative
  accepted recovery imports with `import_source_file`.
- `code/06_enrich/recovery_review_queue.py` - builds ranked manual recovery
  queue from ready split packets.
- `code/06_enrich/insufficient_text_expansion.py` - builds expansion lanes,
  DOI-prefix decisions, investigation packet, and source-route matrix.
- `code/06_enrich/abstract_backfill.py` - imports curated abstracts and can
  require source metadata.
- `code/05_analysis/classification_diagnostics.py` - writes the recovery queue,
  remaining profile, diagnostics, and title-only triage artifact.

Current metrics from local artifacts:

- Remaining recovery rows: 3,912.
- Recovery actions: 1,887 `recover_abstract_from_doi_or_publisher`, 1,476
  `review_openalex_or_title_match`, 492 `extend_existing_short_abstract`, and
  57 `review_oa_pdf_or_first_pages`.
- Largest route units: `openalex_or_title_search` 1,476 rows, `10.2307` 1,048
  rows, `10.1086` 810 rows, `partial_short_text_extension` 492 rows,
  `10.1257` 239 rows, and `10.1111` 155 rows.
- Route probe result: 24 sampled public landing/metadata URLs, with 22
  `access_challenge` and 2 `not_found`; no sampled abstracts or PDF candidates.
- R001 ready rows: 93, split into 38 `ready_partial_text_extension` and 55
  `ready_manual_metadata`; 7 additional R001 rows are waiting for scope review.
- R001 review queue tiers: 24 `tier_1_partial_near_threshold`, 14
  `tier_2_partial_extension`, 41 `tier_3_manual_metadata_has_context`, and 14
  PDF-blocked/suspect-PDF manual metadata rows.
- R001 preflight currently has 0 import-ready rows and 0 errors because the
  reviewer packets are empty.
- Scope review progress is 0 / 70; do not spend recovery time on
  `waiting_scope_review` rows until those decisions are resolved.
- Highest missingness cells by count include AER 1980s 449 rows, AER 1990s 387,
  Econometrica 1980s 382, JPE 1980s 315, Econometrica 1970s 315, AER 2010s
  308, AER 1970s 287, and JPE 1970s 243.

Code excerpts to verify before editing:

`code/06_enrich/recovery_review_queue.py` ranks immediate reviewer work:

```python
READY_REVIEW_GROUPS = {
    "ready_partial_text_extension",
    "ready_manual_metadata",
    "ready_autofill_or_completed",
}

TIER_ORDER = {
    "source_metadata_fix": 0,
    "tier_1_partial_near_threshold": 1,
    "tier_2_partial_extension": 2,
    "tier_3_manual_metadata_has_context": 3,
    "tier_4_manual_metadata_pdf_blocked": 4,
    "tier_5_manual_metadata_sparse": 5,
    "completed_ready_for_preflight": 6,
}
```

`code/06_enrich/abstract_backfill.py` already enforces source metadata when
requested:

```python
def source_metadata_error(backfill_row: pd.Series) -> tuple[str, str] | None:
    source = clean_text(backfill_row.get("_provided_source"))
    source_url = clean_text(backfill_row.get("_provided_source_url"))
    source_record_id = clean_text(backfill_row.get("_provided_source_record_id"))
    if not source:
        return "missing_source", "Filled abstract rows must record the source used for recovery."
    if not source_url and not source_record_id:
        return "missing_source_locator", "Filled abstract rows must include source_url or source_record_id."
    return None
```

`code/06_enrich/insufficient_text_expansion.py` already blocks broad reruns
when probes only find landing-page failures:

```python
if decision == "source_specific_investigation_before_rerun":
    if blocked_probe_route:
        return (
            "do_not_rerun_landing_pages",
            "Use the investigation packet to inspect failed/found source patterns; avoid broad DOI landing-page reruns.",
            "The bounded probe found access challenges or not-found pages rather than abstracts or PDFs.",
            "outputs/tables/enriched/insufficient_text_source_investigation_packet.csv",
        )
```

## Commands You Will Need

| Purpose | Command | Expected on success |
|---|---|---|
| Tests | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest discover -s tests` | exits 0; current full-suite count after this plan is 217 tests |
| R001 queue | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_review_queue.py` | exits 0 and writes R001 review queue artifacts |
| Split preflight | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_split_preflight.py` | exits 0 and reports 0 errors for completed rows |
| Reclassify | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_classification_pilot.py --input data/final/articles_enriched_pilot.csv --output data/final/articles_classified_enriched_pilot.csv` | exits 0 |
| Diagnostics | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_classification_diagnostics.py --classified data/final/articles_classified_enriched_pilot.csv --validation data/intermediate/manual_validation_sample.csv --output-dir outputs/tables/enriched --report docs/classification_diagnostics_enriched.md` | exits 0 |
| Project status | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_project_status.py` | exits 0 and keeps validation gate status visible |
| Validation gate | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_validation_gate.py` | exits 0; expected current gate remains `blocked_calibration` until calibration labels exist |

Use `/usr/bin/python3` in this workspace. The Homebrew Python may not have the
same package behavior.

## Scope

**In scope**:

- `code/06_enrich/recovery_impact.py` (create)
- `run_recovery_impact_report.py` (create)
- `tests/test_recovery_impact.py` (create)
- `code/05_analysis/project_status.py`, only to add a link/next action for the
  recovery impact report
- `tests/test_project_status.py`, only if project-status output changes
- `README.md`
- Generated artifacts:
  - `data/intermediate/recovery_impact_snapshots/`
  - `outputs/tables/enriched/recovery_impact_summary.csv`
  - `outputs/tables/enriched/recovery_impact_changes.csv`
  - `outputs/tables/enriched/recovery_source_experiments.csv`
  - `docs/recovery_impact_report.md`
- `plans/README.md` status update after completion

**Out of scope**:

- Do not change `causal_predictive_category` directly.
- Do not change the 250-character minimum usable text threshold.
- Do not classify title-only rows into final causal/predictive/other labels.
- Do not scrape restricted publisher, JSTOR, Wiley, OUP, AEA, or Chicago full
  text.
- Do not retry broad DOI landing-page passes when route probes show only access
  challenges.
- Do not apply scope decisions automatically.
- Do not edit manual validation labels, calibration packets, reviewer
  submissions, or adjudication fields.

## Git Workflow

- This workspace is not currently a git repository. If the executor is working
  in a git checkout, use a branch named
  `advisor/009-recovery-impact-experiments`.
- Do not push or open a PR unless the operator explicitly asks for it.

## Steps

### Step 1: Add A Recovery Snapshot Model

Create `code/06_enrich/recovery_impact.py` with pure helper functions that
read the current classified file, recovery queue, source-route matrix, and
optional import history. The first command mode should write a snapshot of the
current recovery state to
`data/intermediate/recovery_impact_snapshots/<snapshot_label>.csv`.

The snapshot must be one row per `article_id` in the current recovery universe
and include at least:

- `snapshot_label`
- `article_id`
- `journal_short`
- `publication_year`
- `decade`
- `title`
- `doi`
- `causal_predictive_category`
- `classification_text_chars`
- `has_usable_classification_text`
- `abstract_source`
- `text_enrichment_status`
- `recovery_rank`
- `recovery_batch`
- `recovery_priority`
- `recovery_action`
- `expansion_lane`
- `route_unit`
- `current_route_status`
- `source_route_note`

Use `article_id` as the join key. If a row appears in the classified file but
not in the recovery queue, keep it only when it was present in a comparison
snapshot. This allows before/after comparisons to identify rows that left the
queue.

Add `run_recovery_impact_report.py` with arguments:

- `--snapshot-label`, default `current`
- `--write-snapshot`
- `--compare-to`, optional path or label
- `--classified`, default `data/final/articles_classified_enriched_pilot.csv`
- `--recovery-queue`, default
  `outputs/tables/enriched/insufficient_text_recovery_queue.csv`
- `--route-matrix`, default
  `outputs/tables/enriched/insufficient_text_source_route_matrix.csv`
- `--import-history`, default
  `data/intermediate/abstract_backfill_import_history.csv`
- `--snapshot-dir`, default `data/intermediate/recovery_impact_snapshots`
- `--output-summary`, default
  `outputs/tables/enriched/recovery_impact_summary.csv`
- `--output-changes`, default
  `outputs/tables/enriched/recovery_impact_changes.csv`
- `--output-experiments`, default
  `outputs/tables/enriched/recovery_source_experiments.csv`
- `--report`, default `docs/recovery_impact_report.md`

**Verify**:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_recovery_impact
```

Expected result: new focused tests pass.

### Step 2: Add Before/After Impact Comparisons

In `code/06_enrich/recovery_impact.py`, add comparison logic that joins a prior
snapshot to the current snapshot by `article_id`.

The change table should include rows that were insufficient before and changed
state now. Required columns:

- `article_id`
- `journal_short`
- `publication_year`
- `decade`
- `title`
- `before_category`
- `after_category`
- `before_text_chars`
- `after_text_chars`
- `recovered_from_insufficient`
- `before_recovery_batch`
- `before_recovery_action`
- `before_expansion_lane`
- `before_route_unit`
- `after_abstract_source`
- `after_text_enrichment_status`
- `import_source_file`

The summary table should group by:

- overall totals
- `journal_short`
- `decade`
- `before_recovery_batch`
- `before_recovery_action`
- `before_expansion_lane`
- `before_route_unit`
- `import_source_file`

Metrics must include:

- `before_insufficient_rows`
- `after_insufficient_rows`
- `recovered_rows`
- `newly_insufficient_rows`
- `net_insufficient_change`
- `median_after_text_chars`

**Verify**:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_recovery_impact
```

Expected result: tests cover at least one recovered row, one unchanged
insufficient row, and one row that remains outside the comparison universe.

### Step 3: Add A Source-Experiment Queue With Stop Rules

Generate `outputs/tables/enriched/recovery_source_experiments.csv` from the
current route matrix, remaining profile, review queue, and source-route probe
state. This table is the answer to "what should we try next?" and should be
more actionable than a flat route matrix.

Required columns:

- `experiment_rank`
- `experiment_id`
- `experiment_type`
- `route_unit`
- `target_journal_short`
- `target_decade`
- `candidate_rows`
- `ready_rows`
- `expected_payoff`
- `source_artifact`
- `start_rule`
- `success_rule`
- `stop_rule`
- `next_command_or_packet`

Use these experiment types:

- `manual_partial_extension`: starts from
  `ready_partial_text_extension`; success is any source-complete abstract that
  pushes text over 250 chars.
- `manual_metadata_backfill`: starts from `ready_manual_metadata`; success is
  source-complete explicit abstracts only.
- `source_template_spike`: applies to large unsupported or blocked routes such
  as `10.2307`, `10.1111`, `10.1093/qje`, `10.1086`, and `10.1257`; success is
  a bounded probe finding public metadata or PDF candidates without access
  challenges.
- `credentialed_api_pass`: applies to sources that need credentials or contact
  metadata, such as Unpaywall contact email or Semantic Scholar API key.
- `scope_gate`: applies to rows waiting for scope review; success is a
  completed keep/exclude/unsure decision, not recovered text.

Default ranking rules:

1. R001 `manual_partial_extension` first, because 24 tier-1 rows need 75 or
   fewer characters and 14 tier-2 rows are still source-guided.
2. R001 `manual_metadata_backfill` second, excluding rows waiting for scope
   review.
3. `source_template_spike` for high-volume route units only after the bounded
   probe or investigation packet suggests a lawful public metadata route.
4. `credentialed_api_pass` only after the user provides `CONTACT_EMAIL` or
   `SEMANTIC_SCHOLAR_API_KEY`.
5. Broad manual title-search lanes last, unless a high-value journal-decade
   cell is selected for a small hand-curated sample.

Default stop rules:

- If a source-template spike samples 10 representative public metadata URLs and
  finds 0 abstracts or PDF candidates, do not scale that route.
- If more than half of sampled URLs are access challenges, do not rerun a broad
  landing-page pass.
- If a manual recovery group produces source-incomplete filled abstracts,
  pause imports and fix source metadata before continuing.
- If a route mostly recovers paratext or scope-questionable rows, run scope
  review before expanding it.

**Verify**:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_recovery_impact
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_impact_report.py --snapshot-label before_R001 --write-snapshot
```

Expected result: the runner exits 0, writes the snapshot, writes
`recovery_source_experiments.csv`, and the first experiments point to R001
partial extension and manual metadata work.

### Step 4: Add The Markdown Report

Have `run_recovery_impact_report.py` write `docs/recovery_impact_report.md`.
The report must include:

- Current remaining recovery rows.
- Top journal-decade missingness cells.
- Top route units and their current route status.
- R001 ready work summary.
- Recovery experiment queue preview.
- If `--compare-to` is provided, a before/after impact section with recovered
  row counts by route, batch, journal, decade, and import source file.
- A short "Do not do yet" section listing broad DOI landing-page reruns, title
  only final classification, and scope-waiting recovery rows.

Do not claim trend evidence is analysis-ready in this report while
`run_validation_gate.py` remains blocked.

**Verify**:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_impact_report.py --snapshot-label before_R001 --write-snapshot
```

Expected result: report and CSV outputs exist; current comparison section says
no comparison was requested.

### Step 5: Use The Report Around R001 Imports

Document this operational sequence in `README.md` under "Work
Insufficient-Text Recovery Batches":

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_impact_report.py --snapshot-label before_R001 --write-snapshot
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_review_queue.py
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_split_preflight.py
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_import_abstract_backfill.py --input data/intermediate/insufficient_text_recovery_splits/R001/insufficient_text_recovery_batch_R001_ready_partial_text_extension.csv --skip-empty-abstracts --dry-run --require-source-metadata
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_import_abstract_backfill.py --input data/intermediate/insufficient_text_recovery_splits/R001/insufficient_text_recovery_batch_R001_ready_partial_text_extension.csv --skip-empty-abstracts --require-source-metadata --fail-on-errors
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_classification_pilot.py --input data/final/articles_enriched_pilot.csv --output data/final/articles_classified_enriched_pilot.csv
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_classification_diagnostics.py --classified data/final/articles_classified_enriched_pilot.csv --validation data/intermediate/manual_validation_sample.csv --output-dir outputs/tables/enriched --report docs/classification_diagnostics_enriched.md
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_impact_report.py --snapshot-label after_R001_partial --write-snapshot --compare-to before_R001
```

Repeat the same pattern for the R001 manual metadata split after partial
extension rows are imported.

**Verify**:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest discover -s tests
```

Expected result: all tests pass.

### Step 6: Surface The Impact Report In Project Status

Optionally update `code/05_analysis/project_status.py` so
`run_project_status.py` includes a next action pointing to
`docs/recovery_impact_report.md` when the recovery impact outputs exist.

Keep this status item below calibration and scope-review blockers. It should
not imply that trend outputs are usable before validation passes.

**Verify**:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_project_status
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_project_status.py
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_validation_gate.py
```

Expected result: tests pass; project status mentions recovery impact only as a
recovery-management artifact; validation gate remains governed by calibration.

## Test Plan

- Create `tests/test_recovery_impact.py`.
- Use small in-memory DataFrames; do not require network access.
- Test snapshot construction when a classified insufficient row is present in
  the recovery queue and route matrix.
- Test before/after comparison when a row moves from `insufficient_text` to
  `causal`, `predictive`, or `other`.
- Test experiment ranking so R001 partial extensions appear before unsupported
  source-template spikes.
- Test stop-rule text for access-challenge-heavy route units.
- If `project_status.py` is updated, add a focused status test modeled on
  existing `tests/test_project_status.py` patterns.
- Run the full suite:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest discover -s tests
```

Expected result: all tests pass; baseline before this plan was 212 tests and
the verified full-suite count after implementation is 217 tests.

## Done Criteria

All must hold:

- [ ] `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest discover -s tests`
  exits 0.
- [ ] `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_impact_report.py --snapshot-label before_R001 --write-snapshot`
  exits 0.
- [ ] `data/intermediate/recovery_impact_snapshots/before_R001.csv` exists.
- [ ] `outputs/tables/enriched/recovery_impact_summary.csv` exists.
- [ ] `outputs/tables/enriched/recovery_source_experiments.csv` exists and
  ranks R001 partial-extension work before broad source-template spikes.
- [ ] `docs/recovery_impact_report.md` exists and includes "Do not do yet"
  guardrails.
- [ ] No final causal/predictive/other labels are changed by the impact report
  command itself.
- [ ] `plans/README.md` status row for this plan is updated.

## STOP Conditions

Stop and report back if:

- The current recovery queue or route matrix files are missing.
- The recovery queue no longer has `article_id` or `recovery_action`.
- The route matrix no longer has `route_unit` or `current_route_status`.
- The implementation would require lowering `minimum_usable_text_chars`.
- The implementation would require scraping restricted full text.
- A before/after comparison cannot distinguish recovered rows from rows removed
  by scope decisions.
- A verification command fails twice after a reasonable fix attempt.

## Maintenance Notes

- This plan adds measurement. It does not replace the human recovery packets.
- Reviewers should check that route-level recovered counts are not dominated by
  a single source with weak provenance.
- If the user later approves first-page OCR text as equivalent to abstracts,
  add a separate sensitivity flag rather than changing this impact report's
  source-complete abstract requirement silently.
- If a paid/institutional source such as EconLit is used, store only permitted
  metadata/abstract text and record source provenance; do not add credentials or
  restricted access details to repository files.
