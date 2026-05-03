#!/usr/bin/env python3
"""Quarantine legacy or low-quality issue files before site rendering.

Purpose: keep the public archive focused on useful ForgeCore issues.
This does not permanently delete content. It moves rejected files into
content/issues/quarantine/ so they stop appearing in archive, RSS, sitemap,
and generated public article pages after the next site render.
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

# Keep the first real AM/PM operating era and future issues. Older one-off
# experiments are not strong enough to remain in the public archive.
MIN_ACTIVE_DATE = "2026-05-02"

REQUIRED_SECTIONS = (
    "## Hook",
    "## Top Story",
    "## Why It Matters",
    "## Highlights",
    "## Tool of the Week",
    "## Workflow",
    "## CTA",
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


def quarantine_reason(path: Path, text: str) -> str | None:
    if path.parent.name == "quarantine":
        return None
    if not ACTIVE_SLOT_RE.fullmatch(path.name):
        return "legacy non-AM/PM issue filename"
    if issue_date(path) < MIN_ACTIVE_DATE:
        return f"older than active archive cutoff {MIN_ACTIVE_DATE}"
    if not text.lstrip().startswith("# "):
        return "missing top-level title"
    if word_count(text) < 500:
        return "too thin for public archive"
    lower = text.lower()
    for marker in BAD_MARKERS:
        if marker.lower() in lower:
            return f"contains bad marker: {marker}"
    missing = [section for section in REQUIRED_SECTIONS if section.lower() not in lower]
    if missing:
        return "missing required section: " + missing[0]
    if "## Sources" in text:
        sources = text.split("## Sources", 1)[-1]
        urls = re.findall(r"https?://[^\s)]+", sources)
        if len(urls) < 3:
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
    for path in sorted(ISSUES_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        reason = quarantine_reason(path, text)
        if not reason:
            continue
        target = unique_target(path)
        shutil.move(path.as_posix(), target.as_posix())
        moved.append((path.name, target.relative_to(ROOT).as_posix(), reason))
    if moved:
        print("[content_cleanup] Quarantined public-archive issues:")
        for name, target, reason in moved:
            print(f"- {name} -> {target}: {reason}")
    else:
        print("[content_cleanup] No issues needed quarantine")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
