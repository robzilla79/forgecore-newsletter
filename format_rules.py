"""Slot-aware ForgeCore newsletter format rules.

AM and PM intentionally serve different reader jobs:
- AM teaches one practical workflow/playbook.
- PM briefs the operator on signals, tools, opportunities, cautions, and tomorrow's move.
"""
from __future__ import annotations

import os

AM_REQUIRED_SECTIONS = [
    "## Hook",
    "## Top Story",
    "## Why It Matters",
    "## Highlights",
    "## Tool of the Week",
    "## Workflow",
    "## CTA",
    "## Sources",
]

PM_REQUIRED_SECTIONS = [
    "## The 3 Signals",
    "## Tool Watch",
    "## Operator Opportunity",
    "## Skip / Caution",
    "## Tomorrow's Move",
    "## Sources",
]

AM_FORMAT_RULE = """
AM format rule:
AM = build the system. Write one practical operator workflow/playbook.
Required sections in order:
# <sharp operator workflow headline>
## Hook
## Top Story
## Why It Matters
## Highlights
## Tool of the Week
## Workflow
## CTA
## Sources
""".strip()

PM_FORMAT_RULE = """
PM format rule:
PM = scan the signals. Do not write a second AM workflow article.
Use the ForgeCore PM Brief identity: quick, useful, operator-minded, and different from the morning issue.
Required sections in order:
# ForgeCore PM Brief — <date or sharp signal headline>
## The 3 Signals
Three concise AI/tool/business signals that matter to solo operators. Each signal must explain what changed and what an operator should do or watch.
## Tool Watch
One tool, feature, pricing change, or workflow worth watching. Include best fit, bad fit, and a simpler alternative.
## Operator Opportunity
One practical way a solo founder, creator, consultant, indie hacker, or small business operator can turn the signals into time saved, money made, a system built, or a better tool decision.
## Skip / Caution
One hype trap, privacy risk, bad-fit tool, or waste-of-money warning.
## Tomorrow's Move
One clear action the reader can take tomorrow morning. Include the subscribe URL and sponsor email naturally here.
## Sources
Bullet list of real source URLs.
""".strip()


def issue_slot() -> str:
    return os.getenv("ISSUE_SLOT", "").strip().lower()


def required_sections(slot: str | None = None) -> list[str]:
    slot = (slot or issue_slot()).strip().lower()
    return PM_REQUIRED_SECTIONS if slot == "pm" else AM_REQUIRED_SECTIONS


def format_rule(slot: str | None = None) -> str:
    slot = (slot or issue_slot()).strip().lower()
    return PM_FORMAT_RULE if slot == "pm" else AM_FORMAT_RULE


def is_pm(slot: str | None = None) -> bool:
    return (slot or issue_slot()).strip().lower() == "pm"
