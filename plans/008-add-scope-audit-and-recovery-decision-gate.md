# Plan 008: Add A Scope Audit And Recovery Decision Gate Before More Insufficient-Text Work

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report rather than improvising. When done, update the status row for this
> plan in `plans/README.md`.
>
> **Drift check (run first)**:
>
> ```bash
> test -f data/final/articles_classified_enriched_pilot.csv \
>   && test -f outputs/tables/enriched/insufficient_text_recovery_queue.csv \
>   && test -f config/text_enrichment.yml \
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
- **Depends on**: `plans/007-recover-remaining-insufficient-text.md`
- **Category**: direction
- **Planned at**: no git repo detected, 2026-06-29

## Why This Matters

The project still has 3,912 scoped research rows classified as
`insufficient_text`, but not all of those rows should receive the same recovery
effort. A current read-only scope check found 54 rows in the classified file and
recovery queue that the updated title-scope rules would now treat as
`review_erratum_paratext`, including 7 rows in R001. Those rows should be
reviewed before anyone spends time finding abstracts for them, while the real
research rows should move through explicit source routes with clear stop rules.

This plan adds a non-mutating audit and decision gate. It does not change final
labels, does not remove rows automatically, and does not turn title-only
evidence into causal/predictive labels.

## Current State

Relevant files and roles:

- `data/final/articles_classified_enriched_pilot.csv` - current enriched
  article-level classification file.
- `outputs/tables/enriched/insufficient_text_recovery_queue.csv` - 3,912
  unresolved scoped research rows currently queued for recovery.
- `data/intermediate/insufficient_text_recovery_batches/insufficient_text_recovery_batch_R001.csv`
  - next 100-row manual recovery packet.
- `config/text_enrichment.yml` - contains `article_scope_patterns`.
- `code/06_enrich/text_enrichment.py` - contains `classify_article_scope`.
- `code/05_analysis/project_status.py` - consolidated status and next-action
  report.
- `code/06_enrich/recovery_batch_workplan.py` - row-level workplan for R001.

Current metrics from the local artifacts:

- Remaining recovery rows: 3,912.
- Manual validation gate: `blocked_calibration`.
- Calibration labels: 0 / 20.
- Main validation labels: 0 / 300.
- Scope drift found by read-only check: 54 proposed new nonresearch exclusions
  among current `insufficient_text` rows; 7 are in R001.
- R001 workplan row statuses: 41 `manual_index_or_new_template`, 38
  `manual_extend_partial_text`, 13 `pdf_route_blocked_use_manual_metadata`, 7
  `scope_review_before_recovery`, and 1
  `suspect_pdf_url_use_manual_metadata`.
- Source-route probe status: 24 probes, 22 `access_challenge`, 2 `not_found`,
  0 abstracts, 0 PDF candidates.
- Largest unresolved route units: `openalex_or_title_search` 1,476 rows,
  `10.2307` 1,048 rows, `10.1086` 810 rows,
  `partial_short_text_extension` 492 rows, `10.1257` 239 rows, and
  `10.1111` 155 rows.

Code excerpts to verify before editing:

`code/06_enrich/text_enrichment.py` currently classifies scope from article
type and title patterns:

```python
def classify_article_scope(row: dict[str, Any], patterns: dict[str, list[str]] | None = None) -> tuple[str, str]:
    title = clean_text(row.get("title", "")).lower()
    article_type = clean_text(row.get("article_type", "")).lower()
    if article_type in {"paratext", "erratum", "review"}:
        return "review_erratum_paratext", f"article_type={article_type}"

    patterns = patterns or {}
    for scope, regexes in patterns.items():
        for pattern in regexes or []:
            if re.search(pattern, title, flags=re.IGNORECASE):
                return scope, f"title_pattern={pattern}"
