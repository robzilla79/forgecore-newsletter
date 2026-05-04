#!/usr/bin/env python3
"""Publish verification for ForgeCore PM Brief issues.

This verifier is intentionally narrower than the AM verifier. It confirms the
PM source issue has the PM Brief contract and only requires rendered output when
publish_site.py produced the PM route.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST_DIR = ROOT / "site" / "dist"
ISSUES_DIR = ROOT / "content" / "issues"
SITE_BASE = "https://news.forgecore.co"
PM_REQUIRED_SECTIONS = (
    "## The 3 Signals",
    "## Tool Watch",
    "## Operator Opportunity",
    "## Skip / Caution",
    "## Tomorrow's Move",
    "## Sources",
)


def latest_pm_issue() -> Path:
    files = sorted(ISSUES_DIR.glob("20??-??-??-pm.md"), key=lambda p: p.name)
    if not files:
        raise SystemExit("No PM issue found for PM publish verification")
    return files[-1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    issue = latest_pm_issue()
    slug = issue.stem
    markdown = issue.read_text(encoding="utf-8")

    require(markdown.lstrip().startswith("# "), f"PM issue missing title: {slug}")
    for section in PM_REQUIRED_SECTIONS:
        require(re.search(rf"^{re.escape(section)}\s*$", markdown, flags=re.MULTILINE), f"PM issue missing section: {section}")
    urls = list(dict.fromkeys(re.findall(r"https?://\S+", markdown)))
    require(len(urls) >= 3, f"PM issue needs at least 3 URLs: {slug}")

    article = DIST_DIR / slug / "index.html"
    if article.exists():
        html = article.read_text(encoding="utf-8")
        require("<article" in html, f"PM article route missing article markup: {slug}")
        require('<link rel="canonical"' in html, f"PM article missing canonical metadata: {slug}")
        require('application/ld+json' in html, f"PM article missing JSON-LD: {slug}")

    rss = DIST_DIR / "rss.xml"
    sitemap = DIST_DIR / "sitemap.xml"
    if article.exists() and rss.exists() and sitemap.exists():
        require(f"{SITE_BASE}/{slug}/" in rss.read_text(encoding="utf-8"), f"RSS missing PM issue URL: {slug}")
        require(f"{SITE_BASE}/{slug}/" in sitemap.read_text(encoding="utf-8"), f"Sitemap missing PM issue URL: {slug}")

    print(f"PM publish verified: {slug}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
