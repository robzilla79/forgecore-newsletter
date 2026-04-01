#!/usr/bin/env python3
"""improve_until_passes.py - Critic-driven quality improvement controller.

Runs inside generate.yml after the editor agent. Loops up to MAX_ITERATIONS:
1. runs the critic review
2. runs the quality gate
3. if either fails, runs targeted improvement_loop.py
Exits 0 only when the critic and quality gate both pass.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

MAX_ITERATIONS = 5
STATE_DIR = Path("state")


def find_latest_json(prefix: str) -> Path | None:
    files = sorted(STATE_DIR.glob(f"{prefix}-*.json"), reverse=True)
    return files[0] if files else None


def run_json_script(script_name: str, prefix: str) -> dict:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    result = subprocess.run([sys.executable, script_name], capture_output=True, text=True)
    try:
        return json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        pass
    path = find_latest_json(prefix)
    if path and path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"passed": False, "errors": [f"{script_name} produced no parseable output"]}


def run_improvement() -> int:
    import os

    env_override = {
        "MIN_IMPROVEMENT_INTERVAL_MINUTES": "0",
        "MAX_ISSUES_TO_IMPROVE": "1",
        "IMPROVEMENT_ORIGIN": "generate",
    }
    env = {**os.environ, **env_override}
    result = subprocess.run([sys.executable, "improvement_loop.py"], env=env)
    return result.returncode


def summarise(critic: dict, gate: dict, iteration: int) -> None:
    checks = gate.get("checks", {})
    gate_errors = gate.get("errors") or checks.get("errors", [])
    critic_score = critic.get("overall_score", "?")
    critic_weak = critic.get("weak_categories", [])
    critic_passed = critic.get("passed", False)
    gate_passed = gate.get("passed", False)
    print(
        f"[improve_until_passes] Pass {iteration}/{MAX_ITERATIONS} | "
        f"critic_passed={critic_passed} | critic_score={critic_score} | "
        f"gate_passed={gate_passed} | gate_errors={len(gate_errors)}"
    )
    for item in critic.get("must_fix", [])[:4]:
        print(f"  critic must-fix: {item}")
    for item in critic_weak[:4]:
        print(f"  critic weak category: {item}")
    for item in gate_errors[:4]:
        print(f"  gate error: {item}")


def main() -> int:
    print(f"[improve_until_passes] Starting critic-driven improvement loop (max {MAX_ITERATIONS} passes)")

    for i in range(1, MAX_ITERATIONS + 1):
        critic = run_json_script("critic_review.py", "critic-review")
        gate = run_json_script("quality_gate.py", "quality-gate")
        summarise(critic, gate, i)

        if critic.get("passed") and gate.get("passed"):
            print(f"[improve_until_passes] Critic and quality gate PASSED on pass {i}. Proceeding to publish.")
            return 0

        if i == MAX_ITERATIONS:
            print(f"[improve_until_passes] Still failing after {MAX_ITERATIONS} passes. Blocking publish and deploy.")
            return 1

        print(f"[improve_until_passes] Running targeted improvement agent (pass {i}/{MAX_ITERATIONS - 1} remaining)...")
        rc = run_improvement()
        if rc != 0:
            print(f"[improve_until_passes] improvement_loop.py exited with code {rc} — continuing to re-check quality.")

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
