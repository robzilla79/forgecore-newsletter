"""Issue contract: normalization, validation helpers, and path resolution.

Key rule: normalize_issue_text() may fill MISSING sections but must NEVER
append internal planning language (audience labels, thesis tags, CTA
directions) as literal prose into the rendered output.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from utils import WORKSPACE, load_text, today_str, write_text

REQUIRED_SECTIONS = [
    '## Hook',
    '## Top Story',
    '## Why It Matters',
    '## Highlights',
    '## Tool of the Week',
    '## Workflow',
    '## CTA',
    '## Sources',
]

# Tokens that must never appear in a published issue.
BANNED_TOKENS = [
    'placeholder_image.png',
    'example.com',
    'lorem ipsum',
    'demo link',
    'link to newsletter signup',
    'link to lead magnet',
    # meta-instruction leakage patterns
    'audience focus:',
    'strategic lens:',
    'why this tool fits the issue:',
    'encourage readers to',
    'provide a clear call to action',
    'this issue is for',
    'use this starting workflow',
]


def list_issue_files() -> list[Path]:
    """Return all issue markdown files regardless of naming convention.

    Supports two historical patterns:
      - YYYY-MM-DD.md          (current canonical format)
      - ISSUE-YYYY-MM-DD.md   (legacy prefix format)
      - YYYY-MM-DD-slug.md     (legacy slug suffix format)

    All patterns are de-duplicated and sorted by filename.
    """
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
    files = list_issue_files()
    if files:
        # Sort by the date extracted from filename so slug-suffixed files
        # don't accidentally sort ahead of plain YYYY-MM-DD.md files.
        def _date_key(p: Path) -> str:
            m = re.search(r'(\d{4}-\d{2}-\d{2})', p.name)
            # secondary key is full name so ties within same date are stable
            return (m.group(1) if m else '0000-00-00') + '|' + p.name
        return sorted(files, key=_date_key)[-1]
    return WORKSPACE / 'content' / 'issues' / f'{today_str()}.md'


def latest_brief_path() -> Path:
    files = sorted((WORKSPACE / 'research' / 'briefs').glob('EDITORIAL-BRIEF-*.md'))
    return files[-1] if files else WORKSPACE / 'research' / 'briefs' / f'EDITORIAL-BRIEF-{today_str()}.md'


def latest_raw_intel_path() -> Path:
    files = sorted((WORKSPACE / 'research' / 'raw').glob('RAW-INTEL-*.md'))
    return files[-1] if files else WORKSPACE / 'research' / 'raw' / f'RAW-INTEL-{today_str()}.md'


def slugify(value: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', value.lower()).strip('-')[:80] or today_str()


def issue_date_from_path(path: Path) -> str:
    match = re.search(r'(\d{4}-\d{2}-\d{2})', path.stem)
    return match.group(1) if match else today_str()


def extract_title(text: str, fallback: str) -> str:
    match = re.search(r'^#\s+(.+)$', text, flags=re.MULTILINE)
    return (match.group(1).strip() if match else fallback).strip()


def extract_brief_field(text: str, name: str) -> str:
    pattern = rf'^##\s+{re.escape(name)}\s*$\n(.*?)(?=^##\s+|\Z)'
    match = re.search(pattern, text, flags=re.MULTILINE | re.DOTALL)
    return match.group(1).strip() if match else ''


def paragraphs_from_lines(lines: list[str]) -> str:
    return '\n\n'.join(line.strip() for line in lines if line.strip())


def extract_section(text: str, names: Iterable[str]) -> str:
    for name in names:
        pattern = rf'^##\s+{re.escape(name)}\s*$\n(.*?)(?=^##\s+|\Z)'
        match = re.search(pattern, text, flags=re.MULTILINE | re.DOTALL | re.IGNORECASE)
        if match:
            body = match.group(1).strip()
            if body:
                return body
    return ''


def first_paragraph(text: str) -> str:
    cleaned = re.sub(r'^!\[[^\]]*\]\([^\)]*\)\s*$', '', text, flags=re.MULTILINE)
    cleaned = re.sub(r'^#.*$', '', cleaned, flags=re.MULTILINE)
    paras = [p.strip() for p in re.split(r'\n\s*\n', cleaned) if p.strip()]
    for para in paras:
        if len(para.split()) >= 14:
            return para
    return paras[0] if paras else ''


def bulletize(lines: list[str], minimum: int = 3) -> list[str]:
    """Convert lines to clean bullet points, deduplicate, and pad to minimum."""
    items: list[str] = []
    for line in lines:
        stripped = re.sub(r'^[-*]\s+', '', line).strip()
        # Skip lines that look like internal planning or meta-instructions
        if _is_meta_line(stripped):
            continue
        if stripped and len(stripped.split()) >= 4:
            items.append(f'- {stripped.rstrip(".")}.') if not stripped.endswith('.') else items.append(f'- {stripped}')
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    fillers = [
        '- Teams get more value when AI is attached to a concrete workflow instead of a vague mandate.',
        '- Local and hybrid deployments matter when privacy, latency, or repeatability is part of the buying decision.',
        '- Operators still need evidence, process, and measurable outcomes before a tool becomes part of the stack.',
    ]
    while len(deduped) < minimum:
        deduped.append(fillers[len(deduped) % len(fillers)])
    return deduped[: max(minimum, len(deduped))]


def _is_meta_line(text: str) -> bool:
    """Return True if a line looks like a leaked AI instruction or planning note."""
    lowered = text.lower().strip()
    meta_patterns = [
        r'^audience\s+focus:',
        r'^strategic\s+lens:',
        r'^why\s+this\s+tool\s+fits',
        r'^encourage\s+readers',
        r'^provide\s+a\s+clear\s+call\s+to\s+action',
        r'^this\s+issue\s+is\s+for',
        r'^use\s+this\s+starting\s+workflow',
        r'^\*\*date:\*\*',
        r'^\*\*edition:\*\*',
    ]
    return any(re.match(p, lowered) for p in meta_patterns)


def strip_meta_lines(text: str) -> str:
    """Remove lines that contain leaked planning/instruction language."""
    clean_lines = []
    for line in text.splitlines():
        if not _is_meta_line(line.strip()):
            clean_lines.append(line)
    # Also collapse runs of 3+ blank lines left behind
    result = re.sub(r'\n{3,}', '\n\n', '\n'.join(clean_lines))
    return result.strip()


def dedup_paragraphs(text: str) -> str:
    """Remove exact or near-exact duplicate paragraphs within a section body."""
    paras = re.split(r'\n{2,}', text.strip())
    seen: set[str] = set()
    unique: list[str] = []
    for para in paras:
        key = ' '.join(para.lower().split())
        if key not in seen:
            seen.add(key)
            unique.append(para)
    return '\n\n'.join(unique)


def extract_research_links() -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for path in sorted((WORKSPACE / 'research' / 'raw').glob(f'{today_str()}-*.md'))[-8:]:
        text = load_text(path)
        title = extract_title(text, path.stem)
        match = re.search(r'- URL:\s+(https?://\S+)', text)
        if match:
            url = match.group(1).strip()
            if url not in seen and 'example.com' not in url:
                seen.add(url)
                links.append((title, url))
    return links


def sanitize_text(text: str) -> str:
    # Remove image embeds and bad placeholder URLs
    text = re.sub(r'!\[[^\]]*\]\([^\)]*\)', '', text)
    text = text.replace('placeholder_image.png', '')
    text = re.sub(r'\[([^\]]+)\]\(https?://example\.com[^)]*\)', r'\1', text, flags=re.IGNORECASE)
    text = re.sub(r'https?://example\.com\S*', '', text, flags=re.IGNORECASE)
    # Remove metadata lines the AI injects (**Date:**, **Edition:**)
    text = re.sub(r'^\*\*(?:Date|Edition):\*\*.*$', '', text, flags=re.MULTILINE)
    # Collapse excess blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def normalize_issue_text(text: str, issue_path: Path | None = None) -> str:
    """Normalize issue text: clean, validate structure, fill blanks — no meta-phrase injection."""
    issue_path = issue_path or latest_issue_path()
    issue_date = issue_date_from_path(issue_path)

    # Step 1: strip known garbage before anything else
    text = sanitize_text(text)
    text = strip_meta_lines(text)

    # Step 2: extract title
    title = extract_title(text, f'ForgeCore AI Brief — {issue_date}')

    # Step 3: deduplicate title against other issues
    existing_titles = [
        extract_title(load_text(p), p.stem).strip().lower()
        for p in list_issue_files() if p != issue_path
    ]
    if title.strip().lower() in existing_titles:
        title = f'{title.strip()} — {issue_date}'

    # Step 4: load supporting files (brief + raw intel) for fallback content only
    brief_text = load_text(latest_brief_path())
    raw_text = load_text(latest_raw_intel_path())

    # Step 5: extract each section — fill blanks from brief/raw, never inject labels
    hook = extract_section(text, ['Hook', 'Opening', 'Editor'])
    if not hook:
        hook = first_paragraph(brief_text) or first_paragraph(raw_text) or ''
    hook = dedup_paragraphs(hook)

    top_story = extract_section(text, ['Top Story', 'Main Story'])
    if not top_story:
        top_story = first_paragraph(raw_text) or ''
    top_story = dedup_paragraphs(top_story)

    why_body = extract_section(text, ['Why It Matters', 'Why this matters'])
    why_lines = [line for line in why_body.splitlines() if line.strip()]
    why_items = bulletize(why_lines or re.findall(r'^[-*]\s+.+$', text, flags=re.MULTILINE), minimum=3)

    highlights_body = extract_section(text, ['Highlights', 'Quick Hits', 'Takeaways'])
    highlight_lines = [line for line in highlights_body.splitlines() if line.strip()]
    highlight_items = bulletize(
        highlight_lines or re.findall(r'^[-*]\s+.+$', brief_text + '\n' + raw_text, flags=re.MULTILINE),
        minimum=3,
    )

    tool = extract_section(text, ['Tool of the Week'])
    if not tool:
        tool = extract_brief_field(brief_text, 'Tool of the Week')
    if not tool:
        tool = 'Claude Code with Ollama shortens the path from idea to implementation while keeping model choice flexible.'
    tool = dedup_paragraphs(tool)

    workflow = extract_section(text, ['Workflow', 'Implementation'])
    workflow = dedup_paragraphs(workflow)
    if '```' not in workflow:
        workflow += (
            '\n\n```bash\n'
            '# 1) Pick one workflow that already exists\n'
            'ollama list\n\n'
            '# 2) Define your success metric before rollout\n'
            'echo "Measure time saved, error rate, and cycle time"\n\n'
            '# 3) Pilot with one team and review results weekly\n'
            'echo "Promote only if the workflow is repeatable"\n'
            '```'
        )

    cta = extract_section(text, ['CTA', 'Call to Action'])
    if not cta:
        cta = 'Pick one workflow from this issue, test it with a measurable success metric this week, and only promote it if the gains hold.'
    cta = dedup_paragraphs(cta)
    # Strip any sentence that reads like an AI instruction in the CTA
    cta_lines = [
        line for line in cta.splitlines()
        if not _is_meta_line(line)
        and not re.search(r'subscribe to receive more|encourage|provide a clear call', line, flags=re.IGNORECASE)
    ]
    cta = '\n'.join(cta_lines).strip()

    sources = extract_section(text, ['Sources'])
    links = extract_research_links()
    if not sources:
        sources = '\n'.join(f'- [{label}]({url})' for label, url in links[:5]) if links else '- No source links were available for this run.'
    else:
        for label, url in links[:3]:
            if url not in sources:
                sources += f'\n- [{label}]({url})'
    sources = sources.strip()

    # Step 6: reassemble
    body = '\n\n'.join([
        f'# {title}',
        '## Hook\n' + hook.strip(),
        '## Top Story\n' + top_story.strip(),
        '## Why It Matters\n' + '\n'.join(why_items),
        '## Highlights\n' + '\n'.join(highlight_items),
        '## Tool of the Week\n' + tool.strip(),
        '## Workflow\n' + workflow.strip(),
        '## CTA\n' + cta.strip(),
        '## Sources\n' + sources,
    ])
    return body.strip() + '\n'


def ensure_issue_contract(path: Path | None = None) -> Path:
    path = path or latest_issue_path()
    normalized = normalize_issue_text(load_text(path), path)
    write_text(path, normalized)
    return path
