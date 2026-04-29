#!/usr/bin/env python3
"""critic_review.py - Score the latest issue against a publication-quality rubric."""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import requests

from issue_contract import ensure_issue_contract, latest_issue_path
from templates.system_prompts import CRITIC_SYSTEM
from utils import WORKSPACE, dump_json, load_project_env, load_text

load_project_env()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
CRITIC_MODEL = os.getenv("CRITIC_MODEL", os.getenv("EDITOR_MODEL", os.getenv("WRITER_MODEL", "gemma3:12b")))
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "qwen3:8b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "300"))
OLLAMA_RETRIES = int(os.getenv("OLLAMA_RETRIES", "3"))
MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", "22000"))
MIN_CRITIC_OVERALL = float(os.getenv("MIN_CRITIC_OVERALL", "8.0"))
MIN_CRITIC_CATEGORY = float(os.getenv("MIN_CRITIC_CATEGORY", "7.0"))
_MAX_REWRITE_ITEMS = int(os.getenv("CRITIC_MAX_REWRITE_ITEMS", "6"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

_THINKING_MODEL_PREFIXES = ("qwen3", "qwq", "deepseek-r1", "deepseek-r2")
_OPENAI_MODEL_PREFIXES = ("gpt-", "o1-", "o1", "o3-", "o3", "o4-", "o4")
RUN_TOKEN = os.getenv("RUN_TOKEN", "").strip()


def _is_thinking_model(model: str) -> bool:
    lower = model.lower()
    return any(lower.startswith(p) for p in _THINKING_MODEL_PREFIXES)


def _is_openai_model(model: str) -> bool:
    lower = model.lower()
    return any(lower.startswith(p) for p in _OPENAI_MODEL_PREFIXES)


def call_openai(model: str, prompt: str) -> str:
    """Call an OpenAI chat-completion model and return the text response."""
    try:
        from openai import OpenAI  # type: ignore
    except ImportError as exc:
        raise RuntimeError("openai package not installed; run: pip install openai") from exc

    client = OpenAI(api_key=OPENAI_API_KEY)
    delay = 2.0
    last_exc: Exception | None = None
    for attempt in range(1, OLLAMA_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a strict JSON-only critic. Output only a valid JSON object."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=3000,
            )
            return (response.choices[0].message.content or "").strip()
        except Exception as exc:
            last_exc = exc
            if attempt < OLLAMA_RETRIES:
                time.sleep(delay)
                delay = min(delay * 2, 20.0)
    raise RuntimeError(f"OpenAI call failed: {last_exc}")


def call_ollama(model: str, prompt: str, *, suppress_thinking: bool = True) -> str:
    options: dict[str, Any] = {"temperature": 0.1, "num_predict": 3000}
    final_prompt = prompt
    if suppress_thinking and _is_thinking_model(model):
        options["think"] = False
        final_prompt = prompt.strip() + "\n\n/no_think"
    delay = 2.0
    last_exc: Exception | None = None
    for attempt in range(1, OLLAMA_RETRIES + 1):
        try:
            resp = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": model, "prompt": final_prompt, "stream": False, "options": options},
                timeout=OLLAMA_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except Exception as exc:
            last_exc = exc
            if attempt < OLLAMA_RETRIES:
                time.sleep(delay)
                delay = min(delay * 2, 20.0)
    raise RuntimeError(f"Ollama failed: {last_exc}")


def call_model(model: str, prompt: str) -> str:
    """Route to OpenAI or Ollama based on the model name."""
    if _is_openai_model(model):
        return call_openai(model, prompt)
    return call_ollama(model, prompt)


def extract_json(raw: str) -> str:
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL | re.IGNORECASE).strip()
    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", raw, flags=re.DOTALL)
    if fenced:
        return fenced[0]
    depth = 0
    start = -1
    in_string = False
    escape_next = False
    for i, ch in enumerate(raw):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start != -1:
                return raw[start : i + 1]
    raise ValueError("No balanced JSON object found in critic output")


def parse_json(raw: str) -> dict[str, Any]:
    candidate = extract_json(raw)
    candidate = candidate.replace("\u201c", '"').replace("\u201d", '"').replace("\u2019", "'")
    candidate = re.sub(r",(\s*[}\]])", r"\1", candidate)
    return json.loads(candidate)


def _clamp_score(value: Any) -> float:
    try:
        score = float(value)
    except Exception:
        score = 0.0
    return max(0.0, min(10.0, round(score, 2)))


def _normalize_list(value: Any, *, limit: int = 6) -> list[str]:
    if isinstance(value, str):
        items = [value.strip()]
    elif isinstance(value, list):
        items = [str(item).strip() for item in value]
    else:
        items = []
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
        if len(cleaned) >= limit:
            break
    return cleaned


def build_prompt(issue_name: str, issue_text: str) -> str:
    schema = {
        "summary": "One-sentence verdict.",
        "overall_score": 0,
        "scores": {
            "headline_strength": 0,
            "hook_strength": 0,
            "specificity": 0,
            "originality": 0,
            "readability": 0,
            "tone": 0,
            "utility": 0,
            "non_repetition": 0,
        },
        "strengths": ["short bullets"],
        "weaknesses": ["short bullets"],
        "must_fix": ["specific problems to fix before publish"],
        "rewrite_plan": ["ordered rewrite tasks"],
        "verdict": "publishable|needs_revision|reject",
    }
    return (
        CRITIC_SYSTEM
        + "\n\nYou MUST respond with ONLY one valid JSON object. No prose before or after it. "
        + "Start with { and end with }. Use this schema:\n"
        + json.dumps(schema, indent=2)
        + f"\n\nIssue file: {issue_name}\n\nIssue content:\n{issue_text[:MAX_CONTEXT_CHARS]}"
    )


def evaluate_issue(path: Path) -> dict[str, Any]:
    issue_text = load_text(path)
    parse_failures: list[str] = []
    parsed: dict[str, Any] | None = None

    # --- Primary model attempt ---
    try:
        raw = call_model(CRITIC_MODEL, build_prompt(path.name, issue_text))
        parsed = parse_json(raw)
    except Exception as exc:
        parse_failures.append(f"{CRITIC_MODEL}: {type(exc).__name__}: {exc}")

    # --- Fallback model attempt (only if primary failed) ---
    if parsed is None:
        try:
            raw = call_model(FALLBACK_MODEL, build_prompt(path.name, issue_text))
            parsed = parse_json(raw)
        except Exception as fallback_exc:
            parse_failures.append(f"{FALLBACK_MODEL}: {type(fallback_exc).__name__}: {fallback_exc}")

    # --- Hardcoded reject sentinel if both models failed ---
    if parsed is None:
        parsed = {
            "summary": "Critic model outputs were not parseable JSON.",
            "overall_score": 0,
            "scores": {},
            "strengths": [],
            "weaknesses": ["Critic output parsing failed for both primary and fallback models."],
            "must_fix": ["Repair critic model/output formatting before publishing."],
            "rewrite_plan": [
                "Switch to a known-stable JSON-following model for critic.",
                "Add stricter response format controls and retries.",
            ],
            "verdict": "reject",
        }

    scores = parsed.get("scores", {}) if isinstance(parsed.get("scores"), dict) else {}
    normalized_scores = {
        "headline_strength": _clamp_score(scores.get("headline_strength")),
        "hook_strength": _clamp_score(scores.get("hook_strength")),
        "specificity": _clamp_score(scores.get("specificity")),
        "originality": _clamp_score(scores.get("originality")),
        "readability": _clamp_score(scores.get("readability")),
        "tone": _clamp_score(scores.get("tone")),
        "utility": _clamp_score(scores.get("utility")),
        "non_repetition": _clamp_score(scores.get("non_repetition")),
    }
    overall_score = _clamp_score(parsed.get("overall_score"))
    if overall_score == 0.0 and normalized_scores:
        overall_score = round(sum(normalized_scores.values()) / len(normalized_scores), 2)

    weak_categories = [name for name, score in normalized_scores.items() if score < MIN_CRITIC_CATEGORY]
    strengths = _normalize_list(parsed.get("strengths"))
    weaknesses = _normalize_list(parsed.get("weaknesses"))
    must_fix = _normalize_list(parsed.get("must_fix"))
    rewrite_plan = _normalize_list(parsed.get("rewrite_plan"), limit=_MAX_REWRITE_ITEMS)

    if not rewrite_plan:
        rewrite_plan = must_fix[:_MAX_REWRITE_ITEMS] or weaknesses[:_MAX_REWRITE_ITEMS]
    passed = overall_score >= MIN_CRITIC_OVERALL and not weak_categories and len(must_fix) == 0

    result = {
        "passed": passed,
        "issue": path.as_posix(),
        "model": CRITIC_MODEL,
        "fallback_model": FALLBACK_MODEL,
        "overall_score": overall_score,
        "min_overall_required": MIN_CRITIC_OVERALL,
        "min_category_required": MIN_CRITIC_CATEGORY,
        "scores": normalized_scores,
        "weak_categories": weak_categories,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "must_fix": must_fix,
        "rewrite_plan": rewrite_plan,
        "summary": str(parsed.get("summary", "")).strip(),
        "verdict": str(parsed.get("verdict", "needs_revision")).strip() or "needs_revision",
    }
    if parse_failures:
        result["parser_errors"] = parse_failures
    return result


def main() -> int:
    path = latest_issue_path()
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", path.stem)
    suffix = date_match.group(1) if date_match else "latest"
    out_path = WORKSPACE / "state" / f"critic-review-{suffix}.json"
    try:
        path = ensure_issue_contract(path)
        result = evaluate_issue(path)
    except Exception as exc:
        result = {
            "passed": False,
            "issue": path.as_posix(),
            "model": CRITIC_MODEL,
            "fallback_model": FALLBACK_MODEL,
            "overall_score": 0.0,
            "min_overall_required": MIN_CRITIC_OVERALL,
            "min_category_required": MIN_CRITIC_CATEGORY,
            "scores": {},
            "weak_categories": ["critic_runtime_failure"],
            "strengths": [],
            "weaknesses": [f"critic_review runtime failure: {type(exc).__name__}"],
            "must_fix": ["Resolve critic runtime/model failure before publish."],
            "rewrite_plan": ["Re-run critic_review.py after fixing model and JSON parsing reliability."],
            "summary": f"critic_review failed: {exc}",
            "verdict": "reject",
            "runtime_error": f"{type(exc).__name__}: {exc}",
        }
    result["run_token"] = RUN_TOKEN
    result["artifact_path"] = out_path.as_posix()
    dump_json(out_path, result)
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
