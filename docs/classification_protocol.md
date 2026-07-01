# Classification Protocol

This protocol defines the baseline classification layer for the economics question trends project. It keeps classification outputs separate from raw article metadata.

## Categories

- `causal`: papers primarily focused on estimating, identifying, or interpreting causal effects.
- `predictive`: papers primarily focused on prediction, forecasting, classification, predictive performance, or out-of-sample accuracy.
- `other`: papers that do not clearly fit causal or predictive.
- `insufficient_text`: title and abstract text are not enough to classify reliably.

## Rule-Based Baseline

The rule dictionary is stored in `config/classification_rules.yml`. The rule-based classifier uses only `title` and `abstract`, then appends:

- `causal_predictive_category`
- `classification_confidence`
- `classification_reason`
- `causal_language_indicator`
- `predictive_language_indicator`
- `causal_language_terms`
- `predictive_language_terms`
- `classification_method`
- `classification_text_chars`
- `has_usable_classification_text`

Run:

```bash
python3 run_classification_pilot.py --input data/final/articles_pilot.csv --output data/final/articles_classified_pilot.csv
```

## Limitations

Keyword rules are transparent but blunt. Broad phrases such as `effect of` can appear in noncausal papers, and predictive terminology can appear in papers where prediction is secondary. Rule-based labels should be treated as baseline indicators for audit and validation, not final scientific classifications.

Rows with very short title/abstract text are labeled `insufficient_text` rather than forced into causal, predictive, or other.

## Insufficient-Text Recovery Policy

Recovered text may move a row out of `insufficient_text` only when the recovery source is article-specific and records provenance. The active evidence-tier decision is:

- `tier_a_formal_abstract`: importable as classification text.
- `tier_b_source_description`: importable as classification text when the source description is article-specific and not citation-only boilerplate.
- `tier_c_first_page_abstract_or_intro`: importable as classification text only when the first-page source is public, verified, article-specific, and not a blocked or suspect PDF route.
- `tier_d_title_only_triage`: not importable; use only for triage or sensitivity artifacts.
- `tier_e_blocked`: not importable.

Keep `evidence_tier` in recovery/import artifacts so the main analysis can be compared with a stricter formal-abstract-only robustness cut.

When recovered text is merged into the enriched article file, the structured provenance columns are `text_enrichment_source`, `text_enrichment_url`, `text_enrichment_source_record_id`, and `text_enrichment_evidence_tier`. Use `text_enrichment_evidence_tier == "tier_a_formal_abstract"` for the strict formal-abstract robustness cut.

For legacy automated enrichment rows that predate explicit reviewer tiers, the pipeline infers only conservative tiers: metadata abstract sources such as Crossref, OpenAlex, Semantic Scholar, EconPapers, and publisher metadata are `tier_a_formal_abstract`; verified first-page PDF extracts are `tier_c_first_page_abstract_or_intro`; partial, candidate, blocked, or non-enriched rows remain blank. Manual recovery imports still require an explicit reviewer-provided `evidence_tier`.

## LLM Classification

The LLM classifier uses the OpenAI Responses API with a strict JSON schema response format. The implementation is in `code/04_classify/llm_classifier.py`, the runner is `run_llm_classification_pilot.py`, and the config is `config/llm_classification.yml`.

Prompt version:

- `classify_causal_predictive_v1`

Prompt file:

- `prompts/classify_causal_predictive_v1.md`

Inputs:

- `title`
- `abstract`

Excluded from the main LLM prompt:

- journal
- publication year
- DOI
- authors
- affiliations
- article type
- outside knowledge of the paper

JSON schema:

```json
{
  "category": "causal|predictive|other|insufficient_text",
  "confidence": "high|medium|low",
  "reason": "one short sentence grounded in the title/abstract"
}
```

Dry-run command:

```bash
python3 run_llm_classification_pilot.py --input data/final/articles_classified_pilot.csv --output data/final/articles_classified_llm_sample.csv --limit 10 --dry-run
```

Real-run command:

```bash
export OPENAI_API_KEY="..."
python3 run_llm_classification_pilot.py --input data/final/articles_classified_pilot.csv --output data/final/articles_classified_llm_pilot.csv --resume
```

The model defaults to the value in `config/llm_classification.yml`, and can be overridden with `OPENAI_MODEL`.

Cache behavior:

- One raw response JSON is saved per article under `data/intermediate/llm_cache/<prompt_version>/`.
- Existing cache files are not overwritten unless `--force` is passed.
- `--resume` reuses cached responses when available.
- Rows with text below the configured threshold are marked `skipped_insufficient_text` without an API call.

Do not run a full paid LLM classification until the rule-based output and tests pass, and until the project owner accepts the prompt and validation protocol.

## Next Step

The next step is a stratified manual validation sample. Until a real LLM run is approved and completed, that validation sample can use the rule-based file as the fallback input.
