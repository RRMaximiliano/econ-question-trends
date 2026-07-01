# Economics Question Trends Project Plan

## 1. Project Objective

Build a reproducible article-level dataset of papers in major economics journals from 1975 through 2025, then use that dataset to describe how the focus of published economics research has shifted across three broad categories:

- `causal`: papers primarily focused on estimating, identifying, or interpreting causal effects.
- `predictive`: papers primarily focused on prediction, forecasting, classification, predictive performance, or out-of-sample accuracy.
- `other`: papers that do not clearly fit either category.

The project should be designed so that Phase 1 can stand alone. Classification and substantive claims should wait until data coverage, missingness, and source limitations are understood.

## 2. Core Design Principles

- Prioritize a smaller, well-documented dataset over a larger dataset with unclear provenance.
- Preserve raw source files and source-specific IDs so the dataset can be audited.
- Keep source metadata, cleaned article metadata, classification outputs, and analysis outputs separate.
- Record provenance at the variable level wherever feasible.
- Do not infer article type, field, affiliation, or classification unless the rule is transparent and documented.
- Use article-level unique IDs and duplicate checks before every merge.
- Treat missing abstracts as a first-order coverage issue, not a nuisance.
- Make every table, figure, and documentation artifact reproducible from code.

## 3. Initial Scope

### Journals

The Phase 1 pilot covers the top five general-interest economics journals:

- American Economic Review
- Quarterly Journal of Economics
- Journal of Political Economy
- Econometrica
- Review of Economic Studies

### Period

Target years: 1975-2025.

Do not exclude a source because its coverage starts after 1975. Instead, document the years and variables covered by each source.

### Unit of Observation

One row per published article-like item, using the most inclusive source definition feasible. The dataset should keep article type/category so analyses can later be restricted to full research articles.

## 4. Recommended Repository Structure

```text
econ-question-trends/
  README.md
  PROJECT_PLAN.md
  config/
    journals.yml
    sources.yml
    variable_schema.yml
  code/
    00_setup/
    01_collect/
    02_clean/
    03_diagnostics/
    04_classify/
    05_analysis/
  data/
    raw/
      crossref/
      openalex/
      jstor/
      repec/
      publisher/
      econlit/
    intermediate/
    final/
  docs/
    data_documentation.md
    coverage_report.md
    source_notes.md
    classification_protocol.md
  outputs/
    tables/
    figures/
    logs/
```

The first implementation step should create this skeleton plus a top-level run script or Makefile so a new user can reproduce outputs after editing one configuration file.

## 5. Phase 1: Data Collection and Coverage Diagnostics

### Phase 1A. Source Inventory and Journal Registry

Create `config/journals.yml` with one record per journal. For each journal, record:

- Canonical journal name.
- Short name, such as `aer`, `qje`, `jpe`, `ecta`, `restud`.
- Print ISSN and electronic ISSN.
- Publisher over time, if relevant.
- Crossref member or journal endpoint identifiers.
- OpenAlex source ID.
- JSTOR title ID or stable title URL, if available.
- RePEc series or archive handles, if useful.
- Publisher archive URL.
- Known title changes or supplement/proceedings complications.

Acceptance criteria:

- Every source query is driven from this registry.
- All journal IDs have a cited source or source URL.
- Unverified identifiers are marked `status: needs_verification`.

### Phase 1B. Source Priority

Use sources in layers rather than betting on a single source.

1. `Crossref`: first pass for DOI-based bibliographic metadata, publication dates, journal, volume, issue, pages, article URL, and sometimes abstracts.
2. `OpenAlex`: first pass for broad work discovery, DOI matching, authorships, institutions, abstract availability, concepts/topics, keywords, and bibliographic fields.
3. `JSTOR text analysis support`: strong candidate for historical coverage, bibliographic metadata, and potentially full text or abstracts where allowed.
4. `Publisher websites`: use for gaps in article type/category, issue tables of contents, abstract pages, and DOI/page validation.
5. `EconLit`: use if institutional export terms allow reproducible metadata extraction, especially for JEL codes, abstracts, keywords, and article type.
6. `RePEc`: use as a supplemental economics-specific source, especially for JEL codes and handles, but do not make it the primary bulk download path unless the standard metadata workflow is practical.

