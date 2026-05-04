#!/usr/bin/env python3
"""Quarantine legacy or low-quality issue files before site rendering.

Hard rule for active AM/PM operations:
- Cleanup may quarantine old legacy experiments.
- Cleanup must NOT silently remove recent AM/PM issues from the public archive.
- If a recent AM/PM issue is invalid, fail loudly so the operator/repair loop can fix it.

This prevents a newsletter from "disappearing" because a deploy, business audit,
or cleanup pass decided to move it out of content/issues without a repair step.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ISSUES_DIR = ROOT / "content" / "issues"
QUARANTINE_DIR = ISSUES_DIR / "quarantine"
ACTIVE_SLOT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-(am|pm)\.md$")
DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")
MIN_ACTIVE_DATE = "2026-05-02"

AM_WORKFLOW_SECTIONS = (
    "## Hook",
    "## Top Story",
    "## Why It Matters",
    "## Highlights",
    "## Tool of the Week",
    "## Workflow",
    "## CTA",
    "## Sources",
)
PM_BRIEF_SECTIONS = (
    "## The 3 Signals",
    "## Tool Watch",
    "## Operator Opportunity",
    "## Skip / Caution",
    "## Tomorrow's Move",
    "## Sources",
)
BAD_MARKERS = (
    "No concrete content returned",
    "Missing Content",
    "description incomplete",
    "raw intel",
    "[EMPTY RESPONSE]",
    "TODO",
    "lorem ipsum",
)
LOW_TRUST_SOURCE_MARKERS = (
    "techradar.com/news/the-benefits-of-local-ai",
    "forbes.com/sites/bernardmarr/2022/01/10/the-importance-of-data-privacy-in-ai",
)


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def issue_date(path: Path) -> str:
    match = DATE_RE.match(path.name)
    return match.group(1) if match else "0000-00-00"


def issue_slot(path: Path) -> str:
    if path.stem.endswith("-pm"):
        return "pm"
    if path.stem.endswith("-am"):
        return "am"
    return ""


def is_recent_active_issue(path: Path) -> bool:
    return ACTIVE_SLOT_RE.fullmatch(path.name) is not None and issue_date(path) >= MIN_ACTIVE_DATE


def has_sections(text: str, sections: tuple[str, ...]) -> bool:
    lower = text.lower()
    return all(section.lower() in lower for section in sections)


def missing_sections(text: str, sections: tuple[str, ...]) -> list[str]:
    lower = text.lower()
    return [section for section in sections if section.lower() not in lower]


def has_valid_issue_contract(path: Path, text: str) -> bool:
    slot = issue_slot(path)
    if slot == "pm":
        return has_sections(text, AM_WORKFLOW_SECTIONS) or has_sections(text, PM_BRIEF_SECTIONS)
    return has_sections(text, AM_WORKFLOW_SECTIONS)


def contract_failure_reason(path: Path, text: str) -> str:
    if issue_slot(path) == "pm":
        am_missing = missing_sections(text, AM_WORKFLOW_SECTIONS)
        pm_missing = missing_sections(text, PM_BRIEF_SECTIONS)
        return "missing PM-compatible section contract; AM missing: " + ", ".join(am_missing[:2]) + "; PM missing: " + ", ".join(pm_missing[:2])
    missing = missing_sections(text, AM_WORKFLOW_SECTIONS)
    return "missing required section: " + (missing[0] if missing else "unknown")


def source_url_count(text: str) -> int:
    if "## Sources" not in text:
        return 0
    sources = text.split("## Sources", 1)[-1]
    urls = re.findall(r"https?://[^\s)]+", sources)
    return len(list(dict.fromkeys(urls)))


def quarantine_reason(path: Path, text: str) -> str | None:
    if path.parent.name == "quarantine":
        return None
    if not ACTIVE_SLOT_RE.fullmatch(path.name):
        return "legacy non-AM/PM issue filename"
    if issue_date(path) < MIN_ACTIVE_DATE:
        return f"older than active archive cutoff {MIN_ACTIVE_DATE}"
    if not text.lstrip().startswith("# "):
        return "missing top-level title"
    if word_count(text) < 450:
        return "too thin for public archive"
    lower = text.lower()
    for marker in BAD_MARKERS:
        if marker.lower() in lower:
            return f"contains bad marker: {marker}"
    if not has_valid_issue_contract(path, text):
        return contract_failure_reason(path, text)
    if source_url_count(text) < 3:
        return "fewer than three sources"
    for marker in LOW_TRUST_SOURCE_MARKERS:
        if marker in lower:
            return f"contains weak/low-fit source marker: {marker}"
    return None


def unique_target(path: Path) -> Path:
    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
    target = QUARANTINE_DIR / path.name
    if not target.exists():
        return target
    stem = path.stem
    suffix = path.suffix
    i = 1
    while True:
        candidate = QUARANTINE_DIR / f"{stem}-{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1


def main() -> int:
    if not ISSUES_DIR.exists():
        print("[content_cleanup] SKIP: content/issues missing")
        return 0
    moved = []
    active_failures = []
    for path in sorted(ISSUES_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        reason = quarantine_reason(path, text)
        if not reason:
            continue
        if is_recent_active_issue(path):
            active_failures.append((path.name, reason))
            continue
        target = unique_target(path)
        shutil.move(path.as_posix(), target.as_posix())
        moved.append((path.name, target.relative_to(ROOT).as_posix(), reason))
    if moved:
        print("[content_cleanup] Quarantined legacy public-archive issues:")
        for name, target, reason in moved:
            print(f"- {name} -> {target}: {reason}")
    else:
        print("[content_cleanup] No legacy issues needed quarantine")
    if active_failures:
        print("[content_cleanup] BLOCKED: recent AM/PM issues need repair instead of quarantine:")
        for name, reason in active_failures:
            print(f"- {name}: {reason}")
        raise SystemExit(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
