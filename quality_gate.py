#!/usr/bin/env python3
"""Quality gate: validate the current slot-specific issue before it ships.

This validator is intentionally read-only. It must never mutate issue Markdown.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from issue_contract import BANNED_TOKENS, REQUIRED_SECTIONS
from utils import WORKSPACE, artifact_suffix_for_issue, dump_json, issue_path_for_today, load_text

MIN_WORDS = 500
MIN_SOURCE_LINKS = 3
REQUIRED_CTA_URL = (
    os.getenv("PRIMARY_CTA_URL", "").strip()
    or os.getenv("KIT_SIGNUP_URL", "").strip()
    or "https://news.forgecore.co/"
)
REQUIRED_SPONSOR_EMAIL = "sponsors@forgecore.co"
MIN_CRITIC_OVERALL = float(os.getenv("MIN_CRITIC_OVERALL", "6.5"))
REQUIRE_CRITIC_REVIEW = os.getenv("REQUIRE_CRITIC_REVIEW", "1") == "1"
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
TRUST_WARNING_PATTERNS = (
    r"\bdo not use\b",
    r"\bdon't use\b",
    r"\bavoid this\b",
    r"\bnot a fit\b",
    r"\bwho should avoid\b",
    r"\buse .* instead if\b",
)
TOOL_RECOMMENDATION_PATTERNS = (
    r"\btool of the week\b",
    r"\brecommend\b",
    r"\buse [A-Z][A-Za-z0-9 ._-]{2,}\b",
    r"\btry [A-Z][A-Za-z0-9 ._-]{2,}\b",
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


def proper_section_header_count(text: str, section: str) -> int:
    return len(re.findall(rf"^{re.escape(section)}\s*$", text, flags=re.MULTILINE))


def malformed_section_header_count(text: str, section: str) -> int:
    # Catches glued output such as ```## CTA or ...alternative.## Workflow.
    total_mentions = text.count(section)
    return max(0, total_mentions - proper_section_header_count(text, section))


def section_body(text: str, section: str) -> str:
    match = re.search(rf"^{re.escape(section)}\s*\n(.+?)(?=^## |\Z)", text, flags=re.MULTILINE | re.DOTALL)
    return match.group(1).strip() if match else ""


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


def has_trust_warning(text: str) -> bool:
    return bool(find_matching_patterns(text, TRUST_WARNING_PATTERNS))


def has_tool_recommendation(text: str) -> bool:
    tool_section = section_body(text, "## Tool of the Week")
    return bool(tool_section and find_matching_patterns(tool_section, TOOL_RECOMMENDATION_PATTERNS))


def source_section_present(text: str) -> bool:
    return proper_section_header_count(text, "## Sources") > 0


def source_section_entries(text: str) -> list[str]:
    match = re.search(r"^## Sources\s*\n(.+?)(?=^## |\Z)", text, flags=re.MULTILINE | re.DOTALL)
    if not match:
        return []
    return [line for line in match.group(1).splitlines() if line.strip()]


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


def collect_errors_and_warnings(text: str, critic: dict | None, critic_expected_path: str | None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if not text.strip():
        errors.append("Issue file is empty")
        return errors, warnings

    for header in REQUIRED_SECTIONS:
        proper_count = proper_section_header_count(text, header)
        malformed_count = malformed_section_header_count(text, header)
        if proper_count == 0:
            if header == "## Sources":
                continue
            errors.append(f"Missing required section: {header}")
        elif proper_count > 1:
            errors.append(f"Duplicate required section header: {header} appears {proper_count} times")
        if malformed_count:
            errors.append(f"Malformed or glued section header: {header} appears {malformed_count} time(s) outside its own line")

    for token in BANNED_TOKENS:
        if token.lower() in text.lower():
            errors.append(f'Banned token found: "{token}"')

    for pattern in find_matching_patterns(text, LEAKED_PHRASE_PATTERNS):
        errors.append(f"Leaked meta-phrase pattern found: {pattern}")

    for pattern in find_matching_patterns(text, MISSING_CONTENT_PATTERNS):
        errors.append(f"Placeholder language found (normalized-placeholder risk): {pattern}")

    for para in find_duplicate_paragraphs(text):
        errors.append(f'Duplicate paragraph detected: "{para}"')

    urls = [u.rstrip(").,") for u in re.findall(r"https?://\S+", text)]
    unique_urls = list(dict.fromkeys(urls))
    if len(unique_urls) < MIN_SOURCE_LINKS:
        errors.append(f"Not enough real URLs: found {len(unique_urls)}, need at least {MIN_SOURCE_LINKS}")
    if any("example.com" in url.lower() for url in unique_urls):
        errors.append("example.com URL found in issue content")

    if "```" not in text:
        errors.append("Workflow code block is missing")

    wc = word_count(text)
    if wc < MIN_WORDS:
        errors.append(f"Issue too short: {wc} words (need {MIN_WORDS})")

    title_match = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
    if not title_match:
        errors.append("Issue title is missing")
    else:
        title = title_match.group(1).strip()
        if title.lower().startswith("title:"):
            errors.append("Issue title still contains 'Title:' prefix")
        if title.lower().startswith("author update"):
            errors.append("Issue title still contains generic author-update placeholder")

    hook_match = re.search(r"^## Hook\s*\n(.+?)(?=^## |\Z)", text, flags=re.MULTILINE | re.DOTALL)
    if not hook_match or len(hook_match.group(1).split()) < 12:
        errors.append("Hook section is missing or too short (need 12+ words)")

    top_story_match = re.search(r"^## Top Story\s*\n(.+?)(?=^## |\Z)", text, flags=re.MULTILINE | re.DOTALL)
    if not top_story_match or len(top_story_match.group(1).split()) < 80:
        errors.append("Top Story section is too thin (need 80+ words)")

    tool_text = section_body(text, "## Tool of the Week")
    if not tool_text or len(tool_text.split()) < 35:
        errors.append("Tool of the Week section is missing or too thin (need 35+ words)")
    if not has_tool_recommendation(text):
        errors.append("Tool of the Week must include a concrete tool recommendation")
    if not has_trust_warning(text):
        errors.append("Issue missing a trust warning such as 'do not use this if' or 'not a fit if'")
    if has_affiliate_reference(text) and not has_affiliate_disclosure(text):
        errors.append("Affiliate/partner reference found without clear commission disclosure")

    cta_match = re.search(r"^## CTA\s*\n(.+?)(?=^## |\Z)", text, flags=re.MULTILINE | re.DOTALL)
    if not cta_match or len(cta_match.group(1).split()) < 8:
        errors.append("CTA section is missing or too short (need 8+ words)")
    else:
        cta_text = cta_match.group(1)
        if REQUIRED_CTA_URL and REQUIRED_CTA_URL not in cta_text:
            errors.append("CTA section missing required Kit subscribe URL from PRIMARY_CTA_URL")
        if REQUIRED_SPONSOR_EMAIL not in cta_text:
            errors.append("CTA section missing required sponsor email")
        if "sponsor this issue" not in cta_text.lower():
            errors.append("CTA section missing 'Sponsor this issue' invite")

    source_lines = source_section_entries(text)
    if not source_section_present(text):
        if len(unique_urls) >= MIN_SOURCE_LINKS:
            warnings.append("Sources section header missing, but enough real source URLs are present elsewhere in the issue")
        else:
            errors.append("Sources section is missing")
    elif len(source_lines) < MIN_SOURCE_LINKS:
        if len(unique_urls) >= MIN_SOURCE_LINKS:
            warnings.append("Sources section is thin, but enough real source URLs are present elsewhere in the issue")
        else:
            errors.append(f"Sources section is too short: {len(source_lines)} entries")

    def critic_problem(message: str, *, hard: bool = False) -> None:
        if hard or not ALLOW_FALLBACK_PUBLISH:
            errors.append(message)
        else:
            warnings.append(message)

    if REQUIRE_CRITIC_REVIEW and critic is None:
        critic_problem(f"Critic review missing for current issue: expected {critic_expected_path}")

    if critic:
        runtime_error = str(critic.get("runtime_error", "")).strip()
        weak_categories = critic.get("weak_categories", [])
        if not isinstance(weak_categories, list):
            weak_categories = []
        runtime_failed = bool(runtime_error) or "critic_runtime_failure" in weak_categories
        if runtime_failed:
            critic_problem("Critic runtime failure; publish blocked until critic_review.py runs cleanly.", hard=True)
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
        "word_count": word_count(text),
        "required_sections_present": [h for h in REQUIRED_SECTIONS if proper_section_header_count(text, h) > 0],
        "url_count": len(list(dict.fromkeys(urls))),
        "source_links": list(dict.fromkeys(urls)),
        "has_sources_section": source_section_present(text),
        "sources_section_entries": len(source_section_entries(text)),
        "has_code_block": "```" in text,
        "has_tool_recommendation": has_tool_recommendation(text),
        "has_trust_warning": has_trust_warning(text),
        "has_affiliate_reference": has_affiliate_reference(text),
        "has_affiliate_disclosure": has_affiliate_disclosure(text),
        "required_cta_url": REQUIRED_CTA_URL,
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
