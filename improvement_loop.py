#!/usr/bin/env python3
"""improvement_loop.py - Targeted quality improvement pass for ForgeCore newsletter.

Runs on the 10-minute cadence (via GitHub Actions improve.yml) and inside the
generate pipeline. It reads the latest critic review, asks the editor to fix the
specific weak points, then re-normalizes the issue.
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from issue_contract import ensure_issue_contract, list_issue_files
from templates.system_prompts import EDITOR_SYSTEM
from utils import WORKSPACE, append_text, load_project_env, load_text, now_str, write_text

load_project_env()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
EDITOR_MODEL = os.getenv("EDITOR_MODEL", os.getenv("WRITER_MODEL", "gemma3:12b"))
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "qwen3:8b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "240"))
OLLAMA_RETRIES = int(os.getenv("OLLAMA_RETRIES", "2"))
MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", "22000"))
MAX_ISSUES_TO_IMPROVE = int(os.getenv("MAX_ISSUES_TO_IMPROVE", "3"))
MIN_IMPROVEMENT_INTERVAL_MINUTES = int(os.getenv("MIN_IMPROVEMENT_INTERVAL_MINUTES", "30"))
IMPROVEMENT_ORIGIN = os.getenv("IMPROVEMENT_ORIGIN", "improve").strip() or "improve"
MAX_TARGETED_REWRITE_ITEMS = int(os.getenv("MAX_TARGETED_REWRITE_ITEMS", "6"))

STATE_DIR = WORKSPACE / "state"
IMPROVE_LOG = STATE_DIR / "improvement-log.md"
IMPROVE_LOCK = STATE_DIR / "improvement-lock.json"
_THINKING_MODEL_PREFIXES = ("qwen3", "qwq", "deepseek-r1", "deepseek-r2")


def log(msg: str) -> None:
    append_text(IMPROVE_LOG, f"[{now_str()}] {msg}")


def err(msg: str) -> None:
    append_text(STATE_DIR / "errors.log", f"[{now_str()}] improvement_loop: {msg}")
    log(f"[ERROR] {msg}")


def ollama_ok() -> bool:
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=8)
        r.raise_for_status()
        return True
    except Exception:
        return False


def _is_thinking_model(model: str) -> bool:
    lower = model.lower()
    return any(lower.startswith(p) for p in _THINKING_MODEL_PREFIXES)


def call_ollama(model: str, prompt: str) -> str:
    delay = 2.0
    last_exc: Exception | None = None
    options: dict[str, Any] = {"temperature": 0.1, "num_predict": 3500}
    if _is_thinking_model(model):
        options["think"] = False
        prompt = prompt.strip() + "\n\n/no_think"
    for attempt in range(1, OLLAMA_RETRIES + 1):
        try:
            resp = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False, "options": options},
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


def extract_json(raw: str) -> dict[str, Any] | None:
    cleaned = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL | re.IGNORECASE).strip()
    depth = 0
    start = -1
    in_string = False
    escape_next = False
    for i, ch in enumerate(cleaned):
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start != -1:
                blob = cleaned[start:i+1]
                try:
                    blob = blob.replace('\u201c', '"').replace('\u201d', '"').replace('\u2019', "'")
                    blob = re.sub(r',(\s*[}\]])', r'\1', blob)
                    return json.loads(blob)
                except Exception:
                    return None
    return None


def extract_markdown_payload(raw: str) -> str:
    parsed = extract_json(raw)
    if isinstance(parsed, dict):
        if isinstance(parsed.get('content'), str) and parsed.get('content', '').strip():
            raw = parsed['content']
        elif isinstance(parsed.get('files'), list):
            for item in parsed['files']:
                if isinstance(item, dict) and str(item.get('content', '')).strip():
                    raw = str(item['content'])
                    break
    raw = re.sub(r'^```(?:markdown|md|json)?\s*', '', raw.strip(), flags=re.IGNORECASE)
    raw = re.sub(r'\s*```$', '', raw.strip())
    return raw.strip()


def load_lock() -> dict:
    if IMPROVE_LOCK.exists():
        try:
            return json.loads(IMPROVE_LOCK.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {}


def save_lock(data: dict) -> None:
    IMPROVE_LOCK.parent.mkdir(parents=True, exist_ok=True)
    IMPROVE_LOCK.write_text(json.dumps(data, indent=2), encoding='utf-8')


def minutes_since(iso_str: str) -> float:
    try:
        dt = datetime.fromisoformat(iso_str)
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (now - dt).total_seconds() / 60.0
    except Exception:
        return 9999.0


def load_critic(issue_path: Path) -> dict | None:
    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', issue_path.stem)
    suffix = date_match.group(1) if date_match else 'latest'
    candidate = STATE_DIR / f'critic-review-{suffix}.json'
    if candidate.exists():
        try:
            return json.loads(candidate.read_text(encoding='utf-8'))
        except Exception:
            return None
    return None


def build_improvement_prompt(issue_text: str, issue_name: str, critic: dict | None) -> str:
    goals = load_text(WORKSPACE / 'GOALS.md')
    rewrite_plan = []
    must_fix = []
    weak_categories = []
    summary = ''
    if critic:
        rewrite_plan = [str(item).strip() for item in critic.get('rewrite_plan', []) if str(item).strip()][:MAX_TARGETED_REWRITE_ITEMS]
        must_fix = [str(item).strip() for item in critic.get('must_fix', []) if str(item).strip()][:MAX_TARGETED_REWRITE_ITEMS]
        weak_categories = [str(item).strip() for item in critic.get('weak_categories', []) if str(item).strip()]
        summary = str(critic.get('summary', '')).strip()

    plan_lines = rewrite_plan or must_fix or [
        'Strengthen the headline and hook so they read like a publication, not a summary bot.',
        'Replace generic claims with specific, source-backed details and real consequences.',
        'Cut repetition, filler, and soft transitions.',
        'Make the CTA concrete and useful.',
    ]
    critic_block = '\n'.join(f'- {item}' for item in plan_lines)
    must_fix_block = '\n'.join(f'- {item}' for item in must_fix) or '- None provided by critic.'
    weak_block = ', '.join(weak_categories) or 'none'

    context = f"""# TARGETED IMPROVEMENT TASK
