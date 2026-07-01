# Economics Question Trends

This repository builds a reproducible article-level metadata pilot for studying how the focus of economics journal articles has evolved across causal, predictive, and other research questions.

The current batch covers 1975-2025 for five general-interest journals:

- American Economic Review
- Quarterly Journal of Economics
- Journal of Political Economy
- Econometrica
- Review of Economic Studies

## Run The Phase 1 Pilot

```bash
python3 run_phase1_pilot.py --start-year 1975 --end-year 2025
```

Optional polite API contact metadata can be set with:

```bash
export CONTACT_EMAIL="you@example.com"
```

## Verify The Code

```bash
python3 -m unittest discover -s tests
```

Use a Python environment with `requirements.txt` installed. In the current macOS workspace, `/usr/bin/python3` has the needed packages and the Homebrew `python3` may not have `PyYAML`.

For a no-network rebuild from the saved 1975-2025 raw responses:

```bash
python3 run_phase1_pilot.py --start-year 1975 --end-year 2025 --run-id 1975_2025_yearly_crossref_20260628T --skip-collect
```

## Run Rule-Based Classification

```bash
python3 run_classification_pilot.py --input data/final/articles_pilot.csv --output data/final/articles_classified_pilot.csv
```

## Dry-Run LLM Classification

```bash
python3 run_llm_classification_pilot.py --input data/final/articles_classified_pilot.csv --output data/final/articles_classified_llm_sample.csv --limit 10 --dry-run
```

## Create Manual Validation Sample

```bash
python3 run_validation_sample.py --input data/final/articles_classified_enriched_pilot.csv --output data/intermediate/manual_validation_sample.csv --reviewer-output data/intermediate/manual_validation_review_packet.csv --reviewer-mode blind --reviewer-batch-dir data/intermediate/manual_validation_batches --reviewer-html-dir data/intermediate/manual_validation_forms --reviewer-batch-size 50 --sample-size 300 --seed 20260628 --exclude-scopes review_erratum_paratext,comment_reply,lecture_address
```

Use `data/intermediate/manual_validation_review_packet.csv` for one-file blind reviewer labeling, the 50-row blind CSV files in `data/intermediate/manual_validation_batches/` for split reviewer assignment, or the local HTML forms in `data/intermediate/manual_validation_forms/` for dropdown-based labeling and CSV export. The HTML forms show a compact label rubric plus QA warnings for missing confidence, reviewer IDs, review dates, and invalid dates before export; the import/preflight commands reject completed labels that lack confidence, reviewer ID, or ISO review date.
If the existing validation sample already contains completed `manual_label` values, the sample generator refuses to overwrite it unless `--overwrite-labeled` is passed explicitly.
Before assigning labels, run the full review-handoff refresh:

```bash
python3 run_human_review_refresh.py
```

For narrower targeted reruns, refresh only manual-validation readiness or the combined workboard:

```bash
python3 run_manual_validation_readiness.py
python3 run_human_review_workboard.py
```

The refresh command is the safest default before handing work to reviewers. It refreshes calibration, the evidence-tier policy, scope review, the R001 recovery queue/staging/preflight checks, recovery automation audit, manual-validation readiness, validation gate, project status, and the human review workboard. It writes `docs/human_review_refresh.md` and `outputs/logs/human_review_refresh.log`, and it does not apply labels, scope decisions, abstract imports, or trend outputs.
The readiness command writes `docs/manual_validation_readiness.md`, checks whether the sample still matches the current classified file, and reports the next incomplete reviewer batch. It also writes `docs/manual_validation_portal.html`, a local start page with links to the codebook, human review workboard, readiness/status reports, all reviewer batch forms, the calibration kickoff checklist, calibration guide, remaining-row report, spreadsheet template, calibration dashboard/form, overlap QA form, and scope-review packet/guide. The portal also shows current main-label, calibration, overlap, adjudication, and drift counts. The workboard command writes `docs/human_review_workboard.md` and `outputs/tables/enriched/human_review_workboard.csv`, combining calibration, scope review, recovery, and held validation work into one handoff.
Before assigning the full 300-row sample, generate a 20-row calibration packet:

```bash
python3 run_manual_validation_calibration.py
```

This writes `data/intermediate/manual_validation_calibration/manual_validation_calibration_packet.csv`, browser forms under `data/intermediate/manual_validation_calibration_forms/`, the local calibration dashboard at `data/intermediate/manual_validation_calibration_forms/manual_validation_calibration_dashboard.html`, the filtered remaining-row form at `data/intermediate/manual_validation_calibration_forms/manual_validation_calibration_remaining.html`, the spreadsheet fallback at `data/intermediate/manual_validation_calibration/manual_validation_calibration_remaining_submission_template.csv`, `outputs/tables/enriched/manual_validation_calibration_progress.csv`, `docs/manual_validation_calibration_guide.md`, `docs/manual_validation_calibration_remaining.md`, `docs/manual_validation_calibration.md`, and `docs/manual_validation_calibration_kickoff.md`. The guide is blind to model predictions and uses only title/abstract text-status and cue flags to help reviewers focus attention; those guide flags and the compact label rubric are also shown inside the calibration HTML form. Put reviewer exports or completed spreadsheet copies in `data/intermediate/manual_validation_calibration_submissions/`, then rerun the same command to summarize row-level progress, agreement, and discussion rows. Calibration submissions are checked against the active `calibration_id`, `validation_id`, and `article_id` packet keys; multiple reviewers may label the same calibration row, but duplicate rows from the same reviewer are rejected. The validation gate uses completed calibration rows, not just completed label count, before allowing the full validation sample to proceed.
For inter-reviewer quality control, generate a separate 30-row overlap packet for a second blind reviewer:

