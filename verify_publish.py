#!/usr/bin/env python3
"""Smoke test for ForgeCore static publishing.

Fails the workflow if publish_site.py did not render the newest valid issue
onto the homepage, article route, RSS feed, and sitemap in the expected order.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ISSUES_DIR = ROOT / "content" / "issues"
DIST_DIR = ROOT / "site" / "dist"
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
)


def is_valid_issue(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if len(text.split()) < 350:
        return False
    if not text.lstrip().startswith("# "):
        return False
    lower = text.lower()
    if any(marker.lower() in lower for marker in BAD_MARKERS):
        return False
    return all(section.lower() in lower for section in REQUIRED_SECTIONS)


def issue_sort_key(path: Path) -> tuple[str, int, str]:
    stem = path.stem.lower()
    match = re.search(r"(\d{4}-\d{2}-\d{2})", stem)
    date_key = match.group(1) if match else "0000-00-00"
    if stem.endswith("-pm"):
        slot_rank = 2
    elif stem.endswith("-am"):
        slot_rank = 1
    else:
        slot_rank = 0
    return (date_key, slot_rank, path.name)


def first_href_slug(html: str) -> str:
    match = re.search(r'<h2><a href="/([^"/]+)/">', html)
    return match.group(1) if match else ""


def first_rss_slug(xml: str) -> str:
    match = re.search(r"<item>\s*<title>.*?</title>\s*<link>https://news\.forgecore\.co/([^/]+)/</link>", xml, re.S)
    return match.group(1) if match else ""


def first_sitemap_issue_slug(xml: str) -> str:
    issue_urls = re.findall(r"<loc>https://news\.forgecore\.co/([^/]+)/</loc>", xml)
    return issue_urls[0] if issue_urls else ""


def main() -> int:
    if not ISSUES_DIR.exists():
        raise SystemExit("content/issues directory missing")

    valid_issues = [path for path in ISSUES_DIR.glob("*.md") if is_valid_issue(path)]
    if not valid_issues:
        raise SystemExit("No valid issues found for publish verification")

    latest = sorted(valid_issues, key=issue_sort_key)[-1]
    slug = latest.stem.lower()
    homepage = DIST_DIR / "index.html"
    article = DIST_DIR / slug / "index.html"
    rss = DIST_DIR / "rss.xml"
    sitemap = DIST_DIR / "sitemap.xml"

    if not homepage.exists():
        raise SystemExit("Homepage missing: site/dist/index.html")
    if not article.exists():
        raise SystemExit(f"Article page missing: site/dist/{slug}/index.html")
    if not rss.exists():
        raise SystemExit("RSS feed missing: site/dist/rss.xml")
    if not sitemap.exists():
        raise SystemExit("Sitemap missing: site/dist/sitemap.xml")

    homepage_html = homepage.read_text(encoding="utf-8")
    article_html = article.read_text(encoding="utf-8")
    rss_xml = rss.read_text(encoding="utf-8")
    sitemap_xml = sitemap.read_text(encoding="utf-8")

    if f"/{slug}/" not in homepage_html and slug not in homepage_html:
        raise SystemExit(f"Latest issue not linked from homepage: {slug}")
    if first_href_slug(homepage_html) != slug:
        raise SystemExit(f"Latest issue is not first on homepage: expected {slug}, found {first_href_slug(homepage_html) or 'none'}")
    if first_rss_slug(rss_xml) != slug:
        raise SystemExit(f"Latest issue is not first in RSS: expected {slug}, found {first_rss_slug(rss_xml) or 'none'}")
    if first_sitemap_issue_slug(sitemap_xml) != slug:
        raise SystemExit(
            f"Latest issue is not first issue URL in sitemap: expected {slug}, found {first_sitemap_issue_slug(sitemap_xml) or 'none'}"
        )
    if "ForgeCore" not in homepage_html:
        raise SystemExit("Homepage missing ForgeCore brand marker")
    if "<article" not in article_html:
        raise SystemExit(f"Article page missing article markup: {slug}")

    print(f"Publish verified: {slug}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
