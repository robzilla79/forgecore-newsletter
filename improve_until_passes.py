#!/usr/bin/env python3
"""improve_until_passes.py - Critic-driven quality improvement controller.

Runs inside generate.yml after the editor agent. Loops up to MAX_ITERATIONS:
1. applies deterministic cleanup for mechanical formatting/link failures
2. runs the critic review
3. runs the quality gate
4. if either fails, runs targeted improvement_loop.py

Important production rule:
- Critic and quality gate must both pass before publish.
- Runtime failures in critic/gate are hard-blocking.
- Deterministic cleanup may remove banned placeholder URLs, repair glued headings,
  collapse duplicate sections, and enforce the configured CTA plumbing.
- It must not invent sources, recommendations, or article substance.
"""
from __future__ import annotations

import json
import os
import re
import time
import subprocess
import sys
from pathlib import Path

from issue_contract import issue_path_for_today
from utils import load_text, write_text

MAX_ITERATIONS = int(os.getenv("IMPROVE_MAX_ITERATIONS", "5"))
STATE_DIR = Path("state")
REQUIRED_SECTION_HEADERS = (
    "## Hook",
    "## Top Story",
    "## Why It Matters",
    "## Highlights",
    "## Tool of the Week",
    "## Workflow",
    "## CTA",
    "## Sources",
)
REQUIRED_CTA_URL = (
    os.getenv("PRIMARY_CTA_URL", "").strip()
    or os.getenv("KIT_SIGNUP_URL", "").strip()
    or "https://news.forgecore.co/"
)
REQUIRED_SPONSOR_EMAIL = os.getenv("SPONSOR_EMAIL", "sponsors@forgecore.co").strip() or "sponsors@forgecore.co"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_first_json_object(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        raise ValueError("empty stdout")
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    depth = 0
    start = -1
    in_string = False
    escape_next = False
    for i, ch in enumerate(text):
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
                candidate = text[start : i + 1]
                try:
                    parsed = json.loads(candidate)
                    if isinstance(parsed, dict):
                        return parsed
                except Exception:
                    continue
    raise ValueError("no balanced JSON object found")


def split_issue_sections(text: str) -> tuple[str, dict[str, list[str]]]:
    """Return title/preamble and bodies by exact required section header."""
    matches = list(re.finditer(r"^##\s+.+?\s*$", text, flags=re.MULTILINE))
    if not matches:
        return text.strip(), {}
    title = text[: matches[0].start()].strip()
    sections: dict[str, list[str]] = {header: [] for header in REQUIRED_SECTION_HEADERS}
    for idx, match in enumerate(matches):
        header = match.group(0).strip()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[match.end() : end].strip()
        if header in sections:
            sections[header].append(body)
    return title, sections


def collapse_duplicate_sections(text: str) -> str:
    title, sections = split_issue_sections(text)
    if not sections:
        return text
    output: list[str] = [title.strip()]
    for header in REQUIRED_SECTION_HEADERS:
        bodies = [body.strip() for body in sections.get(header, []) if body.strip()]
        if not bodies:
            continue
        if header in {"## Workflow", "## CTA", "## Sources"}:
            body = "\n\n".join(dict.fromkeys(bodies))
        else:
            body = bodies[0]
        output.append(f"{header}\n{body}".strip())
    return "\n\n".join(part for part in output if part.strip()).strip() + "\n"


def enforce_cta_contract(text: str) -> str:
    title, sections = split_issue_sections(text)
    bodies = [body.strip() for body in sections.get("## CTA", []) if body.strip()]
    if not bodies:
        return text
    cta = "\n\n".join(dict.fromkeys(bodies)).strip()
    additions: list[str] = []
    if REQUIRED_CTA_URL and REQUIRED_CTA_URL not in cta:
        additions.append(f"Subscribe for more operator-grade AI workflows: {REQUIRED_CTA_URL}")
    if REQUIRED_SPONSOR_EMAIL not in cta or "sponsor this issue" not in cta.lower():
        additions.append(f"Sponsor this issue: email {REQUIRED_SPONSOR_EMAIL}.")
    if additions:
        cta = (cta + "\n\n" + "\n".join(additions)).strip()
    sections["## CTA"] = [cta]

    output: list[str] = [title.strip()]
    for header in REQUIRED_SECTION_HEADERS:
        bodies_for_header = [body.strip() for body in sections.get(header, []) if body.strip()]
        if not bodies_for_header:
            continue
        output.append(f"{header}\n{bodies_for_header[0]}".strip())
    return "\n\n".join(part for part in output if part.strip()).strip() + "\n"


def deterministic_cleanup() -> bool:
    """Repair mechanical problems that repeatedly block publish.

    This removes placeholder example.com URLs, fixes section headings glued to
    prior prose/code-fence lines, collapses duplicate sections, and makes sure
    the CTA contains the configured subscribe URL plus the exact sponsor invite.
    """
    path = issue_path_for_today()
    if not path.exists():
        return False
    original = load_text(path)
    text = original

    # Remove banned placeholder URLs without inventing replacement sources.
    text = re.sub(r"\[([^\]]+)\]\(https?://(?:www\.)?example\.com[^)]*\)", r"\1", text, flags=re.IGNORECASE)
    text = re.sub(r"https?://(?:www\.)?example\.com\S*", "", text, flags=re.IGNORECASE)

    # Put headings on their own lines when model output glues them to prose or code fences.
    for header in REQUIRED_SECTION_HEADERS:
        escaped = re.escape(header)
        text = re.sub(rf"(?<!^)(?<!\n)\s*{escaped}\s*", f"\n\n{header}\n", text, flags=re.MULTILINE)
        text = re.sub(rf"^\s*{escaped}\s*(?=\S)", f"{header}\n", text, flags=re.MULTILINE)

    # Repair common fence/header joins such as ```## CTA.
    text = re.sub(r"```\s*(##\s+[A-Za-z])", r"```\n\n\1", text)

    # Normalize before structural collapse.
    text = "\n".join(line.rstrip() for line in text.splitlines())
    text = re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"
    text = collapse_duplicate_sections(text)
    text = enforce_cta_contract(text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"

    if text != original:
        write_text(path, text)
        print(f"[improve_until_passes] Deterministic cleanup updated {path.as_posix()}")
        return True
    return False


def run_json_script(script_name: str, run_token: str) -> dict:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    started = time.time() - 1.0
    env = {**os.environ, "RUN_TOKEN": run_token}
    result = subprocess.run([sys.executable, script_name], capture_output=True, text=True, env=env)
    try:
        payload = _extract_first_json_object(result.stdout)
    except (json.JSONDecodeError, ValueError) as exc:
        stderr = (result.stderr or "").strip()
        raise RuntimeError(
            f"{script_name} produced no parseable JSON stdout ({exc}); stderr={stderr or 'empty'}"
        )

    artifact_path = payload.get("artifact_path")
    if not artifact_path:
        raise RuntimeError(f"{script_name} missing artifact_path in JSON output")
    path = Path(str(artifact_path))
    if not path.exists():
        raise RuntimeError(f"{script_name} did not write expected artifact: {path.as_posix()}")
    if path.stat().st_mtime < started:
        raise RuntimeError(f"{script_name} artifact is stale (not generated during this pass): {path.as_posix()}")
    try:
        artifact_payload = _load_json(path)
    except Exception as exc:
        raise RuntimeError(f"{script_name} wrote non-parseable artifact JSON: {exc}")

    if payload.get("run_token") != run_token or artifact_payload.get("run_token") != run_token:
        raise RuntimeError(f"{script_name} artifact run token mismatch; refusing stale state reuse")
    if result.returncode not in (0, 1):
        raise RuntimeError(f"{script_name} exited {result.returncode}: {result.stderr.strip() or 'no stderr'}")
    return payload


def run_improvement() -> dict:
    env_override = {
        "MIN_IMPROVEMENT_INTERVAL_MINUTES": "0",
        "MAX_ISSUES_TO_IMPROVE": "1",
        "IMPROVEMENT_ORIGIN": "generate",
    }
    env = {**os.environ, **env_override}
    result = subprocess.run([sys.executable, "improvement_loop.py"], env=env, capture_output=True, text=True)
    try:
        payload = _extract_first_json_object(result.stdout)
    except Exception as exc:
        stderr = (result.stderr or "").strip()
        raise RuntimeError(f"improvement_loop.py returned non-JSON output: {exc}; stderr={stderr or 'empty'}")
    if result.returncode != 0:
        raise RuntimeError(f"improvement_loop.py failed: {payload.get('reason') or result.stderr.strip() or 'unknown error'}")
    if not payload.get("issue_path"):
        raise RuntimeError("improvement_loop.py reported no issue_path in output")
    return payload


def gate_errors(gate: dict) -> list[str]:
    checks = gate.get("checks", {}) if isinstance(gate.get("checks"), dict) else {}
    values = checks.get("errors") or gate.get("errors") or []
    return [str(item) for item in values if str(item).strip()]


def summarise(critic: dict, gate: dict, iteration: int) -> list[str]:
    errors = gate_errors(gate)
    critic_score = critic.get("overall_score", "?")
    critic_weak = critic.get("weak_categories", [])
    critic_passed = critic.get("passed", False)
    gate_passed = gate.get("passed", False)
    print(
        f"[improve_until_passes] Pass {iteration}/{MAX_ITERATIONS} | "
        f"critic_passed={critic_passed} | critic_score={critic_score} | "
        f"gate_passed={gate_passed} | gate_errors={len(errors)}"
    )
    for item in critic.get("must_fix", [])[:4]:
        print(f"  critic must-fix: {item}")
    for item in critic_weak[:4]:
        print(f"  critic weak category: {item}")
    for item in errors[:4]:
        print(f"  gate error: {item}")
    return errors


def critic_runtime_failed(critic: dict) -> bool:
    weak = critic.get("weak_categories", [])
    if not isinstance(weak, list):
        weak = []
    return bool(str(critic.get("runtime_error", "")).strip()) or "critic_runtime_failure" in weak


def _new_run_token(iteration: int) -> str:
    return f"pass-{iteration}-{time.time_ns()}"


def main() -> int:
    print(f"[improve_until_passes] Starting critic-driven improvement loop (max {MAX_ITERATIONS} passes)")

    best_score: float = -1.0

    for i in range(1, MAX_ITERATIONS + 1):
        deterministic_cleanup()
        token = _new_run_token(i)
        try:
            critic = run_json_script("critic_review.py", token)
            gate = run_json_script("quality_gate.py", token)
        except RuntimeError as exc:
            print(f"[improve_until_passes] FAIL-FAST: stale critic/gate artifact or invalid JSON: {exc}")
            return 1
        errors = summarise(critic, gate, i)
        if critic_runtime_failed(critic):
            print("[improve_until_passes] FAIL-FAST: critic runtime failure cannot be accepted as best effort.")
            return 1

        current_score = float(critic.get("overall_score") or 0.0)
        if current_score > best_score:
            best_score = current_score

        if critic.get("passed") and gate.get("passed"):
            print(f"[improve_until_passes] Critic and quality gate PASSED on pass {i}. Proceeding to publish.")
            return 0

        if i == MAX_ITERATIONS:
            print(
                f"[improve_until_passes] Reached max passes (best score={best_score:.1f}) "
                "without both critic and quality gate passing. Hard-blocking publish."
            )
            return 1

        print(f"[improve_until_passes] Running targeted improvement agent (pass {i}/{MAX_ITERATIONS - 1} remaining)...")
        try:
            change = run_improvement()
            if not change.get("changed"):
                print(f"[improve_until_passes] Improvement agent made no changes: {change.get('reason', 'no reason provided')}")
            else:
                print(f"[improve_until_passes] Improvement updated {change.get('issue_path')}")
            deterministic_cleanup()
        except RuntimeError as exc:
            print(f"[improve_until_passes] FAIL-FAST: {exc}")
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