```bash
python3 run_manual_validation_overlap.py
```

This writes `data/intermediate/manual_validation_overlap/manual_validation_overlap_packet.csv`, browser forms under `data/intermediate/manual_validation_overlap_forms/`, and `docs/manual_validation_overlap.md`. Keep this overlap packet separate from the main validation batch import; it is used to measure reviewer agreement and produce adjudication rows. The overlap command validates the packet against the active validation sample and rejects stale sample rows, duplicate `overlap_id` values, duplicate validation rows, and row-count drift; if the packet is stale and has no completed labels, regenerate it with `--regenerate`.
After reviewers fill the manual fields, import them back into the full sample and refresh diagnostics:

```bash
python3 run_apply_validation_labels.py --reviewer-input data/intermediate/manual_validation_batches --dry-run
python3 run_apply_validation_labels.py --reviewer-input data/intermediate/manual_validation_batches
python3 run_classification_diagnostics.py --classified data/final/articles_classified_enriched_pilot.csv --validation data/intermediate/manual_validation_sample.csv --output-dir outputs/tables/enriched --report docs/classification_diagnostics_enriched.md
python3 run_validation_gate.py
```

The dry-run import validates exported reviewer CSVs and writes `docs/manual_validation_dry_run_status.md` plus `outputs/tables/enriched/manual_validation_dry_run_*.csv` without modifying `data/intermediate/manual_validation_sample.csv`.
If diagnostics writes rows to `outputs/tables/enriched/validation_adjudication_packet.csv`, fill the adjudication fields, then apply them before the final diagnostics refresh:

```bash
python3 run_apply_adjudication_labels.py --dry-run
python3 run_apply_adjudication_labels.py
python3 run_classification_diagnostics.py --classified data/final/articles_classified_enriched_pilot.csv --validation data/intermediate/manual_validation_sample.csv --output-dir outputs/tables/enriched --report docs/classification_diagnostics_enriched.md
python3 run_validation_gate.py
```

Adjudicated labels are kept in separate `adjudicated_*` columns, and diagnostics uses `adjudicated_label` instead of `manual_label` when it is present. Completed adjudication rows must include notes, adjudicator ID, ISO adjudication date, and disagreement context from either diagnostics (`manual_label` plus `predicted_label`) or overlap QA (`primary_manual_label` plus `overlap_manual_label`).
The validation gate writes `docs/manual_validation_gate.md`, `outputs/tables/enriched/manual_validation_gate.csv`, and `outputs/tables/enriched/manual_validation_gate_checks.csv`. Treat trend outputs as evidence only when `validation_gate` is `proceed`; otherwise follow the gate's `next_action`.
For a consolidated handoff across validation, recovery progress, and source-route decisions, run:

```bash
python3 run_project_status.py
```

This writes `docs/project_status.md`, `outputs/tables/enriched/project_status_summary.csv`, and `outputs/tables/enriched/project_next_actions.csv`.

## Enrich Insufficient Text

```bash
python3 run_text_enrichment.py --classified-input data/final/articles_classified_pilot.csv --articles-input data/final/articles_pilot.csv --max-queries 250 --sources openalex,crossref,semantic_scholar,econpapers,publisher_metadata,unpaywall
python3 run_text_enrichment.py --limit 900 --max-queries 300 --sources econpapers
python3 run_pdf_text_enrichment.py
python3 run_classification_pilot.py --input data/final/articles_enriched_pilot.csv --output data/final/articles_classified_enriched_pilot.csv
python3 run_validation_sample.py --input data/final/articles_classified_enriched_pilot.csv --output data/intermediate/manual_validation_sample.csv --reviewer-output data/intermediate/manual_validation_review_packet.csv --reviewer-mode blind --reviewer-batch-dir data/intermediate/manual_validation_batches --reviewer-html-dir data/intermediate/manual_validation_forms --reviewer-batch-size 50 --sample-size 300 --seed 20260628 --exclude-scopes review_erratum_paratext,comment_reply,lecture_address
python3 run_classification_diagnostics.py --classified data/final/articles_classified_enriched_pilot.csv --validation data/intermediate/manual_validation_sample.csv --output-dir outputs/tables/enriched --report docs/classification_diagnostics_enriched.md
```

Remove `--max-queries` only for a full enrichment sweep. Semantic Scholar is rate-limited without an API key; set `SEMANTIC_SCHOLAR_API_KEY` when available.
The bounded `econpapers` pass also checks deterministic IDEAS metadata URLs for JPE `10.1086/...` DOI records; keep it bounded because older RePEc pages can be slow.
The `publisher_metadata` source currently uses public AEA article metadata for `10.1257/...` DOI records and Academic Commons metadata/PDF links for `10.7916/...` DOI records. It rejects citation-only descriptions that do not expose an abstract.
For source-family passes, filter the candidate set before querying:

