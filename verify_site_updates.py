#!/usr/bin/env python3
"""Verify site/business updates without depending on newsletter generation."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST_DIR = ROOT / "site" / "dist"
HARDENING_SCRIPTS = (
    ROOT / "ai_search_hardening.py",
    ROOT / "business_hardening.py",
)
SITE_BASE = "https://news.forgecore.co"
SIGNUP = "https://forge-daily.kit.com/232bce5a31"
BUSINESS_PAGES = {
    "subscribe": (
        "Subscribe to ForgeCore",
        "Get practical AI workflows for solo operators",
        "Subscribe free",
        "Preview the workflow pack",
        SIGNUP,
        '"@type":"Organization"',
        '"@type":"BreadcrumbList"',
    ),
    "newsletter-advertising": (
        "Advertise with ForgeCore",
        "Best-fit sponsors",
        "Sponsor placements",
        "mailto:sponsors@forgecore.co",
        "Subscribe to see the newsletter",
        '"@type":"Organization"',
        '"@type":"BreadcrumbList"',
    ),
    "workflow-pack": (
        "The Solo Operator AI Workflow Pack",
        "10 workflow checklists",
        "10 copy/paste prompts",
        "Tool decision matrix",
        "Bad-fit warning checklist",
        "Subscribe and get the pack",
        "Subscribe to the newsletter",
        '"@type":"CreativeWork"',
        '"@type":"BreadcrumbList"',
    ),
    "archive": (
        "ForgeCore AI Workflow Archive",
        "Workflow categories",
        "Latest issues",
        "Most AI newsletters tell you what happened",
        '"@type":"CollectionPage"',
        '"@type":"BreadcrumbList"',
    ),
}
STATIC_PAGES = (
    "ai-tools",
    "workflows/solo-founder-ai-automation",
    "ai-tools/content-repurposing",
    "ai-tools/client-onboarding",
    "ai-tools/newsletter-growth",
    "ai-tools/automation",
    "ai-tools/ai-seo-aeo",
)
AI_CRAWLER_MARKERS = (
    "OAI-SearchBot",
    "ChatGPT-User",
    "PerplexityBot",
    "Sitemap: https://news.forgecore.co/sitemap.xml",
)


def run_hardening() -> None:
    for script in HARDENING_SCRIPTS:
        if script.exists():
            subprocess.run([sys.executable, script.as_posix()], cwd=ROOT.as_posix(), check=True)


def read(path: Path) -> str:
    if not path.exists():
        raise SystemExit(f"Required site file missing: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def require_homepage() -> str:
    html = read(DIST_DIR / "index.html")
    markers = (
        "ForgeCore",
        "hero-title",
        "value-grid",
        "The Solo Operator AI Workflow Pack",
        "/subscribe/",
        "/workflow-pack/",
        "/newsletter-advertising/",
        "/archive/",
        "/ai-tools/",
        "Subscribe to the newsletter",
        "forgecore-proof-positioning",
        "Not generic AI news",
        "Every issue has a job",
        "forgecore-workflow-cards",
        "AI tools by workflow",
    )
    for marker in markers:
        if marker not in html:
            raise SystemExit(f"Homepage missing marker: {marker}")
    if f'href="{SIGNUP}">Get the workflow pack</a>' in html:
        raise SystemExit("Homepage workflow-pack CTA points directly to Kit instead of /workflow-pack/")
    if f'href="{SIGNUP}">Subscribe to the newsletter</a>' in html:
        raise SystemExit("Homepage subscribe CTA points directly to Kit instead of /subscribe/")
    return html


def require_discovery_files() -> tuple[str, str]:
    robots = read(DIST_DIR / "robots.txt")
    for marker in AI_CRAWLER_MARKERS:
        if marker not in robots:
            raise SystemExit(f"robots.txt missing marker: {marker}")

    llms = read(DIST_DIR / "llms.txt")
    for marker in (
        "ForgeCore",
        "AI Tools Directory",
        "Trust policy",
        "https://news.forgecore.co/subscribe/",
        "https://news.forgecore.co/workflow-pack/",
        "https://news.forgecore.co/newsletter-advertising/",
        "https://news.forgecore.co/archive/",
    ):
        if marker not in llms:
            raise SystemExit(f"llms.txt missing marker: {marker}")

    sitemap = read(DIST_DIR / "sitemap.xml")
    return llms, sitemap


def require_static_pages(sitemap: str) -> None:
    for slug in STATIC_PAGES:
        page = DIST_DIR / slug / "index.html"
        html = read(page)
        url = f"{SITE_BASE}/{slug}/"
        if f'<link rel="canonical" href="{url}">' not in html:
            raise SystemExit(f"Static page missing canonical: {slug}")
        if "application/ld+json" not in html:
            raise SystemExit(f"Static page missing JSON-LD: {slug}")
        if url not in sitemap:
            raise SystemExit(f"Sitemap missing static page URL: {url}")


def require_business_pages(sitemap: str) -> None:
    for slug, markers in BUSINESS_PAGES.items():
        page = DIST_DIR / slug / "index.html"
        html = read(page)
        url = f"{SITE_BASE}/{slug}/"
        if f'<link rel="canonical" href="{url}">' not in html:
            raise SystemExit(f"Business page missing canonical: {slug}")
        if url not in sitemap:
            raise SystemExit(f"Sitemap missing business page URL: {url}")
        for marker in markers:
            if marker not in html:
                raise SystemExit(f"Business page {slug} missing marker: {marker}")
    subscribe_html = read(DIST_DIR / "subscribe" / "index.html")
    if f'href="{SIGNUP}">Subscribe free</a>' not in subscribe_html:
        raise SystemExit("Subscribe page missing conversion CTA to Kit")
    workflow_html = read(DIST_DIR / "workflow-pack" / "index.html")
    if f'href="{SIGNUP}">Subscribe and get the pack</a>' not in workflow_html:
        raise SystemExit("Workflow-pack page missing conversion CTA to Kit")


def main() -> int:
    run_hardening()
    require_homepage()
    _llms, sitemap = require_discovery_files()
    require_static_pages(sitemap)
    require_business_pages(sitemap)
    print("Site/business updates verified without newsletter send dependency")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
