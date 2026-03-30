#!/usr/bin/env python3
"""improve_until_passes.py - Aggressive quality improvement controller.

Runs inside generate.yml after the editor agent. Loops up to MAX_ITERATIONS
times: checks quality gate, and if it fails, runs improvement_loop.py to
self-improve the latest issue. Exits 0 only when the gate passes.
Exits 1 if the gate still fails after MAX_ITERATIONS (blocking publish/deploy).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

MAX_ITERATIONS = 5
STATE_DIR = Path("state")


def find_latest_quality_json() -> Path | None:
    """Return the most recently written quality-gate JSON file."""
    files = sorted(STATE_DIR.glob("quality-gate-*.json"), reverse=True)
    return files[0] if files else None


def run_quality_gate() -> dict:
    """Run quality_gate.py and return the parsed JSON result."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [sys.executable, "quality_gate.py"],
        capture_output=True,
        text=True,
    )
    # quality_gate.py prints JSON to stdout
    try:
        data = json.loads(result.stdout)
        return data
    except (json.JSONDecodeError, ValueError):
        pass
    # fallback: read from file
    path = find_latest_quality_json()
    if path and path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"passed": False, "errors": ["quality_gate.py produced no parseable output"]}


def run_improvement() -> int:
    """Run improvement_loop.py, bypassing the time-lock for in-pipeline use."""
    env_override = {
        "MIN_IMPROVEMENT_INTERVAL_MINUTES": "0",
        "MAX_ISSUES_TO_IMPROVE": "1",
    }
    import os
    env = {**os.environ, **env_override}
    result = subprocess.run(
        [sys.executable, "improvement_loop.py"],
        env=env,
    )
    return result.returncode


def summarise(gate: dict, iteration: int) -> None:
    checks = gate.get("checks", {})
    errors = gate.get("errors") or checks.get("errors", [])
    wc = checks.get("word_count", "?")
    passed = gate.get("passed", False)
    print(
        f"[improve_until_passes] Pass {iteration}/{MAX_ITERATIONS} "
        f"| passed={passed} | word_count={wc} | errors={len(errors)}"
    )
    for e in errors:
        print(f"  - {e}")


def main() -> int:
    print(f"[improve_until_passes] Starting aggressive improvement loop (max {MAX_ITERATIONS} passes)")

    for i in range(1, MAX_ITERATIONS + 1):
        gate = run_quality_gate()
        summarise(gate, i)

        if gate.get("passed"):
            print(f"[improve_until_passes] Quality gate PASSED on pass {i}. Proceeding to publish.")
            return 0

        if i == MAX_ITERATIONS:
            print(
                f"[improve_until_passes] Quality gate FAILED after {MAX_ITERATIONS} passes. "
                "Blocking publish and deploy."
            )
            return 1

        print(f"[improve_until_passes] Running improvement agent (pass {i}/{MAX_ITERATIONS - 1} remaining)...")
        rc = run_improvement()
        if rc != 0:
            print(f"[improve_until_passes] improvement_loop.py exited with code {rc} — continuing to re-check quality.")

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
