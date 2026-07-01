# Plan 006: Enrich Insufficient Classification Text

Status: IN PROGRESS
Priority: P1
Effort: L
Depends on: 002, 005

## Goal

Reduce `insufficient_text` rows before substantive trend analysis by adding an auditable text-enrichment layer for article abstracts and source text.

## Scope

- Build a candidate table for rows currently classified as `insufficient_text`.
- Attempt cached enrichment through OpenAlex, Crossref, Semantic Scholar, EconPapers/RePEc pages, and Unpaywall OA metadata.
- Merge usable enriched abstracts into a separate enriched article file without overwriting the original article file.
- Capture OA PDF candidates for a second-stage legal PDF extraction workflow.
- Re-run rule-based classification and diagnostics on the enriched article file.

## Deliverables

- `config/text_enrichment.yml`
- `code/06_enrich/text_enrichment.py`
- `run_text_enrichment.py`
- `data/intermediate/text_enrichment_candidates.csv`
- `data/intermediate/text_enrichment_attempts.csv`
- `data/intermediate/text_enrichment_pdf_candidates.csv`
- `data/final/articles_enriched_pilot.csv`
- `data/final/articles_classified_enriched_pilot.csv`
- `docs/text_enrichment_report.md`
- `docs/pdf_text_extraction_report.md`
- Updated diagnostics comparing the enriched classification output against the current gate.

## Verification

Run:

```bash
python3 -m unittest discover -s tests
python3 -m py_compile run_text_enrichment.py code/06_enrich/text_enrichment.py
python3 run_text_enrichment.py --limit 50 --max-queries 150
python3 run_pdf_text_enrichment.py
python3 run_classification_pilot.py --input data/final/articles_enriched_pilot.csv --output data/final/articles_classified_enriched_pilot.csv
python3 run_classification_diagnostics.py --classified data/final/articles_classified_enriched_pilot.csv --validation data/intermediate/manual_validation_sample.csv --output-dir outputs/tables/enriched --report docs/classification_diagnostics_enriched.md
```

## Stop Conditions

- If source APIs rate-limit heavily, stop after producing cached attempts and the PDF queue, then resume later with the existing cache.
- Do not scrape restricted full text or bypass publisher/JSTOR access controls.

## Current Run Notes

- Cached enrichment has produced 116 usable enriched rows so far: 67 RePEc/IDEAS/EconPapers abstracts, 39 OA PDF first-page extracts, 9 Crossref abstracts, and 1 OpenAlex abstract.
- `insufficient_text` has moved from 6,650 to 6,534 in the enriched classification file.
- OpenAlex/Crossref have now been exhausted for the queued candidate set under the current cache: 0 candidates remain in `not_attempted_query_limit`.
- PDF extraction was attempted for 105 OA PDF candidates: 50 extracted, 42 download errors, and 13 too short.
- A deterministic IDEAS fallback for JPE `10.1086/...` DOI records produced the highest-yield metadata recovery. Broader RePEc sweeps should stay bounded because historical RePEc URLs include slow/dead pages.
- Diagnostics now evaluate the expansion gate on scoped research articles only: 20,525 analysis rows out of 23,903 input rows. In that analysis set, abstract coverage is 83.3%, minimum journal abstract coverage is 76.2%, and `insufficient_text` is 19.4%.
- The current enriched diagnostics recommendation is `pause_for_manual_validation`; metadata thresholds pass after scope filtering, but manual labels are still empty.
- Manual validation now has a blind compact reviewer packet at `data/intermediate/manual_validation_review_packet.csv`, six blind 50-row batch packets under `data/intermediate/manual_validation_batches/`, six local dropdown-based HTML forms under `data/intermediate/manual_validation_forms/`, and an importer command, `run_apply_validation_labels.py`, that validates reviewer labels before merging them back into `manual_validation_sample.csv`.
- Semantic Scholar rate limits unauthenticated runs; a larger sweep should use `SEMANTIC_SCHOLAR_API_KEY` or slow resumed batches.
