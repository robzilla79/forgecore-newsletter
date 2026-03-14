#!/usr/bin/env python3
from __future__ import annotations

import json
import re

from issue_contract import BANNED_TOKENS, REQUIRED_SECTIONS, ensure_issue_contract, latest_issue_path
from utils import WORKSPACE, dump_json, load_text

MIN_WORDS = 500
MIN_SOURCE_LINKS = 2


def word_count(text: str) -> int:
    return len(re.findall(r'\b\w+\b', text))



def collect_errors(text: str) -> list[str]:
    errors: list[str] = []
    for header in REQUIRED_SECTIONS:
        if header not in text:
            errors.append(f'Missing required section: {header}')
    for token in BANNED_TOKENS:
        if token.lower() in text.lower():
            errors.append(f'Banned placeholder content found: {token}')
    urls = re.findall(r'https?://\S+', text)
    if len(urls) < MIN_SOURCE_LINKS:
        errors.append(f'Not enough real URLs: found {len(urls)}, need at least {MIN_SOURCE_LINKS}')
    if any('example.com' in url.lower() for url in urls):
        errors.append('Example/demo URL found in issue content')
    if '```' not in text:
        errors.append('Workflow code block is missing')
    if word_count(text) < MIN_WORDS:
        errors.append(f'Issue is too short: {word_count(text)} words < {MIN_WORDS}')
    hook_match = re.search(r'^## Hook\n(.+?)(?=^## |\Z)', text, flags=re.MULTILINE | re.DOTALL)
    if not hook_match or len(hook_match.group(1).split()) < 12:
        errors.append('Hook section is missing or too short')
    cta_match = re.search(r'^## CTA\n(.+?)(?=^## |\Z)', text, flags=re.MULTILINE | re.DOTALL)
    if not cta_match or len(cta_match.group(1).split()) < 8:
        errors.append('CTA section is missing or too short')
    return errors



def main() -> int:
    path = ensure_issue_contract(latest_issue_path())
    text = load_text(path)
    urls = re.findall(r'https?://\S+', text)
    errors = collect_errors(text)
    checks = {
        'exists': path.exists(),
        'issue_path': path.as_posix(),
        'word_count': word_count(text),
        'required_sections_present': [header for header in REQUIRED_SECTIONS if header in text],
        'url_count': len(urls),
        'source_links': [url.rstrip(').,') for url in urls],
        'has_code_block': '```' in text,
        'errors': errors,
    }
    result = {'passed': not errors, 'checks': checks, 'issue': path.as_posix()}
    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', path.stem)
    suffix = date_match.group(1) if date_match else 'latest'
    dump_json(WORKSPACE / 'state' / f'quality-gate-{suffix}.json', result)
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


if __name__ == '__main__':
    raise SystemExit(main())
