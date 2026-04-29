#!/usr/bin/env python3
"""improvement_loop.py - Targeted quality improvement pass for ForgeCore newsletter.
Now uses OpenAI API (gpt-4o-mini).
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

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EDITOR_MODEL = os.getenv("EDITOR_MODEL", "gpt-4o-mini")
MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", "20000"))
MAX_ISSUES_TO_IMPROVE = int(os.getenv("MAX_ISSUES_TO_IMPROVE", "3"))
MIN_IMPROVEMENT_INTERVAL_MINUTES = int(os.getenv("MIN_IMPROVEMENT_INTERVAL_MINUTES", "30"))
IMPROVEMENT_ORIGIN = os.getenv("IMPROVEMENT_ORIGIN", "improve").strip() or "improve"
MAX_TARGETED_REWRITE_ITEMS = int(os.getenv("MAX_TARGETED_REWRITE_ITEMS", "6"))

STATE_DIR = WORKSPACE / "state"
IMPROVE_LOG = STATE_DIR / "improvement-log.md"
IMPROVE_LOCK = STATE_DIR / "improvement-lock.json"


def log(msg: str) -> None:
    append_text(IMPROVE_LOG, f"[{now_str()}] {msg}")


def err(msg: str) -> None:
    append_text(STATE_DIR / "errors.log", f"[{now_str()}] improvement_loop: {msg}")
    log(f"[ERROR] {msg}")


def emit_result(*, changed: bool, issue_path: str | None, reason: str) -> None:
    print(json.dumps({"changed": changed, "issue_path": issue_path, "reason": reason}))


def call_openai(model: str, prompt: str) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set")
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.15,
        "response_format": {"type": "json_object"},
    }
    for attempt in range(1, 4):
        try:
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=300,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
    return ""


def extract_markdown_payload(raw: str) -> str:
    try:
        parsed = json.loads(raw)
        content = parsed.get("content") or ""
        if not content and parsed.get("files"):
            content = parsed["files"][0].get("content") or ""
        return content.strip()
    except Exception:
        return ""


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


def load_critic(issue_path: Path) -> dict | None:
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", issue_path.stem)
    suffix = date_match.group(1) if date_match else "latest"
    candidate = STATE_DIR / f"critic-review-{suffix}.json"
    if candidate.exists():
        try:
            return json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def build_improvement_prompt(issue_text: str, issue_name: str, critic: dict | None) -> str:
    goals = load_text(WORKSPACE / "GOALS.md")
    rewrite_plan = critic.get("rewrite_plan", []) if critic else []
    must_fix = critic.get("must_fix", []) if critic else []
    plan_lines = rewrite_plan or must_fix or ["General improvement of flow and clarity."]

    context = (
        "# TARGETED IMPROVEMENT TASK\n"
        "Rewrite the issue below so it is publishable.\n"
        "## GOALS\n"
        f"{goals[:2000]}\n"
        "## MUST-FIX ITEMS\n"
        + "\n".join(f"- {item}" for item in plan_lines[:6])
        + "\n## ISSUE CONTENT\n"
        f"{issue_text[:MAX_CONTEXT_CHARS]}\n\n"
        "Return a JSON object with a \"content\" field containing the full improved Markdown."
    )
    return EDITOR_SYSTEM + "\n\n" + context


def improve_issue(issue_path: Path) -> tuple[bool, str]:
    original = load_text(issue_path)
    if not original.strip():
        return False, "empty issue payload"
    critic = load_critic(issue_path)
    try:
        raw = call_openai(EDITOR_MODEL, build_improvement_prompt(original, issue_path.name, critic))
        improved = extract_markdown_payload(raw)
        if not improved or len(improved) < 200:
            return False, "invalid editor payload"
        if improved == original:
            return False, "rewrite is identical"
        write_text(issue_path, improved + "\n")
        return True, "rewritten issue saved"
    except Exception as exc:
        err(str(exc))
        return False, str(exc)


def main() -> int:
    fail_fast = IMPROVEMENT_ORIGIN == "generate"
    issues = sorted(list_issue_files(), reverse=True)[:MAX_ISSUES_TO_IMPROVE]
    if not issues:
        emit_result(changed=False, issue_path=None, reason="no issues")
        return 0
    lock = load_lock()
    changed_path = None
    for issue_path in issues:
        key = issue_path.name
        last_improved = lock.get(key, {}).get("last_improved", "")
        if minutes_since(last_improved) < MIN_IMPROVEMENT_INTERVAL_MINUTES:
            continue
        changed, reason = improve_issue(issue_path)
        if changed:
            changed_path = issue_path.as_posix()
            lock[key] = {"last_improved": datetime.now(timezone.utc).isoformat()}
            save_lock(lock)
            break

    emit_result(
        changed=bool(changed_path),
        issue_path=changed_path,
        reason="improved" if changed_path else "no change",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
