#!/usr/bin/env python3
"""Quality gate: validate the current slot-specific Aware column before it ships.

This validator is intentionally read-only. It must never mutate issue Markdown.

Aware format: prose column, 400-750 words, no structural section headers,
exact Aware footer, at least one real source URL, real byline.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

from issue_contract import (
    AWARE_FOOTER,
    BANNED_TOKENS,
    FORBIDDEN_HEADERS,
    has_forbidden_headers,
)
from utils import WORKSPACE, artifact_suffix_for_issue, dump_json, issue_path_for_today, load_text

# Aware is a column, not a report. One strong source plus Em's perspective is valid.
MIN_SOURCE_LINKS = int(os.getenv("MIN_SOURCE_LINKS", "1"))

# Word range for a published Aware column.
MIN_WORDS = int(os.getenv("MIN_WORDS", "400"))
MAX_WORDS = int(os.getenv("MAX_WORDS", "750"))

MIN_CRITIC_OVERALL = float(os.getenv("MIN_CRITIC_OVERALL", "6.5"))
REQUIRE_CRITIC_REVIEW = os.getenv("REQUIRE_CRITIC_REVIEW", "0") == "1"
ALLOW_FALLBACK_PUBLISH = os.getenv("ALLOW_FALLBACK_PUBLISH", "0") == "1"
RUN_TOKEN = os.getenv("RUN_TOKEN", "").strip()

AFFILIATE_TERMS = (
    "affiliate",
    "partner link",
    "partner links",
    "commission",
    "referral link",
    "sponsored link",
)

LEAKED_PHRASE_PATTERNS = [
    r"\baudience\s+focus\b",
    r"\bstrategic\s+lens\b",
    r"\bwhy\s+this\s+tool\s+fits\b",
    r"\bencourage\s+readers\s+to\b",
    r"\bprovide\s+a\s+clear\s+call\s+to\s+action\b",
    r"\bthis\s+issue\s+is\s+for\b",
    r"\buse\s+this\s+starting\s+workflow\b",
    r"\bsubscribe\s+to\s+receive\s+more\b",
    r'^\s*\{',
    r'^\s*"summary":',
    r'^\s*"files":',
    r'^\s*"memory_update":',
    r"^#\s+Title:",
    r"^\*\*Date:\*\*",
    r"^\*\*Edition:\*\*",
]

MISSING_CONTENT_PATTERNS = [
    r"\bmissing content\b",
    r"\bno concrete content returned\b",
    r"\bdescription incomplete in provided content\b",
]


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def body_word_count(text: str) -> int:
    """Word count excluding the title line and the Aware footer."""
    body = re.sub(r"^#.*$", "", text, flags=re.MULTILINE)
    body = re.sub(re.escape(AWARE_FOOTER), "", body, flags=re.IGNORECASE)
    return len(re.findall(r"\b\w+\b", body))


def find_matching_patterns(text: str, patterns: list[str] | tuple[str, ...]) -> list[str]:
    return [p for p in patterns if re.search(p, text, flags=re.IGNORECASE | re.MULTILINE)]


def find_duplicate_paragraphs(text: str) -> list[str]:
    paras = re.split(r"\n{2,}", text.strip())
    seen: dict[str, int] = {}
    for para in paras:
        key = " ".join(para.lower().split())
        if len(key) < 40:
            continue
        seen[key] = seen.get(key, 0) + 1
    return [key[:80] + "..." for key, count in seen.items() if count > 1]


def has_affiliate_reference(text: str) -> bool:
    lower = text.lower()
    return any(term in lower for term in AFFILIATE_TERMS)


def has_affiliate_disclosure(text: str) -> bool:
    lower = text.lower()
    return (
        "disclosure" in lower
        and ("commission" in lower or "may earn" in lower or "we earn" in lower or "partner" in lower or "affiliate" in lower)
    ) or (
        "may earn" in lower
        and ("commission" in lower or "partner" in lower or "affiliate" in lower)
    )


def critic_artifact_path(issue_path: Path) -> Path:
    suffix = artifact_suffix_for_issue(issue_path)
    return WORKSPACE / "state" / f"critic-review-{suffix}.json"


def load_issue_critic(issue_path: Path, *, run_token: str = "") -> tuple[dict | None, str]:
    candidate = critic_artifact_path(issue_path)
    if not candidate.exists():
        return None, candidate.as_posix()
    try:
        data = json.loads(candidate.read_text(encoding="utf-8"))
    except Exception:
        return None, candidate.as_posix()
    if run_token and data.get("run_token", "") != run_token:
        return None, candidate.as_posix()
    return data, candidate.as_posix()


def collect_errors_and_warnings(
    text: str, critic: dict | None, critic_expected_path: str | None
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if not text.strip():
        errors.append("Issue file is empty")
        return errors, warnings

    # ── Title ────────────────────────────────────────────────────────────────
    title_match = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
    if not title_match:
        errors.append("Issue title is missing")
    else:
        title = title_match.group(1).strip()
        if title.lower().startswith("title:"):
            errors.append("Issue title still contains 'Title:' prefix")
        if title.lower().startswith("aware —") and re.search(r"\d{4}-\d{2}-\d{2}", title):
            warnings.append("Title looks like a fallback date slug — Em should give it a real headline")

    # ── Byline ───────────────────────────────────────────────────────────────
    if not re.search(r"\*by\s+Em\s+[\u2014-]\s+.+\*", text):
        errors.append("Issue missing required byline '*by Em — Month Day, Year*'")

    # ── Forbidden structural headers ─────────────────────────────────────────
    if has_forbidden_headers(text):
        forbidden_found = [
            line.strip() for line in text.splitlines()
            if line.strip().lower().rstrip(":") in FORBIDDEN_HEADERS
        ]
        errors.append(
            f"Forbidden structural headers for Aware format: {', '.join(forbidden_found[:4])}. "
            "Remove ## CTA, ## Sources, and all old newsletter section headers."
        )

    # ── Exact Aware footer ───────────────────────────────────────────────────
    if AWARE_FOOTER not in text:
        errors.append(
            "Issue missing exact Aware footer. "
            "Must end with: *Aware by Em · [news.forgecore.co](...) · [empersists.bsky.social](...)*"
        )

    # ── ForgeCore-era branding ───────────────────────────────────────────────
    lower = text.lower()
    if "forgecore ai" in lower or "forgecore newsletter" in lower:
        errors.append("Issue still contains ForgeCore-era footer or branding")

    # ── Word count (body only) ───────────────────────────────────────────────
    bwc = body_word_count(text)
    if bwc < MIN_WORDS:
        errors.append(f"Column too short: {bwc} body words (minimum {MIN_WORDS})")
    elif bwc > MAX_WORDS:
        warnings.append(f"Column is long for Aware: {bwc} body words (soft ceiling {MAX_WORDS})")

    # ── Source URLs ──────────────────────────────────────────────────────────
    urls = [u.rstrip(").,") for u in re.findall(r"https?://\S+", text)]
    unique_urls = list(dict.fromkeys(urls))
    if len(unique_urls) < MIN_SOURCE_LINKS:
        errors.append(
            f"Not enough real URLs: found {len(unique_urls)}, need at least {MIN_SOURCE_LINKS}"
        )
    if any(
        (host == "example.com" or host.endswith(".example.com"))
        for host in (
            (urlparse(url).hostname or "").lower().rstrip(".")
            for url in unique_urls
        )
    ):
        errors.append("example.com URL found in issue content")

    # ── Banned tokens ────────────────────────────────────────────────────────
    for token in BANNED_TOKENS:
        if token.lower() in lower:
            errors.append(f'Banned token found: "{token}"')

    # ── Leaked meta-phrases ──────────────────────────────────────────────────
    for pattern in find_matching_patterns(text, LEAKED_PHRASE_PATTERNS):
        errors.append(f"Leaked meta-phrase pattern found: {pattern}")

    # ── Placeholder language ─────────────────────────────────────────────────
    for pattern in find_matching_patterns(text, MISSING_CONTENT_PATTERNS):
        errors.append(f"Placeholder language found: {pattern}")

    # ── Duplicate paragraphs ─────────────────────────────────────────────────
    for para in find_duplicate_paragraphs(text):
        errors.append(f'Duplicate paragraph detected: "{para}"')

    # ── Affiliate disclosure ─────────────────────────────────────────────────
    if has_affiliate_reference(text) and not has_affiliate_disclosure(text):
        errors.append("Affiliate/partner reference found without clear commission disclosure")

    # ── Critic review ────────────────────────────────────────────────────────
    def critic_problem(message: str, *, hard: bool = False) -> None:
        if hard or not ALLOW_FALLBACK_PUBLISH:
            errors.append(message)
        else:
            warnings.append(message)

    if REQUIRE_CRITIC_REVIEW and critic is None:
        critic_problem(
            f"Critic review missing for current issue: expected {critic_expected_path}"
        )

    if critic:
        runtime_error = str(critic.get("runtime_error", "")).strip()
        weak_categories = critic.get("weak_categories", [])
        if not isinstance(weak_categories, list):
            weak_categories = []
        runtime_failed = bool(runtime_error) or "critic_runtime_failure" in weak_categories
        if runtime_failed:
            critic_problem(
                "Critic runtime failure; publish blocked until critic_review.py runs cleanly.",
                hard=True,
            )
            if runtime_error:
                errors.append(f"Critic runtime failure detail: {runtime_error}")
        overall = float(critic.get("overall_score", 0.0) or 0.0)
        if overall < MIN_CRITIC_OVERALL:
            critic_problem(f"Critic overall score too low: {overall:.2f} < {MIN_CRITIC_OVERALL:.2f}")
        if weak_categories:
            critic_problem("Critic flagged weak categories: " + ", ".join(weak_categories))
        verdict = str(critic.get("verdict", "")).strip().lower()
        if verdict == "reject":
            critic_problem("Critic verdict is reject")

    return errors, warnings


def main() -> int:
    path = issue_path_for_today()
    text = load_text(path)
    urls = [u.rstrip(").,") for u in re.findall(r"https?://\S+", text)]
    critic, critic_path = load_issue_critic(path, run_token=RUN_TOKEN)
    errors, warnings = collect_errors_and_warnings(text, critic, critic_path)

    checks = {
        "exists": path.exists(),
        "issue_path": path.as_posix(),
        "body_word_count": body_word_count(text),
        "total_word_count": word_count(text),
        "has_title": bool(re.search(r"^#\s+\S", text, flags=re.MULTILINE)),
        "has_byline": bool(re.search(r"\*by\s+Em\s+[\u2014-]\s+.+\*", text)),
        "has_aware_footer": AWARE_FOOTER in text,
        "has_forbidden_headers": has_forbidden_headers(text),
        "url_count": len(list(dict.fromkeys(urls))),
        "source_links": list(dict.fromkeys(urls)),
        "has_affiliate_reference": has_affiliate_reference(text),
        "has_affiliate_disclosure": has_affiliate_disclosure(text),
        "critic_expected_path": critic_path,
        "critic_review": critic or {},
        "errors": errors,
        "warnings": warnings,
        "fallback_publish_enabled": ALLOW_FALLBACK_PUBLISH,
        "validation_only": True,
    }

    result = {
        "passed": not errors,
        "fallback_published": bool(warnings and not errors),
        "checks": checks,
        "issue": path.as_posix(),
        "run_token": RUN_TOKEN,
    }
    suffix = artifact_suffix_for_issue(path)
    out_path = WORKSPACE / "state" / f"quality-gate-{suffix}.json"
    result["artifact_path"] = out_path.as_posix()
    dump_json(out_path, result)
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
