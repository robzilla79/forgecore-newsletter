#!/usr/bin/env python3
"""Smoke test for Aware by Em static publishing.

This verifier checks that the newest valid Aware issue rendered to the homepage,
article route, RSS feed, sitemap, and core static pages. It no longer expects the
old operator playbook sections or ## CTA / ## Sources headings.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from issue_contract import AWARE_FOOTER, has_forbidden_headers

ROOT = Path(__file__).resolve().parent
ISSUES_DIR = ROOT / "content" / "issues"
DIST_DIR = ROOT / "site" / "dist"
HARDENING_SCRIPTS = (
    ROOT / "ai_search_hardening.py",
    ROOT / "business_hardening.py",
    ROOT / "lead_magnet_hardening.py",
)
STATIC_PAGE_SLUGS = {
    "ai-tools",
    "workflows/solo-founder-ai-automation",
    "ai-tools/content-repurposing",
    "ai-tools/client-onboarding",
    "ai-tools/newsletter-growth",
    "ai-tools/automation",
    "ai-tools/ai-seo-aeo",
}
BAD_MARKERS = (
    "No concrete content returned",
    "Missing Content",
    "description incomplete",
    "raw intel",
    "[EMPTY RESPONSE]",
    "example.com",
    "ForgeCore AI Productivity Brief",
    "ForgeCore AI",
)


def apply_hardening_if_available() -> None:
    for script in HARDENING_SCRIPTS:
        if script.exists():
            subprocess.run([sys.executable, script.as_posix()], cwd=ROOT.as_posix(), check=True)


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def body_text_for_count(text: str) -> str:
    body = re.sub(r"^#.*$", "", text, flags=re.MULTILINE)
    body = re.sub(r"^\*by\s+Em\s+[\u2014-]\s+.*?\*\s*$", "", body, flags=re.MULTILINE | re.IGNORECASE)
    body = body.replace(AWARE_FOOTER, "")
    body = re.sub(r"https?://\S+", "", body)
    return body


def urls_in(text: str) -> list[str]:
    return [url.rstrip(").,]") for url in re.findall(r"https?://\S+", text)]


def is_valid_issue(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    lower = text.lower()
    if not text.lstrip().startswith("# "):
        return False
    if any(marker.lower() in lower for marker in BAD_MARKERS):
        return False
    if has_forbidden_headers(text) or re.search(r"^##\s+", text, flags=re.MULTILINE):
        return False
    if not re.search(r"^\*by\s+Em\s+[\u2014-]\s+.+\*\s*$", text, flags=re.MULTILINE | re.IGNORECASE):
        return False
    if AWARE_FOOTER not in text:
        return False
    if len(urls_in(text)) < 1:
        return False
    wc = word_count(body_text_for_count(text))
    return 350 <= wc <= 900


def issue_sort_key(path: Path) -> tuple[str, int, str]:
    stem = path.stem.lower()
    match = re.search(r"(\d{4}-\d{2}-\d{2})", stem)
    date_key = match.group(1) if match else "0000-00-00"
    slot_rank = 2 if stem.endswith("-pm") else 1 if stem.endswith("-am") else 0
    return (date_key, slot_rank, path.name)


def first_latest_issue_slug(homepage_html: str) -> str:
    marker = "Latest issues"
    if marker in homepage_html:
        homepage_html = homepage_html.split(marker, 1)[1]
    match = re.search(r'<h2><a href="/([^"/]+)/?">', homepage_html)
    return match.group(1) if match else ""


def first_rss_slug(xml: str) -> str:
    match = re.search(r"<item>\s*<title>.*?</title>\s*<link>https://news\.forgecore\.co/([^/]+)/?</link>", xml, re.S)
    return match.group(1) if match else ""


def first_sitemap_issue_slug(xml: str) -> str:
    slugs = re.findall(r"<loc>https://news\.forgecore\.co/([^<]+?)/</loc>", xml)
    for slug in slugs:
        if slug and slug not in STATIC_PAGE_SLUGS:
            return slug
    return ""


def require_metadata(html: str, slug: str) -> None:
    expected_url = f"https://news.forgecore.co/{slug}/"
    required = {
        "canonical URL": f'<link rel="canonical" href="{expected_url}">',
        "meta description": '<meta name="description" content="',
        "Open Graph type": '<meta property="og:type" content="article">',
        "JSON-LD script": '<script type="application/ld+json">',
        "Article schema": '"@type":"Article"',
        "mainEntityOfPage": '"mainEntityOfPage"',
    }
    for label, snippet in required.items():
        if snippet not in html:
            raise SystemExit(f"Article page missing {label}: {slug}")


def require_static_pages(sitemap_xml: str) -> None:
    for slug in sorted(STATIC_PAGE_SLUGS):
        page = DIST_DIR / slug / "index.html"
        url = f"https://news.forgecore.co/{slug}/"
        if not page.exists():
            raise SystemExit(f"Static page missing: site/dist/{slug}/index.html")
        html = page.read_text(encoding="utf-8")
        if '<link rel="canonical"' not in html or 'application/ld+json' not in html:
            raise SystemExit(f"Static page missing SEO metadata: {slug}")
        if url not in sitemap_xml:
            raise SystemExit(f"Sitemap missing static page URL: {url}")


def main() -> int:
    apply_hardening_if_available()

    if not ISSUES_DIR.exists():
        raise SystemExit("content/issues directory missing")
    valid_issues = [path for path in ISSUES_DIR.glob("*.md") if is_valid_issue(path)]
    if not valid_issues:
        raise SystemExit("No valid Aware issues found for publish verification")

    latest = sorted(valid_issues, key=issue_sort_key)[-1]
    slug = latest.stem.lower()
    homepage = DIST_DIR / "index.html"
    article = DIST_DIR / slug / "index.html"
    rss = DIST_DIR / "rss.xml"
    sitemap = DIST_DIR / "sitemap.xml"

    for path, label in ((homepage, "Homepage"), (article, "Article page"), (rss, "RSS feed"), (sitemap, "Sitemap")):
        if not path.exists():
            raise SystemExit(f"{label} missing: {path}")

    homepage_html = homepage.read_text(encoding="utf-8")
    article_html = article.read_text(encoding="utf-8")
    rss_xml = rss.read_text(encoding="utf-8")
    sitemap_xml = sitemap.read_text(encoding="utf-8")
    latest_markdown = latest.read_text(encoding="utf-8")

    if f"/{slug}/" not in homepage_html and f"/{slug}" not in homepage_html:
        raise SystemExit(f"Latest issue not linked from homepage: {slug}")
    if first_latest_issue_slug(homepage_html) != slug:
        raise SystemExit(f"Latest issue is not first in Latest issues: expected {slug}, found {first_latest_issue_slug(homepage_html) or 'none'}")
    if first_rss_slug(rss_xml) != slug:
        raise SystemExit(f"Latest issue is not first in RSS: expected {slug}, found {first_rss_slug(rss_xml) or 'none'}")
    if first_sitemap_issue_slug(sitemap_xml) != slug:
        raise SystemExit(f"Latest issue is not first issue URL in sitemap: expected {slug}, found {first_sitemap_issue_slug(sitemap_xml) or 'none'}")

    if "Aware by Em" not in homepage_html:
        raise SystemExit("Homepage missing Aware by Em marker")
    if "Latest issues" not in homepage_html:
        raise SystemExit("Homepage missing Latest issues section")
    if "&larr; All issues" not in article_html:
        raise SystemExit(f"Article page missing back link: {slug}")
    if "<article" not in article_html:
        raise SystemExit(f"Article page missing article markup: {slug}")
    if "## CTA" in latest_markdown or "## Sources" in latest_markdown:
        raise SystemExit(f"Latest issue still uses old section headers: {slug}")
    if len(urls_in(latest_markdown)) < 1:
        raise SystemExit(f"Latest issue has no source URL: {slug}")

    require_static_pages(sitemap_xml)
    require_metadata(article_html, slug)

    print(f"Aware publish verified: {slug}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
