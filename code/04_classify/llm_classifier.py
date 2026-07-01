from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Mapping

import pandas as pd
import yaml

sys.path.append(str(Path(__file__).resolve().parents[1] / "lib"))

from econqt_common import strip_source_boilerplate  # noqa: E402


CATEGORY_VALUES = {"causal", "predictive", "other", "insufficient_text"}
CONFIDENCE_VALUES = {"high", "medium", "low"}
JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "category": {"type": "string", "enum": sorted(CATEGORY_VALUES)},
        "confidence": {"type": "string", "enum": sorted(CONFIDENCE_VALUES)},
        "reason": {"type": "string", "minLength": 1, "maxLength": 300},
    },
    "required": ["category", "confidence", "reason"],
}


def load_llm_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_prompt(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return " ".join(str(value).split()).strip()


def build_prompt_input(row: Mapping[str, Any], fields: list[str] | None = None) -> str:
    input_fields = fields or ["title", "abstract"]
    allowed = {field: clean_text(strip_source_boilerplate(row.get(field, ""))) for field in input_fields}
    return "\n\n".join(f"{field.upper()}:\n{value}" for field, value in allowed.items() if value)


def classification_text_chars(row: Mapping[str, Any], fields: list[str] | None = None) -> int:
    return len(build_prompt_input(row, fields))


def stable_cache_key(article_id: str, prompt_version: str, model: str, title: str, abstract: str) -> str:
    payload = json.dumps(
        {
            "article_id": article_id,
            "prompt_version": prompt_version,
            "model": model,
            "title": title,
            "abstract": abstract,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_llm_json(payload: Mapping[str, Any]) -> dict[str, str]:
    missing = [key for key in ["category", "confidence", "reason"] if key not in payload]
    if missing:
        raise ValueError(f"Missing LLM JSON keys: {', '.join(missing)}")

    category = str(payload["category"]).strip()
    confidence = str(payload["confidence"]).strip()
    reason = clean_text(payload["reason"])
    if category not in CATEGORY_VALUES:
        raise ValueError(f"Invalid LLM category: {category}")
    if confidence not in CONFIDENCE_VALUES:
        raise ValueError(f"Invalid LLM confidence: {confidence}")
    if not reason:
        raise ValueError("LLM reason is empty")
    return {"category": category, "confidence": confidence, "reason": reason}


def parse_response_text(response_payload: Mapping[str, Any]) -> str:
    output_text = response_payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    pieces: list[str] = []
    for output_item in response_payload.get("output", []) or []:
        for content_item in output_item.get("content", []) or []:
            text = content_item.get("text")
            if isinstance(text, str):
                pieces.append(text)
    return "\n".join(pieces).strip()


def parse_llm_response(response_payload: Mapping[str, Any]) -> dict[str, str]:
    response_text = parse_response_text(response_payload)
    if not response_text:
        raise ValueError("No text found in LLM response")
    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM response was not valid JSON: {exc}") from exc
    return validate_llm_json(parsed)


def build_openai_request(prompt: str, prompt_input: str, model: str, config: Mapping[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "input": [
            {"role": "developer", "content": prompt},
            {"role": "user", "content": prompt_input},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "causal_predictive_classification",
                "schema": JSON_SCHEMA,
                "strict": True,
            }
        },
        "max_output_tokens": int(config.get("max_output_tokens", 500)),
        "store": False,
    }
    if "temperature" in config and config["temperature"] is not None:
        payload["temperature"] = config["temperature"]
    return payload


def call_openai_responses(payload: Mapping[str, Any], config: Mapping[str, Any], api_key: str) -> dict[str, Any]:
    request = urllib.request.Request(
        str(config.get("api_url", "https://api.openai.com/v1/responses")),
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    timeout = int(config.get("request_timeout_seconds", 90))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API HTTP {exc.code}: {error_body}") from exc


def cache_path_for(cache_dir: Path, prompt_version: str, cache_key: str) -> Path:
    return cache_dir / prompt_version / f"{cache_key}.json"


def existing_rule_method(row: Mapping[str, Any]) -> str:
    method = clean_text(row.get("classification_method", ""))
    return method or "rule_based"


def merge_llm_result(row: Mapping[str, Any], result: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(row)
    llm_status = clean_text(result.get("llm_status", ""))
    if llm_status == "ok":
        merged["llm_category"] = result["category"]
        merged["llm_confidence"] = result["confidence"]
        merged["llm_reason"] = result["reason"]
        merged["causal_predictive_category"] = result["category"]
        merged["classification_confidence"] = result["confidence"]
        merged["classification_reason"] = result["reason"]
        merged["classification_method"] = "hybrid" if existing_rule_method(row) == "rule_based" else "llm_based"
    else:
        merged["llm_category"] = result.get("category", "")
        merged["llm_confidence"] = result.get("confidence", "")
        merged["llm_reason"] = result.get("reason", "")
        merged["classification_method"] = existing_rule_method(row)

    merged["llm_prompt_version"] = result.get("llm_prompt_version", "")
    merged["llm_model"] = result.get("llm_model", "")
    merged["llm_status"] = llm_status
    merged["llm_error"] = result.get("llm_error", "")
    merged["llm_cache_key"] = result.get("llm_cache_key", "")
    return merged


def classify_row(
    row: Mapping[str, Any],
    *,
    prompt: str,
    config: Mapping[str, Any],
    model: str,
    api_key: str | None,
    dry_run: bool,
    resume: bool,
    force: bool,
    project_root: Path,
) -> dict[str, Any]:
    prompt_version = str(config["prompt_version"])
    fields = list(config.get("input_fields", ["title", "abstract"]))
    prompt_input = build_prompt_input(row, fields)
    text_chars = len(prompt_input)
    cache_key = stable_cache_key(
        str(row.get("article_id", "")),
        prompt_version,
        model,
        clean_text(strip_source_boilerplate(row.get("title", ""))),
        clean_text(strip_source_boilerplate(row.get("abstract", ""))),
    )
    cache_dir = project_root / str(config.get("cache_dir", "data/intermediate/llm_cache"))
    cache_path = cache_path_for(cache_dir, prompt_version, cache_key)
    base_result = {
        "llm_prompt_version": prompt_version,
        "llm_model": model,
        "llm_cache_key": cache_key,
    }

    if text_chars < int(config.get("minimum_usable_text_chars", 250)):
        return merge_llm_result(
            row,
            {
                **base_result,
                "category": "insufficient_text",
                "confidence": "low",
                "reason": "Title and abstract text are too short for reliable LLM classification.",
                "llm_status": "skipped_insufficient_text",
                "llm_error": "",
            },
        )

    if dry_run:
        return merge_llm_result(
            row,
            {
                **base_result,
                "category": "",
                "confidence": "",
                "reason": "Dry run only; no API call was made.",
                "llm_status": "dry_run",
                "llm_error": "",
            },
        )

    if resume and cache_path.exists():
        try:
            cached_payload = json.loads(cache_path.read_text(encoding="utf-8"))
            parsed = parse_llm_response(cached_payload["response"])
            return merge_llm_result(row, {**base_result, **parsed, "llm_status": "ok", "llm_error": ""})
        except Exception as exc:  # noqa: BLE001
            return merge_llm_result(
                row,
                {
                    **base_result,
                    "category": "",
                    "confidence": "",
                    "reason": "",
                    "llm_status": "error",
                    "llm_error": f"cache parse error: {exc}",
                },
            )

    if cache_path.exists() and not force:
        return merge_llm_result(
            row,
            {
                **base_result,
                "category": "",
                "confidence": "",
                "reason": "",
                "llm_status": "error",
                "llm_error": f"cache file exists; use --resume or --force: {cache_path}",
            },
        )

    if not api_key:
        raise RuntimeError(f"Missing API key environment variable: {config.get('api_key_env_var', 'OPENAI_API_KEY')}")

    request_payload = build_openai_request(prompt, prompt_input, model, config)
    started = time.time()
    try:
        response_payload = call_openai_responses(request_payload, config, api_key)
        parsed = parse_llm_response(response_payload)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(
                {
                    "article_id": row.get("article_id", ""),
                    "prompt_version": prompt_version,
                    "model": model,
                    "request": request_payload,
                    "response": response_payload,
                    "elapsed_seconds": round(time.time() - started, 3),
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return merge_llm_result(row, {**base_result, **parsed, "llm_status": "ok", "llm_error": ""})
    except Exception as exc:  # noqa: BLE001
        return merge_llm_result(
            row,
            {
                **base_result,
                "category": "",
                "confidence": "",
                "reason": "",
                "llm_status": "error",
                "llm_error": str(exc),
            },
        )


def classify_dataframe(
    df: pd.DataFrame,
    *,
    prompt: str,
    config: Mapping[str, Any],
    model: str,
    api_key: str | None,
    dry_run: bool,
    resume: bool,
    force: bool,
    project_root: Path,
) -> pd.DataFrame:
    rows = [
        classify_row(
            row,
            prompt=prompt,
            config=config,
            model=model,
            api_key=api_key,
            dry_run=dry_run,
            resume=resume,
            force=force,
            project_root=project_root,
        )
        for row in df.to_dict(orient="records")
    ]
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/final/articles_classified_pilot.csv")
    parser.add_argument("--output", default="data/final/articles_classified_llm_pilot.csv")
    parser.add_argument("--config", default="config/llm_classification.yml")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    project_root = Path.cwd()
    config = load_llm_config(project_root / args.config)
    prompt = load_prompt(project_root / str(config["prompt_path"]))
    model = os.environ.get(str(config.get("model_env_var", "OPENAI_MODEL")), str(config["default_model"]))
    api_key = os.environ.get(str(config.get("api_key_env_var", "OPENAI_API_KEY")))

    if not args.dry_run and not api_key:
        raise SystemExit(f"Missing API key environment variable: {config.get('api_key_env_var', 'OPENAI_API_KEY')}")

    data = pd.read_csv(args.input, dtype=str).fillna("")
    if args.limit is not None:
        data = data.head(args.limit).copy()
    classified = classify_dataframe(
        data,
        prompt=prompt,
        config=config,
        model=model,
        api_key=api_key,
        dry_run=args.dry_run,
        resume=args.resume,
        force=args.force,
        project_root=project_root,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    classified.to_csv(output, index=False)
    print(f"rows={len(classified)}")
    print(classified["llm_status"].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