You are the ForgeCore editor. Rewrite the issue below so it is publishable.

## GOALS
{goals[:2000]}

## ISSUE FILE
{issue_name}

## CRITIC SUMMARY
{summary or 'No summary provided.'}

## WEAK CATEGORIES
{weak_block}

## MUST-FIX ITEMS
{must_fix_block}

## TARGETED REWRITE PLAN
{critic_block}

## ISSUE CONTENT
{issue_text[:MAX_CONTEXT_CHARS - 3500]}

## REQUIREMENTS
1. Fix the targeted issues above first. Do not ignore them.
2. Keep the same core topic, date, and source links unless a sentence is unsupported.
3. Make the writing feel publication-grade: sharper hook, stronger sentences, less repetition, more specificity.
4. Preserve all required sections: Hook, Top Story, Why It Matters, Highlights, Tool of the Week, Workflow, CTA, Sources.
5. Keep the Beehiiv subscribe URL and sponsor email in the CTA.
6. Return the full improved issue only. If you choose JSON, put the markdown in a content field; if you choose markdown, return plain markdown with no commentary."""
    return EDITOR_SYSTEM + '\n\n' + context


def improve_issue(issue_path: Path) -> bool:
    original = load_text(issue_path)
    if not original.strip():
        log(f'Skipping {issue_path.name}: empty')
        return False

    critic = load_critic(issue_path)
    log(f'Improving {issue_path.name} using targeted critic guidance ...')
    try:
        improved_raw = call_ollama(EDITOR_MODEL, build_improvement_prompt(original, issue_path.name, critic))
    except RuntimeError as exc:
        err(f'Editor model failed on {issue_path.name}: {exc}')
        try:
            improved_raw = call_ollama(FALLBACK_MODEL, build_improvement_prompt(original, issue_path.name, critic))
        except RuntimeError as exc2:
            err(f'Fallback model also failed: {exc2}')
            return False

    improved = extract_markdown_payload(improved_raw)
    if not improved or '## Hook' not in improved or '## CTA' not in improved:
        err(f'Editor returned invalid issue payload for {issue_path.name}; skipping write')
        return False
    if improved == original:
        log(f'No improvement detected for {issue_path.name}')
        return False

    change_ratio = abs(len(improved) - len(original)) / max(len(original), 1)
    if change_ratio < 0.005 and len(improved) > len(original) * 0.99:
        log(f'Improvement too minor for {issue_path.name}, skipping write')
        return False

    write_text(issue_path, improved + '\n')
    try:
        ensure_issue_contract(issue_path)
    except Exception as exc:
        err(f'Contract enforcement failed after improvement: {exc}')

    log(f'Improved {issue_path.name} ({len(original)} -> {len(improved)} chars)')
    return True


def main() -> int:
    if not ollama_ok():
        log('Ollama not reachable - skipping improvement pass')
        return 0

    issues = sorted(list_issue_files(), reverse=True)[:MAX_ISSUES_TO_IMPROVE]
    if not issues:
        log('No issue files found - nothing to improve')
        return 0

    lock = load_lock()
    improved_count = 0

    for issue_path in issues:
        key = issue_path.name
        last_entry = lock.get(key, {})
        last_improved = last_entry.get('last_improved', '')
        mins_ago = minutes_since(last_improved)

        if mins_ago < MIN_IMPROVEMENT_INTERVAL_MINUTES:
            log(f'Skipping {key}: improved {mins_ago:.1f}m ago (min interval {MIN_IMPROVEMENT_INTERVAL_MINUTES}m)')
            continue

        changed = improve_issue(issue_path)
        if changed:
            improved_count += 1
            lock[key] = {
                'last_improved': datetime.now(timezone.utc).isoformat(),
                'pass': int(last_entry.get('pass', 0)) + 1,
                'origin': IMPROVEMENT_ORIGIN,
            }
            save_lock(lock)

    log(f'Improvement pass complete: {improved_count}/{len(issues)} issues updated (model={EDITOR_MODEL}, origin={IMPROVEMENT_ORIGIN})')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
