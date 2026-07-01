# Plan 003: Add auditable LLM classification

> **Executor instructions**: Follow this plan step by step. Run every verification command and confirm the expected result before moving to the next step. If anything in the "STOP conditions" section occurs, stop and report; do not improvise. When done, update the status row for this plan in `plans/README.md`.
>
> **Drift check (run first)**: `test ! -d .git && echo no-git-repo || git status --short`
> Expected result in the current workspace: `no-git-repo`. If this has become a git repo, inspect changes to the in-scope files before proceeding.

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: MED
- **Depends on**: `plans/001-establish-verification-baseline.md`, `plans/002-add-rule-based-classification-indicators.md`
- **Category**: direction
- **Planned at**: no git repository detected, 2026-06-28

## Why this matters

The final causal/predictive/other classification should use the semantics of titles and abstracts, not just keywords. But an LLM classifier is only credible if it is deterministic enough to audit: fixed prompt version, JSON schema validation, cached raw responses, retry/failure handling, and clear separation from raw metadata. This plan adds that path without forcing a full paid run.

## Current state

Relevant files after plan 002 should exist:

- `run_classification_pilot.py` - rule-based classification runner.
- `code/04_classify/rule_based.py` - deterministic rule scoring.
- `config/classification_rules.yml` - rule dictionary.
- `docs/classification_protocol.md` - baseline protocol.
- `data/final/articles_classified_pilot.csv` - rule-based output.

Existing pipeline separation:

```python
# run_phase1_pilot.py:41-45
if not args.skip_collect:
    run_step(project_root, "code/01_collect/collect_crossref.py", args.start_year, args.end_year, run_id)
    run_step(project_root, "code/01_collect/collect_openalex.py", args.start_year, args.end_year, run_id)
run_step(project_root, "code/02_clean/build_articles_pilot.py", args.start_year, args.end_year, run_id)
run_step(project_root, "code/03_diagnostics/make_phase1_reports.py", args.start_year, args.end_year, run_id)
```

Keep classification separate from this Phase 1 runner.

Current data limitation to preserve:

```markdown
# docs/data_documentation.md
- Abstract missingness must be accounted for before any classification exercise.
```

Repo conventions:

- Generated raw/source artifacts are preserved under `data/raw/<source>/<run_id>/`.
- Logs go under `outputs/logs/`.
- Classification output must be a second CSV, not an overwrite of `articles_pilot.csv`.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Unit tests | `python3 -m unittest discover -s tests` | exits 0 |
| Dry-run LLM classification | `python3 run_llm_classification_pilot.py --input data/final/articles_classified_pilot.csv --output data/final/articles_classified_llm_sample.csv --limit 10 --dry-run` | exits 0, writes a 10-row file with dry-run labels or pending status |
| Mocked schema check | `python3 - <<'PY'\nimport pandas as pd\np='data/final/articles_classified_llm_sample.csv'\ndf=pd.read_csv(p)\nrequired=['article_id','llm_category','llm_confidence','llm_reason','llm_prompt_version','llm_model','llm_status','classification_method']\nmissing=[c for c in required if c not in df.columns]\nassert not missing, missing\nassert len(df)==10, len(df)\nprint('llm sample schema ok')\nPY` | prints `llm sample schema ok` |

## Scope

**In scope**:

- Create `config/llm_classification.yml`.
- Create `prompts/classify_causal_predictive_v1.md`.
- Create `code/04_classify/llm_classifier.py`.
- Create `run_llm_classification_pilot.py`.
- Create `tests/test_llm_classifier.py` with mocked responses only.
- Update `docs/classification_protocol.md`.
- Update `README.md` with dry-run and real-run commands.
- Create output/cache directories only when the runner executes: `data/intermediate/llm_cache/` and `outputs/logs/`.

**Out of scope**:

- Do not run a paid/full LLM classification unless the operator explicitly instructs it.
- Do not store API keys in files.
- Do not include full abstracts in committed prompt logs beyond local raw cache files.
- Do not use journal, author, institution, or year as main classification inputs in this plan; main labels should use title and abstract only.

## Git workflow

If git exists by execution time, use branch `advisor/003-llm-classification`. Do not push or open a PR unless instructed.

## Steps

### Step 1: Add LLM config and prompt

Create `config/llm_classification.yml`:

```yaml
prompt_version: classify_causal_predictive_v1
model_env_var: OPENAI_MODEL
default_model: gpt-4.1-mini
api_key_env_var: OPENAI_API_KEY
temperature: 0
max_output_tokens: 500
input_fields:
  - title
  - abstract
minimum_usable_text_chars: 250
cache_dir: data/intermediate/llm_cache
```

Create `prompts/classify_causal_predictive_v1.md` with a stable prompt that asks for JSON only:

```text
You are classifying economics journal articles by their primary research question.

Categories:
- causal: primarily focused on estimating, identifying, or interpreting causal effects.
- predictive: primarily focused on prediction, forecasting, classification, predictive performance, or out-of-sample accuracy.
- other: does not clearly fit causal or predictive.
- insufficient_text: title and abstract are not enough to classify reliably.

Use only the title and abstract. Do not use journal prestige, authors, institutions, year, or your outside knowledge of the paper.

Return JSON with exactly:
{
  "category": "causal|predictive|other|insufficient_text",
  "confidence": "high|medium|low",
  "reason": "one short sentence grounded in the title/abstract"
}
```

**Verify**: `python3 - <<'PY'\nimport yaml\nfor p in ['config/llm_classification.yml']:\n    with open(p) as f: yaml.safe_load(f)\nprint('llm config ok')\nPY` -> prints `llm config ok`.

### Step 2: Implement JSON validation and prompt construction

Create `code/04_classify/llm_classifier.py`.

Required pure functions:

- `load_llm_config(path)`
- `load_prompt(path)`
- `build_prompt_input(row)` - uses title and abstract only.
- `stable_cache_key(article_id, prompt_version, model, title, abstract)`
- `validate_llm_json(payload)` - accepts only the four categories and three confidence levels.
- `merge_llm_result(row, result)` - returns appended columns without dropping rule columns.

Required output columns:

- `llm_category`
- `llm_confidence`
- `llm_reason`
- `llm_prompt_version`
- `llm_model`
- `llm_status`
- `llm_error`
- `llm_cache_key`
- `classification_method`

When `llm_status == ok`, set `classification_method = hybrid` if rule columns are present. When dry-run or failure, keep the existing rule-based category and set LLM fields accordingly.

**Verify**: `python3 -m unittest discover -s tests` -> exits 0.

### Step 3: Add mocked unit tests

Create `tests/test_llm_classifier.py`.

Test cases:

- Valid JSON with category `causal` passes validation.
- Invalid category fails validation.
- Missing `reason` fails validation.
- Prompt input excludes journal, authors, year, and DOI.
- Cache key changes when prompt version changes.
- `insufficient_text` is returned without API call when text is below the configured threshold.

Do not call a real API in tests.

**Verify**: `python3 -m unittest discover -s tests` -> exits 0.

### Step 4: Add the runner with dry-run support

Create `run_llm_classification_pilot.py`.

Arguments:

- `--input`, default `data/final/articles_classified_pilot.csv`
- `--output`, default `data/final/articles_classified_llm_pilot.csv`
- `--config`, default `config/llm_classification.yml`
- `--limit`, optional integer
- `--dry-run`, no API calls
- `--resume`, reuse cache when available

Behavior:

- In dry-run mode, build prompts and write rows with `llm_status = dry_run`.
- In real mode, require the configured API key environment variable. If missing, stop with a clear error.
- Save one raw response JSON per article under `data/intermediate/llm_cache/<prompt_version>/<cache_key>.json`.
- Never overwrite an existing cache file unless `--force` is explicitly added and documented.
- Continue past row-level API failures by writing `llm_status = error` and `llm_error`, then report failure counts.

Provider note:

- If using OpenAI, use the current official OpenAI Python SDK and current official API docs at implementation time. Do not hardcode a stale API shape from memory if the installed SDK differs.

**Verify**: `python3 run_llm_classification_pilot.py --input data/final/articles_classified_pilot.csv --output data/final/articles_classified_llm_sample.csv --limit 10 --dry-run` -> exits 0 and writes 10 rows.

### Step 5: Document real-run safety

Update `docs/classification_protocol.md` with:

- Prompt version.
- LLM inputs and excluded fields.
- JSON schema.
- Cache behavior.
- Dry-run command.
- Real-run command requiring `OPENAI_API_KEY` or configured equivalent.
- Statement that full pilot classification should not run until the rule-based output and tests pass.

Update `README.md` with dry-run command only. Put real-run command in the protocol doc to avoid accidental spending.

**Verify**: `sed -n '1,260p' docs/classification_protocol.md` -> includes the LLM section.

## Test plan

- Mocked tests in `tests/test_llm_classifier.py`.
- Existing tests from plans 001 and 002 remain passing.
- Dry-run creates a schema-compatible 10-row output.
- No test calls a real LLM API.

## Done criteria

- [ ] `python3 -m unittest discover -s tests` exits 0.
- [ ] Dry-run command exits 0.
- [ ] `data/final/articles_classified_llm_sample.csv` has 10 rows and required LLM columns.
- [ ] No API key is written to disk.
- [ ] Full real LLM classification is not run unless explicitly requested.
- [ ] `plans/README.md` row for 003 is updated.

## STOP conditions

Stop and report if:

- Plan 002 outputs are missing.
- The API provider package is not installed and adding it would require a dependency decision.
- The official SDK/API shape conflicts with this plan.
- The user has not provided explicit permission for any paid/full LLM run.
- You need to include fields beyond title and abstract to get plausible labels.

## Maintenance notes

Reviewers should inspect the prompt and JSON validation more closely than the API plumbing. The central research risk is label leakage from metadata or outside knowledge; the classifier must ground reasons in title and abstract text.
