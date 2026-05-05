#!/usr/bin/env python3
"""Patch publish_site.py so PM Brief issues render into index, RSS, and sitemap.

This keeps the source renderer fail-loud while adding the PM Brief contract used by
pm_verify_publish.py. The script is intentionally idempotent because the GitHub
workflows run it before publishing.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
PUBLISH_SITE = ROOT / "publish_site.py"

PM_REQUIRED_SECTIONS_BLOCK = '''PM_REQUIRED_SECTIONS = (
    "The 3 Signals",
    "Tool Watch",
    "Operator Opportunity",
    "Skip / Caution",
    "Tomorrow's Move",
    "Sources",
)
'''

REQUIRED_SECTIONS_BLOCK = '''REQUIRED_SECTIONS = (
    "Hook",
    "Top Story",
    "Why It Matters",
    "Highlights",
    "Tool of the Week",
    "Workflow",
    "CTA",
    "Sources",
)
'''

OLD_IS_VALID_ISSUE = '''def is_valid_issue(text: str) -> bool:
    if len(text.split()) < 350:
        return False
    if any(marker.lower() in text.lower() for marker in BAD_MARKERS):
        return False
    if not text.lstrip().startswith("# "):
        return False
    lower = text.lower()
    return all(f"## {section}".lower() in lower for section in REQUIRED_SECTIONS)
'''

NEW_IS_VALID_ISSUE = '''def issue_has_sections(text: str, sections: tuple[str, ...]) -> bool:
    lower = text.lower()
    return all(f"## {section}".lower() in lower for section in sections)


def is_valid_issue(text: str) -> bool:
    if len(text.split()) < 350:
        return False
    if any(marker.lower() in text.lower() for marker in BAD_MARKERS):
        return False
    if not text.lstrip().startswith("# "):
        return False
    return issue_has_sections(text, REQUIRED_SECTIONS) or issue_has_sections(text, PM_REQUIRED_SECTIONS)
'''


def main() -> int:
    text = PUBLISH_SITE.read_text(encoding="utf-8")

    if "PM_REQUIRED_SECTIONS" not in text:
        if REQUIRED_SECTIONS_BLOCK not in text:
            raise SystemExit("publish_site.py: REQUIRED_SECTIONS block not found")
        text = text.replace(
            REQUIRED_SECTIONS_BLOCK,
            REQUIRED_SECTIONS_BLOCK + PM_REQUIRED_SECTIONS_BLOCK,
            1,
        )

    if "def issue_has_sections" not in text:
        if OLD_IS_VALID_ISSUE not in text:
            raise SystemExit("publish_site.py: is_valid_issue block not found")
        text = text.replace(OLD_IS_VALID_ISSUE, NEW_IS_VALID_ISSUE, 1)

    PUBLISH_SITE.write_text(text, encoding="utf-8")
    print("publish_site.py PM Brief contract patch applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
