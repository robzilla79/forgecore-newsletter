#!/usr/bin/env python3
"""Generate a daily ForgeCore operator review report.

This script is intentionally read-only with respect to generation. It inspects
committed issues, rendered site outputs, and state artifacts, then writes a
Markdown report for CEO/operator review.
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


def site_status(latest_slug: str) -> tuple[str, list[str]]:
    checks: list[str] = []
    homepage = DIST_DIR / "index.html"
    article = DIST_DIR / latest_slug / "index.html"
    rss = DIST_DIR / "rss.xml"
    sitemap = DIST_DIR / "sitemap.xml"
    if homepage.exists() and f"/{latest_slug}/" in load_text(homepage):
        checks.append("homepage links latest issue")
    else:
        checks.append("homepage missing latest issue link")
    if article.exists():
        article_html = load_text(article)
        if "<article" in article_html:
            checks.append("latest article route exists")
        if '<link rel="canonical"' in article_html and 'application/ld+json' in article_html:
            checks.append("latest article has SEO metadata")
        else:
            checks.append("latest article missing SEO metadata")
    else:
        checks.append("latest article route missing")
    checks.append("RSS exists" if rss.exists() else "RSS missing")
    checks.append("sitemap exists" if sitemap.exists() else "sitemap missing")
    bad = [item for item in checks if "missing" in item]
    return ("Attention" if bad else "OK", checks)


def issue_health(path: Path) -> dict[str, Any]:
    text = load_text(path)
    title = title_from_markdown(text, path.stem)
    missing = [section for section in REQUIRED_SECTIONS if section not in text]
    repeated = {section: section_count(text, section) for section in REQUIRED_SECTIONS if section_count(text, section) > 1}
    return {
        "path": path.as_posix(),
        "slug": path.stem,
        "title": title,
        "words": word_count(text),
        "urls": len(urls(text)),
        "missing_sections": missing,
        "repeated_sections": repeated,
        "has_workflow_block": "```" in text and "## Workflow" in text,
        "has_subscribe": "https://forgecore-newsletter.beehiiv.com/" in text,
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


def state_summary() -> list[str]:
    quality = latest_json("quality-gate-")
    critic = latest_json("critic-review-")
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
    return lines


def recommendation(issues: list[dict[str, Any]], site_label: str, duplicate_items: list[str]) -> str:
    latest = issues[0] if issues else {}
    if site_label != "OK":
        return "Fix site publish verification or rendered output before adding new features."
    if duplicate_items:
        return "Review duplicate-topic risk and keep the dedupe threshold active for the next two cycles."
    if latest and (latest.get("words", 0) < 750 or latest.get("urls", 0) < 3):
        return "Tighten article depth: latest issue is thin or undersourced."
    return "Hold the pipeline steady for the next cycle, then continue with affiliate registry and sponsor CTA improvements."


def build_report() -> str:
    issue_paths = issue_files(limit=8)
    issues = [issue_health(path) for path in issue_paths]
    latest_slug = issues[0]["slug"] if issues else ""
    site_label, site_checks = site_status(latest_slug) if latest_slug else ("Attention", ["no issues found"])
    duplicate_items = duplicate_risks(issues)
    status_counts = Counter()
    for item in issues[:2]:
        if item["missing_sections"] or item["repeated_sections"]:
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
        f"- Recommended next move: {recommendation(issues, site_label, duplicate_items)}",
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
        if not item["has_workflow_block"]:
            flags.append("workflow block missing")
        if not item["has_sponsor"]:
            flags.append("sponsor CTA incomplete")
        flag_text = "; ".join(flags) if flags else "OK"
        lines.append(f"- `{item['slug']}` — {item['title']} ({item['words']} words, {item['urls']} URLs) — {flag_text}")

    lines.extend(["", "## Site Checks", ""])
    for check in site_checks:
        lines.append(f"- {check}")

    lines.extend(["", "## Quality / Critic Artifacts", ""])
    for line in state_summary():
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
        "- It is a daily dashboard for spotting quality drift, duplicate topics, and deployment problems.",
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