For each variable, store both the chosen value and the source used to populate it where feasible.

### Phase 1C. Feasibility Scan

Before collecting the full article-level dataset, run a lightweight scan across all five journals and all years from 1975 to 2025.

For each journal-year-source, collect:

- Number of records returned.
- Share with DOI.
- Share with title.
- Share with abstract.
- Share with volume/issue/pages.
- Share with authors.
- Share with affiliations.
- Share with JEL codes.
- Share with keywords.
- Share with article type/category.
- Earliest and latest publication date observed.
- Source query URL or source file name.
- API errors, rate limits, or manual-access requirements.

Deliverable: `docs/coverage_report.md` plus `outputs/tables/source_coverage_by_journal_year.csv`.

Stop/go question after Phase 1C:

- Is programmatic metadata coverage good enough to build a meaningful top-five pilot without relying on opaque manual scraping?

### Phase 1D. Article-Level Pilot Dataset

Build `data/final/articles_pilot.csv`, with one row per article-like item for the five journals over 1975-2025, subject to source availability.

Minimum variables:

- `article_id`: deterministic project ID.
- `title`
- `abstract`
- `journal`
- `journal_short`
- `publication_year`
- `publication_date`
- `doi`
- `volume`
- `issue`
- `first_page`
- `last_page`
- `pages_raw`
- `article_type`
- `article_type_source`
- `article_url`
- `primary_source`

Preferred variables:

- `authors_raw`
- `author_names`
- `author_affiliations_raw`
- `num_authors`
- `jel_codes`
- `keywords`
- `field_jel_primary`
- `field_jel_broad`
- `openalex_id`
- `crossref_id`
- `jstor_id`
- `repec_handle`
- `publisher_record_id`

Coverage and provenance variables:

- `title_source`
- `abstract_source`
- `doi_source`
- `bibliographic_source`
- `authors_source`
- `affiliations_source`
- `jel_source`
- `keywords_source`
- `field_source`
- `source_record_count`
- `duplicate_resolution_rule`
- `metadata_warning`

### Phase 1E. Raw Data and Audit Trail

For every source pull:

- Save raw response files under `data/raw/<source>/`.
- Use JSONL or original downloaded format where possible.
- Include request date, query parameters, source URL, and source version if available.
- Do not overwrite raw files silently.
- Save collection logs to `outputs/logs/`.

For every cleaned dataset:

- Check uniqueness of `article_id`.
- Check DOI uniqueness where DOI is nonmissing.
- Check likely duplicates by normalized title, journal, year, volume, and first page.
- Count records by journal-year before and after deduplication.
- Export a duplicate review file if uncertain matches remain.

### Phase 1F. Deduplication Strategy

Preferred matching hierarchy:

1. Exact DOI match.
2. Exact normalized title plus journal plus publication year.
3. Normalized title plus journal plus volume plus first page.
4. Fuzzy title match only for candidate review, not automatic final matching.

When sources disagree:

- Keep all source-specific raw values in intermediate files.
- Use a documented source priority rule for final values.
- Flag conflicts in `metadata_warning`.
- Do not silently drop source records unless the duplicate rule is explicit.

### Phase 1G. Data Documentation

Create `docs/data_documentation.md` with:

- Data sources used.
- Source access method and date accessed.
- Coverage by journal and year.
- Variables collected.
- Missingness by variable.
- Known limitations.
- Variables with source-specific caveats.
- Journals, years, fields, article types, or metadata fields that were difficult to obtain.
- Recommendation on whether to proceed to Phase 2.
- Recommendation on whether to expand beyond the top-five pilot.

Minimum coverage exhibits:

- Count of records by journal-year.
- Share with nonmissing abstract by journal-year.
- Share with DOI by journal-year.
- Share with article type by journal-year.
- Share with JEL codes by journal-year.
- Share with affiliations by journal-year.
- Overlap matrix across sources.
- List of journal-years with suspiciously low counts.

## 6. Phase 1 Deliverables

Phase 1 is complete when the project has:

- `data/final/articles_pilot.csv`
- `docs/data_documentation.md`
- `docs/coverage_report.md`
- `outputs/tables/source_coverage_by_journal_year.csv`
- `outputs/tables/missingness_by_variable.csv`
- `outputs/tables/article_counts_by_journal_year.csv`
- Reproducible scripts for every artifact above.
- A written recommendation on whether to proceed to classification.

Do not begin Phase 2 until these deliverables exist.

## 7. Phase 1 Decision Gates

Proceed to Phase 2 only if:

- Article counts by journal-year look plausible after comparison across sources.
- Abstract coverage is high enough for classification or missingness can be handled transparently.
- Article type coverage or a documented article-type inference rule is sufficient for key robustness checks.
- DOI/title/year coverage is sufficient for deduplication.
- Raw data provenance is preserved.
- The team accepts the limitations around JEL codes, affiliations, and historical abstracts.

Pause or narrow scope if:

- Pre-1990 abstract coverage is too thin for meaningful text classification.
- Publisher or JSTOR access terms make reproducible extraction infeasible.
- Article type is unavailable and cannot be documented well enough for research-article restrictions.
- Source overlap reveals large unresolved count discrepancies.

## 8. Phase 2: Classification Protocol

Phase 2 should produce a second dataset, not overwrite the Phase 1 article file.

Primary output:

```text
data/final/articles_classified.csv
```

Classification variables:

- `article_id`
- `causal_predictive_category`: `causal`, `predictive`, `other`, or `insufficient_text`.
- `classification_confidence`: `high`, `medium`, `low`.
- `classification_reason`: brief explanation based on title and abstract.
- `causal_language_indicator`: rule-based indicator or score.
- `predictive_language_indicator`: rule-based indicator or score.
- `classification_method`: `rule_based`, `llm_based`, `manual_reviewed`, or `hybrid`.
- `manual_review_status`
- `manual_review_label`
- `manual_review_notes`

### Rule-Based Baseline

Create transparent keyword and phrase indicators before using an LLM.

Potential causal language examples:

- causal effect
- treatment effect
- impact of
- effect of
- randomized
- experiment
- natural experiment
- instrumental variable
- difference-in-differences
- regression discontinuity
- identification strategy
- exogenous variation
- counterfactual

Potential predictive language examples:

- predict
- prediction
- forecast
- forecasting
- nowcast
- out-of-sample
- predictive accuracy
- classification
- machine learning
- model performance
- cross-validation

Important caveat: keyword indicators are descriptive text features, not final labels. For example, "effect of" can appear in noncausal theoretical or descriptive work, and "model" is too broad to indicate prediction.

### LLM-Based Classification

Use title and abstract only for the main classifier. Include journal, year, article type, and field only in robustness variants if needed.

The LLM prompt should ask for:

- The paper's primary question.
- Whether the paper is mainly causal, predictive, or other.
- Confidence.
- A short explanation tied to the title/abstract.
- A JSON-only response for reproducibility.

The classifier should return `insufficient_text` when the abstract is missing or too short to classify reliably.

### Manual Validation

Before full-scale classification, draw a stratified validation sample across:

- Journal.
- Decade.
- Article type.
- Field, where JEL codes exist.
- Rule-based causal/predictive score bins.
- Abstract availability and length.

Suggested first validation sample: 300-500 articles, with oversampling of ambiguous and high-score cases.

Validation outputs:

- Confusion matrix comparing LLM labels to manual labels.
- Accuracy by decade, journal, field, and article type.
- Share of low-confidence classifications.
- Examples of systematic false positives and false negatives.
- Revised prompt and rule dictionary if needed.

## 9. Phase 2 Descriptive Analysis

Main outcomes:

- Annual and five-year-bin shares of articles by category.
- Category shares by journal.
- Category shares by JEL field.
- Category shares by article type.
- Category shares by number of authors.
- Category shares by author affiliation, only if affiliation coverage is reliable.

Core robustness checks:

- Restrict to full research articles.
- Restrict to articles with abstracts.
- Restrict to high-confidence classifications.
- Exclude comments, replies, notes, proceedings, presidential addresses, and reviews.
- Compare rule-based indicators with hybrid/LLM labels.
- Show denominator changes when abstracts, JEL codes, or article types are missing.

