#!/usr/bin/env python3
"""improve_until_passes.py - Critic-driven quality improvement controller.

Runs inside generate.yml after the editor agent. Loops up to MAX_ITERATIONS:
1. runs the critic review
2. runs the quality gate
3. if either fails, runs targeted improvement_loop.py

Important production rule:
- Critic and quality gate must both pass before publish.
- Runtime failures in critic/gate are hard-blocking.
"""
from __future__ import annotations

import json
import os
import time
import subprocess
import sys
from pathlib import Path

MAX_ITERATIONS = int(os.getenv("IMPROVE_MAX_ITERATIONS", "5"))
STATE_DIR = Path("state")


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
        except RuntimeError as exc:
            print(f"[improve_until_passes] FAIL-FAST: {exc}")
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