```bash
python3 run_text_enrichment.py --classified-input data/final/articles_classified_enriched_pilot.csv --articles-input data/final/articles_pilot.csv --sources publisher_metadata --doi-prefixes 10.1257 --max-queries 100
python3 run_text_enrichment.py --classified-input data/final/articles_classified_enriched_pilot.csv --articles-input data/final/articles_pilot.csv --sources publisher_metadata --doi-prefixes 10.7916 --max-queries 20
python3 run_pdf_text_enrichment.py --pdf-candidates data/intermediate/text_enrichment_pdf_candidates_academic_commons.csv --enrichment-candidates data/intermediate/text_enrichment_candidates.csv --output-pdf-text data/intermediate/text_enrichment_pdf_text_academic_commons_ocr.csv --output-candidates data/intermediate/text_enrichment_candidates.csv --output-articles data/final/articles_enriched_pilot.csv --report docs/pdf_text_extraction_academic_commons_ocr_report.md --timeout 20 --retry-existing --ocr-fallback --ocr-pages 3
```

Use `python3 run_text_enrichment.py --cached-only --no-merge-existing` to rebuild enrichment outputs from cached source responses without making new external calls.

## Import Curated Abstract Backfills

Use this when you have abstracts from EconLit, JSTOR metadata, publisher metadata, or hand-curated sources. Start from `data/intermediate/abstract_backfill_template.csv`; each row should include `abstract` plus at least `article_id`, `doi`, or a high-confidence `title` and `publication_year` match. When using `--require-source-metadata`, filled rows must also include `source`, either `source_url` or `source_record_id`, and an importable `evidence_tier`. The shared tier policy is regenerated with `python3 run_evidence_tier_policy.py` and written to `docs/evidence_tier_policy.md` plus `outputs/tables/enriched/evidence_tier_policy.csv`.

```bash
python3 run_import_abstract_backfill.py --input data/intermediate/abstract_backfill_template.csv
python3 run_classification_pilot.py --input data/final/articles_enriched_pilot.csv --output data/final/articles_classified_enriched_pilot.csv
python3 run_classification_diagnostics.py --classified data/final/articles_classified_enriched_pilot.csv --validation data/intermediate/manual_validation_sample.csv --output-dir outputs/tables/enriched --report docs/classification_diagnostics_enriched.md
```

The importer writes latest-run matched rows to `data/intermediate/abstract_backfill_imported.csv`, latest-run rejected rows to `data/intermediate/abstract_backfill_import_errors.csv`, and cumulative audit histories to `data/intermediate/abstract_backfill_import_history.csv` and `data/intermediate/abstract_backfill_import_error_history.csv`. It rejects duplicate article rows, missing abstracts, unknown IDs/DOIs, weak title matches, missing required source metadata, and non-importable evidence tiers. Imported abstracts are merged into `data/final/articles_enriched_pilot.csv`; the original `data/final/articles_pilot.csv` is not overwritten. The default import path replays cumulative enrichment candidates from `data/intermediate/text_enrichment_candidates.csv`, so do not point `--enrichment-candidates` at an empty file unless you intentionally want to rebuild the enriched article file from only that import.

## Work Insufficient-Text Recovery Batches

Generate 100-row recovery packets from the current diagnostics queue:

```bash
python3 run_evidence_tier_policy.py
python3 run_recovery_batches.py
python3 run_insufficient_text_expansion_plan.py
python3 run_source_route_probe.py --max-urls-per-decision 4 --max-total-urls 24
python3 run_scope_review_audit.py
python3 run_scope_review_packet.py
```

