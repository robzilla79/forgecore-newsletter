#!/usr/bin/env python3
"""Activate approved affiliate links when a matching tool is already mentioned.

This mutates the current slot issue, but only in a narrow, trust-preserving way:
- never inserts a tool mention that was not already present
- never uses placeholder links
- links at most one approved affiliate tool per issue by default
- adds disclosure language when it activates a partner link
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from utils import WORKSPACE, artifact_suffix_for_issue, dump_json, issue_path_for_today, load_text, write_text

REGISTRY_PATH = WORKSPACE / "monetization" / "affiliate-registry.json"
MAX_LINKS_PER_ISSUE = int(os.getenv("MAX_AFFILIATE_LINKS_PER_ISSUE", "1"))
RUN_TOKEN = os.getenv("RUN_TOKEN", "").strip()


@dataclass(frozen=True)
class ApprovedAffiliate:
    name: str
    url: str
    disclosure: str


def load_registry() -> dict[str, Any]:
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("affiliate registry must be a JSON object")
    return data


def approved_affiliates(registry: dict[str, Any]) -> list[ApprovedAffiliate]:
    out: list[ApprovedAffiliate] = []
    for tool in registry.get("approved_tools", []) or []:
        if not isinstance(tool, dict):
            continue
        if str(tool.get("status", "")).strip() != "approved_affiliate":
            continue
        name = str(tool.get("name", "")).strip()
        disclosure = str(tool.get("example_disclosure") or registry.get("default_disclosure") or "").strip()
        for link in tool.get("approved_links", []) or []:
            if not isinstance(link, dict):
                continue
            url = str(link.get("url", "")).strip()
            link_type = str(link.get("type", "")).strip()
            if name and url.startswith("https://") and link_type == "affiliate":
                out.append(ApprovedAffiliate(name=name, url=url, disclosure=disclosure))
                break
    return out


def split_markdown_link_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for match in re.finditer(r"\[[^\]]+\]\([^\)]+\)", text):
        spans.append((match.start(), match.end()))
    return spans


def inside_spans(index: int, spans: list[tuple[int, int]]) -> bool:
    return any(start <= index < end for start, end in spans)


def already_linked(text: str, affiliate: ApprovedAffiliate) -> bool:
    return affiliate.url in text or re.search(rf"\[{re.escape(affiliate.name)}\]\([^)]+\)", text, flags=re.IGNORECASE) is not None


def link_first_plain_mention(text: str, affiliate: ApprovedAffiliate) -> tuple[str, bool]:
    if already_linked(text, affiliate):
        return text, False
    spans = split_markdown_link_spans(text)
    pattern = re.compile(rf"\b{re.escape(affiliate.name)}\b", flags=re.IGNORECASE)
    for match in pattern.finditer(text):
        if inside_spans(match.start(), spans):
            continue
        linked = f"[{match.group(0)}]({affiliate.url})"
        return text[: match.start()] + linked + text[match.end() :], True
    return text, False


def has_affiliate_disclosure(text: str) -> bool:
    lower = text.lower()
    return "disclosure" in lower and ("commission" in lower or "partner link" in lower or "affiliate" in lower or "may earn" in lower)


def append_disclosure_to_tool_section(text: str, disclosure: str) -> str:
    if has_affiliate_disclosure(text):
        return text
    if not disclosure:
        disclosure = "Disclosure: ForgeCore may earn a commission if you buy through partner links, but recommendations are based on workflow fit, not payout."
    pattern = r"(^## Tool of the Week\s*\n)(.+?)(?=^## |\Z)"
    match = re.search(pattern, text, flags=re.MULTILINE | re.DOTALL)
    if not match:
        return text.rstrip() + "\n\n" + disclosure + "\n"
    body = match.group(2).rstrip()
    replacement = match.group(1) + body + "\n\n" + disclosure + "\n\n"
    return text[: match.start()] + replacement + text[match.end() :]


def activate_links(markdown: str, affiliates: list[ApprovedAffiliate]) -> tuple[str, list[dict[str, str]]]:
    current = markdown
    activated: list[dict[str, str]] = []
    for affiliate in affiliates:
        if len(activated) >= MAX_LINKS_PER_ISSUE:
            break
        updated, changed = link_first_plain_mention(current, affiliate)
        if changed:
            current = append_disclosure_to_tool_section(updated, affiliate.disclosure)
            activated.append({"tool": affiliate.name, "url": affiliate.url})
    return current, activated


def main() -> int:
    registry = load_registry()
    issue_path = issue_path_for_today()
    original = load_text(issue_path)
    updated, activated = activate_links(original, approved_affiliates(registry))
    changed = updated != original
    if changed:
        write_text(issue_path, updated)
    result = {
        "changed": changed,
        "issue": issue_path.as_posix(),
        "activated_links": activated,
        "max_links_per_issue": MAX_LINKS_PER_ISSUE,
        "run_token": RUN_TOKEN,
    }
    suffix = artifact_suffix_for_issue(issue_path)
    out_path = WORKSPACE / "state" / f"affiliate-linker-{suffix}.json"
    result["artifact_path"] = out_path.as_posix()
    dump_json(out_path, result)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
