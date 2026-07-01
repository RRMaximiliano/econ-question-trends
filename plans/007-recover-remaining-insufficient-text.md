# Plan 007: Recover Remaining Insufficient Text In Staged Source Passes

> **Executor instructions**: Follow this plan step by step. Run every verification command and confirm the expected result before moving to the next step. If anything in the "STOP conditions" section occurs, stop and report rather than improvising.
>
> **Drift check (run first)**: `test -f data/final/articles_classified_enriched_pilot.csv && test -f data/intermediate/text_enrichment_attempts.csv && echo no-git-repo-current-files-present`
> Expected result in the current workspace: `no-git-repo-current-files-present`. This workspace is not currently a git repository, so no commit SHA is available for drift comparison. If the workspace has become a git repo, run `git diff --stat HEAD -- plans/007-recover-remaining-insufficient-text.md code/06_enrich code/05_analysis config README.md docs` and inspect any in-scope drift before proceeding.

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: MED
- **Depends on**: `plans/006-enrich-insufficient-text.md`
- **Category**: direction
- **Planned at**: no git repo detected, 2026-06-29

## Why This Matters

The enriched gate is close enough to pass the metadata threshold, but 3,912 scoped research rows still classify as `insufficient_text`, or 19.08% of analysis rows. That share is just under the configured 20% stop line and is concentrated in older articles, so trend estimates before the 2000s can still be biased by missing text. The right next move is not one more broad API sweep; it is a staged recovery workflow that measures which source families reduce missingness and stops before restricted full-text scraping.

## Current State

- `data/final/articles_classified_enriched_pilot.csv` has 23,903 rows. After excluding `review_erratum_paratext`, `comment_reply`, and `lecture_address`, it has 20,501 scoped research rows.
- Remaining scoped research `insufficient_text`: 3,912 rows, 19.08%.
- Remaining insufficient share by journal: Econometrica 26.2%, JPE 24.1%, AER 21.2%, QJE 11.0%, ReStud 6.3%.
- Remaining insufficient share by decade: 1970s 48.7%, 1980s 33.8%, 1990s 21.6%, 2000s 11.7%, 2010s 10.3%, 2020s 1.3%.
- Remaining scoped research insufficient rows by enrichment status: `not_found` 3,406, `partial_short_text` 512, `pdf_candidate` 21.
- Of the 3,912 scoped research insufficient rows, 3,901 have an OpenAlex ID, 2,392 have a DOI, 57 have an OA PDF URL, and 3,411 have no abstract text at all.
- `data/intermediate/text_enrichment_attempts.csv` shows Unpaywall was skipped 7,806 times because `CONTACT_EMAIL` was missing, and Semantic Scholar had rate-limit failures without an API key.

Relevant code excerpts:

- `code/06_enrich/text_enrichment.py:73-86` selects candidate rows by `causal_predictive_category == insufficient_text` or text length below `minimum_usable_text_chars`.
- `code/06_enrich/text_enrichment.py:89-99` currently prioritizes DOI, title, recent year, and text length; it does not yet prioritize the older high-missingness journal-year cells.
- `code/06_enrich/text_enrichment.py:682-779` runs source attempts and records one row per candidate with `enrichment_status`, `enrichment_source`, `oa_pdf_url`, and `enrichment_detail`.
- `code/06_enrich/text_enrichment.py:782-835` applies only `enriched` results to the article file while preserving `abstract_original`.
- `code/06_enrich/pdf_text_extraction.py:75-154` downloads OA PDFs, extracts first pages, and marks rows `extracted`, `download_error`, `too_short`, or `extract_error`.
- `code/05_analysis/classification_diagnostics.py:119-148` filters analysis rows by `article_scope` before computing the expansion gate.

Existing verification pattern:

- `tests/test_text_enrichment.py` covers candidate selection, RePEc parsing, OA PDF URL detection, scope assignment, enrichment application, and merge behavior.
- `tests/test_classification_diagnostics.py` covers scope filtering and gate recommendations.

## Commands You Will Need

