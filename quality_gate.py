#!/usr/bin/env python3
"""Quality gate: validate a normalized issue before it ships."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from issue_contract import BANNED_TOKENS, REQUIRED_SECTIONS, ensure_issue_contract, latest_issue_path
from utils import WORKSPACE, dump_json, load_text

MIN_WORDS = 500
MIN_SOURCE_LINKS = 3
REQUIRED_CTA_URL = "https://forgecore-newsletter.beehiiv.com/"
REQUIRED_SPONSOR_EMAIL = "sponsors@forgecore.co"
MIN_CRITIC_OVERALL = float(os.getenv("MIN_CRITIC_OVERALL", "8.0"))
REQUIRE_CRITIC_REVIEW = os.getenv("REQUIRE_CRITIC_REVIEW", "1") == "1"
RUN_TOKEN = os.getenv("RUN_TOKEN", "").strip()

LEAKED_PHRASE_PATTERNS: list[str] = [
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

MISSING_CONTENT_PATTERNS: list[str] = [
    r"\bmissing content\b",
    r"\bno concrete content returned\b",
    r"\bdescription incomplete in provided content\b",
]


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def find_matching_patterns(text: str, patterns: list[str]) -> list[str]:
    found: list[str] = []
    for pattern in patterns:
        if re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE):
            found.append(pattern)
    return found


def find_duplicate_paragraphs(text: str) -> list[str]:
    paras = re.split(r"\n{2,}", text.strip())
    seen: dict[str, int] = {}
    for para in paras:
        key = " ".join(para.lower().split())
        if len(key) < 40:
            continue
        seen[key] = seen.get(key, 0) + 1
    return [key[:80] + "..." for key, count in seen.items() if count > 1]


def load_issue_critic(issue_path: Path) -> tuple[dict | None, str | None]:
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", issue_path.stem)
    suffix = date_match.group(1) if date_match else "latest"
    candidate = WORKSPACE / "state" / f"critic-review-{suffix}.json"
    if not candidate.exists():
        return None, candidate.as_posix()
    try:
        return json.loads(candidate.read_text(encoding="utf-8")), candidate.as_posix()
    except Exception:
        return None, candidate.as_posix()


def collect_errors(text: str, critic: dict | None = None, critic_expected_path: str | None = None) -> list[str]:
    errors: list[str] = []

    for header in REQUIRED_SECTIONS:
        if header not in text:
            errors.append(f"Missing required section: {header}")

    for token in BANNED_TOKENS:
        if token.lower() in text.lower():
            errors.append(f'Banned token found: "{token}"')

    for pattern in find_matching_patterns(text, LEAKED_PHRASE_PATTERNS):
        errors.append(f"Leaked meta-phrase pattern found: {pattern}")

    for pattern in find_matching_patterns(text, MISSING_CONTENT_PATTERNS):
        errors.append(f"Placeholder language found (normalized-placeholder risk): {pattern}")

    dupes = find_duplicate_paragraphs(text)
    for para in dupes:
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

    hook_match = re.search(r"^## Hook\n(.+?)(?=^## |\Z)", text, flags=re.MULTILINE | re.DOTALL)
    if not hook_match or len(hook_match.group(1).split()) < 12:
        errors.append("Hook section is missing or too short (need 12+ words)")

    top_story_match = re.search(r"^## Top Story\n(.+?)(?=^## |\Z)", text, flags=re.MULTILINE | re.DOTALL)
    if not top_story_match or len(top_story_match.group(1).split()) < 80:
        errors.append("Top Story section is too thin (need 80+ words)")

    cta_match = re.search(r"^## CTA\n(.+?)(?=^## |\Z)", text, flags=re.MULTILINE | re.DOTALL)
    if not cta_match or len(cta_match.group(1).split()) < 8:
        errors.append("CTA section is missing or too short (need 8+ words)")
    else:
        cta_text = cta_match.group(1)
        if REQUIRED_CTA_URL not in cta_text:
            errors.append("CTA section missing required Beehiiv subscribe URL")
        if REQUIRED_SPONSOR_EMAIL not in cta_text:
            errors.append("CTA section missing required sponsor email")
        if "sponsor this issue" not in cta_text.lower():
            errors.append("CTA section missing 'Sponsor this issue' invite")

    sources_match = re.search(r"^## Sources\n(.+?)(?=^## |\Z)", text, flags=re.MULTILINE | re.DOTALL)
    if not sources_match:
        errors.append("Sources section is missing")
    else:
        source_lines = [line for line in sources_match.group(1).splitlines() if line.strip()]
        if len(source_lines) < MIN_SOURCE_LINKS:
            errors.append(f"Sources section is too short: {len(source_lines)} entries")

    if REQUIRE_CRITIC_REVIEW and critic is None:
        expected = critic_expected_path or "state/critic-review-<date>.json"
        errors.append(f"Critic review missing for current issue: expected {expected}")

    if critic:
        overall = float(critic.get("overall_score", 0.0) or 0.0)
        if overall < MIN_CRITIC_OVERALL:
            errors.append(f"Critic overall score too low: {overall:.2f} < {MIN_CRITIC_OVERALL:.2f}")
        weak_categories = critic.get("weak_categories", [])
        if weak_categories:
            errors.append("Critic flagged weak categories: " + ", ".join(weak_categories))
        must_fix = critic.get("must_fix", [])
        if must_fix:
            errors.append("Critic must-fix items remain: " + "; ".join(str(item) for item in must_fix[:4]))
        verdict = str(critic.get("verdict", "")).strip().lower()
        if verdict == "reject":
            errors.append("Critic verdict is reject")

    return errors


def main() -> int:
    contract_error = ""
    path = latest_issue_path()
    try:
        path = ensure_issue_contract(path)
    except Exception as exc:
        contract_error = str(exc).strip() or "issue contract failed"
    text = load_text(path)
    urls = [u.rstrip(").,") for u in re.findall(r"https?://\S+", text)]
    leaked = find_matching_patterns(text, LEAKED_PHRASE_PATTERNS)
    missing = find_matching_patterns(text, MISSING_CONTENT_PATTERNS)
    dupes = find_duplicate_paragraphs(text)
    critic, critic_path = load_issue_critic(path)
    errors = collect_errors(text, critic, critic_path)
    if contract_error:
        errors.append(f"Issue contract failed before gate: {contract_error}")
        if "placeholder/meta upstream content blocked" in contract_error.lower():
            errors.append("Placeholder/meta language was present upstream and blocked before normalization.")

    checks = {
        "exists": path.exists(),
        "issue_path": path.as_posix(),
        "word_count": word_count(text),
        "required_sections_present": [h for h in REQUIRED_SECTIONS if h in text],
        "url_count": len(list(dict.fromkeys(urls))),
        "source_links": list(dict.fromkeys(urls)),
        "has_code_block": "```" in text,
        "leaked_phrases": leaked,
        "placeholder_language": missing,
        "duplicate_paragraphs": dupes,
        "critic_expected_path": critic_path,
        "critic_review": critic or {},
        "errors": errors,
        "contract_error": contract_error,
    }
    result = {"passed": not errors, "checks": checks, "issue": path.as_posix()}
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", path.stem)
    suffix = date_match.group(1) if date_match else "latest"
    out_path = WORKSPACE / "state" / f"quality-gate-{suffix}.json"
    result["run_token"] = RUN_TOKEN
    result["artifact_path"] = out_path.as_posix()
    dump_json(out_path, result)
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