Recommended figures:

- Stacked area or line plot of category shares over time.
- Journal-specific small multiples.
- Field-specific small multiples.
- Heatmap of category shares by journal and decade.
- Missingness dashboard by journal-year.
- Validation performance table.

## 10. Expansion Beyond Top Five Journals

Expand only after the Phase 1 pilot is documented and the team accepts the source limitations.

Recommended staged expansion:

1. Add one leading field journal per broad field.
2. Re-run source coverage diagnostics before full extraction.
3. Compare metadata coverage against the top-five pilot.
4. Add field-specific source notes where journal archives differ.

Candidate fields and example journals to consider:

- Development: Journal of Development Economics
- Labor: Journal of Labor Economics or Labour Economics
- Public finance: Journal of Public Economics
- Industrial organization: RAND Journal of Economics
- Macroeconomics: Journal of Monetary Economics
- Finance: Journal of Finance or Review of Financial Studies
- Health: Journal of Health Economics
- Environmental economics: Journal of Environmental Economics and Management
- Econometrics: Journal of Econometrics

The final field-journal list should be chosen for disciplinary credibility, coverage feasibility, and balance across fields.

## 11. Key Risks and Mitigations

### Abstract Coverage

Risk: Historical abstracts may be missing or inconsistently available.

Mitigation: Treat abstract availability as a central diagnostic. Report classification denominators clearly. Consider JSTOR text analysis support or publisher archives for gap filling where terms permit.

### Article Type

Risk: Comments, replies, notes, reviews, presidential addresses, and proceedings may be mixed with research articles.

Mitigation: Preserve article type when available. If inferred, use a documented rule and keep the original source category. Always report robustness excluding non-research categories.

### JEL Codes

Risk: JEL coverage may be incomplete, especially in older records or non-EconLit sources.

Mitigation: Prioritize source-provided JEL codes. Do not infer fields in the main Phase 1 dataset. Use `field_source` and missingness flags.

### Affiliations

Risk: Historical author affiliations at publication may be sparse or unreliable.

Mitigation: Keep raw affiliation strings where available. Do not substitute current affiliations unless clearly labeled as current rather than publication-time metadata.

### Source Terms and Reproducibility

Risk: Subscription databases may allow research use but not redistributable raw data.

Mitigation: Separate reproducible public-source pulls from restricted-source enrichment. Document access requirements and redistribution limits.

### Classification Validity

Risk: LLM labels may overstate precision or confuse causal methods with causal questions.

Mitigation: Use manual validation, confidence levels, short explanations, and robustness checks. Keep rule-based text indicators visible alongside final labels.

## 12. Suggested Milestones

### Milestone 0. Setup

- Create folder structure.
- Create journal registry.
- Create source registry.
- Create variable schema.
- Create top-level run instructions.

### Milestone 1. Feasibility Scan

- Query Crossref and OpenAlex for all journal-years.
- Inventory JSTOR, RePEc, publisher, and EconLit feasibility.
- Produce source coverage tables.

### Milestone 2. Pilot Dataset

- Build source-specific standardized files.
- Merge and deduplicate records.
- Produce `articles_pilot.csv`.
- Produce missingness and count diagnostics.

### Milestone 3. Phase 1 Documentation

- Write data documentation.
- Write coverage report.
- Write recommendation on Phase 2 and expansion.

### Milestone 4. Classification Prototype

- Draft classification protocol.
- Build rule-based indicators.
- Run LLM classification on a small stratified sample.
- Conduct manual validation.

### Milestone 5. Full Classification and Descriptive Analysis

- Run approved classifier on all eligible articles.
- Produce `articles_classified.csv`.
- Produce trend figures and robustness checks.
- Update documentation.

## 13. Immediate Next Steps

1. Create the repository structure and config files.
2. Verify identifiers for the five journals.
3. Write the Phase 1 variable schema.
4. Implement Crossref and OpenAlex collection scripts.
5. Run the feasibility scan across 1975-2025.
6. Review coverage results before adding JSTOR, publisher, EconLit, or RePEc enrichment.

