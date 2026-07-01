# Plan 002: Add rule-based classification indicators

> **Executor instructions**: Follow this plan step by step. Run every verification command and confirm the expected result before moving to the next step. If anything in the "STOP conditions" section occurs, stop and report; do not improvise. When done, update the status row for this plan in `plans/README.md`.
>
> **Drift check (run first)**: `test ! -d .git && echo no-git-repo || git status --short`
> Expected result in the current workspace: `no-git-repo`. If this has become a git repo, inspect changes to the in-scope files before proceeding.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: `plans/001-establish-verification-baseline.md`
- **Category**: direction
- **Planned at**: no git repository detected, 2026-06-28

## Why this matters

The project needs transparent baseline indicators before any LLM labeling. Rule-based causal and predictive scores will not be the final scientific classification, but they are essential for auditing labels, stratifying validation samples, and explaining trends to economists. This plan creates the first separate classification output without overwriting the metadata file.

## Current state

Relevant files:

- `data/final/articles_pilot.csv` - current article-level metadata, 1,610 rows.
- `PROJECT_PLAN.md` - defines the target classification fields.
- `run_phase1_pilot.py` - currently runs only collection, cleaning, and diagnostics.
- `README.md` - states classification is not part of the first batch.

Current project objective excerpt:

```markdown
# PROJECT_PLAN.md:5-9
Build a reproducible article-level dataset ... across three broad categories:

- `causal`: papers primarily focused on estimating, identifying, or interpreting causal effects.
- `predictive`: papers primarily focused on prediction, forecasting, classification, predictive performance, or out-of-sample accuracy.
- `other`: papers that do not clearly fit either category.
```

Current Phase 2 output target excerpt:

```markdown
# PROJECT_PLAN.md:232-239
- `article_id`
- `causal_predictive_category`: `causal`, `predictive`, `other`, or `insufficient_text`.
- `classification_confidence`: `high`, `medium`, `low`.
- `classification_reason`: brief explanation based on title and abstract.
- `causal_language_indicator`: rule-based indicator or score.
- `predictive_language_indicator`: rule-based indicator or score.
- `classification_method`: `rule_based`, `llm_based`, `manual_reviewed`, or `hybrid`.
```

Current metadata schema excerpt:

```python
# code/02_clean/build_articles_pilot.py:68-110
FINAL_COLUMNS = [
    "article_id",
    "title",
    "abstract",
    ...
    "metadata_warning",
]
```

Repo conventions:

- Keep raw metadata separate from classification outputs.
- Generated outputs go under `data/final/`, `outputs/tables/`, and `docs/`.
- Use config files under `config/` for reusable project rules.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Unit tests | `python3 -m unittest discover -s tests` | exits 0 |
| Rule classifier run | `python3 run_classification_pilot.py --input data/final/articles_pilot.csv --output data/final/articles_classified_pilot.csv` | exits 0 and writes output |
| Output schema check | `python3 - <<'PY'\nimport pandas as pd\np='data/final/articles_classified_pilot.csv'\ndf=pd.read_csv(p)\nrequired=['article_id','causal_predictive_category','classification_confidence','classification_reason','causal_language_indicator','predictive_language_indicator','classification_method']\nmissing=[c for c in required if c not in df.columns]\nassert not missing, missing\nassert len(df)==1610, len(df)\nassert set(df['classification_method'].dropna()) == {'rule_based'}\nprint('rule output schema ok')\nPY` | prints `rule output schema ok` |

## Scope

**In scope**:

- Create `config/classification_rules.yml`.
- Create `code/04_classify/rule_based.py`.
- Create `run_classification_pilot.py`.
- Create or update `docs/classification_protocol.md`.
- Create or update `tests/test_rule_based_classification.py`.
- Update `README.md` with the rule-based classification command.

**Out of scope**:

- Do not call any LLM API in this plan.
- Do not edit `data/final/articles_pilot.csv`.
- Do not infer JEL fields.
- Do not classify rows with missing/very short text as high-confidence labels.

## Git workflow

If git exists by execution time, use branch `advisor/002-rule-based-classification`. Do not push or open a PR unless instructed.

## Steps

### Step 1: Define the rule dictionary

Create `config/classification_rules.yml` with explicit lists and weights.

Minimum structure:

```yaml
text_fields:
  - title
  - abstract
minimum_usable_text_chars: 250
causal:
  strong_phrases:
    - causal effect
    - treatment effect
    - randomized controlled trial
    - difference-in-differences
    - regression discontinuity
    - instrumental variable
    - natural experiment
    - identification strategy
    - exogenous variation
  moderate_phrases:
    - effect of
    - impact of
    - randomized
    - experiment
    - counterfactual
predictive:
  strong_phrases:
    - out-of-sample
    - predictive accuracy
    - machine learning
    - forecast accuracy
    - cross-validation
  moderate_phrases:
    - predict
    - prediction
    - forecast
    - forecasting
    - classification
```

