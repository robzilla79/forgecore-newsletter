"""Issue contract: validation helpers and safe path resolution.

Production rule: the issue contract must never pull stale raw intel, stale briefs,
or legacy fallback copy into the active issue. It may validate and normalize safe
structure, but it must fail loudly when fresh slot-specific context is missing.

Design philosophy: this contract does not enforce a template. It enforces quality.
Em writes in whatever structure serves the piece. The contract checks that the result
has substance: a real opening, a real argument, a real landing, and clean sources.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable

from utils import WORKSPACE, load_text, today_str, write_text

# Minimum required sections — structural, not prescriptive.
# Em may use any section names she wants. These are the only hard requirements.
REQUIRED_SECTIONS = [
    '## Sources',
    '## CTA',
]

CTA_TEMPLATE = """**Subscribe free:** [ForgeCore Newsletter](https://forgecore-newsletter.beehiiv.com/)

**Sponsor this issue:** Want your tool, product, or service in front of AI-forward operators and founders? Email [sponsors@forgecore.co](mailto:sponsors@forgecore.co)."""

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

# Listicle detection — catches template-factory output
LISTICLE_PATTERNS = [
    r'^\s*#+\s*(five|five proven|top \d+|\d+ ways|\d+ strategies|\d+ tips)',
    r'^\s*\d+\.\s+(anchoring|charm pricing|decoy pricing|tiered pricing)',
]


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


def extract_all_sections(text: str) -> dict[str, str]:
    """Extract all ## sections from the text as a dict of name -> content."""
    result = {}
    pattern = r'^##\s+(.+?)\s*$\n(.*?)(?=^##\s+|\Z)'
    for match in re.finditer(pattern, text, flags=re.MULTILINE | re.DOTALL):
        name = match.group(1).strip()
        body = match.group(2).strip()
        if body:
            result[name] = body
    return result


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
    """Return True if the text smells like a template-factory listicle."""
    for pattern in LISTICLE_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE):
            return True
    # Five or more numbered items near the top is a strong signal
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


def _research_paragraphs(text: str) -> list[str]:
    cleaned = sanitize_text(text)
    paras = [p.strip() for p in re.split(r'\n\s*\n', cleaned) if p.strip()]
    out: list[str] = []
    for para in paras:
        if _is_meta_line(para) or contains_placeholder_or_meta(para):
            continue
        if len(para.split()) >= 20:
            out.append(para)
    return out


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
            if 'example.com' in url.lower() or 'ollama.com/blog' in url.lower() or url in seen:
                continue
            seen.add(url)
            links.append((title, url))
    return links


def normalize_sources(sources: str) -> str:
    entries: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r'\[([^\]]+)\]\((https?://[^)]+)\)', sources):
        label = match.group(1).strip()
        url = match.group(2).strip()
        if 'example.com' in url.lower() or 'ollama.com/blog' in url.lower() or url in seen:
            continue
        seen.add(url)
        entries.append(f'- [{label}]({url})')
    if len(entries) < 3:
        for label, url in extract_research_links():
            if url not in seen:
                seen.add(url)
                entries.append(f'- [{label}]({url})')
            if len(entries) >= 3:
                break
    if len(entries) < 3:
        raise ValueError('Need at least 3 non-Ollama source links for publication.')
    return '\n'.join(entries)


def check_required_sections(text: str) -> None:
    """Verify the hard-minimum required sections exist."""
    for section in REQUIRED_SECTIONS:
        if not re.search(rf'^{re.escape(section)}\s*$', text, flags=re.MULTILINE):
            raise ValueError(f'author Markdown missing required section: {section}')


def check_substance(text: str) -> None:
    """Verify the piece has enough real content — not a format check, a quality check."""
    # Must have a title
    if not re.search(r'^#\s+\S', text, flags=re.MULTILINE):
        raise ValueError('Issue missing a title (# heading).')

    # Must have at least 300 words of body content
    body = re.sub(r'^#.*$', '', text, flags=re.MULTILINE)
    body = re.sub(r'^##.*$', '', body, flags=re.MULTILINE)
    words = len(body.split())
    if words < 300:
        raise ValueError(f'Issue body too thin: {words} words. Minimum 300.')

    # Must not be a listicle
    if detect_listicle(text):
        raise ValueError(
            'Issue rejected: detected listicle/template structure. '
            'Em writes columns, not listicles. Rewrite with a real argument.'
        )

    # Must have at least 2 ## sections beyond CTA and Sources
    sections = re.findall(r'^##\s+\S', text, flags=re.MULTILINE)
    content_sections = [s for s in sections if s not in ('## CTA', '## Sources')]
    if len(content_sections) < 2:
        raise ValueError('Issue needs at least 2 content sections beyond CTA and Sources.')


def normalize_issue_text(text: str, issue_path: Path | None = None) -> str:
    issue_path = issue_path or latest_issue_path()
    issue_date = issue_date_from_path(issue_path)
    upstream_hits = contains_placeholder_or_meta(text)
    if upstream_hits:
        raise ValueError('Placeholder/meta upstream content blocked by issue contract: ' + ', '.join(upstream_hits[:4]))

    text = sanitize_text(text)

    # Quality checks — substance over structure
    check_substance(text)

    title = extract_title(text, f'ForgeCore AI — {issue_date}')

    existing_titles = [extract_title(load_text(p), p.stem).strip().lower() for p in list_issue_files() if p != issue_path]
    if title.strip().lower() in existing_titles:
        title = f'{title.strip()} — {issue_date}'

    # Verify fresh context exists (scout ran)
    require_fresh_context()

    # Preserve Em's section structure exactly — just clean and deduplicate
    all_sections = extract_all_sections(text)
    rebuilt_sections = [f'# {title}']

    for section_name, section_body in all_sections.items():
        clean_body = dedup_paragraphs(sanitize_text(section_body))
        if section_name.lower() == 'cta':
            # Ensure CTA always has subscribe + sponsor links
            if 'forgecore-newsletter.beehiiv.com' not in clean_body or 'sponsors@forgecore.co' not in clean_body.lower():
                clean_body = (clean_body + '\n\n' + CTA_TEMPLATE).strip()
        if section_name.lower() == 'sources':
            clean_body = normalize_sources(clean_body)
        rebuilt_sections.append(f'## {section_name}\n\n{clean_body}')

    # Ensure CTA and Sources exist even if Em omitted them
    section_names_lower = [s.lower() for s in all_sections.keys()]
    if 'cta' not in section_names_lower:
        rebuilt_sections.append(f'## CTA\n\n{CTA_TEMPLATE}')
    if 'sources' not in section_names_lower:
        sources = normalize_sources('')
        rebuilt_sections.append(f'## Sources\n\n{sources}')

    normalized = '\n\n'.join(rebuilt_sections).strip() + '\n'

    final_hits = contains_placeholder_or_meta(normalized)
    if final_hits:
        raise ValueError('Normalized issue still contains placeholder/meta content: ' + ', '.join(final_hits[:4]))

    # Hard-minimum section check
    check_required_sections(normalized)

    return normalized


def ensure_issue_contract(path: Path | None = None) -> Path:
    path = path or issue_path_for_today()
    normalized = normalize_issue_text(load_text(path), path)
    write_text(path, normalized)
    return path
