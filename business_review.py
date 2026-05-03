#!/usr/bin/env python3
"""Generate a daily ForgeCore CEO business review.

Reads state/business-audit.json and business/mission-guardrails.md, then writes
state/business-review.md with a concise operator-facing action brief.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "state"
AUDIT_PATH = STATE / "business-audit.json"
REVIEW_PATH = STATE / "business-review.md"
MISSION_PATH = ROOT / "business" / "mission-guardrails.md"
RATE_CARD_PATH = ROOT / "business" / "sponsorship-rate-card.md"

MISSION_QUESTION = "Are we becoming the best practical AI workflow resource for solo operators, or are we drifting into generic AI news?"


def load_json(path: Path) -> dict:
    if not path.exists():
        return {"passed": False, "errors": [f"Missing {path.as_posix()}"], "warnings": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"passed": False, "errors": ["Audit JSON is not an object"], "warnings": []}
    except Exception as exc:
        return {"passed": False, "errors": [f"Could not read audit JSON: {exc}"], "warnings": []}


def status_line(audit: dict) -> str:
    if audit.get("passed"):
        return "PASS - business guardrails are intact."
    return "FAIL - critical business guardrail issue needs attention."


def recommended_actions(errors: list[str], warnings: list[str]) -> list[str]:
    actions: list[str] = []
    joined = "\n".join(errors + warnings).lower()

    if errors:
        actions.append("Fix critical audit errors before sending or promoting new traffic.")
    if "subscribe" in joined:
        actions.append("Repair the subscribe funnel: homepage -> /subscribe/ -> Kit signup.")
    if "workflow-pack" in joined or "workflow pack" in joined:
        actions.append("Repair the workflow-pack funnel: homepage -> /workflow-pack/ -> Kit signup.")
    if "newsletter-advertising" in joined or "sponsor" in joined or "advertis" in joined:
        actions.append("Repair sponsor surfaces and confirm sponsors@forgecore.co is visible.")
    if "kit" in joined or "email" in joined or "locked" in joined:
        actions.append("Treat email safety as priority one: confirm locked snapshots and one-AM/one-PM send protection.")
    if "affiliate" in joined:
        actions.append("Review affiliate registry before publishing monetized recommendations.")
    if "rates are still early" in joined or "traffic/subscriber proof" in joined:
        actions.append("Keep sponsor prices in test mode until subscriber, traffic, click, or reply proof improves.")

    actions.extend([
        "Run Deploy Site Updates after fixing site/business surface issues.",
        "Review the latest AM/PM email slots only if send workflows failed or Kit logs look inconsistent.",
        "Pick one growth asset to improve today: subscribe page, workflow pack, sponsor page, or AI tools directory.",
    ])

    # De-dupe while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for action in actions:
        if action not in seen:
            seen.add(action)
            unique.append(action)
    return unique[:8]


def build_review(audit: dict) -> str:
    errors = [str(item) for item in audit.get("errors", [])]
    warnings = [str(item) for item in audit.get("warnings", [])]
    checked_at = audit.get("checked_at") or datetime.now(timezone.utc).isoformat()
    generated_at = datetime.now(timezone.utc).isoformat()
    mission_exists = MISSION_PATH.exists()
    rate_card_exists = RATE_CARD_PATH.exists()

    lines: list[str] = []
    lines.append("# ForgeCore Daily Business Review")
    lines.append("")
    lines.append(f"Generated: {generated_at}")
    lines.append(f"Audit checked: {checked_at}")
    lines.append("")
    lines.append("## Status")
    lines.append("")
    lines.append(status_line(audit))
    lines.append("")
    lines.append("## Mission check")
    lines.append("")
    lines.append(MISSION_QUESTION)
    lines.append("")
    lines.append("Default CEO priority order: reader trust -> email reliability -> practical usefulness -> search compounding -> monetization -> polish.")
    lines.append("")
    lines.append("## Critical issues")
    lines.append("")
    if errors:
        for error in errors:
            lines.append(f"- {error}")
    else:
        lines.append("- None.")
    lines.append("")
    lines.append("## Warnings")
    lines.append("")
    if warnings:
        for warning in warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- None.")
    lines.append("")
    lines.append("## Business surface checklist")
    lines.append("")
    checklist = [
        ("Subscribe funnel", "homepage -> /subscribe/ -> Kit"),
        ("Workflow-pack funnel", "homepage -> /workflow-pack/ -> Kit"),
        ("Sponsor funnel", "homepage -> /newsletter-advertising/ -> sponsors@forgecore.co"),
        ("Email safety", "prepare locks content/email; send uses locked snapshot once"),
        ("Site-only deploy", "Deploy Site Updates can publish business pages without newsletter generation"),
        ("AI discovery", "sitemap, robots.txt, and llms.txt expose important pages"),
        ("Sponsor inventory", "rate card exists" if rate_card_exists else "rate card missing"),
        ("Mission guardrails", "guardrails exist" if mission_exists else "guardrails missing"),
    ]
    for name, detail in checklist:
        lines.append(f"- {name}: {detail}")
    lines.append("")
    lines.append("## Recommended CEO actions")
    lines.append("")
    for action in recommended_actions(errors, warnings):
        lines.append(f"- {action}")
    lines.append("")
    lines.append("## Next growth move")
    lines.append("")
    if errors:
        lines.append("Fix the critical issues first. Do not scale traffic or sponsor outreach while guardrails are broken.")
    elif warnings:
        lines.append("Business guardrails are intact. Address warnings, then improve one growth asset today.")
    else:
        lines.append("Business guardrails are clean. Improve one growth asset today: AI tools directory, workflow pack, sponsor page, or subscribe page.")
    lines.append("")
    lines.append("## Files to inspect")
    lines.append("")
    lines.append("- state/business-audit.json")
    lines.append("- business/mission-guardrails.md")
    lines.append("- business/sponsorship-rate-card.md")
    lines.append("- .github/workflows/business-audit.yml")
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    STATE.mkdir(parents=True, exist_ok=True)
    audit = load_json(AUDIT_PATH)
    REVIEW_PATH.write_text(build_review(audit), encoding="utf-8")
    print(f"Wrote {REVIEW_PATH.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