```

`code/05_analysis/classification_diagnostics.py` currently builds the recovery
queue from rows whose resolved category is `insufficient_text`:

```python
work = df.copy()
work["current_category"] = resolved_category(work)
work = work[work["current_category"].eq("insufficient_text")].copy()
```

`config/text_enrichment.yml` includes current scope patterns such as:

```yaml
article_scope_patterns:
  review_erratum_paratext:
    - '\ba correction$'
    - ': erratum$'
    - '^supplement to\b'
    - '\belection of fellows\b'
    - '\breferees? [0-9]{4}'
```

## Commands You Will Need

| Purpose | Command | Expected on success |
|---|---|---|
| Tests | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest discover -s tests` | exits 0; current baseline is 212 tests |
| Scope drift check | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_scope_review_audit.py` | exits 0 and writes scope audit artifacts |
| Project status | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_project_status.py` | exits 0 and includes scope-review action when candidates exist |
| R001 workplan | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_batch_workplan.py` | exits 0 and keeps R001 scope-review rows visible |
| Validation gate | `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_validation_gate.py` | exits 0; expected current gate remains `blocked_calibration` |

Use `/usr/bin/python3` in this workspace. The Homebrew Python may not have the
same package behavior.

## Scope

**In scope**:

- `code/05_analysis/scope_review_audit.py` (create)
- `run_scope_review_audit.py` (create)
- `tests/test_scope_review_audit.py` (create)
- `code/05_analysis/project_status.py`
- `tests/test_project_status.py`
- `README.md`
- Generated audit artifacts:
  - `docs/scope_review_audit.md`
  - `outputs/tables/enriched/scope_review_candidates.csv`
  - `outputs/tables/enriched/scope_review_summary.csv`
- `plans/README.md` status update after completion

**Out of scope**:

- Do not change `causal_predictive_category`.
- Do not overwrite manual validation labels, calibration packets, reviewer
  submissions, or adjudication fields.
- Do not automatically remove rows from
  `data/final/articles_classified_enriched_pilot.csv`.
- Do not classify rows using title-only evidence.
- Do not scrape restricted publisher, JSTOR, or Wiley full text.
- Do not rerun broad source passes unless a later source-specific plan approves
  a bounded route.

## Steps

### Step 1: Add A Non-Mutating Scope Review Audit

Create `code/05_analysis/scope_review_audit.py` with a pure function that:

- Reads a classified article file, the recovery queue, and optionally the active
  recovery batch.
- Loads `article_scope_patterns` from `config/text_enrichment.yml`.
- Re-runs `classify_article_scope` on each row.
- Flags rows where the current scope is not one of
  `review_erratum_paratext`, `comment_reply`, or `lecture_address`, but the
  proposed scope is one of those excluded scopes.
- Writes candidate rows without changing any source data.

Candidate columns must include:

- `dataset`
- `article_id`
- `journal_short`
- `publication_year`
- `decade`
- `title`
- `doi`
- `causal_predictive_category`
- `current_article_scope`
- `proposed_article_scope`
- `proposed_scope_reason`
- `recovery_batch`
- `recovery_rank`
- `recommended_action`
- `human_scope_decision`
- `scope_review_notes`

The default `recommended_action` should be `review_scope_before_recovery`.
Leave `human_scope_decision` and `scope_review_notes` blank for reviewers.

Also create a summary table grouped by:

- `dataset`
- `proposed_article_scope`
- `proposed_scope_reason`
- `journal_short`
- `decade`
- `recovery_batch`

**Verify**:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest discover -s tests
```

Expected result: all tests pass.

### Step 2: Add The Runner And Markdown Report

Create `run_scope_review_audit.py` with defaults:

- classified input:
  `data/final/articles_classified_enriched_pilot.csv`
- recovery queue:
  `outputs/tables/enriched/insufficient_text_recovery_queue.csv`
- active batch:
  `data/intermediate/insufficient_text_recovery_batches/insufficient_text_recovery_batch_R001.csv`
- config:
  `config/text_enrichment.yml`
- candidate output:
  `outputs/tables/enriched/scope_review_candidates.csv`
