#!/usr/bin/env python3
"""Minimal Aware publish smoke test.

This verifies the current rendered site is safe enough to email. Navigation
chrome is intentionally not a send blocker.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from issue_contract import AWARE_FOOTER, has_forbidden_headers

ROOT = Path(__file__).resolve().parent
ISSUES_DIR = ROOT / "content" / "issues"
DIST_DIR = ROOT / "site" / "dist"
STATIC_PAGE_SLUGS = {
    "ai-tools",
    "workflows/solo-founder-ai-automation",
    "ai-tools/content-repurposing",
    "ai-tools/client-onboarding",
    "ai-tools/newsletter-growth",
    "ai-tools/automation",
    "ai-tools/ai-seo-aeo",
}


def urls_in(text: str) -> list[str]:
    return re.findall(r"https?://\S+", text)


def is_valid_issue(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if not text.lstrip().startswith("# "):
        return False
    if has_forbidden_headers(text) or re.search(r"^##\s+", text, flags=re.MULTILINE):
        return False
    if not re.search(r"^\*by\s+Em\s+[\u2014-]\s+.+\*\s*$", text, flags=re.MULTILINE | re.IGNORECASE):
        return False
    if AWARE_FOOTER not in text:
        return False
    if not urls_in(text):
        return False
    bad = ["ForgeCore AI Productivity Brief", "ForgeCore AI", "example.com", "No concrete content returned"]
    return not any(marker.lower() in text.lower() for marker in bad)


def issue_sort_key(path: Path) -> tuple[str, int, str]:
    stem = path.stem.lower()
    match = re.search(r"(\d{4}-\d{2}-\d{2})", stem)
    date_key = match.group(1) if match else "0000-00-00"
    slot_rank = 2 if stem.endswith("-pm") else 1 if stem.endswith("-am") else 0
    return (date_key, slot_rank, path.name)


def first_sitemap_issue_slug(xml: str) -> str:
    slugs = re.findall(r"<loc>https://news\.forgecore\.co/([^<]+?)/</loc>", xml)
    for slug in slugs:
        if slug and slug not in STATIC_PAGE_SLUGS:
            return slug
    return ""


def main() -> int:
    target = os.environ.get("ISSUE_SLUG", "").strip()
    if target:
        issue = ISSUES_DIR / f"{target}.md"
        valid_issues = [issue] if issue.exists() and is_valid_issue(issue) else []
    else:
        valid_issues = [path for path in ISSUES_DIR.glob("*.md") if is_valid_issue(path)]
    if not valid_issues:
        raise SystemExit("No valid Aware issue found for publish verification")

    latest = sorted(valid_issues, key=issue_sort_key)[-1]
    slug = latest.stem.lower()
    homepage = DIST_DIR / "index.html"
    article = DIST_DIR / slug / "index.html"
    rss = DIST_DIR / "rss.xml"
    sitemap = DIST_DIR / "sitemap.xml"
    for path in (homepage, article, rss, sitemap):
        if not path.exists():
            raise SystemExit(f"Rendered output missing: {path}")

    homepage_html = homepage.read_text(encoding="utf-8")
    article_html = article.read_text(encoding="utf-8")
    rss_xml = rss.read_text(encoding="utf-8")
    sitemap_xml = sitemap.read_text(encoding="utf-8")
    markdown = latest.read_text(encoding="utf-8")

    if f"/{slug}" not in homepage_html:
        raise SystemExit(f"Issue not linked from homepage: {slug}")
    if f"https://news.forgecore.co/{slug}/" not in sitemap_xml:
        raise SystemExit(f"Issue missing from sitemap: {slug}")
    if f"https://news.forgecore.co/{slug}/" not in rss_xml:
        raise SystemExit(f"Issue missing from RSS: {slug}")
    if "<article" not in article_html:
        raise SystemExit(f"Article markup missing: {slug}")
    if '<link rel="canonical"' not in article_html or 'application/ld+json' not in article_html:
        raise SystemExit(f"Article metadata missing: {slug}")
    if "## CTA" in markdown or "## Sources" in markdown:
        raise SystemExit(f"Old section headers present: {slug}")
    if not urls_in(markdown):
        raise SystemExit(f"Source URL missing: {slug}")

    first_issue = first_sitemap_issue_slug(sitemap_xml)
    if first_issue and first_issue != slug:
        print(f"Warning: first issue in sitemap is {first_issue}; verified target is {slug}")
    print(f"Aware publish verified: {slug}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
