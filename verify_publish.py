#!/usr/bin/env python3
"""Smoke test for ForgeCore static publishing.

Fails the workflow if publish_site.py did not render the newest valid issue
onto the homepage, article route, RSS feed, sitemap, and SEO metadata layer in
the expected order. Also verifies evergreen growth pages, AI-search files,
business pages, source relevance, structured data, and trust warnings.

This verifier intentionally applies deterministic hardening scripts when they
are available. That keeps older workflow reruns safe even if the workflow file
itself does not yet have dedicated hardening steps before verification.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

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
BUSINESS_PAGE_MARKERS = {
    "newsletter-advertising": (
        "Advertise with ForgeCore",
        "Best-fit sponsors",
        "Sponsor placements",
        "Starter package",
        "mailto:sponsors@forgecore.co",
        '"@type":"Organization"',
        '"@type":"BreadcrumbList"',
    ),
    "workflow-pack": (
        "The Solo Operator AI Workflow Pack",
        "10 workflow checklists",
        "10 copy/paste prompts",
        "Tool decision matrix",
        "Bad-fit warning checklist",
        "Read the workflow pack now",
        '"@type":"CreativeWork"',
        '"@type":"BreadcrumbList"',
    ),
}
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
LEAD_MAGNET = "The Solo Operator AI Workflow Pack"
BLOCKED_SOURCE_PATTERNS = (
    "forge-daily.kit.com",
    "forgecore-newsletter.beehiiv.com",
    "example.com",
)
AI_CRAWLER_MARKERS = (
    "OAI-SearchBot",
    "ChatGPT-User",
    "PerplexityBot",
    "Sitemap: https://news.forgecore.co/sitemap.xml",
)
AI_SEARCH_PAGE_MARKERS = (
    "AI search visibility",
    "Answer Engine Optimization",
    "Generative Engine Optimization",
    "Citation-ready page",
    "SEO vs AEO vs GEO vs LLMO",
    "Do not invent expertise",
)
LATEST_TRUST_MARKERS = (
    "Trust warnings",
    "Do not paste unredacted client secrets",
    "Ollama",
)


def apply_hardening_if_available() -> None:
    for script in HARDENING_SCRIPTS:
        if script.exists():
            subprocess.run([sys.executable, script.as_posix()], cwd=ROOT.as_posix(), check=True)


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


def first_latest_issue_slug(homepage_html: str) -> str:
    marker = "Latest operator playbooks"
    if marker in homepage_html:
        homepage_html = homepage_html.split(marker, 1)[1]
    match = re.search(r'<h2><a href="/([^"/]+)/">', homepage_html)
    return match.group(1) if match else ""


def first_rss_slug(xml: str) -> str:
    match = re.search(r"<item>\s*<title>.*?</title>\s*<link>https://news\.forgecore\.co/([^/]+)/</link>", xml, re.S)
    return match.group(1) if match else ""


def first_sitemap_issue_slug(xml: str) -> str:
    slugs = re.findall(r"<loc>https://news\.forgecore\.co/([^<]+?)/</loc>", xml)
    for slug in slugs:
        if slug and slug not in STATIC_PAGE_SLUGS and slug not in BUSINESS_PAGE_MARKERS:
            return slug
    return ""


def source_urls(markdown: str) -> list[str]:
    section = markdown.split("## Sources", 1)[-1]
    urls = re.findall(r"https?://[^\s)]+", section)
    return [url.rstrip(".,]") for url in urls]


def require_source_relevance(markdown: str, slug: str) -> None:
    urls = source_urls(markdown)
    if len(urls) < 3:
        raise SystemExit(f"AI search source gate failed for {slug}: fewer than 3 source URLs")
    blocked = [url for url in urls if any(pattern in url for pattern in BLOCKED_SOURCE_PATTERNS)]
    if blocked:
        raise SystemExit(f"AI search source gate failed for {slug}: CTA or placeholder URL counted as source: {blocked[0]}")
    lower = markdown.lower()
    source_blob = "\n".join(urls).lower()
    if "ollama" in lower and "ollama" not in source_blob:
        raise SystemExit(f"AI search source gate failed for {slug}: Ollama mentioned without Ollama source")


def require_static_pages(homepage_html: str, sitemap_xml: str) -> None:
    for slug in sorted(STATIC_PAGE_SLUGS):
        page = DIST_DIR / slug / "index.html"
        url = f"https://news.forgecore.co/{slug}/"
        if not page.exists():
            raise SystemExit(f"Static growth page missing: site/dist/{slug}/index.html")
        html = page.read_text(encoding="utf-8")
        if '<link rel="canonical"' not in html or 'application/ld+json' not in html:
            raise SystemExit(f"Static growth page missing SEO metadata: {slug}")
        if LEAD_MAGNET not in html:
            raise SystemExit(f"Static growth page missing lead magnet CTA: {slug}")
        if url not in sitemap_xml:
            raise SystemExit(f"Sitemap missing static growth page URL: {url}")
    if "/ai-tools/" not in homepage_html:
        raise SystemExit("Homepage missing AI tools directory link")
    if LEAD_MAGNET not in homepage_html:
        raise SystemExit("Homepage missing lead magnet CTA")
    if "/workflows/solo-founder-ai-automation/" not in homepage_html:
        raise SystemExit("Homepage missing workflow library link")


def require_business_pages(homepage_html: str, sitemap_xml: str) -> None:
    llms = DIST_DIR / "llms.txt"
    llms_text = llms.read_text(encoding="utf-8") if llms.exists() else ""
    for slug, markers in BUSINESS_PAGE_MARKERS.items():
        page = DIST_DIR / slug / "index.html"
        url = f"https://news.forgecore.co/{slug}/"
        if not page.exists():
            raise SystemExit(f"Business page missing: site/dist/{slug}/index.html")
        html = page.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in html:
                raise SystemExit(f"Business page {slug} missing marker: {marker}")
        if f'<link rel="canonical" href="{url}">' not in html:
            raise SystemExit(f"Business page {slug} missing canonical URL")
        if url not in sitemap_xml:
            raise SystemExit(f"Sitemap missing business page URL: {url}")
        if url not in llms_text:
            raise SystemExit(f"llms.txt missing business page URL: {url}")
        if f'/{slug}/' not in homepage_html:
            raise SystemExit(f"Homepage missing business page link: /{slug}/")


def require_metadata(html: str, slug: str) -> None:
    expected_url = f"https://news.forgecore.co/{slug}/"
    required_snippets = {
        "canonical URL": f'<link rel="canonical" href="{expected_url}">',
        "meta description": '<meta name="description" content="',
        "Open Graph type": '<meta property="og:type" content="article">',
        "Open Graph URL": f'<meta property="og:url" content="{expected_url}">',
        "Twitter card": '<meta name="twitter:card" content="summary">',
        "JSON-LD script": '<script type="application/ld+json">',
        "Article schema": '"@type":"Article"',
        "mainEntityOfPage": '"mainEntityOfPage"',
        "BreadcrumbList schema": '"@type":"BreadcrumbList"',
        "article keywords": '"keywords"',
        "article about": '"about"',
    }
    for label, snippet in required_snippets.items():
        if snippet not in html:
            raise SystemExit(f"Article page missing {label}: {slug}")


def require_site_polish(homepage_html: str, article_html: str, slug: str) -> None:
    homepage_required = {
        "hero title": "hero-title",
        "value grid": "value-grid",
        "read link": "Read the workflow",
        "responsive layout": "@media (max-width: 860px)",
    }
    article_required = {
        "back link": "Back to all playbooks",
        "lead magnet": LEAD_MAGNET,
        "mailto sponsor link": "mailto:sponsors@forgecore.co",
    }
    for label, snippet in homepage_required.items():
        if snippet not in homepage_html:
            raise SystemExit(f"Homepage missing polished {label}: {slug}")
    for label, snippet in article_required.items():
        if snippet not in article_html:
            raise SystemExit(f"Article page missing polished {label}: {slug}")
    if "[sponsors@forgecore.co](mailto:sponsors@forgecore.co)" in article_html:
        raise SystemExit(f"Article page still contains raw Markdown mailto link: {slug}")


def require_ai_search_assets(rss_xml: str) -> None:
    robots = DIST_DIR / "robots.txt"
    llms = DIST_DIR / "llms.txt"
    aeo_page = DIST_DIR / "ai-tools" / "ai-seo-aeo" / "index.html"
    if not robots.exists():
        raise SystemExit("robots.txt missing")
    robots_text = robots.read_text(encoding="utf-8")
    for marker in AI_CRAWLER_MARKERS:
        if marker not in robots_text:
            raise SystemExit(f"robots.txt missing AI crawler marker: {marker}")
    if not llms.exists():
        raise SystemExit("llms.txt missing")
    llms_text = llms.read_text(encoding="utf-8")
    for marker in ("ForgeCore", "AI Tools Directory", "Trust policy"):
        if marker not in llms_text:
            raise SystemExit(f"llms.txt missing marker: {marker}")
    if "<pubDate>" not in rss_xml:
        raise SystemExit("RSS missing pubDate")
    if not aeo_page.exists():
        raise SystemExit("AI SEO/AEO page missing")
    aeo_html = aeo_page.read_text(encoding="utf-8")
    for marker in AI_SEARCH_PAGE_MARKERS:
        if marker not in aeo_html:
            raise SystemExit(f"AI SEO/AEO page missing marker: {marker}")
    if '"@type":"HowTo"' not in aeo_html or '"@type":"BreadcrumbList"' not in aeo_html:
        raise SystemExit("AI SEO/AEO page missing HowTo or BreadcrumbList schema")


def require_latest_trust_markers(markdown: str, article_html: str, slug: str) -> None:
    combined = markdown + "\n" + article_html
    for marker in LATEST_TRUST_MARKERS:
        if marker not in combined:
            raise SystemExit(f"Latest issue missing AI-search trust marker ({slug}): {marker}")


def main() -> int:
    apply_hardening_if_available()

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
    latest_markdown = latest.read_text(encoding="utf-8")

    if f"/{slug}/" not in homepage_html and slug not in homepage_html:
        raise SystemExit(f"Latest issue not linked from homepage: {slug}")
    if first_latest_issue_slug(homepage_html) != slug:
        raise SystemExit(f"Latest issue is not first in latest-issues section: expected {slug}, found {first_latest_issue_slug(homepage_html) or 'none'}")
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
    require_static_pages(homepage_html, sitemap_xml)
    require_business_pages(homepage_html, sitemap_xml)
    require_metadata(article_html, slug)
    require_site_polish(homepage_html, article_html, slug)
    require_source_relevance(latest_markdown, slug)
    require_latest_trust_markers(latest_markdown, article_html, slug)
    require_ai_search_assets(rss_xml)

    print(f"Publish verified with AI search and business audit: {slug}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