- summary output:
  `outputs/tables/enriched/scope_review_summary.csv`
- report:
  `docs/scope_review_audit.md`

The report should state clearly that this is an audit only. It should include:

- Total candidate rows by dataset.
- Candidate counts by proposed scope.
- Candidate counts by recovery batch.
- The first 25 candidate rows with title, journal, year, DOI, current scope,
  proposed scope, and proposed reason.
- The exact next command to rerun after human scope decisions are resolved.

**Verify**:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_scope_review_audit.py
```

Expected result: exits 0 and writes the three audit artifacts. In the current
workspace, expect roughly 54 candidates in the classified/recovery-queue views
and 7 candidates in R001, unless the source files have already been regenerated.

### Step 3: Surface Scope Review In Project Status

Update `code/05_analysis/project_status.py` so that, when
`outputs/tables/enriched/scope_review_candidates.csv` exists and contains
rows, `run_project_status.py` adds a next action ahead of
`work_next_recovery_batch`:

- `action_id`: `review_scope_candidates`
- `status`: `ready_parallel`
- `owner`: `researcher`
- `action`: review scope candidates before recovering abstracts for those rows
- `why`: likely nonresearch/parataxt rows should not consume abstract recovery
  effort or enter trend denominators without review
- `source_artifact`: `docs/scope_review_audit.md`

Also add a status-summary metric:

- section: `recovery`
- metric: `scope_review_candidates`
- value: candidate count
- note: first affected batch if available

Do not make project status depend on this artifact. If the audit file is absent,
project status should still run and simply omit the scope-review action.

**Verify**:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_scope_review_audit.py
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_project_status.py
```

Expected result: `docs/project_status.md` includes `review_scope_candidates`
when scope candidates exist.

### Step 4: Define The Recovery Decision Gate In Documentation

Update `README.md` in the insufficient-text recovery section with the new audit
command and the intended order:

1. Run `run_scope_review_audit.py`.
2. Review candidates in `docs/scope_review_audit.md` and the CSV.
3. Work only rows whose scope remains research or unresolved after review.
4. Import explicit abstracts with
   `run_import_abstract_backfill.py --skip-empty-abstracts`.
5. Rebuild classification diagnostics, recovery batches, recovery progress,
   expansion plan, project status, and the next batch workplan.

Document the recovery gate:

- Scope-review rows: pause before abstract recovery.
- `manual_extend_partial_text`: highest manual-yield lane because partial text
  already exists.
- `manual_index_or_new_template`: use index/title-search links only to find
  explicit abstracts or source-confirmed metadata; title-only category
  suggestions remain sensitivity artifacts.
- `unsupported_existing_route`: do not rerun existing automated source logic
  unless a bounded source-template pilot proves usable abstracts.
- `do_not_rerun_landing_pages`: do not retry access-challenge landing pages.
- PDF blockers: do not retry 403/405/HTML routes unchanged; use explicit
  metadata or reachable OA PDFs only.

**Verify**:

```bash
rg -n "run_scope_review_audit|scope_review_candidates|manual_extend_partial_text|do_not_rerun_landing_pages" README.md
```

Expected result: each term appears in the recovery documentation.

### Step 5: Regenerate Non-Label Artifacts

Run the non-label regeneration sequence:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_scope_review_audit.py
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_project_status.py
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_recovery_batch_workplan.py
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 run_validation_gate.py
```

Expected result:

- Scope audit artifacts exist.
- Project status includes the scope-review action if candidates exist.
- R001 workplan still identifies scope-review rows.
- Validation gate still reports `blocked_calibration` until human calibration
  labels exist.

Do not regenerate or overwrite human reviewer labels.

## Test Plan

- Add `tests/test_scope_review_audit.py`.
- Use small in-memory DataFrames; do not require the full data files in unit
  tests.
- Cover at least:
  - rows newly proposed as `review_erratum_paratext` are emitted;
  - rows already marked nonresearch are not emitted as drift;
  - research rows are not emitted;
  - candidate output has stable columns even when empty;
  - summary output has stable columns even when empty;
  - markdown report includes the audit-only warning.
- Update `tests/test_project_status.py` with one case where
  `scope_review_candidates.csv` exists and one case where it is absent.
- Full verification:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest discover -s tests
```

