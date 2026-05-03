#!/usr/bin/env python3
"""Generate a daily ForgeCore operator review report.

This script is intentionally read-only with respect to generation. It inspects
committed issues, rendered site outputs, traffic/conversion artifacts, and state
artifacts, then writes a Markdown report for CEO/operator review.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from utils import WORKSPACE, load_text, today_str, write_text

ISSUES_DIR = WORKSPACE / "content" / "issues"
STATE_DIR = WORKSPACE / "state"
DIST_DIR = WORKSPACE / "site" / "dist"
REPORT_DIR = WORKSPACE / "state" / "operator-reviews"
LATEST_REPORT = WORKSPACE / "state" / "operator-review-latest.md"
KIT_SENT_LOG = STATE_DIR / "kit_sent.json"
TRAFFIC_REPORT = STATE_DIR / "traffic-report.json"
LEAD_MAGNET = "The Solo Operator AI Workflow Pack"

REQUIRED_SECTIONS = [
    "## Hook",
    "## Top Story",
    "## Why It Matters",
    "## Highlights",
    "## Tool of the Week",
    "## Workflow",
    "## CTA",
    "## Sources",
]

STATIC_GROWTH_PAGES = [
    "ai-tools",
    "workflows/solo-founder-ai-automation",
    "ai-tools/content-repurposing",
    "ai-tools/client-onboarding",
    "ai-tools/newsletter-growth",
    "ai-tools/automation",
    "ai-tools/ai-seo-aeo",
]

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "for", "from", "how", "in", "into", "is", "it",
    "of", "on", "or", "the", "this", "to", "use", "using", "with", "your", "you", "managers", "manager",
    "operators", "operator", "solo", "ai", "forgecore", "newsletter", "issue", "brand", "brands",
}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


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


def issue_files(limit: int = 10) -> list[Path]:
    if not ISSUES_DIR.exists():
        return []
    return sorted(ISSUES_DIR.glob("*.md"), key=issue_sort_key, reverse=True)[:limit]


def title_from_markdown(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback.replace("-", " ").title()


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def urls(text: str) -> list[str]:
    return list(dict.fromkeys([url.rstrip(".,)") for url in re.findall(r"https?://\S+", text)]))


def section_count(text: str, section: str) -> int:
    return len(re.findall(rf"^{re.escape(section)}\s*$", text, flags=re.MULTILINE))


def malformed_section_count(text: str, section: str) -> int:
    return max(0, text.count(section) - section_count(text, section))


def topic_tokens(value: str) -> set[str]:
    out: set[str] = set()
    for token in re.findall(r"[a-z0-9]+", value.lower()):
        if len(token) >= 3 and token not in STOPWORDS:
            out.add(token)
    return out


def topic_similarity(left: str, right: str) -> float:
    a = topic_tokens(left)
    b = topic_tokens(right)
    if not a or not b:
        return 0.0
    return round(len(a & b) / max(1, len(a | b)), 2)


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def latest_json(prefix: str) -> dict[str, Any]:
    if not STATE_DIR.exists():
        return {}
    files = sorted(STATE_DIR.glob(f"{prefix}*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return load_json(files[0]) if files else {}


def kit_status_for_latest(latest_slug: str) -> str:
    sent = load_json(KIT_SENT_LOG)
    if not sent:
        return "Kit latest: no draft/send log found"
    if latest_slug in sent:
        item = sent.get(latest_slug, {}) if isinstance(sent.get(latest_slug), dict) else {}
        return (
            "Kit latest: synced; "
            f"mode={item.get('mode', 'unknown')}; "
            f"broadcast_id={item.get('broadcast_id', 'unknown')}"
        )
    return f"Kit latest: no entry for `{latest_slug}`"


def site_status(latest_slug: str) -> tuple[str, list[str]]:
    checks: list[str] = []
    homepage = DIST_DIR / "index.html"
    article = DIST_DIR / latest_slug / "index.html"
    rss = DIST_DIR / "rss.xml"
    sitemap = DIST_DIR / "sitemap.xml"
    homepage_html = load_text(homepage) if homepage.exists() else ""
    sitemap_xml = load_text(sitemap) if sitemap.exists() else ""

    if homepage.exists() and f"/{latest_slug}/" in homepage_html:
        checks.append("homepage links latest issue")
    else:
        checks.append("homepage missing latest issue link")
    if article.exists():
        article_html = load_text(article)
        checks.append("latest article route exists" if "<article" in article_html else "latest article markup missing")
        checks.append("latest article has SEO metadata" if '<link rel="canonical"' in article_html and 'application/ld+json' in article_html else "latest article missing SEO metadata")
        checks.append("latest article has lead magnet CTA" if LEAD_MAGNET in article_html else "latest article missing lead magnet CTA")
    else:
        checks.append("latest article route missing")
    checks.append("RSS exists" if rss.exists() else "RSS missing")
    checks.append("sitemap exists" if sitemap.exists() else "sitemap missing")
    for slug in STATIC_GROWTH_PAGES:
        page = DIST_DIR / slug / "index.html"
        url = f"https://news.forgecore.co/{slug}/"
        if page.exists() and url in sitemap_xml:
            checks.append(f"growth page OK: {slug}")
        else:
            checks.append(f"growth page missing or unsitemapped: {slug}")
    bad = [item for item in checks if "missing" in item]
    return ("Attention" if bad else "OK", checks)


def issue_health(path: Path) -> dict[str, Any]:
    text = load_text(path)
    title = title_from_markdown(text, path.stem)
    missing = [section for section in REQUIRED_SECTIONS if section_count(text, section) == 0]
    repeated = {section: section_count(text, section) for section in REQUIRED_SECTIONS if section_count(text, section) > 1}
    malformed = {section: malformed_section_count(text, section) for section in REQUIRED_SECTIONS if malformed_section_count(text, section) > 0}
    return {
        "path": path.as_posix(),
        "slug": path.stem,
        "title": title,
        "words": word_count(text),
        "urls": len(urls(text)),
        "missing_sections": missing,
        "repeated_sections": repeated,
        "malformed_sections": malformed,
        "has_workflow_block": "```" in text and "## Workflow" in text,
        "has_subscribe": "https://forge-daily.kit.com/232bce5a31" in text or "https://forgecore-newsletter.beehiiv.com/" in text,
        "has_sponsor": "sponsors@forgecore.co" in text and "sponsor this issue" in text.lower(),
    }


def duplicate_risks(issues: list[dict[str, Any]]) -> list[str]:
    risks: list[str] = []
    for idx, left in enumerate(issues):
        for right in issues[idx + 1:]:
            score = topic_similarity(left["title"], right["title"])
            if score >= 0.5:
                risks.append(f"{score:.2f} — `{left['slug']}` and `{right['slug']}` look close: {left['title']} / {right['title']}")
    return risks[:6]


def traffic_summary() -> tuple[str, list[str], list[str]]:
    data = load_json(TRAFFIC_REPORT)
    lines: list[str] = []
    actions: list[str] = []
    if not data:
        return (
            "Attention",
            [
                "Traffic report missing: add `state/traffic-report.json` from Cloudflare Web Analytics, Google Search Console, Kit/Beehiiv, and affiliate dashboards.",
                "Expected fields: period, top_pages, top_queries, newsletter_signups, cta_clicks, affiliate_clicks, sponsor_page_views.",
            ],
            ["Connect traffic and conversion exports so topic decisions are based on actual reader behavior."],
        )

    period = data.get("period", "unknown period")
    lines.append(f"Period: {period}")
    for metric in ["sessions", "pageviews", "newsletter_signups", "cta_clicks", "affiliate_clicks", "sponsor_page_views"]:
        if metric in data:
            lines.append(f"{metric.replace('_', ' ').title()}: {data.get(metric)}")
    top_pages = data.get("top_pages", []) or []
    top_queries = data.get("top_queries", []) or []
    if top_pages:
        lines.append("Top pages: " + "; ".join(f"{item.get('path', item)} ({item.get('views', 'n/a')})" if isinstance(item, dict) else str(item) for item in top_pages[:5]))
    else:
        actions.append("Add top page data to identify which workflows attract readers.")
    if top_queries:
        lines.append("Top search queries: " + "; ".join(f"{item.get('query', item)} ({item.get('clicks', 'n/a')})" if isinstance(item, dict) else str(item) for item in top_queries[:5]))
    else:
        actions.append("Add Search Console query data to steer article and landing-page topics.")
    if not data.get("newsletter_signups"):
        actions.append("Review lead magnet CTA placement once signup data is available.")
    return ("OK" if not actions else "Attention", lines, actions)


def state_summary(latest_slug: str) -> list[str]:
    quality = latest_json("quality-gate-")
    critic = latest_json("critic-review-")
    affiliate = latest_json("affiliate-linker-")
    monetization = latest_json("monetization-guard-")
    lines: list[str] = []
    if quality:
        passed = quality.get("passed")
        checks = quality.get("checks", {}) if isinstance(quality.get("checks"), dict) else {}
        errors = checks.get("errors", [])
        warnings = checks.get("warnings", [])
        lines.append(f"Quality gate latest: {'passed' if passed else 'failed'}; errors={len(errors)}, warnings={len(warnings)}")
    else:
        lines.append("Quality gate latest: no artifact found")
    if critic:
        lines.append(
            "Critic latest: "
            f"score={critic.get('overall_score', 'unknown')}; "
            f"verdict={critic.get('verdict', 'unknown')}; "
            f"weak={', '.join(critic.get('weak_categories', []) or []) or 'none'}"
        )
    else:
        lines.append("Critic latest: no artifact found")
    if affiliate:
        activated = affiliate.get("activated_links", []) or []
        tools = ", ".join(item.get("tool", "unknown") for item in activated if isinstance(item, dict)) or "none"
        lines.append(f"Affiliate linker latest: {'changed' if affiliate.get('changed') else 'no change'}; activated={len(activated)} ({tools})")
    else:
        lines.append("Affiliate linker latest: no artifact found")
    if monetization:
        lines.append(
            "Monetization guard latest: "
            f"{'passed' if monetization.get('passed') else 'failed'}; "
            f"errors={len(monetization.get('errors', []) or [])}, warnings={len(monetization.get('warnings', []) or [])}"
        )
    else:
        lines.append("Monetization guard latest: no artifact found")
    if latest_slug:
        lines.append(kit_status_for_latest(latest_slug))
    return lines


def recommendation(issues: list[dict[str, Any]], site_label: str, duplicate_items: list[str], traffic_label: str) -> str:
    latest = issues[0] if issues else {}
    if site_label != "OK":
        return "Fix site publish verification or rendered output before adding new features."
    if traffic_label != "OK":
        return "Connect traffic and conversion data so the next topic selection can optimize for reader behavior."
    if duplicate_items:
        return "Review duplicate-topic risk and keep the dedupe threshold active for the next two cycles."
    if latest and (latest.get("words", 0) < 750 or latest.get("urls", 0) < 3):
        return "Tighten article depth: latest issue is thin or undersourced."
    return "Scale the highest-performing workflow page into follow-up articles, tool comparisons, and sponsor inventory."


def build_report() -> str:
    issue_paths = issue_files(limit=8)
    issues = [issue_health(path) for path in issue_paths]
    latest_slug = issues[0]["slug"] if issues else ""
    site_label, site_checks = site_status(latest_slug) if latest_slug else ("Attention", ["no issues found"])
    duplicate_items = duplicate_risks(issues)
    traffic_label, traffic_lines, traffic_actions = traffic_summary()
    status_counts = Counter()
    for item in issues[:2]:
        if item["missing_sections"] or item["repeated_sections"] or item["malformed_sections"]:
            status_counts["attention"] += 1
        else:
            status_counts["ok"] += 1

    lines = [
        f"# ForgeCore Operator Review — {today_str()}",
        "",
        f"Generated: {now_utc().strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        "## Executive Status",
        "",
        f"- Site status: **{site_label}**",
        f"- Recent issue health: **{status_counts['ok']} OK / {status_counts['attention']} attention** among latest two issues",
        f"- Duplicate-topic risk: **{'Attention' if duplicate_items else 'OK'}**",
        f"- Traffic/conversion data: **{traffic_label}**",
        f"- Recommended next move: {recommendation(issues, site_label, duplicate_items, traffic_label)}",
        "",
        "## Latest Issues",
        "",
    ]
    if not issues:
        lines.append("- No issues found.")
    for item in issues[:6]:
        flags: list[str] = []
        if item["missing_sections"]:
            flags.append("missing sections")
        if item["repeated_sections"]:
            flags.append("repeated sections")
        if item["malformed_sections"]:
            flags.append("malformed sections")
        if not item["has_workflow_block"]:
            flags.append("workflow block missing")
        if not item["has_sponsor"]:
            flags.append("sponsor CTA incomplete")
        flag_text = "; ".join(flags) if flags else "OK"
        lines.append(f"- `{item['slug']}` — {item['title']} ({item['words']} words, {item['urls']} URLs) — {flag_text}")

    lines.extend(["", "## Site Checks", ""])
    for check in site_checks:
        lines.append(f"- {check}")

    lines.extend(["", "## Traffic and Conversion Feedback Loop", ""])
    for line in traffic_lines:
        lines.append(f"- {line}")
    if traffic_actions:
        lines.append("")
        lines.append("### Traffic Actions")
        lines.append("")
        for action in traffic_actions:
            lines.append(f"- {action}")

    lines.extend(["", "## Quality / Critic / Affiliate / Monetization / Kit Artifacts", ""])
    for line in state_summary(latest_slug):
        lines.append(f"- {line}")

    lines.extend(["", "## Duplicate Topic Watchlist", ""])
    if duplicate_items:
        for item in duplicate_items:
            lines.append(f"- {item}")
    else:
        lines.append("- No high-risk duplicate titles detected among recent issues.")

    lines.extend([
        "",
        "## Operator Notes",
        "",
        "- This report does not generate, edit, publish, or deploy newsletter content.",
        "- It is a daily dashboard for spotting quality drift, duplicate topics, affiliate activation, monetization guard status, Kit draft sync, growth-page coverage, traffic signals, and deployment problems.",
    ])
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    report = build_report()
    dated_path = REPORT_DIR / f"{today_str()}.md"
    write_text(dated_path, report)
    write_text(LATEST_REPORT, report)
    print(report)
    print(f"Wrote {dated_path.as_posix()} and {LATEST_REPORT.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