Include comments or a `notes` key explaining that broad terms like `effect of` and `model` are not sufficient alone for high-confidence labels.

**Verify**: `python3 - <<'PY'\nimport yaml\nwith open('config/classification_rules.yml') as f:\n    cfg=yaml.safe_load(f)\nfor key in ['causal','predictive','minimum_usable_text_chars']:\n    assert key in cfg, key\nprint('classification rules config ok')\nPY` -> prints `classification rules config ok`.

### Step 2: Implement deterministic rule scoring

Create `code/04_classify/rule_based.py` with pure functions:

- `load_rules(path: Path) -> dict`
- `build_classification_text(row: Mapping[str, str]) -> str`
- `score_text(text: str, rules: dict) -> dict`
- `classify_rule_based(row: Mapping[str, str], rules: dict) -> dict`
- `classify_dataframe(df: pandas.DataFrame, rules: dict) -> pandas.DataFrame`

Output columns to add:

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

Conservative category logic:

- If abstract is missing and title+abstract text length is below `minimum_usable_text_chars`, set `causal_predictive_category = insufficient_text`, `classification_confidence = low`.
- If causal score is clearly positive and predictive score is zero, set `causal`.
- If predictive score is clearly positive and causal score is zero, set `predictive`.
- If both causal and predictive scores are positive, use `classification_confidence = low` and a reason that says both rule families matched. If one score is much larger, category may follow the larger score but must remain low/medium confidence.
- If neither score is positive, set `other`.

Use word-boundary or phrase-aware regex matching so `prediction` does not accidentally match unrelated substrings.

**Verify**: `python3 -m unittest discover -s tests` -> exits 0.

### Step 3: Add the runner

Create `run_classification_pilot.py` with `argparse` arguments:

- `--input`, default `data/final/articles_pilot.csv`
- `--output`, default `data/final/articles_classified_pilot.csv`
- `--rules`, default `config/classification_rules.yml`

The runner should:

1. Read the metadata CSV.
2. Load rules.
3. Append rule-based classification columns.
4. Write the output CSV.
5. Print row count and category counts.

Do not modify `run_phase1_pilot.py` in this plan. Keeping classification as a separate command preserves the Phase 1/Phase 2 separation.

**Verify**: `python3 run_classification_pilot.py --input data/final/articles_pilot.csv --output data/final/articles_classified_pilot.csv` -> exits 0 and writes 1,610 rows.

### Step 4: Add tests for rule scoring

Create `tests/test_rule_based_classification.py`.

Test cases:

- A text containing `difference-in-differences` and `treatment effect` scores causal.
- A text containing `out-of-sample` and `forecast accuracy` scores predictive.
- A text containing neither scores `other`.
- A row with only a short title and missing abstract is `insufficient_text`.
- A text containing both causal and predictive phrases is low or medium confidence, not high confidence.
- Matching is case-insensitive.

**Verify**: `python3 -m unittest discover -s tests` -> exits 0.

### Step 5: Document the protocol

Create or update `docs/classification_protocol.md` with:

- Category definitions.
- Rule dictionary path.
- Rule-based output columns.
- Known limitations of keyword rules.
- Statement that rule-based labels are a baseline, not final scientific classifications.
- Next step: LLM classification and manual validation.

Update `README.md` with the command to run rule-based classification.

**Verify**: `sed -n '1,220p' docs/classification_protocol.md` -> includes category definitions and limitations.

## Test plan

- New unit tests in `tests/test_rule_based_classification.py`.
- Existing tests from plan 001 must continue passing.
- Output schema check command above must pass.

## Done criteria

- [ ] `python3 -m unittest discover -s tests` exits 0.
- [ ] `python3 run_classification_pilot.py --input data/final/articles_pilot.csv --output data/final/articles_classified_pilot.csv` exits 0.
- [ ] `data/final/articles_classified_pilot.csv` has exactly 1,610 rows.
- [ ] `classification_method` is `rule_based` for all rows.
- [ ] `data/final/articles_pilot.csv` is not modified.
- [ ] `docs/classification_protocol.md` exists.
- [ ] `plans/README.md` row for 002 is updated.

## STOP conditions

Stop and report if:

- `articles_pilot.csv` is missing `article_id`, `title`, or `abstract`.
- The rule configuration cannot be loaded with PyYAML.
- The rule-based classifier requires a manual judgment not encoded in config or tests.
- You need to call an LLM API to complete this plan.

## Maintenance notes

Reviewers should treat these labels as baseline indicators. The main review risk is overconfident causal classification from broad words like `effect` and overbroad predictive classification from generic words like `model`. Keep the dictionary conservative and documented.