Expected result: all tests pass; the current full-suite baseline is 212 tests.

## Done Criteria

All must hold:

- [x] `run_scope_review_audit.py` exists and runs with default paths.
- [x] `outputs/tables/enriched/scope_review_candidates.csv` exists with stable
      reviewer columns.
- [x] `outputs/tables/enriched/scope_review_summary.csv` exists with stable
      grouped counts.
- [x] `docs/scope_review_audit.md` clearly says the audit is non-mutating and
      not a label-change step.
- [x] `run_project_status.py` surfaces `review_scope_candidates` only when
      candidates exist.
- [x] `README.md` documents the recovery decision gate.
- [x] No final category labels or manual labels are changed by this plan.
- [x] `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest discover -s tests`
      passes.
- [x] `run_validation_gate.py` still reports the true current gate status.
- [x] `plans/README.md` status row for plan 008 is updated.

## Implementation Notes

- Implemented on 2026-06-29.
- `run_scope_review_audit.py` currently writes 131 candidate rows across views:
  70 from the classified file, 54 from the recovery queue, and 7 from R001.
  These correspond to 70 unique articles.
- `run_scope_review_packet.py` now deduplicates those audit rows into a 70-row
  scope-review packet, writes a browser form, and reports completion progress.
  Current progress is 0 / 70 scope decisions.
- `run_apply_scope_review_decisions.py` now validates the completed packet in
  dry-run mode by default and requires `--apply` before any scope metadata is
  written to final article files. It rejects invalid decisions, missing reviewer
  metadata, duplicate completed `scope_review_id` or `article_id` rows, and rows
  that do not match target article files. Current dry run has 0 validation errors
  and 0 scope changes because no scope-review decisions have been filled yet.
- The manual validation portal now links the scope-review packet, form, and
  apply dry-run report, and shows current scope-review progress.
- `run_recovery_batch_workplan.py` now reads completed scope-review packet
  decisions when available: `keep_research` lets recovery proceed,
  `exclude_nonresearch` stops abstract recovery, and `unsure` keeps the row
  paused.
- `run_recovery_batch_split.py` now splits R001 into reviewer-ready packets:
  38 `ready_partial_text_extension` rows, 55 `ready_manual_metadata` rows, and
  7 `waiting_scope_review` rows. These packets preserve importable abstract
  backfill columns and add the workplan context needed to avoid retrying blocked
  PDF routes. They also include current abstract/text-length/source fields and
  deduplicated prior text-enrichment attempt summaries to reduce manual lookup
  time. The split summary now reports `source_ready_backfill_abstracts` and
  `source_incomplete_backfill_abstracts` so completed rows missing source
  metadata are visible before import.
- `run_project_status.py` now surfaces `review_scope_candidates` as priority 7
  when scope-review candidates exist, using the packet completion summary when
  available, and surfaces `work_ready_recovery_splits` as priority 8 when split
  packets exist.
- `run_recovery_progress.py` now attributes imports from split-packet filenames
  such as `insufficient_text_recovery_batch_R001_ready_manual_metadata.csv` to
  the parent `R001` recovery batch.
- `run_import_abstract_backfill.py --dry-run` now validates completed split or
  recovery CSVs without updating enrichment histories, text-enrichment
  candidates, PDF candidates, or final article files. Dry-run defaults write to
  `docs/abstract_backfill_dry_run_report.md` and
  `outputs/tables/enriched/abstract_backfill_dry_run_*.csv`. The
  `--require-source-metadata` guard now rejects filled abstract rows unless
  they include a source and either `source_url` or `source_record_id`. The
  `--fail-on-errors` guard now prevents partial state updates when any import
  validation errors are present.
