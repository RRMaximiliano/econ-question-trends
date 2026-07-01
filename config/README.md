# Config Directory

Configuration files define the project scope and reproducibility policy:

- `journals.yml`: journal identifiers and metadata.
- `sources.yml`: source priority and collection metadata.
- `classification_rules.yml`: transparent rule-based classification cues.
- `classification_diagnostics.yml`: validation gate thresholds.
- `text_enrichment.yml`: source routes, text thresholds, and scope patterns.
- `llm_classification.yml`: LLM prompt/provider settings.
- `variable_schema.yml`: article-level variable documentation.

Changing these files can change the analysis sample, classification behavior, or validation gate. Record substantive changes in `plans/` or project notes before rerunning outputs.

