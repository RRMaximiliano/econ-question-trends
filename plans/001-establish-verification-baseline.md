# Plan 001: Establish a Python verification baseline

> **Executor instructions**: Follow this plan step by step. Run every verification command and confirm the expected result before moving to the next step. If anything in the "STOP conditions" section occurs, stop and report; do not improvise. When done, update the status row for this plan in `plans/README.md`.
>
> **Drift check (run first)**: `test ! -d .git && echo no-git-repo || git status --short`
> Expected result in the current workspace: `no-git-repo`. If this has become a git repo, record `git rev-parse --short HEAD` in your final notes and inspect changes to the in-scope files before proceeding.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW
- **Depends on**: none
- **Category**: tests
- **Planned at**: no git repository detected, 2026-06-28

## Why this matters

The project is about to add classification logic that will determine the main research outcome. Right now the repo has a runnable metadata pipeline but no persistent tests, no test fixtures, and no one-command verification baseline. A small standard-library `unittest` suite should land first so later executors can safely change classification and reporting code.

## Current state

Relevant files:

- `run_phase1_pilot.py` - top-level runner for collection, cleaning, and diagnostics.
- `code/lib/econqt_common.py` - shared helpers for text cleaning, DOI normalization, source keys, and OpenAlex abstract reconstruction.
- `code/02_clean/build_articles_pilot.py` - source-standardization and article-level deduplication.
- `README.md` - documents how to run Phase 1 but not how to test.
- `requirements.txt` - runtime dependencies only.

Current runner excerpt:

```python
# run_phase1_pilot.py:41-45
if not args.skip_collect:
    run_step(project_root, "code/01_collect/collect_crossref.py", args.start_year, args.end_year, run_id)
    run_step(project_root, "code/01_collect/collect_openalex.py", args.start_year, args.end_year, run_id)
run_step(project_root, "code/02_clean/build_articles_pilot.py", args.start_year, args.end_year, run_id)
run_step(project_root, "code/03_diagnostics/make_phase1_reports.py", args.start_year, args.end_year, run_id)
```

Current helper excerpts to cover:

```python
# code/lib/econqt_common.py:119-143
def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        value = first_nonempty(value) or ""
    text = str(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def normalize_doi(value: Any) -> str:
    if value is None:
        return ""
    doi = str(value).strip().lower()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)
    doi = re.sub(r"^doi:\s*", "", doi)
    return doi.strip()
```

```python
# code/lib/econqt_common.py:195-205
def reconstruct_openalex_abstract(inverted_index: Optional[Dict[str, List[int]]]) -> str:
    if not inverted_index:
        return ""
    max_position = max((pos for positions in inverted_index.values() for pos in positions), default=-1)
    if max_position < 0:
        return ""
    words: List[str] = [""] * (max_position + 1)
    for word, positions in inverted_index.items():
        for pos in positions:
            words[pos] = word
    return clean_text(" ".join(words))
```

Repo conventions:

- Scripts use plain Python modules with `argparse`.
- Existing code imports shared helpers by appending `code/lib` to `sys.path`.
- Existing outputs are CSVs and markdown files under `data/`, `outputs/`, and `docs/`.
- Prefer standard-library tests to adding a new dependency unless there is a clear reason.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Syntax check without bytecode writes | `python3 - <<'PY'\nfrom pathlib import Path\nfor path in ['run_phase1_pilot.py','code/lib/econqt_common.py','code/01_collect/collect_crossref.py','code/01_collect/collect_openalex.py','code/02_clean/build_articles_pilot.py','code/03_diagnostics/make_phase1_reports.py']:\n    compile(Path(path).read_text(), path, 'exec')\nprint('in-memory compile ok')\nPY` | Prints `in-memory compile ok` |
| Existing pipeline rebuild from raw files | `python3 run_phase1_pilot.py --start-year 2023 --end-year 2025 --run-id 20260628T202006Z --skip-collect` | Exits 0 and prints `source_records=2998` and `articles=1610` |
| New unit tests | `python3 -m unittest discover -s tests` | Exits 0 and all tests pass |