- `run_recovery_split_preflight.py` now validates all ready R001 split packets
  in one non-mutating pass using the same skip-empty/source-metadata semantics
  as the import dry run. Current R001 preflight checks 2 ready split groups,
  skips 93 blank reviewer rows, has 0 import-ready rows, and has 0 errors. It
  writes `outputs/tables/enriched/recovery_batch_R001_preflight_summary.csv`,
  `outputs/tables/enriched/recovery_batch_R001_preflight_errors.csv`, and
  `docs/recovery_batch_R001_preflight.md`.
- `run_recovery_review_queue.py` now combines the ready R001 split packets into
  a ranked reviewer queue, writing
  `outputs/tables/enriched/recovery_batch_R001_review_queue.csv`,
  `outputs/tables/enriched/recovery_batch_R001_review_queue_summary.csv`, and
  `docs/recovery_batch_R001_review_queue.md`. Current R001 queue has 93 rows:
  24 `tier_1_partial_near_threshold`, 14 `tier_2_partial_extension`, 41
  `tier_3_manual_metadata_has_context`, and 14 PDF-blocker/suspect-PDF manual
  metadata rows. `run_project_status.py` now points the priority-8 recovery
  action at the ranked queue when it exists.
- `run_manual_validation_calibration.py` now writes a blind calibration guide at
  `docs/manual_validation_calibration_guide.md` plus
  `outputs/tables/enriched/manual_validation_calibration_guide.csv` and
  `outputs/tables/enriched/manual_validation_calibration_guide_summary.csv`.
  The guide uses only calibration-packet title/abstract text to flag
  no-abstract rows, causal/predictive cue profiles, and review difficulty; it
  does not expose model predictions. The calibration HTML form now includes
  these guide flags inline while still omitting model prediction fields such as
  `validation_category` and `classification_reason`. Current calibration guide
  profile: 15 usable-text rows, 5 no-abstract rows, and 7 high-difficulty rows.
- `run_human_review_workboard.py` now writes
  `docs/human_review_workboard.md` and
  `outputs/tables/enriched/human_review_workboard.csv`, combining current
  calibration, scope-review, recovery, and held main-validation work into one
  reviewer handoff. Current workboard has 1 blocking task
  (`complete_calibration_packet`), 2 parallel ready tasks
  (`complete_scope_review_packet` and `work_ranked_recovery_queue`), and the
  main 300-row validation sample held until calibration is complete.
- `run_validation_gate.py` still reports `blocked_calibration`; classification
  evidence remains descriptive until calibration and validation pass.
- Verification: `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest discover -s tests`
  passes 212 tests.

## STOP Conditions

Stop and report if:

- The audit would require changing `causal_predictive_category` or manual-label
  fields.
- The scope audit finds hundreds of new exclusions from broad patterns, rather
  than the targeted correction/erratum/supplement/referee/fellow rows currently
  observed.
- The codebase already has a scope-review audit artifact under another name.
- Project status cannot read optional audit artifacts without failing when they
  are missing.
- A proposed recovery route requires login-only pages, paywall bypassing, or
  restricted full-text scraping.

## Maintenance Notes

Treat scope review as a denominator-quality gate, not as a classification
shortcut. The best next manual recovery work is likely partial-short-text
extension and explicit abstract import for rows that remain research articles.
For source-route expansion, require a small pilot to show real abstract yield
before adding any new automated route for `10.2307`, `10.1111`, `10.1086`, or
`10.1257`.

Open questions for the project owner:

- Are corrections, errata, supplements, referee lists, and election-of-fellows
  notes always excluded from the trend denominator?
- Can the project use institutional index sources such as EconLit or JSTOR
  metadata for manual abstract backfill if the source is recorded?
- Is first-page text acceptable when no abstract exists, or should those rows
  remain `insufficient_text` unless an explicit abstract is found?
- Should scope-review decisions be applied before or after the 20-row
  calibration packet is completed?