| Purpose | Command | Expected on success |
|---|---|---|
| Tests | `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` | exits 0; current baseline is 212 tests |
| Syntax check | `python3 - <<'PY' ... compile selected files ... PY` | prints `syntax_ok=<N>` without writing `__pycache__` |
| Cached enrichment rebuild | `python3 run_text_enrichment.py --cached-only --no-merge-existing` | exits 0 and rebuilds from cache only |
| Reclassify enriched file | `python3 run_classification_pilot.py --input data/final/articles_enriched_pilot.csv --output data/final/articles_classified_enriched_pilot.csv` | exits 0 |
| Diagnostics | `python3 run_classification_diagnostics.py --classified data/final/articles_classified_enriched_pilot.csv --validation data/intermediate/manual_validation_sample.csv --output-dir outputs/tables/enriched --report docs/classification_diagnostics_enriched.md` | exits 0 and writes recommendation |

For the syntax check, use this shape:

```bash
python3 - <<'PY'
from pathlib import Path
paths = [
    'run_text_enrichment.py',
    'run_pdf_text_enrichment.py',
    'code/06_enrich/text_enrichment.py',
    'code/06_enrich/pdf_text_extraction.py',
    'code/05_analysis/classification_diagnostics.py',
]
for path in paths:
    compile(Path(path).read_text(encoding='utf-8'), path, 'exec')
print(f'syntax_ok={len(paths)}')
PY
```

## Scope

**In scope**:

- `config/text_enrichment.yml`
- `code/06_enrich/text_enrichment.py`
- `code/06_enrich/pdf_text_extraction.py`
- `code/05_analysis/classification_diagnostics.py`, only if a metric/report field is needed
- `tests/test_text_enrichment.py`
- `tests/test_classification_diagnostics.py`, only if diagnostics output changes
- `README.md`
- `docs/text_enrichment_report.md`
- `docs/pdf_text_extraction_report.md`
- `docs/classification_diagnostics_enriched.md`
- Generated data files under `data/intermediate/`, `data/final/`, and `outputs/tables/enriched/`

**Out of scope**:

- Do not change manual validation labels or reviewer packets.
- Do not scrape restricted publisher or JSTOR full text.
- Do not overwrite `data/final/articles_pilot.csv`; enriched text must stay in `data/final/articles_enriched_pilot.csv`.
- Do not lower `minimum_usable_text_chars` just to reduce `insufficient_text`.
- Do not treat title-only labels as final labels unless the user explicitly approves that design decision.

## Steps

### Step 1: Add A Remaining-Gap Report

Add a small reporting function or CLI output that summarizes remaining scoped research `insufficient_text` rows by journal, decade, enrichment status, abstract source, and identifier availability. It can live in `code/06_enrich/text_enrichment.py` if it naturally fits the enrichment report, or in `code/05_analysis/classification_diagnostics.py` if it is clearer as a diagnostic artifact.

The report must write a CSV, for example `outputs/tables/enriched/remaining_insufficient_text_profile.csv`, and include enough fields to decide the next batch order:

- `journal_short`
- `decade`
- `rows`
- `insufficient_rows`
- `insufficient_share`
- `has_doi_rows`
- `has_openalex_rows`
- `has_oa_pdf_rows`
- `missing_abstract_rows`
- `partial_short_text_rows`

Use `article_scope` and the configured excluded scopes from `config/classification_diagnostics.yml`; do not hard-code analysis rows differently from diagnostics.

