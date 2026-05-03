#!/usr/bin/env python3
"""Lean ForgeCore business audit.

Purpose: catch only business-critical failures that affect newsletter quality,
subscriber growth, sponsor/affiliate revenue, site discovery, or email safety.
This is intentionally not a dashboard or management system.
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
PACK_URL = f"{SITE_BASE}/downloads/solo-operator-ai-workflow-pack/"

REQUIRED_FILES = (
    ROOT / "business_hardening.py",
    ROOT / "lead_magnet_hardening.py",
    ROOT / "verify_site_updates.py",
    ROOT / "lead-magnets/solo-operator-ai-workflow-pack.md",
    ROOT / "lock_email_issue.py",
    ROOT / "kit_publish.py",
    ROOT / ".github/workflows/deploy-site.yml",
    ROOT / ".github/workflows/generate.yml",
    ROOT / ".github/workflows/send.yml",
    ROOT / "business/sponsorship-rate-card.md",
    ROOT / "monetization/affiliate-registry.json",
)

FUNNEL_PAGES = {
    "subscribe": ("Subscribe to ForgeCore", "Subscribe free", SIGNUP),
    "workflow-pack": ("The Solo Operator AI Workflow Pack", "Subscribe and get the pack", "Read the workflow pack now"),
    "newsletter-advertising": ("Advertise with ForgeCore", "Sponsor placements", f"mailto:{SPONSOR_EMAIL}"),
    "archive": ("ForgeCore AI Workflow Archive", "Workflow categories", "Latest issues"),
    "downloads/solo-operator-ai-workflow-pack": ("The Solo Operator AI Workflow Pack", "Tool decision matrix", "Automation readiness checklist"),
}

DISCOVERY_URLS = (
    f"{SITE_BASE}/subscribe/",
    f"{SITE_BASE}/workflow-pack/",
    f"{SITE_BASE}/newsletter-advertising/",
    f"{SITE_BASE}/archive/",
    PACK_URL,
    f"{SITE_BASE}/ai-tools/",
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def error(errors: list[str], message: str) -> None:
    errors.append(message)


def warning(warnings: list[str], message: str) -> None:
    warnings.append(message)


def check_required_files(errors: list[str]) -> None:
    for path in REQUIRED_FILES:
        if not path.exists():
            error(errors, f"Missing required business file: {path.relative_to(ROOT)}")


def check_funnels(errors: list[str]) -> None:
    homepage = read(DIST / "index.html")
    if not homepage:
        error(errors, "Homepage missing from site/dist")
        return

    required_home_links = (
        'href="/subscribe/">Subscribe to the newsletter</a>',
        'href="/workflow-pack/">Get the workflow pack</a>',
        'href="/archive/">Read the archive</a>',
        '/newsletter-advertising/',
        '/ai-tools/',
        'forgecore-proof-positioning',
        'Not generic AI news',
        'Every issue has a job',
        'forgecore-workflow-cards',
        'AI tools by workflow',
    )
    for marker in required_home_links:
        if marker not in homepage:
            error(errors, f"Homepage missing growth/revenue asset: {marker}")

    if f'href="{SIGNUP}">Subscribe to the newsletter</a>' in homepage:
        error(errors, "Homepage subscribe CTA points directly to Kit instead of /subscribe/")
    if f'href="{SIGNUP}">Get the workflow pack</a>' in homepage:
        error(errors, "Homepage workflow-pack CTA points directly to Kit instead of /workflow-pack/")

    for slug, markers in FUNNEL_PAGES.items():
        html = read(DIST / slug / "index.html")
        if not html:
            error(errors, f"Funnel/discovery page missing: /{slug}/")
            continue
        canonical = f'<link rel="canonical" href="{SITE_BASE}/{slug}/">'
        if canonical not in html:
            error(errors, f"Funnel/discovery page missing canonical: /{slug}/")
        for marker in markers:
            if marker not in html:
                error(errors, f"Funnel/discovery page /{slug}/ missing marker: {marker}")


def check_discovery(errors: list[str]) -> None:
    sitemap = read(DIST / "sitemap.xml")
    llms = read(DIST / "llms.txt")
    robots = read(DIST / "robots.txt")
    if not sitemap:
        error(errors, "sitemap.xml missing")
    if not llms:
        error(errors, "llms.txt missing")
    if not robots:
        error(errors, "robots.txt missing")
    for url in DISCOVERY_URLS:
        if sitemap and url not in sitemap:
            error(errors, f"Sitemap missing key business URL: {url}")
        if llms and url not in llms:
            error(errors, f"llms.txt missing key business URL: {url}")
    for bot in ("OAI-SearchBot", "ChatGPT-User", "PerplexityBot"):
        if robots and bot not in robots:
            error(errors, f"robots.txt missing AI crawler marker: {bot}")


def check_email_safety(errors: list[str]) -> None:
    prepare = read(ROOT / ".github/workflows/generate.yml")
    send = read(ROOT / ".github/workflows/send.yml")
    kit = read(ROOT / "kit_publish.py")

    if "python kit_publish.py" in prepare:
        error(errors, "Prepare workflow must not send email")
    if "python lock_email_issue.py" not in prepare or "content/email/" not in prepare:
        error(errors, "Prepare workflow must lock and commit email snapshots")
    if "python kit_publish.py" not in send:
        error(errors, "Send workflow must call Kit sender")
    if "Locked email snapshot not found" not in send:
        error(errors, "Send workflow must refuse missing locked email snapshots")
    if "send_at" not in kit or "scheduled_or_sent" not in kit:
        error(errors, "Kit sender must use send_at and record scheduled_or_sent")
    if "record_blocks_slot_email" not in kit or "sent_public_slots_for_date" not in kit:
        error(errors, "Kit sender missing one-AM/one-PM idempotency guard")
    if "content/email" not in kit:
        error(errors, "Kit sender must send from locked content/email snapshots")


def check_site_deploy_path(errors: list[str]) -> None:
    deploy = read(ROOT / ".github/workflows/deploy-site.yml")
    if "python verify_site_updates.py" not in deploy:
        error(errors, "Site deploy must use site-only verifier")
    if "python lead_magnet_hardening.py" not in deploy:
        error(errors, "Site deploy must render lead magnet assets")
    if "python kit_publish.py" in deploy or "python lock_email_issue.py" in deploy:
        error(errors, "Site deploy must not touch Kit or locked emails")
    if "pages deploy site/dist" not in deploy:
        error(errors, "Site deploy workflow must deploy site/dist to Cloudflare")


def check_sponsor_and_affiliate_safety(errors: list[str], warnings: list[str]) -> None:
    rate_card = read(ROOT / "business/sponsorship-rate-card.md")
    for marker in ("Newsletter sponsor block", "Tool of the Week placement", "Approval rules", SPONSOR_EMAIL):
        if marker not in rate_card:
            error(errors, f"Sponsor rate card missing marker: {marker}")
    if "$50-$150" in rate_card:
        warning(warnings, "Sponsor rates are still early test prices; revisit after subscriber/traffic proof")

    registry_path = ROOT / "monetization/affiliate-registry.json"
    try:
        registry: dict[str, Any] = json.loads(registry_path.read_text(encoding="utf-8"))
    except Exception as exc:
        error(errors, f"Affiliate registry invalid or missing: {exc}")
        return
    tools = registry.get("approved_tools")
    if not isinstance(tools, list) or not tools:
        error(errors, "Affiliate registry has no approved_tools")
        return
    for tool in tools:
        if not isinstance(tool, dict):
            error(errors, "Affiliate registry contains non-object tool entry")
            continue
        name = str(tool.get("name", "unknown"))
        for field in ("use_when", "do_not_use_when", "simpler_alternatives"):
            if not tool.get(field):
                error(errors, f"Affiliate tool {name} missing {field}")


def write_result(errors: list[str], warnings: list[str]) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    result = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "passed": not errors,
        "purpose": "lean business audit: newsletter quality, growth, revenue, and email safety",
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }
    out = STATE / "business-audit.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    check_required_files(errors)
    check_funnels(errors)
    check_discovery(errors)
    check_email_safety(errors)
    check_site_deploy_path(errors)
    check_sponsor_and_affiliate_safety(errors, warnings)
    write_result(errors, warnings)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
