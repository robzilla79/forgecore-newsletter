#!/usr/bin/env python3
"""improvement_loop.py - Continuous quality improvement pass for ForgeCore newsletter.

Runs on the 10-minute cadence (via GitHub Actions improve.yml).
Picks the most recent issue file, sends it through the editor agent
for a targeted improvement pass, checks quality, and optionally
runs fresh research to keep source signals warm.

Designed to be idempotent: if nothing meaningful has changed, it
writes nothing new and the git diff will be empty.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import traceback
from pathlib import Path
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

from issue_contract import (
    ensure_issue_contract,
    latest_issue_path,
    list_issue_files,
)
from utils import WORKSPACE, append_text, load_text, now_str, today_str, write_text
from templates.system_prompts import EDITOR_SYSTEM

load_dotenv(WORKSPACE / ".env")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
EDITOR_MODEL = os.getenv("EDITOR_MODEL", os.getenv("WRITER_MODEL", "gemma3:12b"))
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "qwen3:8b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "240"))
OLLAMA_RETRIES = int(os.getenv("OLLAMA_RETRIES", "2"))
MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", "22000"))

# How many issues to cycle through for improvement (most-recent first)
MAX_ISSUES_TO_IMPROVE = int(os.getenv("MAX_ISSUES_TO_IMPROVE", "3"))

# Minimum minutes between improvement passes on the same issue
MIN_IMPROVEMENT_INTERVAL_MINUTES = int(
    os.getenv("MIN_IMPROVEMENT_INTERVAL_MINUTES", "30")
)

# Label for where this improvement loop was triggered from (generate vs improve)
IMPROVEMENT_ORIGIN = os.getenv("IMPROVEMENT_ORIGIN", "improve").strip() or "improve"

STATE_DIR = WORKSPACE / "state"
IMPROVE_LOG = STATE_DIR / "improvement-log.md"
IMPROVE_LOCK = STATE_DIR / "improvement-lock.json"


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


def call_ollama(model: str, prompt: str) -> str:
    delay = 2.0
    last_exc: Exception | None = None
    for attempt in range(1, OLLAMA_RETRIES + 1):
        try:
            resp = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 3000},
                },
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


def load_lock() -> dict:
    if IMPROVE_LOCK.exists():
        try:
            return json.loads(IMPROVE_LOCK.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_lock(data: dict) -> None:
    IMPROVE_LOCK.parent.mkdir(parents=True, exist_ok=True)
    IMPROVE_LOCK.write_text(json.dumps(data, indent=2), encoding="utf-8")


def minutes_since(iso_str: str) -> float:
    try:
        dt = datetime.fromisoformat(iso_str)
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (now - dt).total_seconds() / 60.0
    except Exception:
        return 9999.0


def build_improvement_prompt(issue_text: str, issue_name: str) -> str:
    goals = load_text(WORKSPACE / "GOALS.md")
    context = f"""# IMPROVEMENT TASK
You are the Forgecore editor. Your job is to improve the quality of an existing newsletter issue.

## GOALS
{goals[:2000]}

## ISSUE FILE: {issue_name}
{issue_text[:MAX_CONTEXT_CHARS - 3000]}

## IMPROVEMENT INSTRUCTIONS
Review the issue above and make targeted improvements:
1. Fix any awkward phrasing, passive voice, or weak topic sentences.
2. Strengthen the Hook if it is generic or cliched.
3. Ensure the "Why It Matters" section delivers a concrete business/ROI angle.
4. Remove any AI meta-phrases ("delve", "it's worth noting", "in conclusion", "As an AI").
5. Verify all section headings are present: Hook, Top Story, Why It Matters, Highlights, Tool of the Week, Workflow, CTA, Sources.
6. Tighten CTAs - make sure the Beehiiv subscribe link is present and the sponsor email is mentioned.
7. Improve any bullet lists that are vague or redundant.
8. Do NOT change the fundamental topic, date, or slug.
9. Return ONLY the improved full issue as Markdown - no commentary, no code fences."""
    return EDITOR_SYSTEM + "\n\n" + context


def improve_issue(issue_path: Path) -> bool:
    """Attempt to improve a single issue. Returns True if content was updated."""
    original = load_text(issue_path)
    if not original.strip():
        log(f"Skipping {issue_path.name}: empty")
        return False

    log(f"Improving {issue_path.name} ...")
    try:
        improved = call_ollama(
            EDITOR_MODEL,
            build_improvement_prompt(original, issue_path.name),
        )
    except RuntimeError as exc:
        err(f"Editor model failed on {issue_path.name}: {exc}")
        # Try fallback
        try:
            improved = call_ollama(
                FALLBACK_MODEL,
                build_improvement_prompt(original, issue_path.name),
            )
        except RuntimeError as exc2:
            err(f"Fallback model also failed: {exc2}")
            return False

    # Only write if there's a meaningful change (>50 chars difference or >1% change)
    if not improved or improved == original:
        log(f"No improvement detected for {issue_path.name}")
        return False

    change_ratio = abs(len(improved) - len(original)) / max(len(original), 1)
    if change_ratio < 0.005 and len(improved) > len(original) * 0.99:
        log(f"Improvement too minor for {issue_path.name}, skipping write")
        return False

    write_text(issue_path, improved + "\n")
    try:
        ensure_issue_contract(issue_path)
    except Exception as exc:
        err(f"Contract enforcement failed after improvement: {exc}")

    log(f"Improved {issue_path.name} ({len(original)} -> {len(improved)} chars)")
    return True


def main() -> int:
    if not ollama_ok():
        log("Ollama not reachable - skipping improvement pass")
        return 0

    issues = sorted(list_issue_files(), reverse=True)[:MAX_ISSUES_TO_IMPROVE]
    if not issues:
        log("No issue files found - nothing to improve")
        return 0

    lock = load_lock()
    improved_count = 0

    for issue_path in issues:
        key = issue_path.name
        last_entry = lock.get(key, {})
        last_improved = last_entry.get("last_improved", "")
        mins_ago = minutes_since(last_improved)

        if mins_ago < MIN_IMPROVEMENT_INTERVAL_MINUTES:
            log(
                f"Skipping {key}: improved {mins_ago:.1f}m ago "
                f"(min interval {MIN_IMPROVEMENT_INTERVAL_MINUTES}m)"
            )
            continue

        changed = improve_issue(issue_path)
        if changed:
            improved_count += 1
            lock[key] = {
                "last_improved": datetime.now(timezone.utc).isoformat(),
                "pass": int(last_entry.get("pass", 0)) + 1,
                "origin": IMPROVEMENT_ORIGIN,
            }
            save_lock(lock)

    log(
        f"Improvement pass complete: {improved_count}/{len(issues)} issues updated "
        f"(model={EDITOR_MODEL}, origin={IMPROVEMENT_ORIGIN})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
