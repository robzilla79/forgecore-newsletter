#!/usr/bin/env python3
"""Fail loudly on contradictory critic artifacts.

This is a belt-and-suspenders gate. critic_review.py should already produce a
clean pass/fail result, but this script protects the publish path from older,
manually edited, or inconsistent critic artifacts where the overall score says
pass while the verdict or category floors say the issue still needs work.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from utils import WORKSPACE, artifact_suffix_for_issue, dump_json, issue_path_for_today

MIN_CRITIC_OVERALL = float(os.getenv("MIN_CRITIC_OVERALL", "6.5"))
MIN_CRITIC_CATEGORY = float(os.getenv("MIN_CRITIC_CATEGORY", "6.0"))
RUN_TOKEN = os.getenv("RUN_TOKEN", "").strip()
PUBLISHABLE_VERDICT = "publishable"


def critic_path_for_issue(issue_path: Path) -> Path:
    return WORKSPACE / "state" / f"critic-review-{artifact_suffix_for_issue(issue_path)}.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalized_verdict(value: Any) -> str:
    verdict = str(value or "").strip().lower()
    if verdict in {"publish", "pass", "passed", "approved"}:
        return PUBLISHABLE_VERDICT
    return verdict or "missing"


def collect_errors(critic: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if RUN_TOKEN and critic.get("run_token", "") != RUN_TOKEN:
        errors.append("Critic artifact run_token does not match current run")
    if not critic.get("passed"):
        errors.append("Critic artifact did not pass")
    runtime_error = str(critic.get("runtime_error", "")).strip()
    if runtime_error:
        errors.append(f"Critic runtime error present: {runtime_error}")
    overall = float(critic.get("overall_score", 0.0) or 0.0)
    if overall < MIN_CRITIC_OVERALL:
        errors.append(f"Critic overall score too low: {overall:.2f} < {MIN_CRITIC_OVERALL:.2f}")
    verdict = normalized_verdict(critic.get("verdict"))
    if verdict != PUBLISHABLE_VERDICT:
        errors.append(f"Critic verdict blocks publish: {verdict}")
    weak_categories = critic.get("weak_categories", [])
    if not isinstance(weak_categories, list):
        weak_categories = []
    scores = critic.get("scores", {})
    if not isinstance(scores, dict):
        scores = {}
    floor_weak = []
    for key, value in scores.items():
        try:
            score = float(value)
        except Exception:
            score = 0.0
        if score < MIN_CRITIC_CATEGORY:
            floor_weak.append(str(key))
    combined_weak = sorted(set(str(item) for item in weak_categories) | set(floor_weak))
    if combined_weak:
        errors.append("Critic category floor failed: " + ", ".join(combined_weak))
    return errors


def main() -> int:
    issue_path = issue_path_for_today()
    critic_path = critic_path_for_issue(issue_path)
    errors: list[str] = []
    critic: dict[str, Any] = {}
    if not critic_path.exists():
        errors.append(f"Critic artifact missing: {critic_path.as_posix()}")
    else:
        try:
            critic = load_json(critic_path)
            errors.extend(collect_errors(critic))
        except Exception as exc:
            errors.append(f"Could not read critic artifact: {type(exc).__name__}: {exc}")
    result = {
        "passed": not errors,
        "issue": issue_path.as_posix(),
        "critic_artifact": critic_path.as_posix(),
        "errors": errors,
        "critic_review": critic,
        "run_token": RUN_TOKEN,
        "validation_only": True,
    }
    out_path = WORKSPACE / "state" / f"critic-consistency-{artifact_suffix_for_issue(issue_path)}.json"
    result["artifact_path"] = out_path.as_posix()
    dump_json(out_path, result)
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
