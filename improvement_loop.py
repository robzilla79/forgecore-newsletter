#!/usr/bin/env python3
"""improvement_loop.py - Targeted quality improvement pass for the current ForgeCore issue slot."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from openai import OpenAI

from templates.system_prompts import EDITOR_SYSTEM
from utils import (
    WORKSPACE,
    append_text,
    artifact_suffix_for_issue,
    issue_path_for_today,
    load_project_env,
    load_text,
    now_str,
    write_text,
)

load_project_env()

EDITOR_MODEL = os.getenv("EDITOR_MODEL", "gpt-4o-mini")
MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", "22000"))
MAX_TARGETED_REWRITE_ITEMS = int(os.getenv("MAX_TARGETED_REWRITE_ITEMS", "6"))

STATE_DIR = WORKSPACE / "state"
IMPROVE_LOG = STATE_DIR / "improvement-log.md"
EDITORIAL_LESSONS = STATE_DIR / "editorial-lessons.md"


def log(message: str) -> None:
    append_text(IMPROVE_LOG, f"[{now_str()}] {message}")


def err(message: str) -> None:
    append_text(STATE_DIR / "errors.log", f"[{now_str()}] improvement_loop: {message}")
    log(f"[ERROR] {message}")


def emit_result(*, changed: bool, issue_path: str | None, reason: str) -> None:
    print(json.dumps({"changed": changed, "issue_path": issue_path, "reason": reason}))


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def critic_path(issue_path: Path) -> Path:
    return STATE_DIR / f"critic-review-{artifact_suffix_for_issue(issue_path)}.json"


def gate_path(issue_path: Path) -> Path:
    return STATE_DIR / f"quality-gate-{artifact_suffix_for_issue(issue_path)}.json"


def extract_gate_errors(gate: dict[str, Any] | None) -> list[str]:
    if not gate:
        return []
    checks = gate.get("checks", {}) if isinstance(gate.get("checks"), dict) else {}
    values = checks.get("errors") or gate.get("errors") or []
    return [str(item) for item in values if str(item).strip()]


def extract_gate_warnings(gate: dict[str, Any] | None) -> list[str]:
    if not gate:
        return []
    checks = gate.get("checks", {}) if isinstance(gate.get("checks"), dict) else {}
    values = checks.get("warnings") or gate.get("warnings") or []
    return [str(item) for item in values if str(item).strip()]


def extract_critic_items(critic: dict[str, Any] | None) -> list[str]:
    if not critic:
        return []
    items: list[str] = []
    for key in ["must_fix", "rewrite_plan", "weaknesses", "weak_categories"]:
        value = critic.get(key)
        if isinstance(value, list):
            items.extend(str(item) for item in value if str(item).strip())
        elif isinstance(value, str) and value.strip():
            items.append(value.strip())
    return items[:MAX_TARGETED_REWRITE_ITEMS]


def lesson_rule_from_item(item: str) -> str:
    lower = item.lower()
    if "hook" in lower:
        return "Start the Hook with the operator outcome or decision, not a product announcement."
    if "headline" in lower or "title" in lower:
        return "Make the headline name the workflow, operator, tool choice, or measurable outcome."
    if "workflow" in lower or "step" in lower:
        return "Turn vague advice into 3-6 named steps plus one prompt, checklist, config, or command block."
    if "specific" in lower or "generic" in lower:
        return "Name the exact operator persona, job-to-be-done, tool stack, and tradeoff."
    if "source" in lower or "unsupported" in lower:
        return "Remove unsupported claims or tie them to a real source URL from today's research."
    if "cta" in lower:
        return "CTA must tell the reader what to try this week and include subscribe plus sponsor links."
    if "tradeoff" in lower:
        return "Include practical tradeoffs: cost, speed, privacy, quality, maintenance, or learning curve."
    return "Convert weak prose into a concrete operator decision, workflow, or tool tradeoff."


def persist_editorial_lessons(issue_path: Path, critic: dict[str, Any] | None, gate: dict[str, Any] | None, changed: bool, reason: str) -> None:
    critic_items = extract_critic_items(critic)
    gate_errors = extract_gate_errors(gate)
    gate_warnings = extract_gate_warnings(gate)
    priorities = (critic_items + gate_errors + gate_warnings)[:MAX_TARGETED_REWRITE_ITEMS]
    if not priorities and not changed:
        return
    lines = [
        f"## {now_str()} — {issue_path.as_posix()}",
        f"- Improvement result: {'changed' if changed else 'unchanged'} ({reason})",
    ]
    if critic:
        lines.append(f"- Critic score: {critic.get('overall_score', 'unknown')} | verdict: {critic.get('verdict', 'unknown')}")
    if priorities:
        lines.append("- Weaknesses found:")
        for item in priorities:
            lines.append(f"  - {item}")
        lines.append("- Rules for future issues:")
        seen_rules: set[str] = set()
        for item in priorities:
            rule = lesson_rule_from_item(item)
            if rule not in seen_rules:
                seen_rules.add(rule)
                lines.append(f"  - {rule}")
    else:
        lines.append("- Rule for future issues: Preserve the structure that passed and keep the workflow specific.")
    append_text(EDITORIAL_LESSONS, "\n".join(lines))


def call_editor(prompt: str) -> str:
    client = OpenAI()
    result = client.chat.completions.create(
        model=EDITOR_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return (result.choices[0].message.content or "").strip()


def clean_markdown(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```markdown"):
        cleaned = cleaned[len("```markdown"):].strip()
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:].strip()
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()
    return cleaned.strip() + "\n"


def build_prompt(issue_path: Path, issue_text: str, critic: dict[str, Any] | None, gate: dict[str, Any] | None) -> str:
    critic_items = extract_critic_items(critic)
    gate_errors = extract_gate_errors(gate)
    gate_warnings = extract_gate_warnings(gate)
    priorities = critic_items + gate_errors + gate_warnings
    if not priorities:
        priorities = ["Improve headline, hook, specificity, operator usefulness, and workflow clarity."]

    priority_block = "\n".join(f"- {item}" for item in priorities[:MAX_TARGETED_REWRITE_ITEMS])
    lessons = load_text(EDITORIAL_LESSONS)[-5000:]
    return (
        EDITOR_SYSTEM
        + "\n\n# TARGETED IMPROVEMENT TASK\n"
        + f"Rewrite the issue at {issue_path.as_posix()} so it is more publishable.\n"
        + "Return ONLY the complete final Markdown issue. Do not wrap it in JSON. Do not include notes.\n\n"
        + "## Must-fix priorities\n"
        + priority_block
        + "\n\n## Recent editorial lessons to apply\n"
        + (lessons or "No prior lessons yet.")
        + "\n\n## Current issue\n"
        + issue_text[:MAX_CONTEXT_CHARS]
    )


def structurally_valid(markdown: str) -> tuple[bool, str]:
    required = ["## Hook", "## Top Story", "## Why It Matters", "## Highlights", "## Tool of the Week", "## Workflow", "## CTA", "## Sources"]
    if not markdown.lstrip().startswith("# "):
        return False, "missing title"
    missing = [section for section in required if section not in markdown]
    if missing:
        return False, "missing sections: " + ", ".join(missing)
    if len(markdown.split()) < 500:
        return False, f"too short: {len(markdown.split())} words"
    return True, "ok"


def improve_issue(issue_path: Path) -> tuple[bool, str]:
    original = load_text(issue_path)
    if not original.strip():
        return False, "empty issue payload"
    critic = load_json(critic_path(issue_path))
    gate = load_json(gate_path(issue_path))
    try:
        raw = call_editor(build_prompt(issue_path, original, critic, gate))
        improved = clean_markdown(raw)
        ok, reason = structurally_valid(improved)
        if not ok:
            persist_editorial_lessons(issue_path, critic, gate, False, f"invalid improved markdown: {reason}")
            return False, f"invalid improved markdown: {reason}"
        if improved.strip() == original.strip():
            persist_editorial_lessons(issue_path, critic, gate, False, "rewrite is identical")
            return False, "rewrite is identical"
        write_text(issue_path, improved)
        persist_editorial_lessons(issue_path, critic, gate, True, "rewritten issue saved")
        return True, "rewritten issue saved"
    except Exception as exc:
        err(f"{type(exc).__name__}: {exc}")
        persist_editorial_lessons(issue_path, critic, gate, False, f"{type(exc).__name__}: {exc}")
        return False, f"{type(exc).__name__}: {exc}"


def main() -> int:
    path = issue_path_for_today()
    if not path.exists():
        emit_result(changed=False, issue_path=path.as_posix(), reason="no issue for slot")
        return 0
    log(f"Improving {path.as_posix()} using targeted critic/gate guidance ...")
    changed, reason = improve_issue(path)
    if changed:
        log(f"Improved {path.as_posix()}: {reason}")
    else:
        log(f"No improvement applied to {path.as_posix()}: {reason}")
    emit_result(changed=changed, issue_path=path.as_posix(), reason=reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