**Verify**: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` -> all tests pass.

### Step 2: Run A Proper Unpaywall Pass

Set `CONTACT_EMAIL` in the shell before running this step. The current code requires it, and `contact_email()` reads `CONTACT_EMAIL`, `CROSSREF_MAILTO`, or `OPENALEX_MAILTO` from the environment.

Run a bounded Unpaywall-only pass first:

```bash
export CONTACT_EMAIL="your-real-contact-email@example.com"
python3 run_text_enrichment.py --sources unpaywall --limit 1000 --max-queries 1000
```

Then inspect:

```bash
python3 - <<'PY'
import pandas as pd
attempts = pd.read_csv('data/intermediate/text_enrichment_attempts.csv', dtype=str).fillna('')
print(attempts[attempts['attempt_source'].eq('unpaywall')]['attempt_status'].value_counts(dropna=False).to_string())
print(attempts[attempts['attempt_source'].eq('unpaywall')]['attempt_detail'].replace('', '(none)').value_counts().head(20).to_string())
PY
```

If Unpaywall produces OA PDF URLs, run PDF extraction:

```bash
python3 run_pdf_text_enrichment.py --retry-existing
```

**Verify**: `docs/pdf_text_extraction_report.md` updates and `data/intermediate/text_enrichment_pdf_text.csv` contains any new `extracted` rows if new OA PDFs were found.

### Step 3: Run Semantic Scholar With Credentials Or Slow Batches

If `SEMANTIC_SCHOLAR_API_KEY` is available, set it and run DOI-based batches:

```bash
export SEMANTIC_SCHOLAR_API_KEY="..."
python3 run_text_enrichment.py --sources semantic_scholar --limit 1000 --max-queries 1000
```

If there is no API key, use smaller slow batches and preserve cache:

```bash
python3 run_text_enrichment.py --sources semantic_scholar --limit 200 --max-queries 200
```

Do not enable title search globally yet. Title search should be tested separately because older article titles can collide.

**Verify**: `data/intermediate/text_enrichment_attempts.csv` has fewer `rate_limited` rows for `semantic_scholar`, and any `found` rows have title-match details at or above the existing threshold.

### Step 4: Add Targeted Journal URL Templates

Add source-specific URL generation for high-yield journal families only where the URL pattern is deterministic and title verification is possible. Start with the current successful precedent: `tests/test_text_enrichment.py:69-71` checks JPE DOI fallback to an IDEAS URL for `10.1086/...`.

Add one journal family at a time, with tests:

- Econometrica `10.2307/...` and `10.3982/...` records: investigate whether they map to stable publisher, Wiley, Econometric Society, RePEc, or JSTOR metadata pages that expose abstracts legally.
- AER older records: investigate whether AEA, JSTOR metadata, or RePEc pages expose abstracts or stable metadata snippets.
- JPE older records: extend the existing University of Chicago/RePEc DOI URL strategy only if tests can prove deterministic mapping.

For each new source/template:

- Require DOI or a stable source ID.
- Fetch metadata pages only, not restricted full text.
- Extract only abstracts, citation description metadata, or OA PDF URLs.
- Require `title_match_score >= 0.82` before accepting title-search results.
- Record `attempt_detail` with the URL template used.

**Verify**: Add tests modeled after `test_repec_candidate_urls_adds_jpe_doi_fallback`, `test_extract_econpapers_abstract_reads_citation_meta`, and `test_title_match_score_accepts_minor_punctuation_changes`. Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` -> all pass.

### Step 5: Create A Title-Only Triage Layer, Not Final Labels

For rows that still lack abstracts, add an optional triage output such as `data/intermediate/title_only_triage_candidates.csv`. This must not alter `causal_predictive_category`.

The triage file should include:

- `article_id`, `journal_short`, `publication_year`, `title`
- rule-based title indicators using the existing causal/predictive dictionaries
- `title_only_suggested_category`
- `title_only_confidence`
- `title_only_reason`
- `needs_manual_review = True`

Use this for manual prioritization and possible sensitivity analysis only. Do not merge title-only labels into the main classified file until the user decides that title-only classification is acceptable.

**Verify**: New tests prove title-only triage leaves `data/final/articles_classified_enriched_pilot.csv` categories unchanged.

### Step 6: Rebuild, Reclassify, And Compare Gates

After any new source stage, rebuild from cache and rerun classification:

```bash
python3 run_text_enrichment.py --cached-only --no-merge-existing
python3 run_pdf_text_enrichment.py --report-only
python3 run_classification_pilot.py --input data/final/articles_enriched_pilot.csv --output data/final/articles_classified_enriched_pilot.csv
python3 run_classification_diagnostics.py --classified data/final/articles_classified_enriched_pilot.csv --validation data/intermediate/manual_validation_sample.csv --output-dir outputs/tables/enriched --report docs/classification_diagnostics_enriched.md
```