## Scope

**In scope**:

- Create `tests/`.
- Create `tests/test_common.py`.
- Create `tests/test_build_articles.py`.
- Update `README.md` to document the test command.
- If needed, add tiny fixture data under `tests/fixtures/`.

**Out of scope**:

- Do not change collector behavior.
- Do not add classification logic.
- Do not change existing generated CSVs except by running documented verification commands.
- Do not add external testing dependencies unless standard-library `unittest` cannot cover the planned cases.

## Git workflow

This workspace is not a git repository. If the operator has initialized git before execution, use a branch named `advisor/001-verification-baseline` and commit only this plan's in-scope files.

## Steps

### Step 1: Create a standard-library test skeleton

Create `tests/__init__.py` and a small helper in each test file that appends `code/lib` and `code/02_clean` to `sys.path` before imports. Use `unittest.TestCase`.

Test cases in `tests/test_common.py`:

- `clean_text` removes XML/HTML tags, unescapes entities, and collapses whitespace.
- `normalize_doi` strips `https://doi.org/`, `http://dx.doi.org/`, and `doi:` prefixes.
- `normalize_title` lowercases and removes punctuation consistently.
- `source_key` returns DOI keys when DOI is present and title/journal/year keys otherwise.
- `reconstruct_openalex_abstract` reconstructs words in position order.
- `as_json_string([])` and `as_json_string({})` return an empty string, matching the current missingness convention.

**Verify**: `python3 -m unittest discover -s tests` -> exits 0.

### Step 2: Add article-builder characterization tests

Create `tests/test_build_articles.py`.

Build a minimal in-memory `source_records` list with:

- One Crossref record and one OpenAlex record with the same DOI but different abstract availability. Assert `build_articles` returns one row and chooses the OpenAlex abstract because `SOURCE_PRIORITY['abstract']` prefers OpenAlex.
- One record without DOI. Assert `duplicate_resolution_rule == 'title_journal_year'`.
- One record with `article_type == 'report'`. Assert `metadata_warning` contains `nonstandard_article_type`.
- One record with no `jel_codes`. Assert `metadata_warning` contains `missing_jel_codes`.

Use a temporary project root with a minimal `config/journals.yml`, because `build_articles` calls `load_journals(project_root)` at `code/02_clean/build_articles_pilot.py:323`.

**Verify**: `python3 -m unittest discover -s tests` -> exits 0.

### Step 3: Document the verification baseline

Update `README.md` with a short "Verify The Code" section:

Use this content shape:

````markdown
## Verify The Code

```bash
python3 -m unittest discover -s tests
```

For a no-network rebuild from the saved 2023-2025 raw responses:

```bash
python3 run_phase1_pilot.py --start-year 2023 --end-year 2025 --run-id 20260628T202006Z --skip-collect
```
````

Be careful with nested code fences in markdown; render/read the README after editing.

**Verify**: `sed -n '1,180p' README.md` -> shows the new section and existing Phase 1 instructions.

## Test plan

- `tests/test_common.py` covers shared helper behavior.
- `tests/test_build_articles.py` covers source priority, deduplication grouping, and metadata warning behavior.
- Verification: `python3 -m unittest discover -s tests` -> all tests pass.
- Verification: in-memory syntax check command above -> prints `in-memory compile ok`.

## Done criteria

- [ ] `python3 -m unittest discover -s tests` exits 0.
- [ ] In-memory syntax check exits 0.
- [ ] README documents the test command.
- [ ] No classification outputs or scripts are created in this plan.
- [ ] `plans/README.md` row for 001 is updated to DONE, or BLOCKED with a one-line reason.

## STOP conditions

Stop and report if:

- `build_articles` cannot be imported without executing the script body.
- The minimal temporary `config/journals.yml` cannot satisfy `load_journals`.
- Any test requires network access.
- You need to touch files outside the in-scope list.

## Maintenance notes

Later classification plans should extend this same `unittest` suite rather than creating a second test style. Reviewers should insist that every new classification output schema has at least one unit or integration test.