This writes editable CSV packets to `data/intermediate/insufficient_text_recovery_batches/`, local browser forms to `data/intermediate/insufficient_text_recovery_forms/`, and a progress summary to `outputs/tables/enriched/insufficient_text_recovery_batch_summary.csv`. Rerunning the command preserves non-empty `abstract`, `source`, `source_url`, `source_record_id`, and reviewer `notes` fields from existing batch CSVs by `article_id`; use `--overwrite-existing` only when you intentionally want a clean reset.
The expansion-plan command summarizes the unresolved recovery queue into source-family lanes and DOI-prefix passes, writing `docs/insufficient_text_expansion_plan.md`, `outputs/tables/enriched/insufficient_text_recovery_decisions.csv`, `outputs/tables/enriched/insufficient_text_source_route_matrix.csv`, `outputs/tables/enriched/insufficient_text_source_investigation_packet.csv`, `outputs/tables/enriched/insufficient_text_expansion_overview.csv`, `outputs/tables/enriched/insufficient_text_expansion_plan.csv`, `outputs/tables/enriched/insufficient_text_expansion_doi_prefixes.csv`, and `outputs/tables/enriched/insufficient_text_expansion_attempt_summary.csv`. The decision, route-matrix, investigation-packet, and attempt-summary tables roll up prior source attempts and probe evidence by DOI prefix/source so reruns can be separated from source-specific failures that need new recovery logic.
The source-route probe checks a bounded set of representative public landing/metadata pages from the investigation packet, writing `docs/source_route_probe.md` and `outputs/tables/enriched/source_route_probe_results.csv`. It does not download restricted full text or update article labels.
The scope-review audit checks whether updated title-scope patterns identify likely nonresearch/parataxt rows that are still in the insufficient-text queue. It writes `docs/scope_review_audit.md`, `outputs/tables/enriched/scope_review_candidates.csv`, and `outputs/tables/enriched/scope_review_summary.csv`. This is a non-mutating audit: review `scope_review_candidates` before recovering abstracts for those rows, and do not use the audit to change `causal_predictive_category` or manual validation labels.
The scope-review packet command deduplicates audit rows to one row per article, writes `data/intermediate/scope_review/scope_review_packet.csv`, a local browser form at `data/intermediate/scope_review_forms/scope_review_packet.html`, `outputs/tables/enriched/scope_review_completion.csv`, and `docs/scope_review_packet.md`. It also writes a non-mutating guide to `outputs/tables/enriched/scope_review_guide.csv`, `outputs/tables/enriched/scope_review_guide_summary.csv`, and `docs/scope_review_guide.md`; the guide groups repeated patterns such as corrections, supplements, election notices, and referee lists so reviewers can work faster without applying automatic decisions. Reviewers should fill only `human_scope_decision`, `scope_review_notes`, `reviewer_id`, and `review_date`; allowed decisions are `exclude_nonresearch`, `keep_research`, and `unsure`.
After the packet is filled, validate it before applying denominator changes:

```bash
python3 run_apply_scope_review_decisions.py
python3 run_apply_scope_review_decisions.py --apply
```

The first command is a dry run that writes `docs/scope_review_apply.md`, `outputs/tables/enriched/scope_review_apply_summary.csv`, `outputs/tables/enriched/scope_review_apply_errors.csv`, and `outputs/tables/enriched/scope_review_apply_changes.csv` without changing final files. It rejects invalid decisions, missing reviewer metadata, duplicate completed `scope_review_id` or `article_id` rows, and rows that do not match target article files. Use `--apply` only after the error file is empty; it updates scope metadata in `data/final/articles_enriched_pilot.csv` and `data/final/articles_classified_enriched_pilot.csv` but still does not alter causal/predictive labels.
For the next recovery packet, generate a row-level workplan that combines the batch rows with prior PDF failures and source-route decisions:

```bash
python3 run_recovery_batch_workplan.py
python3 run_recovery_batch_split.py
python3 run_recovery_review_queue.py
python3 run_recovery_cached_evidence.py
python3 run_recovery_split_preflight.py
python3 run_recovery_action_progress.py
python3 run_recovery_cell_targets.py
```