Record before/after rows:

- total scoped research rows
- scoped research `insufficient_text` count and share
- journal-level insufficient shares
- decade-level insufficient shares
- source yield by source and status
- number of new PDF candidates and extracted PDF texts

**Verify**: The diagnostics report still uses `article_scope` and still excludes nonresearch scopes.

## Test Plan

- Add tests in `tests/test_text_enrichment.py` for any new source URL template, parser, or triage helper.
- If adding diagnostics output, add a focused test in `tests/test_classification_diagnostics.py` using the existing `analysis_scope_filter` pattern.
- Keep network calls out of unit tests. Test parsers and URL builders with local HTML/string fixtures.
- Run the full test command: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests`.

## Current Run Notes

- Step 1 is implemented. `run_classification_diagnostics.py` now writes `outputs/tables/enriched/remaining_insufficient_text_profile.csv` and includes a "Remaining Insufficient Text Profile" section in `docs/classification_diagnostics_enriched.md`.
- Current profile shape: 30 rows by `journal_short` and decade, with columns for total rows, insufficient rows/share, DOI handles, OpenAlex handles, OA PDF URLs, missing abstracts, and partial short text.
- Largest remaining recovery cells after scoped filtering are AER 1980s, AER 1990s, Econometrica 1980s, AER 2010s, Econometrica 1970s, JPE 1980s, AER 1970s, and JPE 1970s.
- The current environment does not define `CONTACT_EMAIL`, `CROSSREF_MAILTO`, `OPENALEX_MAILTO`, or `SEMANTIC_SCHOLAR_API_KEY`, so Step 2 and Step 3 source passes were not run in this continuation.
- Step 5 is implemented as `outputs/tables/enriched/title_only_triage_candidates.csv`. It is a separate manual-review/sensitivity artifact only; it does not alter `causal_predictive_category`.
- Current title-only triage shape after the OCR and publisher-metadata passes is 3,912 rows. All rows have `needs_manual_review=True`; 107 have title-only `causal` suggestions, 19 have title-only `predictive` suggestions, and 3,786 remain title-only `other`.
- A verification merge against `data/final/articles_classified_enriched_pilot.csv` confirms all triage rows still have final `causal_predictive_category == insufficient_text`.
- Diagnostics now write `outputs/tables/enriched/insufficient_text_recovery_queue.csv` and include an "Insufficient Text Recovery Queue" section in `docs/classification_diagnostics_enriched.md`. The queue now ranks 3,912 unresolved scoped research rows into 100-row recovery batches and includes DOI/OpenAlex/Crossref/title lookup URLs plus backfill-import columns.
- Current recovery queue action counts are 1,930 `recover_abstract_from_doi_or_publisher`, 1,476 `review_openalex_or_title_match`, 496 `extend_existing_short_abstract`, and 37 `review_oa_pdf_or_first_pages`.
- A targeted `publisher_metadata` enrichment source now handles public AEA article pages for `10.1257/...` DOI records and Academic Commons metadata/PDF links for `10.7916/...` DOI records. It extracts explicit abstract sections or abstract-marked metadata, rejects citation-only descriptions, and is covered by network-free URL/parser/cache tests. The AEA pass has 265 cached page responses and contributes 5 research rows: 2 `enriched` rows and 3 `partial_short_text` rows. The Academic Commons pass added 8 PDF candidates; normal PDF extraction recovered 1 usable row, and OCR fallback recovered the remaining 7, for 8 total `oa_pdf_first_pages` rows from this pass.
- `run_text_enrichment.py` now supports source-family filters with `--doi-prefixes`, `--journals`, `--start-year`, and `--end-year`, so future metadata passes can target DOI families without crawling every unresolved row.
- The scope patterns now exclude `The American Economic Review` front matter, and enrichment-result merging now prefers current nonresearch-scope skips over older recovered-text statuses. This removed 24 journal-title rows from the scoped research recovery queue without changing final labels for research articles.
- A bounded R001 Semantic Scholar retry without an API key recovered 0 abstracts because the service returned 429 rate limits. The enrichment loop now preserves `rate_limited` results and halts later candidate requests after a rate limit instead of continuing to query.
- Recovery batches are available via `run_recovery_batches.py`. Current generated artifacts are 40 CSV packets in `data/intermediate/insufficient_text_recovery_batches/`, 40 local HTML forms in `data/intermediate/insufficient_text_recovery_forms/`, and `outputs/tables/enriched/insufficient_text_recovery_batch_summary.csv`.
- Recovery batch regeneration preserves filled `abstract`, `source`, `source_url`, `source_record_id`, and non-generated reviewer `notes` from existing batch CSVs by `article_id`; `--overwrite-existing` is now the explicit reset path.
- Recovery batch imports can use `run_import_abstract_backfill.py --skip-empty-abstracts` to ignore unfinished rows. The first R001 OCR-assisted import skipped 88 empty rows and imported 12 rows; a cached R014 OA-PDF OCR import skipped 99 empty rows and imported 1 row. Both produced 0 errors.
- Backfill imports now also maintain cumulative audit files, `data/intermediate/abstract_backfill_import_history.csv` and `data/intermediate/abstract_backfill_import_error_history.csv`, with an `import_source_file` column. The current imported history has 13 rows and the error history has 0 rows.
- PDF text extraction now has an opt-in OCR fallback (`run_pdf_text_enrichment.py --ocr-fallback --ocr-pages 3`) for scanned OA PDFs. In the first R001 pass it recovered 12 usable `oa_pdf_first_pages` texts from scanned PDFs; the audit extract is `data/intermediate/insufficient_text_recovery_batch_R001_ocr_recovered.csv`, with a compact report at `docs/pdf_text_extraction_r001_ocr_recovered.md`.
- A cached-only remaining OA-PDF OCR pass recovered 1 additional usable `oa_pdf_first_pages` text; the audit extract is `data/intermediate/insufficient_text_recovery_cached_oa_pdf_ocr_recovered.csv`, with a compact report at `docs/pdf_text_extraction_cached_oa_pdf_ocr_recovered.md`.
- The recovery queue now has 37 `review_oa_pdf_or_first_pages` rows, all blocked by prior PDF download errors such as `403`, `405`, HTML responses, or Econometric Society read timeouts; that blocker profile is `outputs/tables/enriched/remaining_oa_pdf_download_blockers.csv`, summarized in `docs/remaining_oa_pdf_download_blockers.md`.
- `run_recovery_batch_autofill.py` copies accepted enriched results back into a recovery batch CSV for import. The first R001 autofill wrote `outputs/tables/enriched/recovery_batch_autofill_summary_R001.csv` and `docs/recovery_batch_autofill_R001_report.md`.
- Recovery progress is consolidated by `run_recovery_progress.py`, which writes `outputs/tables/enriched/recovery_progress_overview.csv`, `outputs/tables/enriched/recovery_progress_by_batch.csv`, and `docs/recovery_progress_status.md`. Current status: 3,912 remaining recovery rows, 13 cumulative imported recovery rows, 300 remaining manual validation labels, and next recovery batch `R001`.
- Current regenerated R001 recovery batch has 100 high-priority rows: 41 `recover_abstract_from_doi_or_publisher`, 41 `extend_existing_short_abstract`, and 18 `review_oa_pdf_or_first_pages`; the 12 recovered OCR rows, 2 AEA publisher-metadata enriched rows, and 8 Academic Commons PDF-text rows are no longer in the insufficient-text queue.
- A curated abstract backfill importer is available via `run_import_abstract_backfill.py`. It accepts CSV exports with `article_id`, `doi`, or high-confidence `title` plus `publication_year`, validates title matches, rejects duplicates/errors, merges accepted rows into the existing enrichment table, and preserves `data/final/articles_pilot.csv`.
- A blank backfill template is available at `data/intermediate/abstract_backfill_template.csv`.
- Manual-validation diagnostics now write `outputs/tables/enriched/validation_category_metrics.csv` and `outputs/tables/enriched/validation_disagreements.csv`. They are currently empty with stable schemas because no manual labels have been completed yet; once labels are imported, they will report per-label precision/recall/F1 and disagreement packets for adjudication.
- Sensitivity diagnostics now write `outputs/tables/enriched/category_sensitivity_by_year.csv` and `outputs/tables/enriched/category_sensitivity_by_journal.csv`. Scenarios are `baseline`, `exclude_insufficient_text`, `insufficient_text_as_other`, `title_triage_non_other`, and `title_triage_all_suggestions`; these are derived sensitivity tables and do not change final article labels.
- Current sensitivity output shapes: 867 year-scenario-category rows and 85 journal-scenario-category rows.
- A recent 2023-2025 trend summary is available via `run_trend_summary.py`. It writes `docs/recent_trend_summary_enriched.md`, `outputs/tables/enriched/recent_category_trends.csv`, `outputs/tables/enriched/recent_category_trend_changes.csv`, `outputs/tables/enriched/recent_journal_category_trends.csv`, and `outputs/tables/enriched/recent_journal_category_trend_changes.csv`.
- Current recent trend run covers 1,394 scoped research rows for 2023-2025 and keeps the report explicitly validation-gated under the current `pause_for_manual_validation` recommendation.
- Manual-validation diagnostics now also write `outputs/tables/enriched/validation_adjudication_packet.csv`, which mirrors disagreement rows and adds `adjudicated_label`, `adjudication_notes`, `adjudicator_id`, and `adjudication_date` fields for later adjudication.
- Current adjudication packet is empty with a stable 15-column schema because no manual labels have been completed and no disagreements exist yet.
- Manual-validation imports now also write `outputs/tables/enriched/manual_validation_batch_completion.csv` and include a "Batch Completion" section in `docs/manual_validation_status.md`. The current batch summary has six 50-row batches, 0 completed manual labels, 300 remaining labels, and 0 import errors.
- `run_apply_validation_labels.py --dry-run` validates exported reviewer CSVs without writing the merged validation sample. By default it writes `docs/manual_validation_dry_run_status.md` and `outputs/tables/enriched/manual_validation_dry_run_*.csv`, keeping real import status separate from preflight checks.
- `run_apply_adjudication_labels.py` validates and applies completed `validation_adjudication_packet.csv` rows into separate `adjudicated_*` columns on the validation sample, with a `--dry-run` mode that writes separate adjudication dry-run status files. Completed adjudication rows must include notes, adjudicator ID, ISO adjudication date, and disagreement context from either diagnostics (`manual_label` plus `predicted_label`) or overlap QA (`primary_manual_label` plus `overlap_manual_label`). Classification diagnostics now uses `adjudicated_label` as the effective human label when present.
- The manual-validation sample was regenerated from the latest classified file with seed `20260628` and scoped exclusions for `review_erratum_paratext`, `comment_reply`, and `lecture_address`. Current sample mix is 122 `other`, 94 `insufficient_text`, 52 `causal`, and 32 `predictive`, with 0 completed manual labels and 0 drifted rows against `data/final/articles_classified_enriched_pilot.csv`.
- `run_validation_sample.py` now refuses to overwrite a validation sample with completed `manual_label` values unless `--overwrite-labeled` is passed explicitly.
- `run_manual_validation_readiness.py` now writes `docs/manual_validation_readiness.md`, `outputs/tables/enriched/manual_validation_readiness.csv`, and `outputs/tables/enriched/manual_validation_sample_drift.csv`. Current readiness is `yes`, with 6 reviewer batches, next incomplete batch `B001`, 0 drifted articles, and 300 remaining manual labels.
- `run_manual_validation_readiness.py` also writes `docs/manual_validation_portal.html`, a local reviewer start page with links to the codebook, status/readiness reports, all six main reviewer forms, the calibration kickoff checklist, the calibration form, and the overlap QA form. The portal now includes live main-label, calibration, overlap, adjudication, and drift counts from the current summary CSVs.
- `run_manual_validation_calibration.py` now writes a separate 20-row reviewer calibration packet, browser form, submissions directory, `docs/manual_validation_calibration.md`, `docs/manual_validation_calibration_kickoff.md`, `outputs/tables/enriched/manual_validation_calibration_kickoff.csv`, and calibration agreement/disagreement CSVs. Current calibration status has 20 rows and 0 completed calibration labels; the kickoff packet profile has 15 rows with abstracts and 5 without.
- `run_manual_validation_overlap.py` now writes a separate 30-row second-review QA packet, `data/intermediate/manual_validation_overlap/manual_validation_overlap_packet.csv`, browser forms under `data/intermediate/manual_validation_overlap_forms/`, `docs/manual_validation_overlap.md`, and overlap agreement/disagreement CSVs under `outputs/tables/enriched/`. Current overlap status has 30 rows and 0 completed overlap labels.
- Reviewer HTML forms now initialize their dropdowns/text fields from existing CSV values, so regenerated forms preserve partially completed labels instead of showing blank fields. They also warn about missing confidence, reviewer IDs, review dates, and invalid date formats before export, with bulk buttons for reviewer ID and current date.
- `run_validation_gate.py` now writes `docs/manual_validation_gate.md`, `outputs/tables/enriched/manual_validation_gate.csv`, and `outputs/tables/enriched/manual_validation_gate_checks.csv`. Current gate is `blocked_calibration`, with first next action to complete the 20-row calibration packet before assigning the full validation sample.
- `publisher_metadata` now supports public Econometric Society DOI pages for `10.3982/...` records. A bounded `10.3982` pass recovered 27 analysis-relevant rows, moving the scoped insufficient-text queue from 3,939 to 3,912 rows and the insufficient-text share from 19.21% to 19.08%.
- `run_insufficient_text_expansion_plan.py` now summarizes the unresolved queue into source-family lanes and DOI-prefix passes. Current outputs cover 3,912 planned rows across 8 lanes. The largest remaining DOI-prefix opportunities are `10.2307` (1,048 rows), `10.1086` (810 rows), `10.1257` (239 rows), and `10.1111` (155 rows). The plan now marks `10.2307`, `10.1111`, `10.1093/...`, and `10.1162` as unsupported by automated `publisher_metadata` routes until tested public metadata pages are available.
- The expansion plan now writes `outputs/tables/enriched/insufficient_text_recovery_decisions.csv`, `outputs/tables/enriched/insufficient_text_source_route_matrix.csv`, `outputs/tables/enriched/insufficient_text_source_investigation_packet.csv`, and `outputs/tables/enriched/insufficient_text_expansion_attempt_summary.csv`, and includes all four in `docs/insufficient_text_expansion_plan.md`. For `10.1086`, prior attempts cover 984 articles with 80 prior found articles, 887 error attempts, 3,342 not-found attempts, 1,886 skipped attempts, 2,318 not-cached attempts, and 27 rate-limited attempts; the `econpapers` source specifically has 130 found attempts but 877 `Not Found` errors. The decision table marks `10.1086` as `source_specific_investigation_before_rerun`, while `10.2307` and `10.1111` are `new_source_template_or_manual_recovery`. The route matrix has 18 rows and marks `10.1086` as `do_not_rerun_landing_pages`, while `10.2307` and `10.1111` are `unsupported_existing_route`; the investigation packet currently has 113 evidence rows: 80 failed current-queue attempts, 18 found reference attempts, and 15 lane queue samples.
- `run_source_route_probe.py` now checks a bounded set of representative public landing/metadata pages from the investigation packet. The current 24-row probe found 22 `access_challenge` pages and 2 RePEc `not_found` pages, with 0 abstracts and 0 PDF candidates. This supports manual/index recovery or new lawful source templates instead of broad reruns of DOI landing pages.
- `run_project_status.py` now writes a consolidated handoff across validation, calibration, recovery progress, and source-route decisions: `docs/project_status.md`, `outputs/tables/enriched/project_status_summary.csv`, and `outputs/tables/enriched/project_next_actions.csv`. Current first action is `complete_calibration_packet`; parallel researcher action is recovery batch `R001`.
- `run_recovery_batch_workplan.py` now writes a row-level workplan for the next recovery packet: `docs/recovery_batch_R001_workplan.md` and `outputs/tables/enriched/recovery_batch_R001_workplan.csv`. Current R001 status is 41 `manual_index_or_new_template`, 38 `manual_extend_partial_text`, 13 `pdf_route_blocked_use_manual_metadata`, 7 `scope_review_before_recovery`, and 1 `suspect_pdf_url_use_manual_metadata`; this avoids retrying already-blocked PDFs, likely out-of-scope rows, and false non-article PDF URLs.
- `run_recovery_review_queue.py` now writes a non-mutating row-level source guide for the 93 ready R001 rows: `outputs/tables/enriched/recovery_batch_R001_source_guide.csv`, `outputs/tables/enriched/recovery_batch_R001_source_guide_summary.csv`, `docs/recovery_batch_R001_source_guide.md`, and the guided browser form `data/intermediate/insufficient_text_recovery_review_forms/R001/recovery_batch_R001_guided_queue.html`. It also writes tiered quick-win packets in `outputs/tables/enriched/recovery_batch_R001_tiered_packets/`, `outputs/tables/enriched/recovery_batch_R001_tiered_packet_index.csv`, `docs/recovery_batch_R001_tiered_packets.md`, and tiered HTML forms under `data/intermediate/insufficient_text_recovery_review_forms/R001/tiered/`; partial-extension forms are prefilled with the current short abstract. Current source-guide families are 38 `partial_text_extension`, 24 `jpe_chicago_or_repec`, 17 `jstor_or_legacy_doi`, and 14 `pdf_blocker_metadata`; the guide records first-source, fallback-source, acceptable-evidence, and stop-rule guidance without changing importable split packets or CSV export columns.
- `run_recovery_tiered_stage.py` stages completed tiered-form exports from `data/intermediate/insufficient_text_recovery_review_exports/R001/` into non-mutating split-packet copies under `data/intermediate/insufficient_text_recovery_staged/R001/`. It writes `outputs/tables/enriched/recovery_batch_R001_staged_split_summary.csv`, `outputs/tables/enriched/recovery_batch_R001_tiered_stage_changes.csv`, `outputs/tables/enriched/recovery_batch_R001_tiered_stage_errors.csv`, and `docs/recovery_batch_R001_tiered_stage.md`; it rejects unknown rows, duplicate completed rows, missing source provenance, and partial-extension rows that were not actually extended before preflight/import.
- Verification on 2026-06-29: `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest discover -s tests` passed 171 tests at implementation time; the current full-suite baseline is tracked in `plans/README.md`.
- Regenerated diagnostics still recommend `pause_for_manual_validation`.

## Done Criteria

All must hold:

- [x] The remaining insufficient-text profile CSV exists and includes journal and decade breakdowns.
- [x] Unpaywall has been retried with `CONTACT_EMAIL` set, or the run notes explain why this could not be done.
- [x] Semantic Scholar has been retried with an API key or slow bounded batches, or the run notes explain why this could not be done.
- [x] Any new source/template has parser and URL-builder tests.
- [x] No restricted full-text scraping is introduced.
- [x] `data/final/articles_pilot.csv` is unchanged by the enrichment workflow.
- [x] `data/final/articles_classified_enriched_pilot.csv` is regenerated after enrichment.
- [x] `docs/classification_diagnostics_enriched.md` reports the updated gate.
- [x] `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` passes.
- [x] `plans/README.md` status for plan 007 is updated.

## STOP Conditions

Stop and report if:

- A proposed source requires logging in, bypassing paywalls, or scraping restricted full text.
- A source result cannot be matched to the article title with a defensible threshold.
- The implementation would require lowering `minimum_usable_text_chars`.
- Title-only triage starts changing final labels instead of producing a separate review file.
- A source batch produces many ambiguous title matches for older articles.
- Tests fail twice after a reasonable fix attempt.

## Maintenance Notes

The highest-value remaining work is not all rows equally. Prioritize older Econometrica, JPE, and AER cells because they dominate pre-2000 missingness. Keep each source's yield auditable: reviewers should be able to answer how many rows each source recovered, how many failed, and whether the remaining historical trend is robust to treating unresolved rows as missing.
