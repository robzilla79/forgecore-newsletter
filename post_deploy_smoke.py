#!/usr/bin/env python3
"""Live post-deploy smoke test for news.forgecore.co.

verify_publish.py validates rendered repo artifacts in site/dist. This script
validates the public Cloudflare Pages deployment after deploy. It never mutates
content; it only fetches live URLs and fails loudly if the newest valid issue is
not publicly visible in the expected places.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from verify_publish import first_latest_issue_slug, first_rss_slug, first_sitemap_issue_slug, is_valid_issue, issue_sort_key
from utils import WORKSPACE, dump_json

SITE_BASE_URL = os.getenv("SITE_BASE_URL", "https://news.forgecore.co").rstrip("/")
ISSUES_DIR = WORKSPACE / "content" / "issues"
TIMEOUT_SECONDS = int(os.getenv("POST_DEPLOY_TIMEOUT_SECONDS", "20"))
RETRIES = int(os.getenv("POST_DEPLOY_RETRIES", "6"))
RETRY_DELAY_SECONDS = int(os.getenv("POST_DEPLOY_RETRY_DELAY_SECONDS", "15"))


def latest_issue_slug() -> str:
    if not ISSUES_DIR.exists():
        raise SystemExit("content/issues directory missing")
    valid = [path for path in ISSUES_DIR.glob("*.md") if is_valid_issue(path)]
    if not valid:
        raise SystemExit("No valid issues found for live post-deploy smoke test")
    return sorted(valid, key=issue_sort_key)[-1].stem.lower()


def fetch_text(url: str) -> str:
    req = Request(url, headers={"User-Agent": "ForgeCore post-deploy smoke/1.0"})
    with urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
        status = getattr(resp, "status", 200)
        if status >= 400:
            raise RuntimeError(f"HTTP {status} for {url}")
        body = resp.read()
    return body.decode("utf-8", errors="replace")


def attempt(slug: str) -> dict:
    homepage_url = f"{SITE_BASE_URL}/"
    article_url = f"{SITE_BASE_URL}/{slug}/"
    rss_url = f"{SITE_BASE_URL}/rss.xml"
    sitemap_url = f"{SITE_BASE_URL}/sitemap.xml"
    homepage = fetch_text(homepage_url)
    article = fetch_text(article_url)
    rss = fetch_text(rss_url)
    sitemap = fetch_text(sitemap_url)

    errors: list[str] = []
    if f"/{slug}/" not in homepage:
        errors.append(f"Homepage does not link latest issue: {slug}")
    if first_latest_issue_slug(homepage) != slug:
        errors.append(f"Homepage latest section mismatch: expected {slug}, found {first_latest_issue_slug(homepage) or 'none'}")
    if first_rss_slug(rss) != slug:
        errors.append(f"RSS first item mismatch: expected {slug}, found {first_rss_slug(rss) or 'none'}")
    if first_sitemap_issue_slug(sitemap) != slug:
        errors.append(f"Sitemap first issue URL mismatch: expected {slug}, found {first_sitemap_issue_slug(sitemap) or 'none'}")
    if f'<link rel="canonical" href="{article_url}">' not in article:
        errors.append(f"Article canonical missing or mismatched: {article_url}")
    if "<article" not in article:
        errors.append(f"Article markup missing: {article_url}")
    if '"@type":"Article"' not in article:
        errors.append(f"Article schema missing: {article_url}")
    return {
        "passed": not errors,
        "errors": errors,
        "urls": {
            "homepage": homepage_url,
            "article": article_url,
            "rss": rss_url,
            "sitemap": sitemap_url,
        },
    }


def main() -> int:
    slug = latest_issue_slug()
    last_result: dict | None = None
    transient_errors: list[str] = []
    for index in range(1, RETRIES + 1):
        try:
            last_result = attempt(slug)
            last_result["attempt"] = index
            if last_result["passed"]:
                break
        except (URLError, HTTPError, TimeoutError, RuntimeError) as exc:
            transient_errors.append(f"attempt {index}: {type(exc).__name__}: {exc}")
            last_result = {"passed": False, "errors": transient_errors[:], "attempt": index}
        if index < RETRIES:
            time.sleep(RETRY_DELAY_SECONDS)

    result = last_result or {"passed": False, "errors": ["post-deploy smoke did not run"]}
    result.update({
        "latest_slug": slug,
        "site_base_url": SITE_BASE_URL,
        "retries": RETRIES,
        "retry_delay_seconds": RETRY_DELAY_SECONDS,
        "validation_only": True,
    })
    out_path = WORKSPACE / "state" / f"post-deploy-smoke-{slug}.json"
    result["artifact_path"] = out_path.as_posix()
    dump_json(out_path, result)
    print(json.dumps(result, indent=2))
    return 0 if result.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