The workplan command writes `docs/recovery_batch_R001_workplan.md` and `outputs/tables/enriched/recovery_batch_R001_workplan.csv`, so reviewers can avoid retrying blocked PDFs, suspect non-article PDF URLs, likely out-of-scope rows, or unsupported DOI routes.
The split command reorganizes that same editable batch into reviewer-ready packets under `data/intermediate/insufficient_text_recovery_splits/R001/`, local browser forms under `data/intermediate/insufficient_text_recovery_split_forms/R001/`, a split summary at `outputs/tables/enriched/recovery_batch_R001_split_summary.csv`, and `docs/recovery_batch_R001_split.md`. The split packets preserve importable backfill fields and add reviewer context such as current abstract text, current text length, abstract source, text-enrichment status, and prior source-attempt summaries. Work the `ready_partial_text_extension` and `ready_manual_metadata` packets first; leave `waiting_scope_review` untouched until scope review decisions are complete.
The review-queue command combines ready split packets into a ranked manual work queue, writing `outputs/tables/enriched/recovery_batch_R001_review_queue.csv`, `outputs/tables/enriched/recovery_batch_R001_review_queue_summary.csv`, `outputs/tables/enriched/recovery_batch_R001_source_guide.csv`, `outputs/tables/enriched/recovery_batch_R001_source_guide_summary.csv`, `outputs/tables/enriched/recovery_batch_R001_tiered_packet_index.csv`, `docs/recovery_batch_R001_review_queue.md`, `docs/recovery_batch_R001_source_guide.md`, `docs/recovery_batch_R001_tiered_packets.md`, a guided browser form at `data/intermediate/insufficient_text_recovery_review_forms/R001/recovery_batch_R001_guided_queue.html`, and tiered quick-win forms under `data/intermediate/insufficient_text_recovery_review_forms/R001/tiered/`. Start with `source_metadata_fix` rows if any, then clean `tier_1_partial_near_threshold` rows, then `tier_2_partial_replace_suspect_text`, then deeper partial extensions and manual metadata rows. Partial-extension forms are prefilled with the current short abstract only when that text is not flagged as boilerplate; flagged rows must be replaced from source-confirmed metadata while recording source provenance and `evidence_tier`.
The cached-evidence command writes `outputs/tables/enriched/recovery_batch_R001_cached_evidence.csv`, `outputs/tables/enriched/recovery_batch_R001_cached_evidence_summary.csv`, and `docs/recovery_batch_R001_cached_evidence.md`. It also writes the reviewer-facing action packet at `outputs/tables/enriched/recovery_batch_R001_action_packet.csv`, `outputs/tables/enriched/recovery_batch_R001_action_summary.csv`, `outputs/tables/enriched/recovery_batch_R001_action_packet_index.csv`, and `docs/recovery_batch_R001_action_packet.md`, plus action-group CSV packets under `outputs/tables/enriched/recovery_batch_R001_action_packets/` and browser forms under `data/intermediate/insufficient_text_recovery_review_forms/R001/actions/`. It checks only local cached source responses and `data/intermediate/source_records.csv`, does not call the network, and helps reviewers distinguish rows where local metadata only repeats short/suspect text from rows with candidate importable metadata.
Put completed tiered-form or action-form CSV exports in `data/intermediate/insufficient_text_recovery_review_exports/R001/`, then run `python3 run_recovery_tiered_stage.py`. The staging command validates reviewer rows against the active split packets, rejects duplicate completed rows, requires source provenance plus importable `evidence_tier`, rejects title-only or blocked evidence tiers, rejects partial-extension rows that were not actually extended, and writes staged split copies plus `outputs/tables/enriched/recovery_batch_R001_staged_split_summary.csv` for preflight.
The split-preflight command validates all ready split packets together with `--skip-empty-abstracts --require-source-metadata` semantics and the shared evidence-tier policy. Completed rows must use `tier_a_formal_abstract`, `tier_b_source_description`, or `tier_c_first_page_abstract_or_intro`; `tier_d_title_only_triage` and `tier_e_blocked` are rejected before import. It writes `outputs/tables/enriched/recovery_batch_R001_preflight_summary.csv`, `outputs/tables/enriched/recovery_batch_R001_preflight_errors.csv`, and `docs/recovery_batch_R001_preflight.md` without updating enrichment histories or final article files.
The action-progress command writes `outputs/tables/enriched/recovery_batch_R001_action_progress_overview.csv`, `outputs/tables/enriched/recovery_batch_R001_action_progress_summary.csv`, `outputs/tables/enriched/recovery_batch_R001_action_progress_detail.csv`, `docs/recovery_batch_R001_action_progress.md`, and a local launch dashboard at `data/intermediate/insufficient_text_recovery_review_forms/R001/recovery_batch_R001_action_dashboard.html`. It summarizes action-form exports, staged rows, stage errors, and preflight errors by action group without importing abstracts or changing final article files.
The cell-targets command writes `docs/recovery_cell_targets.md`, `outputs/tables/enriched/recovery_cell_targets.csv`, and `outputs/tables/enriched/recovery_cell_target_queue.csv`. Use it to keep recovery balanced across weak journal-decade cells rather than only working the easiest rows; it is non-mutating and does not import abstracts. By default it reports recovered-row needs against a 20% insufficient-text target share, matching `config/classification_diagnostics.yml`, plus a 10% stretch target.
Before importing completed recovery rows, write a baseline impact snapshot and review the experiment queue:

```bash
python3 run_recovery_impact_report.py --snapshot-label before_R001 --write-snapshot
```

This writes `data/intermediate/recovery_impact_snapshots/before_R001.csv`, `outputs/tables/enriched/recovery_impact_summary.csv`, `outputs/tables/enriched/recovery_impact_changes.csv`, `outputs/tables/enriched/recovery_source_experiments.csv`, and `docs/recovery_impact_report.md`. The report is non-mutating; use it to confirm that R001 partial extensions and manual metadata rows are ranked ahead of broad source-template spikes.

Use this recovery decision gate before spending manual time:

- `scope_review_before_recovery` rows: pause abstract recovery until the row's analysis scope is reviewed.
- `manual_extend_partial_text` rows: extend existing short text only from explicit source metadata and record the source.
- `manual_index_or_new_template` rows: use index/title-search links only to find explicit abstracts or source-confirmed metadata; title-only category suggestions stay as sensitivity artifacts.
- `unsupported_existing_route` rows: do not rerun existing source logic unless a bounded public metadata template has been tested.
- `do_not_rerun_landing_pages` rows: do not retry access-challenge landing pages.
- PDF blocker rows: do not retry `403`, `405`, HTML, or timed-out PDF routes unchanged; use explicit metadata or a reachable OA PDF only.

For scanned OA PDFs in a recovery batch, use the OCR fallback deliberately on that batch, then autofill any accepted enrichment results back into the editable recovery CSV:

```bash
python3 run_pdf_text_enrichment.py --pdf-candidates data/intermediate/insufficient_text_recovery_batches/insufficient_text_recovery_batch_R001.csv --enrichment-candidates data/intermediate/text_enrichment_candidates.csv --output-pdf-text data/intermediate/insufficient_text_recovery_batch_R001_pdf_text.csv --output-candidates data/intermediate/text_enrichment_candidates.csv --output-articles data/final/articles_enriched_pilot.csv --report docs/pdf_text_extraction_r001_report.md --ocr-fallback --ocr-pages 3 --retry-existing --timeout 10
python3 run_recovery_batch_autofill.py --batch-input data/intermediate/insufficient_text_recovery_batches/insufficient_text_recovery_batch_R001.csv --summary-output outputs/tables/enriched/recovery_batch_autofill_summary_R001.csv --report docs/recovery_batch_autofill_R001_report.md
```

