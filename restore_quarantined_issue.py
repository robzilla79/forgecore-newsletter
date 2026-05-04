#!/usr/bin/env python3
"""Restore a quarantined AM/PM issue after it has been repaired.

Usage:
  python restore_quarantined_issue.py 2026-05-03-am

This moves content/issues/quarantine/<slug>.md back to content/issues/<slug>.md
only when the active file does not already exist.
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ISSUES_DIR = ROOT / "content" / "issues"
QUARANTINE_DIR = ISSUES_DIR / "quarantine"
SLUG_RE = re.compile(r"^20\d\d-\d\d-\d\d-(am|pm)$")


def main() -> int:
    if len(sys.argv) != 2 or not SLUG_RE.fullmatch(sys.argv[1]):
        print("Usage: python restore_quarantined_issue.py YYYY-MM-DD-am|pm", file=sys.stderr)
        return 2
    slug = sys.argv[1]
    src = QUARANTINE_DIR / f"{slug}.md"
    dst = ISSUES_DIR / f"{slug}.md"
    if not src.exists():
        print(f"Quarantined issue not found: {src.as_posix()}", file=sys.stderr)
        return 1
    if dst.exists():
        print(f"Active issue already exists: {dst.as_posix()}", file=sys.stderr)
        return 1
    text = src.read_text(encoding="utf-8", errors="ignore")
    if not text.lstrip().startswith("# ") or "## Sources" not in text:
        print("Refusing restore: issue still lacks basic title/sources structure", file=sys.stderr)
        return 1
    shutil.move(src.as_posix(), dst.as_posix())
    print(f"Restored {src.as_posix()} -> {dst.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
