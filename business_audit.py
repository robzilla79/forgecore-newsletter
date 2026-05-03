#!/usr/bin/env python3
"""Daily ForgeCore business audit.

This is a business-surface audit, not a newsletter generation workflow.
It checks that ForgeCore still has the core business infrastructure needed to
operate as a content-driven AI workflow media business.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "site" / "dist"
STATE = ROOT / "state"
SITE_BASE = "https://news.forgecore.co"
SIGNUP = "https://forge-daily.kit.com/232bce5a31"
SPONSOR_EMAIL = "sponsors@forgecore.co"

CHECK_FILES = {
    "business_hardening": ROOT / "business_hardening.py",
    "ai_search_hardening": ROOT / "ai_search_hardening.py",
    "verify_site_updates": ROOT / "verify_site_updates.py",
    "lock_email_issue": ROOT / "lock_email_issue.py",
    "kit_publish": ROOT / "kit_publish.py",
    "deploy_site_workflow": ROOT / ".github/workflows/deploy-site.yml",
    "prepare_workflow": ROOT / ".github/workflows/generate.yml",
    "send_workflow": ROOT / ".github/workflows/send.yml",
    "prepare_am": ROOT / ".github/workflows/generate-am.yml",
    "prepare_pm": ROOT / ".github/workflows/generate-pm.yml",
    "send_am": ROOT / ".github/workflows/send-am.yml",
    "send_pm": ROOT / ".github/workflows/send-pm.yml",
    "rate_card": ROOT / "business/sponsorship-rate-card.md",
    "affiliate_registry": ROOT / "monetization/affiliate-registry.json",
}

BUSINESS_PAGES = {
    "subscribe": {
        "required": [
            "Subscribe to ForgeCore",
            "Get practical AI workflows for solo operators",
            "Subscribe free",
            "Preview the workflow pack",
            SIGNUP,
            '"@type":"Organization"',
            '"@type":"BreadcrumbList"',
        ],
        "forbidden": [
            'href="/subscribe/">Subscribe to the newsletter</a>',
        ],
    },
    "workflow-pack": {
        "required": [
            "The Solo Operator AI Workflow Pack",
            "10 workflow checklists",
            "10 copy/paste prompts",
            "Tool decision matrix",
            "Bad-fit warning checklist",
            "Subscribe and get the pack",
            "Subscribe to the newsletter",
            SIGNUP,
            '"@type":"CreativeWork"',
            '"@type":"BreadcrumbList"',
        ],
        "forbidden": [
            'href="/workflow-pack/">Get the workflow pack</a>',
        ],
    },
    "newsletter-advertising": {
        "required": [
            "Advertise with ForgeCore",
            "Best-fit sponsors",
            "Sponsor placements",
            "Sample sponsor block",
            f"mailto:{SPONSOR_EMAIL}",
            "Subscribe to see the newsletter",
            '"@type":"Organization"',
            '"@type":"BreadcrumbList"',
        ],
        "forbidden": [],
    },
}

HOME_REQUIRED = [
    "ForgeCore",
    "hero-title",
    "value-grid",
    "Subscribe to the newsletter",
    'href="/subscribe/">Subscribe to the newsletter</a>',
    'href="/workflow-pack/">Get the workflow pack</a>',
    "/newsletter-advertising/",
    "/ai-tools/",
    f"mailto:{SPONSOR_EMAIL}",
]

DISCOVERY_URLS = [
    f"{SITE_BASE}/subscribe/",
    f"{SITE_BASE}/workflow-pack/",
    f"{SITE_BASE}/newsletter-advertising/",
    f"{SITE_BASE}/ai-tools/",
    f"{SITE_BASE}/ai-tools/ai-seo-aeo/",
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def add_error(errors: list[str], message: str) -> None:
    errors.append(message)


def add_warning(warnings: list[str], message: str) -> None:
    warnings.append(message)


def check_required_files(errors: list[str]) -> None:
    for label, path in CHECK_FILES.items():
        if not path.exists():
            add_error(errors, f"Missing required business file: {label} ({path.relative_to(ROOT)})")


def check_homepage(errors: list[str], warnings: list[str]) -> None:
    html = read_text(DIST / "index.html")
    if not html:
        add_error(errors, "Rendered homepage missing: site/dist/index.html")
        return
    for marker in HOME_REQUIRED:
        if marker not in html:
            add_error(errors, f"Homepage missing business marker: {marker}")
    if f'href="{SIGNUP}">Get the workflow pack</a>' in html:
        add_error(errors, "Homepage workflow-pack CTA points directly to Kit instead of /workflow-pack/")
    if f'href="{SIGNUP}">Subscribe to the newsletter</a>' in html:
        add_error(errors, "Homepage subscribe CTA points directly to Kit instead of /subscribe/")
    if html.count("Subscribe to the newsletter") < 1:
        add_warning(warnings, "Homepage has fewer than one explicit newsletter subscribe label")


def check_business_pages(errors: list[str]) -> None:
    for slug, rules in BUSINESS_PAGES.items():
        page = DIST / slug / "index.html"
        html = read_text(page)
        if not html:
            add_error(errors, f"Rendered business page missing: site/dist/{slug}/index.html")
            continue
        canonical = f'<link rel="canonical" href="{SITE_BASE}/{slug}/">'
        if canonical not in html:
            add_error(errors, f"Business page missing canonical: {slug}")
        for marker in rules["required"]:
            if marker not in html:
                add_error(errors, f"Business page {slug} missing marker: {marker}")
        for marker in rules["forbidden"]:
            if marker in html:
                add_error(errors, f"Business page {slug} contains forbidden marker: {marker}")


def check_discovery(errors: list[str]) -> None:
    sitemap = read_text(DIST / "sitemap.xml")
    llms = read_text(DIST / "llms.txt")
    robots = read_text(DIST / "robots.txt")
    if not sitemap:
        add_error(errors, "Missing sitemap.xml")
    if not llms:
        add_error(errors, "Missing llms.txt")
    if not robots:
        add_error(errors, "Missing robots.txt")
    for url in DISCOVERY_URLS:
        if sitemap and url not in sitemap:
            add_error(errors, f"Sitemap missing business/discovery URL: {url}")
        if llms and url not in llms:
            add_error(errors, f"llms.txt missing business/discovery URL: {url}")
    for bot in ("OAI-SearchBot", "ChatGPT-User", "PerplexityBot"):
        if robots and bot not in robots:
            add_error(errors, f"robots.txt missing AI crawler allowance marker: {bot}")


def check_workflows(errors: list[str]) -> None:
    prepare = read_text(CHECK_FILES["prepare_workflow"])
    send = read_text(CHECK_FILES["send_workflow"])
    deploy = read_text(CHECK_FILES["deploy_site_workflow"])
    gen_am = read_text(CHECK_FILES["prepare_am"])
    gen_pm = read_text(CHECK_FILES["prepare_pm"])
    send_am = read_text(CHECK_FILES["send_am"])
    send_pm = read_text(CHECK_FILES["send_pm"])

    if "python kit_publish.py" in prepare:
        add_error(errors, "Prepare workflow must not call kit_publish.py")
    if "python lock_email_issue.py" not in prepare:
        add_error(errors, "Prepare workflow does not lock email snapshot")
    if "python business_hardening.py" not in prepare:
        add_error(errors, "Prepare workflow does not apply business hardening")
    if "content/email/" not in prepare:
        add_error(errors, "Prepare workflow does not commit locked email snapshots")

    if "python kit_publish.py" not in send:
        add_error(errors, "Send workflow does not call kit_publish.py")
    if "Locked email snapshot not found" not in send:
        add_error(errors, "Send workflow does not verify locked email snapshot exists")
    if "python business_hardening.py" not in send:
        add_error(errors, "Send workflow does not apply business hardening")
    if "cancel-in-progress: false" not in send:
        add_error(errors, "Send workflow should not cancel in-progress slot sends")

    if "python verify_site_updates.py" not in deploy:
        add_error(errors, "Site deploy workflow must use verify_site_updates.py, not newsletter verifier")
    if "python kit_publish.py" in deploy or "python lock_email_issue.py" in deploy:
        add_error(errors, "Site deploy workflow must not touch Kit or email locking")

    expected_crons = {
        "prepare_am": "30 12 * * *",
        "prepare_pm": "30 18 * * *",
        "send_am": "7 15 * * *",
        "send_pm": "21 21 * * *",
    }
    workflow_texts = {
        "prepare_am": gen_am,
        "prepare_pm": gen_pm,
        "send_am": send_am,
        "send_pm": send_pm,
    }
    for label, cron in expected_crons.items():
        if cron not in workflow_texts[label]:
            add_error(errors, f"Workflow {label} missing expected cron: {cron}")


def check_kit_safety(errors: list[str]) -> None:
    text = read_text(CHECK_FILES["kit_publish"])
    required = [
        "record_blocks_slot_email",
        "sent_public_slots_for_date",
        "send_at",
        "scheduled_or_sent",
        "content/email",
        "Locked email snapshot missing",
        "Web output may be updated, but this slot will not email again",
    ]
    for marker in required:
        if marker not in text:
            add_error(errors, f"kit_publish.py missing email safety marker: {marker}")
    if "public=true" in text.lower() and "send_at" not in text:
        add_error(errors, "kit_publish.py appears to rely on public=true without send_at")


def check_rate_card(errors: list[str], warnings: list[str]) -> None:
    text = read_text(CHECK_FILES["rate_card"])
    if not text:
        add_error(errors, "Missing sponsorship rate card")
        return
    for marker in (
        "Newsletter sponsor block",
        "Tool of the Week placement",
        "Evergreen workflow page placement",
        "Poor-fit sponsors",
        "Approval rules",
        SPONSOR_EMAIL,
    ):
        if marker not in text:
            add_error(errors, f"Sponsorship rate card missing marker: {marker}")
    if "$50-$150" in text:
        add_warning(warnings, "Sponsorship rates are still early test prices; revisit after traffic/subscriber proof")


def check_affiliate_registry(errors: list[str], warnings: list[str]) -> None:
    path = CHECK_FILES["affiliate_registry"]
    if not path.exists():
        add_error(errors, "Affiliate registry missing")
        return
    try:
        registry: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        add_error(errors, f"Affiliate registry invalid JSON: {exc}")
        return
    tools = registry.get("approved_tools")
    if not isinstance(tools, list) or not tools:
        add_error(errors, "Affiliate registry has no approved_tools list")
        return
    for tool in tools:
        if not isinstance(tool, dict):
            add_error(errors, "Affiliate registry contains non-object tool entry")
            continue
        name = str(tool.get("name", "unknown"))
        for field in ("use_when", "do_not_use_when", "simpler_alternatives"):
            if not tool.get(field):
                add_error(errors, f"Affiliate tool {name} missing {field}")
        links = tool.get("approved_links", []) or []
        if not links:
            add_warning(warnings, f"Affiliate tool {name} has no approved_links yet")


def write_result(errors: list[str], warnings: list[str]) -> Path:
    STATE.mkdir(parents=True, exist_ok=True)
    result = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "passed": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }
    out = STATE / "business-audit.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return out


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    check_required_files(errors)
    check_homepage(errors, warnings)
    check_business_pages(errors)
    check_discovery(errors)
    check_workflows(errors)
    check_kit_safety(errors)
    check_rate_card(errors, warnings)
    check_affiliate_registry(errors, warnings)
    write_result(errors, warnings)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