Partially completed recovery CSVs can be imported with the same abstract backfill command. Use `--skip-empty-abstracts` so unfinished rows are ignored rather than reported as expected missing-abstract errors:

```bash
python3 run_human_review_refresh.py
python3 run_recovery_review_queue.py
python3 run_recovery_cached_evidence.py
python3 run_recovery_tiered_stage.py
python3 run_recovery_split_preflight.py --split-summary outputs/tables/enriched/recovery_batch_R001_staged_split_summary.csv
python3 run_recovery_action_progress.py
python3 run_recovery_impact_report.py --snapshot-label before_R001 --write-snapshot
python3 run_import_abstract_backfill.py --input data/intermediate/insufficient_text_recovery_staged/R001/insufficient_text_recovery_batch_R001_ready_partial_text_extension.csv --skip-empty-abstracts --dry-run --require-source-metadata
python3 run_import_abstract_backfill.py --input data/intermediate/insufficient_text_recovery_staged/R001/insufficient_text_recovery_batch_R001_ready_partial_text_extension.csv --skip-empty-abstracts --require-source-metadata --fail-on-errors
python3 run_import_abstract_backfill.py --input data/intermediate/insufficient_text_recovery_staged/R001/insufficient_text_recovery_batch_R001_ready_manual_metadata.csv --skip-empty-abstracts --dry-run --require-source-metadata
python3 run_import_abstract_backfill.py --input data/intermediate/insufficient_text_recovery_staged/R001/insufficient_text_recovery_batch_R001_ready_manual_metadata.csv --skip-empty-abstracts --require-source-metadata --fail-on-errors
python3 run_classification_pilot.py --input data/final/articles_enriched_pilot.csv --output data/final/articles_classified_enriched_pilot.csv
python3 run_classification_diagnostics.py --classified data/final/articles_classified_enriched_pilot.csv --validation data/intermediate/manual_validation_sample.csv --output-dir outputs/tables/enriched --report docs/classification_diagnostics_enriched.md
python3 run_recovery_impact_report.py --snapshot-label after_R001 --write-snapshot --compare-to before_R001
python3 run_recovery_batches.py
python3 run_recovery_progress.py
python3 run_insufficient_text_expansion_plan.py
python3 run_scope_review_audit.py
python3 run_scope_review_packet.py
python3 run_apply_scope_review_decisions.py
python3 run_project_status.py
python3 run_human_review_workboard.py
python3 run_recovery_batch_workplan.py
python3 run_recovery_batch_split.py
python3 run_recovery_review_queue.py
python3 run_recovery_cached_evidence.py
python3 run_recovery_tiered_stage.py
python3 run_recovery_split_preflight.py --split-summary outputs/tables/enriched/recovery_batch_R001_staged_split_summary.csv
```

## Run Classification Diagnostics

```bash
python3 run_classification_diagnostics.py --classified data/final/articles_classified_pilot.csv --validation data/intermediate/manual_validation_sample.csv --output-dir outputs/tables --report docs/classification_diagnostics.md
```

## Run Recent Trend Summary

```bash
python3 run_trend_summary.py --classified data/final/articles_classified_enriched_pilot.csv --recommendation outputs/tables/enriched/classification_recommendation.csv --output-dir outputs/tables/enriched --report docs/recent_trend_summary_enriched.md --start-year 2023 --end-year 2025
```

The recent trend summary is descriptive and validation-gated. Do not treat it as final evidence until manual validation passes.

## Main Outputs

