"""Issue contract: validation helpers and safe path resolution.

Production rule: the issue contract must never pull stale raw intel, stale briefs,
or legacy fallback copy into the active issue. It may validate and normalize safe
structure, but it must fail loudly when fresh slot-specific context is missing.

Design philosophy: this contract does not enforce a template. It enforces quality.
Aware is a prose column. Em writes in whatever structure serves the piece.
The contract checks that the result has substance: a real opening, a real argument,
a real landing, at least one source URL, and the exact Aware footer.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable

from utils import WORKSPACE, load_text, today_str, write_text

# Exact Aware footer. Must appear in every published issue.
AWARE_FOOTER = (
    "*Aware by Em \u00b7 [news.forgecore.co](https://news.forgecore.co) \u00b7 "
    "[empersists.bsky.social](https://bsky.app/profile/empersists.bsky.social)*"
)

# Structural headers that are forbidden in Aware prose columns.
FORBIDDEN_HEADERS = {
    "## cta",
    "## sources",
    "## hook",
    "## workflow",
    "## why it matters",
    "## highlights",
    "## tool of the week",
    "## operator brief",
    "## top story",
}

BANNED_TOKENS = [
    'placeholder_image.png',
    'example.com',
    'lorem ipsum',
    'demo link',
    'link to newsletter signup',
    'link to lead magnet',
    'audience focus:',
    'strategic lens:',
    'why this tool fits the issue:',
    'encourage readers to',
    'provide a clear call to action',
    'this issue is for',
    'use this starting workflow',
    '"summary":',
    '"files":',
    '"memory_update":',
]

FILLER_PHRASES = [
    'game-changing',
    'groundbreaking',
    'revolutionary',
    'in today\'s fast-paced environment',
    'it is important to note that',
    'this underscores the importance of',
    'are you leaving money on the table',
    'science-backed',
    'proven strategies',
    'boost your',
    'transform your',
    'skyrocket your',
    'unlock the power of',
    'supercharge your',
]

META_PATTERNS = [
    r'^audience\s+focus:',
    r'^strategic\s+lens:',
    r'^why\s+this\s+tool\s+fits',
    r'^encourage\s+readers',
    r'^provide\s+a\s+clear\s+call\s+to\s+action',
    r'^this\s+issue\s+is\s+for',
    r'^use\s+this\s+starting\s+workflow',
    r'^"summary":',
    r'^"files":',
    r'^"memory_update":',
    r'^\*\*date:\*\*',
    r'^\*\*edition:\*\*',
]

PLACEHOLDER_PATTERNS = [
    r"\bno concrete content returned\b",
    r"\bmissing content\b",
    r"\bdescription incomplete in provided content\b",
]

LISTICLE_PATTERNS = [
    r'^\s*#+\s*(five|five proven|top \d+|\d+ ways|\d+ strategies|\d+ tips)',
    r'^\s*\d+\.\s+(anchoring|charm pricing|decoy pricing|tiered pricing)',
]


def has_forbidden_headers(text: str) -> bool:
    """Return True if the text contains any structural header forbidden in Aware."""
    for line in text.splitlines():
        stripped = line.strip().lower().rstrip(":")
        if stripped in FORBIDDEN_HEADERS:
            return True
    return False


def issue_slot() -> str:
    return os.getenv('ISSUE_SLOT', '').strip().lower()


def issue_id_for_today() -> str:
    slot = issue_slot()
    base = today_str()
    return f'{base}-{slot}' if slot in {'am', 'pm'} else base


def slot_suffix() -> str:
    slot = issue_slot()
    return f'-{slot}' if slot in {'am', 'pm'} else ''


def issue_path_for_today() -> Path:
    return WORKSPACE / 'content' / 'issues' / f'{issue_id_for_today()}.md'


def brief_path_for_today() -> Path:
    return WORKSPACE / 'research' / 'briefs' / f'EDITORIAL-BRIEF-{today_str()}{slot_suffix()}.md'


def raw_intel_path_for_today() -> Path:
    return WORKSPACE / 'research' / 'raw' / f'RAW-INTEL-{today_str()}{slot_suffix()}.md'


def list_issue_files() -> list[Path]:
    root = WORKSPACE / 'content' / 'issues'
    patterns = [
        '20[0-9][0-9]-[0-9][0-9]-[0-9][0-9].md',
        '20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]-*.md',
        'ISSUE-20[0-9][0-9]-[0-9][0-9]-[0-9][0-9].md',
    ]
    files: set[Path] = set()
    for pattern in patterns:
        files.update(p.resolve() for p in root.glob(pattern) if p.is_file())
    return sorted(files, key=lambda p: p.name)


def latest_issue_path() -> Path:
    current = issue_path_for_today()
    if current.exists() or issue_slot() in {'am', 'pm'}:
        return current
    files = list_issue_files()
    if files:
        def _date_key(p: Path) -> str:
            m = re.search(r'(\d{4}-\d{2}-\d{2})', p.name)
            return (m.group(1) if m else '0000-00-00') + '|' + p.name
        return sorted(files, key=_date_key)[-1]
    return current


def latest_brief_path() -> Path:
    return brief_path_for_today()


def latest_raw_intel_path() -> Path:
    return raw_intel_path_for_today()


def require_fresh_context() -> tuple[str, str]:
    brief_path = brief_path_for_today()
    raw_path = raw_intel_path_for_today()
    missing = [path.as_posix() for path in [brief_path, raw_path] if not path.exists()]
    if missing:
        raise ValueError('Fresh slot-specific context missing: ' + ', '.join(missing))
    brief_text = load_text(brief_path)
    raw_text = load_text(raw_path)
    hits = contains_placeholder_or_meta(brief_text + '\n' + raw_text)
    if hits:
        raise ValueError('Fresh slot-specific context is contaminated: ' + ', '.join(hits[:4]))
    return brief_text, raw_text


def slugify(value: str) -> str:
    value = re.sub(r'^title:\s*', '', value.strip(), flags=re.IGNORECASE)
    return re.sub(r'[^a-z0-9]+', '-', value.lower()).strip('-')[:80] or today_str()


def issue_date_from_path(path: Path) -> str:
    match = re.search(r'(\d{4}-\d{2}-\d{2})', path.stem)
    return match.group(1) if match else today_str()


def extract_title(text: str, fallback: str) -> str:
    match = re.search(r'^#\s+(.+)$', text, flags=re.MULTILINE)
    title = (match.group(1).strip() if match else fallback).strip()
    title = re.sub(r'^title:\s*', '', title, flags=re.IGNORECASE).strip()
    return title or fallback


def extract_brief_field(text: str, name: str) -> str:
    pattern = rf'^##\s+{re.escape(name)}\s*$\n(.*?)(?=^##\s+|\Z)'
    match = re.search(pattern, text, flags=re.MULTILINE | re.DOTALL)
    return match.group(1).strip() if match else ''


def extract_section(text: str, names: Iterable[str]) -> str:
    for name in names:
        pattern = rf'^##\s+{re.escape(name)}\s*$\n(.*?)(?=^##\s+|\Z)'
        match = re.search(pattern, text, flags=re.MULTILINE | re.DOTALL | re.IGNORECASE)
        if match:
            body = match.group(1).strip()
            if body:
                return body
    return ''


def _is_meta_line(text: str) -> bool:
    lowered = text.lower().strip()
    return any(re.match(pattern, lowered) for pattern in META_PATTERNS)


def strip_meta_lines(text: str) -> str:
    lines: list[str] = []
    in_json_blob = False
    brace_depth = 0
    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not in_json_blob and (stripped.startswith('{') or stripped.startswith('"summary":') or stripped.startswith('"files":')):
            in_json_blob = True
        if in_json_blob:
            brace_depth += stripped.count('{')
            brace_depth -= stripped.count('}')
            if brace_depth <= 0 and stripped.endswith('}'):
                in_json_blob = False
            continue
        if _is_meta_line(stripped):
            continue
        lines.append(line)
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip()


def strip_filler_phrases(text: str) -> str:
    result = text
    for phrase in FILLER_PHRASES:
        result = re.sub(re.escape(phrase), '', result, flags=re.IGNORECASE)
    return re.sub(r'\s{2,}', ' ', result).strip()


def dedup_paragraphs(text: str) -> str:
    paras = [p.strip() for p in re.split(r'\n{2,}', text.strip()) if p.strip()]
    seen: set[str] = set()
    unique: list[str] = []
    for para in paras:
        key = ' '.join(para.lower().split())
        if key not in seen:
            seen.add(key)
            unique.append(para)
    return '\n\n'.join(unique)


def first_paragraph(text: str) -> str:
    cleaned = re.sub(r'!\[[^\]]*\]\([^\)]*\)', '', text)
    cleaned = re.sub(r'^#.*$', '', cleaned, flags=re.MULTILINE)
    cleaned = strip_meta_lines(cleaned)
    paras = [p.strip() for p in re.split(r'\n\s*\n', cleaned) if p.strip()]
    for para in paras:
        if len(para.split()) >= 14 and not _is_meta_line(para):
            return strip_filler_phrases(para)
    return strip_filler_phrases(paras[0]) if paras else ''


def detect_listicle(text: str) -> bool:
    for pattern in LISTICLE_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE):
            return True
    numbered = re.findall(r'^\s*\d+\.', text[:2000], flags=re.MULTILINE)
    if len(numbered) >= 5:
        return True
    return False


def sanitize_text(text: str) -> str:
    text = re.sub(r'!\[[^\]]*\]\([^\)]*\)', '', text)
    text = re.sub(r'```(?:json|markdown)?', '```', text, flags=re.IGNORECASE)
    text = text.replace('placeholder_image.png', '')
    text = re.sub(r'\[([^\]]+)\]\(https?://example\.com[^)]*\)', r'\1', text, flags=re.IGNORECASE)
    text = re.sub(r'https?://example\.com\S*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^\*\*(?:Date|Edition):\*\*.*$', '', text, flags=re.MULTILINE)
    text = strip_meta_lines(text)
    text = strip_filler_phrases(text)
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def contains_placeholder_or_meta(text: str) -> list[str]:
    hits: list[str] = []
    for pattern in PLACEHOLDER_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE):
            hits.append(pattern)
    for pattern in META_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE):
            hits.append(pattern)
    return list(dict.fromkeys(hits))


def extract_research_links() -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    raw_path = raw_intel_path_for_today()
    candidate_paths = [raw_path] if raw_path.exists() else []
    for path in candidate_paths:
        text = load_text(path)
        title = extract_title(text, path.stem)
        for match in re.finditer(r'https?://\S+', text):
            url = match.group(0).rstrip(').,]')
            if 'example.com' in url.lower() or url in seen:
                continue
            seen.add(url)
            links.append((title, url))
    return links


def check_substance(text: str) -> None:
    """Verify the piece has enough real content for an Aware column."""
    # Must have a title.
    if not re.search(r'^#\s+\S', text, flags=re.MULTILINE):
        raise ValueError('Issue missing a title (# heading).')

    # Must have a byline.
    if not re.search(r'\*by\s+Em\s+[\u2014-]\s+.+\*', text):
        raise ValueError("Issue missing required byline '*by Em \u2014 [Month Day, Year]*'.")

    # No forbidden structural headers.
    if has_forbidden_headers(text):
        raise ValueError(
            'Issue contains forbidden structural headers for Aware format. '
            'Remove ## CTA, ## Sources, and all old newsletter section headers.'
        )

    # Word count on body (strip title line and footer).
    body = re.sub(r'^#.*$', '', text, flags=re.MULTILINE)
    body = re.sub(re.escape(AWARE_FOOTER), '', body, flags=re.IGNORECASE)
    words = len(body.split())
    if words < 400:
        raise ValueError(f'Issue body too thin for Aware: {words} words. Minimum 400.')
    if words > 750:
        raise ValueError(f'Issue body too long for Aware: {words} words. Maximum ~700.')

    # Must not be a listicle.
    if detect_listicle(text):
        raise ValueError(
            'Issue rejected: detected listicle/template structure. '
            'Em writes columns, not listicles. Rewrite with a real argument.'
        )

    # Must have at least two substantive paragraphs beyond intro/footer.
    paras = [p.strip() for p in re.split(r'\n\s*\n', body.strip()) if p.strip()]
    real_paras = [p for p in paras if len(p.split()) >= 20]
    if len(real_paras) < 2:
        raise ValueError(
            'Issue needs at least two substantive paragraphs. '
            'Cannot be only an intro line and a footer.'
        )


def normalize_issue_text(text: str, issue_path: Path | None = None) -> str:
    """Validate and lightly normalize an Aware column. Does not reconstruct sections."""
    issue_path = issue_path or latest_issue_path()
    issue_date = issue_date_from_path(issue_path)

    upstream_hits = contains_placeholder_or_meta(text)
    if upstream_hits:
        raise ValueError(
            'Placeholder/meta upstream content blocked by issue contract: '
            + ', '.join(upstream_hits[:4])
        )

    text = sanitize_text(text)

    # Substance and format checks.
    check_substance(text)

    # Title normalization — preserves Em's prose structure, only normalizes the H1.
    title = extract_title(text, f'Aware \u2014 {issue_date}')
    existing_titles = [
        extract_title(load_text(p), p.stem).strip().lower()
        for p in list_issue_files()
        if p != issue_path
    ]
    if title.strip().lower() in existing_titles:
        title = f'{title.strip()} \u2014 {issue_date}'

    text_no_title = re.sub(r'^#\s+.+$', '', text, count=1, flags=re.MULTILINE).lstrip()
    rebuilt = f'# {title}\n\n{text_no_title}'.rstrip() + '\n'

    # Fresh context must exist.
    require_fresh_context()

    # Branding check — no ForgeCore-era footer.
    lower = rebuilt.lower()
    if 'forgecore ai' in lower or 'forgecore newsletter' in lower:
        raise ValueError(
            'Issue still contains ForgeCore-era footer or branding. '
            'Replace with the Aware footer from em/VOICE.md.'
        )

    # Aware footer must be present.
    if AWARE_FOOTER not in rebuilt:
        rebuilt = rebuilt.rstrip() + '\n\n' + AWARE_FOOTER + '\n'

    # At least one real URL.
    if not re.findall(r'https?://\S+', rebuilt):
        raise ValueError('Issue missing any source URL for Aware.')

    final_hits = contains_placeholder_or_meta(rebuilt)
    if final_hits:
        raise ValueError(
            'Normalized issue still contains placeholder/meta content: '
            + ', '.join(final_hits[:4])
        )

    return rebuilt


def ensure_issue_contract(path: Path | None = None) -> Path:
    path = path or issue_path_for_today()
    normalized = normalize_issue_text(load_text(path), path)
    write_text(path, normalized)
    return path
