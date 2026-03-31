#!/usr/bin/env python3
"""Quality gate: validate a normalized issue before it ships."""
from __future__ import annotations

import json
import re

from issue_contract import BANNED_TOKENS, REQUIRED_SECTIONS, ensure_issue_contract, latest_issue_path
from utils import WORKSPACE, dump_json, load_text

MIN_WORDS = 500
# Require at least 3 real source URLs to match AGENTS.md quality rules
MIN_SOURCE_LINKS = 3

# Regex patterns that indicate leaked AI meta-instructions in final output.
# These are in addition to BANNED_TOKENS (which are exact-string checks).
LEAKED_PHRASE_PATTERNS: list[str] = [
    r"\baudience\s+focus\b",
    r"\bstrategic\s+lens\b",
    r"\bwhy\s+this\s+tool\s+fits\b",
    r"\bencourage\s+readers\s+to\b",
    r"\bprovide\s+a\s+clear\s+call\s+to\s+action\b",
    r"\bthis\s+issue\s+is\s+for\b",
    r"\buse\s+this\s+starting\s+workflow\b",
    r"\bsubscribe\s+to\s+receive\s+more\s+practical\b",
    r"^\*\*Date:\*\*",
    r"^\*\*Edition:\*\*",
]


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def find_leaked_phrases(text: str) -> list[str]:
    found: list[str] = []
    for pattern in LEAKED_PHRASE_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE):
            found.append(pattern)
    return found


def find_duplicate_paragraphs(text: str) -> list[str]:
    """Return list of paragraphs that appear more than once (normalized)."""
    paras = re.split(r"\n{2,}", text.strip())
    seen: dict[str, int] = {}
    for p in paras:
        key = " ".join(p.lower().split())
        if len(key) < 40:  # skip very short fragments
            continue
        seen[key] = seen.get(key, 0) + 1
    return [k[:80] + "..." for k, count in seen.items() if count > 1]


def collect_errors(text: str) -> list[str]:
    errors: list[str] = []

    # Required sections
    for header in REQUIRED_SECTIONS:
        if header not in text:
            errors.append(f"Missing required section: {header}")

    # Banned tokens (exact string)
    for token in BANNED_TOKENS:
        if token.lower() in text.lower():
            errors.append(f"Banned token found: \"{token}\"")

    # Leaked AI meta-phrases (regex)
    for pattern in find_leaked_phrases(text):
    errors.append(f"Leaked meta-phrase pattern found: {pattern}")

    # Duplicate paragraphs
    dupes = find_duplicate_paragraphs(text)
    for d in dupes:
        errors.append(f"Duplicate paragraph detected: \"{d}\"")

    # URLs
    urls = re.findall(r"https?://\S+", text)
    if len(urls) < MIN_SOURCE_LINKS:
        errors.append(
            f"Not enough real URLs: found {len(urls)}, need at least {MIN_SOURCE_LINKS}"
        )
    if any("example.com" in url.lower() for url in urls):
        errors.append("example.com URL found in issue content")

    # Code block
    if "```" not in text:
        errors.append("Workflow code block is missing")

    # Word count
    wc = word_count(text)
    if wc < MIN_WORDS:
        errors.append(f"Issue too short: {wc} words (need {MIN_WORDS})")

    # Hook length
    hook_match = re.search(r"^## Hook\n(.+?)(?=^## |\Z)", text, flags=re.MULTILINE | re.DOTALL)
    if not hook_match or len(hook_match.group(1).split()) < 12:
        errors.append("Hook section is missing or too short (need 12+ words)")

    # CTA length
    cta_match = re.search(r"^## CTA\n(.+?)(?=^## |\Z)", text, flags=re.MULTILINE | re.DOTALL)
    if not cta_match or len(cta_match.group(1).split()) < 8:
        errors.append("CTA section is missing or too short (need 8+ words)")

    return errors


def main() -> int:
    path = ensure_issue_contract(latest_issue_path())
    text = load_text(path)
    urls = re.findall(r"https?://\S+", text)
    errors = collect_errors(text)
    leaked = find_leaked_phrases(text)
    dupes = find_duplicate_paragraphs(text)

    checks = {
        "exists": path.exists(),
        "issue_path": path.as_posix(),
        "word_count": word_count(text),
        "required_sections_present": [h for h in REQUIRED_SECTIONS if h in text],
        "url_count": len(urls),
        "source_links": [u.rstrip(").,") for u in urls],
        "has_code_block": "```" in text,
        "leaked_phrases": leaked,
        "duplicate_paragraphs": dupes,
        "errors": errors,
    }
    result = {"passed": not errors, "checks": checks, "issue": path.as_posix()}
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", path.stem)
    suffix = date_match.group(1) if date_match else "latest"
    dump_json(WORKSPACE / "state" / f"quality-gate-{suffix}.json", result)
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