- `data/final/articles_pilot.csv`
- `data/final/articles_classified_pilot.csv`
- `data/final/articles_enriched_pilot.csv`
- `data/final/articles_classified_enriched_pilot.csv`
- `data/intermediate/text_enrichment_candidates.csv`
- `data/intermediate/text_enrichment_pdf_candidates.csv`
- `data/intermediate/text_enrichment_pdf_text.csv`
- `data/intermediate/abstract_backfill_template.csv`
- `data/intermediate/abstract_backfill_imported.csv`
- `data/intermediate/abstract_backfill_import_errors.csv`
- `data/intermediate/abstract_backfill_import_history.csv`
- `data/intermediate/abstract_backfill_import_error_history.csv`
- `data/intermediate/manual_validation_review_packet.csv`
- `data/intermediate/manual_validation_batches/`
- `data/intermediate/manual_validation_forms/`
- `data/intermediate/manual_validation_calibration/`
- `data/intermediate/manual_validation_calibration_forms/`
- `data/intermediate/manual_validation_calibration_submissions/`
- `data/intermediate/manual_validation_calibration/manual_validation_calibration_remaining_submission_template.csv`
- `data/intermediate/manual_validation_overlap/`
- `data/intermediate/manual_validation_overlap_forms/`
- `data/intermediate/insufficient_text_recovery_batches/`
- `data/intermediate/insufficient_text_recovery_forms/`
- `data/intermediate/insufficient_text_recovery_splits/R001/`
- `data/intermediate/insufficient_text_recovery_split_forms/R001/`
- `data/intermediate/insufficient_text_recovery_review_forms/R001/recovery_batch_R001_guided_queue.html`
- `data/intermediate/insufficient_text_recovery_review_forms/R001/tiered/`
- `data/intermediate/insufficient_text_recovery_review_exports/R001/`
- `data/intermediate/insufficient_text_recovery_staged/R001/`
- `data/intermediate/scope_review/scope_review_packet.csv`
- `data/intermediate/scope_review_forms/scope_review_packet.html`
- `data/intermediate/insufficient_text_recovery_batch_R001_ocr_recovered.csv`
- `data/intermediate/insufficient_text_recovery_cached_oa_pdf_ocr_recovered.csv`
- `outputs/tables/enriched/manual_validation_completion.csv`
- `outputs/tables/enriched/manual_validation_batch_completion.csv`
- `outputs/tables/enriched/manual_validation_import_errors.csv`
- `outputs/tables/enriched/manual_validation_readiness.csv`
- `outputs/tables/enriched/manual_validation_sample_drift.csv`
- `outputs/tables/enriched/manual_validation_dry_run_completion.csv`
- `outputs/tables/enriched/manual_validation_dry_run_batch_completion.csv`
- `outputs/tables/enriched/manual_validation_dry_run_errors.csv`
- `outputs/tables/enriched/manual_validation_overlap_summary.csv`
- `outputs/tables/enriched/manual_validation_overlap_disagreements.csv`
- `outputs/tables/enriched/manual_validation_overlap_errors.csv`
- `outputs/tables/enriched/manual_validation_calibration_summary.csv`
- `outputs/tables/enriched/manual_validation_calibration_submission_files.csv`
- `outputs/tables/enriched/manual_validation_calibration_disagreements.csv`
- `outputs/tables/enriched/manual_validation_calibration_errors.csv`
- `outputs/tables/enriched/manual_validation_calibration_kickoff.csv`
- `outputs/tables/enriched/manual_validation_calibration_guide.csv`
- `outputs/tables/enriched/manual_validation_calibration_guide_summary.csv`
- `outputs/tables/enriched/human_review_workboard.csv`
- `outputs/tables/enriched/validation_category_metrics.csv`
- `outputs/tables/enriched/validation_disagreements.csv`
- `outputs/tables/enriched/validation_adjudication_packet.csv`
- `outputs/tables/enriched/manual_validation_adjudication_completion.csv`
- `outputs/tables/enriched/manual_validation_adjudication_errors.csv`
- `outputs/tables/enriched/manual_validation_adjudication_dry_run_completion.csv`
- `outputs/tables/enriched/manual_validation_adjudication_dry_run_errors.csv`
- `outputs/tables/enriched/manual_validation_gate.csv`
- `outputs/tables/enriched/manual_validation_gate_checks.csv`
- `outputs/tables/enriched/project_status_summary.csv`
- `outputs/tables/enriched/project_next_actions.csv`
- `outputs/tables/enriched/remaining_insufficient_text_profile.csv`
- `outputs/tables/enriched/remaining_oa_pdf_download_blockers.csv`
- `outputs/tables/enriched/remaining_oa_pdf_download_blockers_by_status.csv`
- `outputs/tables/enriched/title_only_triage_candidates.csv`
- `outputs/tables/enriched/evidence_tier_policy.csv`
- `outputs/tables/enriched/insufficient_text_recovery_queue.csv`
- `outputs/tables/enriched/insufficient_text_recovery_batch_summary.csv`
- `outputs/tables/enriched/insufficient_text_recovery_decisions.csv`
- `outputs/tables/enriched/insufficient_text_source_route_matrix.csv`
- `outputs/tables/enriched/insufficient_text_source_investigation_packet.csv`
- `outputs/tables/enriched/insufficient_text_expansion_overview.csv`
- `outputs/tables/enriched/insufficient_text_expansion_plan.csv`
- `outputs/tables/enriched/insufficient_text_expansion_doi_prefixes.csv`
- `outputs/tables/enriched/insufficient_text_expansion_attempt_summary.csv`
- `outputs/tables/enriched/source_route_probe_results.csv`
- `outputs/tables/enriched/scope_review_candidates.csv`
- `outputs/tables/enriched/scope_review_summary.csv`
- `outputs/tables/enriched/scope_review_completion.csv`
- `outputs/tables/enriched/scope_review_apply_summary.csv`
- `outputs/tables/enriched/scope_review_apply_errors.csv`
- `outputs/tables/enriched/scope_review_apply_changes.csv`
- `outputs/tables/enriched/recovery_batch_R001_workplan.csv`
- `outputs/tables/enriched/recovery_batch_R001_split_summary.csv`
- `outputs/tables/enriched/recovery_batch_R001_review_queue.csv`
- `outputs/tables/enriched/recovery_batch_R001_review_queue_summary.csv`
- `outputs/tables/enriched/recovery_batch_R001_source_guide.csv`
- `outputs/tables/enriched/recovery_batch_R001_source_guide_summary.csv`
- `outputs/tables/enriched/recovery_batch_R001_cached_evidence.csv`
- `outputs/tables/enriched/recovery_batch_R001_cached_evidence_summary.csv`
- `outputs/tables/enriched/recovery_batch_R001_action_packet.csv`
- `outputs/tables/enriched/recovery_batch_R001_action_summary.csv`
- `outputs/tables/enriched/recovery_batch_R001_action_packet_index.csv`
- `outputs/tables/enriched/recovery_batch_R001_action_packets/`
- `outputs/tables/enriched/recovery_batch_R001_tiered_packet_index.csv`
- `outputs/tables/enriched/recovery_batch_R001_tiered_packets/`
- `outputs/tables/enriched/recovery_batch_R001_staged_split_summary.csv`
- `outputs/tables/enriched/recovery_batch_R001_tiered_stage_changes.csv`
- `outputs/tables/enriched/recovery_batch_R001_tiered_stage_errors.csv`
- `outputs/tables/enriched/recovery_batch_R001_preflight_summary.csv`
- `outputs/tables/enriched/recovery_batch_R001_preflight_errors.csv`
- `outputs/tables/enriched/recovery_batch_R001_action_progress_overview.csv`
- `outputs/tables/enriched/recovery_batch_R001_action_progress_summary.csv`
- `outputs/tables/enriched/recovery_batch_R001_action_progress_detail.csv`
- `outputs/tables/enriched/recovery_cell_targets.csv`
- `outputs/tables/enriched/recovery_cell_target_queue.csv`
- `data/intermediate/insufficient_text_recovery_review_forms/R001/recovery_batch_R001_action_dashboard.html`
- `outputs/tables/enriched/recovery_batch_autofill_summary_R001.csv`
- `outputs/tables/enriched/recovery_progress_overview.csv`
- `outputs/tables/enriched/recovery_progress_by_batch.csv`
- `outputs/tables/enriched/category_sensitivity_by_year.csv`
- `outputs/tables/enriched/category_sensitivity_by_journal.csv`
- `outputs/tables/enriched/recent_category_trends.csv`
- `outputs/tables/enriched/recent_category_trend_changes.csv`
- `outputs/tables/enriched/recent_journal_category_trends.csv`
- `outputs/tables/enriched/recent_journal_category_trend_changes.csv`
- `docs/text_enrichment_report.md`
- `docs/pdf_text_extraction_report.md`
- `docs/pdf_text_extraction_r001_ocr_recovered.md`
- `docs/pdf_text_extraction_cached_oa_pdf_ocr_recovered.md`
- `docs/remaining_oa_pdf_download_blockers.md`
- `docs/insufficient_text_expansion_plan.md`
- `docs/source_route_probe.md`
- `docs/scope_review_audit.md`
- `docs/scope_review_packet.md`
- `docs/scope_review_apply.md`
- `docs/recovery_batch_R001_workplan.md`
- `docs/recovery_batch_R001_split.md`
- `docs/recovery_batch_R001_review_queue.md`
- `docs/recovery_batch_R001_source_guide.md`
- `docs/recovery_batch_R001_cached_evidence.md`
- `docs/recovery_batch_R001_action_packet.md`
- `docs/recovery_batch_R001_tiered_packets.md`
- `docs/recovery_batch_R001_tiered_stage.md`
- `docs/recovery_batch_R001_preflight.md`
- `docs/recovery_batch_R001_action_progress.md`
- `docs/manual_validation_status.md`
- `docs/manual_validation_dry_run_status.md`
- `docs/manual_validation_adjudication_status.md`
- `docs/manual_validation_adjudication_dry_run_status.md`
- `docs/manual_validation_readiness.md`
- `docs/manual_validation_portal.html`
- `docs/manual_validation_calibration.md`
- `docs/manual_validation_calibration_kickoff.md`
- `docs/manual_validation_calibration_guide.md`
- `docs/manual_validation_calibration_remaining.md`
- `data/intermediate/manual_validation_calibration_forms/manual_validation_calibration_dashboard.html`
- `docs/human_review_workboard.md`
- `docs/manual_validation_overlap.md`
- `docs/manual_validation_gate.md`
- `docs/project_status.md`
- `docs/classification_diagnostics_enriched.md`
- `docs/recovery_batch_autofill_R001_report.md`
- `docs/recovery_progress_status.md`
- `docs/recent_trend_summary_enriched.md`
- `outputs/tables/enriched/`
- `data/intermediate/manual_validation_sample.csv`
- `docs/classification_diagnostics.md`
- `data/intermediate/source_records.csv`
- `outputs/tables/source_coverage_by_journal_year.csv`
- `outputs/tables/source_overlap_by_article.csv`
- `outputs/tables/missingness_by_variable.csv`
- `outputs/tables/article_counts_by_journal_year.csv`
- `docs/coverage_report.md`
- `docs/data_documentation.md`

The rule-based classification file is a transparent baseline for audit and validation. It should not be treated as the final causal/predictive/other classification until LLM classification and manual validation are complete.
