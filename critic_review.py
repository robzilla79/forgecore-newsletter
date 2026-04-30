#!/usr/bin/env python3
"""critic_review.py - Score the current slot-specific issue against the ForgeCore rubric."""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import requests

from issue_contract import ensure_issue_contract
from templates.system_prompts import CRITIC_SYSTEM
from utils import WORKSPACE, artifact_suffix_for_issue, dump_json, issue_path_for_today, load_project_env, load_text

load_project_env()

CRITIC_MODEL = os.getenv("CRITIC_MODEL", os.getenv("EDITOR_MODEL", os.getenv("WRITER_MODEL", "gpt-4o-mini")))
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "gpt-4o-mini")
OPENAI_RETRIES = int(os.getenv("OPENAI_RETRIES", "3"))
MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", "22000"))
MIN_CRITIC_OVERALL = float(os.getenv("MIN_CRITIC_OVERALL", "6.5"))
MIN_CRITIC_CATEGORY = float(os.getenv("MIN_CRITIC_CATEGORY", "6.0"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
RUN_TOKEN = os.getenv("RUN_TOKEN", "").strip()

SCORE_KEYS = [
    "headline_strength",
    "hook_strength",
    "specificity",
    "originality",
    "readability",
    "tone",
    "utility",
    "non_repetition",
]


def call_openai(model: str, prompt: str) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set")
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a strict JSON-only critic. Output only one valid JSON object."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.15,
        "response_format": {"type": "json_object"},
    }
    last_exc: Exception | None = None
    for attempt in range(1, OPENAI_RETRIES + 1):
        try:
            resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=180)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            last_exc = exc
            if attempt < OPENAI_RETRIES:
                time.sleep(min(2 ** attempt, 20))
    raise RuntimeError(f"OpenAI call failed after {OPENAI_RETRIES} attempts: {last_exc}")


def parse_json(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in critic output")
    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("Critic output JSON was not an object")
    return parsed


def clamp(value: Any) -> float:
    try:
        score = float(value)
    except Exception:
        score = 0.0
    return max(0.0, min(10.0, round(score, 2)))


def as_list(value: Any, limit: int = 6) -> list[str]:
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, list):
        items = value
    else:
        items = []
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= limit:
            break
    return out


def build_prompt(issue_path: Path, issue_text: str) -> str:
    schema = {
        "summary": "One-sentence verdict.",
        "overall_score": 0,
        "scores": {key: 0 for key in SCORE_KEYS},
        "strengths": ["short bullets"],
        "weaknesses": ["short bullets"],
        "must_fix": ["specific problems to fix before publish"],
        "rewrite_plan": ["ordered rewrite tasks"],
        "verdict": "publishable|needs_revision|reject",
    }
    return (
        CRITIC_SYSTEM
        + "\n\nReturn ONLY valid JSON matching this schema:\n"
        + json.dumps(schema, indent=2)
        + f"\n\nIssue file: {issue_path.name}\n\nIssue content:\n{issue_text[:MAX_CONTEXT_CHARS]}"
    )


def evaluate_issue(path: Path) -> dict[str, Any]:
    issue_text = load_text(path)
    parsed: dict[str, Any] | None = None
    parser_errors: list[str] = []
    for model in [CRITIC_MODEL, FALLBACK_MODEL]:
        try:
            parsed = parse_json(call_openai(model, build_prompt(path, issue_text)))
            break
        except Exception as exc:
            parser_errors.append(f"{model}: {type(exc).__name__}: {exc}")
            print(f"[critic_review] {model} failed: {exc}", file=sys.stderr)
    if parsed is None:
        parsed = {
            "summary": "Critic model outputs were not parseable JSON.",
            "overall_score": 0,
            "scores": {},
            "strengths": [],
            "weaknesses": ["Critic output parsing failed."],
            "must_fix": ["Repair critic JSON reliability before publishing."],
            "rewrite_plan": ["Re-run critic after fixing output formatting."],
            "verdict": "reject",
        }

    raw_scores = parsed.get("scores", {}) if isinstance(parsed.get("scores"), dict) else {}
    scores = {key: clamp(raw_scores.get(key)) for key in SCORE_KEYS}
    overall = clamp(parsed.get("overall_score"))
    if overall == 0.0 and scores:
        overall = round(sum(scores.values()) / len(scores), 2)
    weak = [key for key, score in scores.items() if score < MIN_CRITIC_CATEGORY]
    verdict = str(parsed.get("verdict", "needs_revision")).strip().lower() or "needs_revision"
    passed = overall >= MIN_CRITIC_OVERALL and not weak and verdict != "reject"

    result = {
        "passed": passed,
        "issue": path.as_posix(),
        "model": CRITIC_MODEL,
        "fallback_model": FALLBACK_MODEL,
        "overall_score": overall,
        "min_overall_required": MIN_CRITIC_OVERALL,
        "min_category_required": MIN_CRITIC_CATEGORY,
        "scores": scores,
        "weak_categories": weak,
        "strengths": as_list(parsed.get("strengths")),
        "weaknesses": as_list(parsed.get("weaknesses")),
        "must_fix": as_list(parsed.get("must_fix")),
        "rewrite_plan": as_list(parsed.get("rewrite_plan")),
        "summary": str(parsed.get("summary", "")).strip(),
        "verdict": verdict,
    }
    if parser_errors:
        result["parser_errors"] = parser_errors
    return result


def main() -> int:
    path = issue_path_for_today()
    suffix = artifact_suffix_for_issue(path)
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
            "rewrite_plan": ["Re-run critic_review.py after fixing model and path handling."],
            "summary": f"critic_review failed: {exc}",
            "verdict": "reject",
            "runtime_error": f"{type(exc).__name__}: {exc}",
        }
    result["run_token"] = RUN_TOKEN
    result["artifact_path"] = out_path.as_posix()
    dump_json(out_path, result)
    print(json.dumps(result, indent=2))
    return 0 if result.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
