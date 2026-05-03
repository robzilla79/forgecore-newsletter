#!/usr/bin/env python3
"""Validate ForgeCore issue monetization against the approved registry.

This is a validation-only guard. It never mutates issue Markdown.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from utils import WORKSPACE, artifact_suffix_for_issue, dump_json, issue_path_for_today, load_text

REGISTRY_PATH = WORKSPACE / "monetization" / "affiliate-registry.json"
MIN_REGISTERED_TOOL_WARNING_WORDS = 8
AFFILIATE_TERMS = (
    "affiliate",
    "partner link",
    "partner links",
    "commission",
    "referral link",
    "sponsored link",
)
PLACEHOLDER_RE = re.compile(r"AFFILIATE_[A-Z0-9_]+")
RUN_TOKEN = os.getenv("RUN_TOKEN", "").strip()


def load_registry() -> dict[str, Any]:
    if not REGISTRY_PATH.exists():
        raise FileNotFoundError(REGISTRY_PATH.as_posix())
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("affiliate registry must be a JSON object")
    return data


def section_body(text: str, section: str) -> str:
    match = re.search(rf"^{re.escape(section)}\n(.+?)(?=^## |\Z)", text, flags=re.MULTILINE | re.DOTALL)
    return match.group(1).strip() if match else ""


def has_affiliate_language(text: str) -> bool:
    lower = text.lower()
    return any(term in lower for term in AFFILIATE_TERMS)


def has_clear_disclosure(text: str) -> bool:
    lower = text.lower()
    return (
        "disclosure" in lower
        and ("commission" in lower or "partner" in lower or "affiliate" in lower or "may earn" in lower)
    )


def approved_url_map(registry: dict[str, Any]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for tool in registry.get("approved_tools", []):
        if not isinstance(tool, dict):
            continue
        for link in tool.get("approved_links", []) or []:
            if not isinstance(link, dict):
                continue
            label = str(link.get("label", "")).strip()
            url = str(link.get("url", "")).strip()
            if label and url:
                mapping[label] = url
    return mapping


def approved_affiliate_links(tool: dict[str, Any]) -> list[str]:
    """Return active approved affiliate URLs/labels for one tool.

    Placeholder labels such as AFFILIATE_CASTMAGIC are intentionally excluded
    because they are not live affiliate links and are already blocked elsewhere.
    """
    links: list[str] = []
    for link in tool.get("approved_links", []) or []:
        if not isinstance(link, dict):
            continue
        if link.get("type") != "affiliate":
            continue
        for key in ("url", "label"):
            value = str(link.get(key, "")).strip()
            if value and not PLACEHOLDER_RE.fullmatch(value):
                links.append(value)
    return links


def active_affiliate_tools(text: str, registry: dict[str, Any]) -> list[dict[str, Any]]:
    """Tools that are actually monetized in this issue.

    A global disclosure alone should not make every mentioned registry tool count
    against max_affiliate_tools_per_issue. The cap applies only when the issue
    contains a live approved affiliate URL or label for that specific tool.
    """
    found: list[dict[str, Any]] = []
    for tool in registry.get("approved_tools", []) or []:
        if not isinstance(tool, dict):
            continue
        links = approved_affiliate_links(tool)
        if links and any(link in text for link in links):
            found.append(tool)
    return found


def mentioned_tools(text: str, registry: dict[str, Any]) -> list[dict[str, Any]]:
    lower = text.lower()
    found: list[dict[str, Any]] = []
    for tool in registry.get("approved_tools", []) or []:
        if not isinstance(tool, dict):
            continue
        name = str(tool.get("name", "")).strip()
        if name and name.lower() in lower:
            found.append(tool)
    return found


def validate_registry(registry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    tools = registry.get("approved_tools")
    if not isinstance(tools, list) or not tools:
        errors.append("affiliate registry has no approved_tools list")
        return errors
    for tool in tools:
        if not isinstance(tool, dict):
            errors.append("affiliate registry contains non-object tool entry")
            continue
        name = str(tool.get("name", "")).strip()
        if not name:
            errors.append("approved tool missing name")
        for key in ["use_when", "do_not_use_when", "simpler_alternatives"]:
            value = tool.get(key)
            if not isinstance(value, list) or not value:
                errors.append(f"{name or 'unknown tool'} missing non-empty {key}")
    return errors


def collect_issue_errors(text: str, registry: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    registry_errors = validate_registry(registry)
    errors.extend(registry_errors)

    placeholders = sorted(set(PLACEHOLDER_RE.findall(text)))
    if placeholders:
        errors.append("Issue contains placeholder affiliate URLs or labels: " + ", ".join(placeholders))

    if has_affiliate_language(text) and not has_clear_disclosure(text):
        errors.append("Issue uses affiliate/partner/commission language without a clear disclosure")

    tool_section = section_body(text, "## Tool of the Week")
    if not tool_section:
        warnings.append("Tool of the Week section not found for monetization review")

    found_tools = mentioned_tools(text, registry)
    monetized_tools = active_affiliate_tools(text, registry)
    if monetized_tools:
        if len(monetized_tools) > int(registry.get("rules", {}).get("max_affiliate_tools_per_issue", 2)):
            errors.append("Issue contains too many active affiliate tools")
        if "do not use" not in text.lower() and "not a fit" not in text.lower() and "avoid" not in text.lower():
            errors.append("Issue mentions monetized tools without a bad-fit warning")
        if "alternative" not in text.lower() and "simpler" not in text.lower() and "cheaper" not in text.lower():
            errors.append("Issue mentions monetized tools without a simpler or cheaper alternative")
    elif found_tools:
        warnings.append("Registry tool mentioned without active affiliate links; OK if no approved link is being used")

    approved = approved_url_map(registry)
    approved_values = set(approved.values()) | set(approved.keys())
    raw_urls = set(re.findall(r"https?://\S+", text))
    # This intentionally does not block normal source URLs. It only blocks unapproved affiliate-looking URLs.
    for url in raw_urls:
        lowered = url.lower()
        affiliate_like = any(token in lowered for token in ["partner", "affiliate", "ref=", "utm_source=forgecore", "deal", "promo"])
        if affiliate_like and url.rstrip(".,)") not in approved_values:
            errors.append(f"Unapproved affiliate-looking URL found: {url.rstrip('.,)')}")

    return errors, warnings


def main() -> int:
    registry = load_registry()
    issue_path = issue_path_for_today()
    text = load_text(issue_path)
    errors, warnings = collect_issue_errors(text, registry)
    result = {
        "passed": not errors,
        "issue": issue_path.as_posix(),
        "registry": REGISTRY_PATH.as_posix(),
        "errors": errors,
        "warnings": warnings,
        "run_token": RUN_TOKEN,
        "validation_only": True,
    }
    suffix = artifact_suffix_for_issue(issue_path)
    out_path = WORKSPACE / "state" / f"monetization-guard-{suffix}.json"
    result["artifact_path"] = out_path.as_posix()
    dump_json(out_path, result)
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
