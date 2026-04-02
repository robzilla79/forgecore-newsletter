"""Issue contract: normalization, validation helpers, and path resolution.

Key rule: normalize_issue_text() may fill missing sections but must never
let raw JSON, planning notes, or machine-control text leak into a published issue.
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
    files = list_issue_files()
    if files:
        def _date_key(p: Path) -> str:
            m = re.search(r'(\d{4}-\d{2}-\d{2})', p.name)
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


def bulletize(lines: list[str], minimum: int = 3) -> list[str]:
    items: list[str] = []
    for line in lines:
        stripped = re.sub(r'^[-*]\s+', '', line).strip()
        stripped = re.sub(r'^\d+\.\s+', '', stripped)
        stripped = strip_filler_phrases(stripped)
        if not stripped or _is_meta_line(stripped) or len(stripped.split()) < 4:
            continue
        if not stripped.endswith('.'):
            stripped += '.'
        items.append(f'- {stripped}')
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
    return deduped[:max(minimum, len(deduped))]


def extract_research_links() -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    raw_dir = WORKSPACE / 'research' / 'raw'
    if not raw_dir.exists():
        return links
    for path in sorted(raw_dir.glob('*.md'))[-12:]:
        text = load_text(path)
        title = extract_title(text, path.stem)
        for match in re.finditer(r'https?://\S+', text):
            url = match.group(0).rstrip(').,]')
            if 'example.com' in url.lower() or url in seen:
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
        if 'example.com' in url.lower() or url in seen:
            continue
        seen.add(url)
        entries.append(f'- [{label}]({url})')
    if not entries:
        for label, url in extract_research_links()[:5]:
            if url not in seen:
                seen.add(url)
                entries.append(f'- [{label}]({url})')
    return '\n'.join(entries) if entries else '- No source links were available for this run.'


def ensure_workflow_block(workflow: str) -> str:
    workflow = workflow.strip()
    fallback = """```bash
# 1) Pick one workflow that already exists
ollama list

# 2) Define your success metric before rollout
echo \"Measure time saved, error rate, and cycle time\"

# 3) Pilot with one team and review results weekly
echo \"Promote only if the workflow is repeatable\"
```"""
    if '```' in workflow:
        return workflow
    if workflow:
        return workflow + '\n\n' + fallback
    return fallback


def sanitize_text(text: str) -> str:
    text = re.sub(r'!\[[^\]]*\]\([^\)]*\)', '', text)
    text = re.sub(r'```(?:json|markdown)?', '', text, flags=re.IGNORECASE)
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
        if _is_meta_line(para):
            continue
        if len(para.split()) >= 20:
            out.append(para)
    return out


def _expand_top_story(brief_text: str, raw_text: str) -> str:
    candidates = _research_paragraphs(raw_text) + _research_paragraphs(brief_text)
    deduped: list[str] = []
    seen: set[str] = set()
    for para in candidates:
        key = ' '.join(para.lower().split())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(para)
    selected: list[str] = []
    words = 0
    for para in deduped:
        selected.append(para)
        words += len(para.split())
        if len(selected) >= 2 and words >= 110:
            break
    if len(selected) < 2 or words < 80:
        raise ValueError(
            "Top Story contract failure: missing substantive content. "
            "Need multiple research paragraphs; refusing single-paragraph autofill."
        )
    return '\n\n'.join(selected)


def normalize_issue_text(text: str, issue_path: Path | None = None) -> str:
    issue_path = issue_path or latest_issue_path()
    issue_date = issue_date_from_path(issue_path)
    upstream_hits = contains_placeholder_or_meta(text)
    if upstream_hits:
        raise ValueError(
            "Placeholder/meta upstream content blocked by issue contract: "
            + ", ".join(upstream_hits[:4])
        )

    text = sanitize_text(text)
    title = extract_title(text, f'ForgeCore AI Brief — {issue_date}')

    existing_titles = [extract_title(load_text(p), p.stem).strip().lower() for p in list_issue_files() if p != issue_path]
    if title.strip().lower() in existing_titles:
        title = f'{title.strip()} — {issue_date}'

    brief_text = load_text(latest_brief_path())
    raw_text = load_text(latest_raw_intel_path())

    hook = sanitize_text(extract_section(text, ['Hook', 'Opening', 'Editor']))
    if not hook:
        hook = first_paragraph(brief_text) or first_paragraph(raw_text)
    hook = dedup_paragraphs(hook)

    top_story = sanitize_text(extract_section(text, ['Top Story', 'Main Story']))
    if not top_story or len(top_story.split()) < 80:
        top_story = _expand_top_story(brief_text, raw_text)
    top_story = dedup_paragraphs(top_story)

    why_body = sanitize_text(extract_section(text, ['Why It Matters', 'Why this matters']))
    why_items = bulletize([line for line in why_body.splitlines() if line.strip()], minimum=3)

    highlights_body = sanitize_text(extract_section(text, ['Highlights', 'Quick Hits', 'Takeaways']))
    highlight_seed = [line for line in highlights_body.splitlines() if line.strip()]
    if not highlight_seed:
        highlight_seed = re.findall(r'^[-*]\s+.+$', brief_text + '\n' + raw_text, flags=re.MULTILINE)
    highlight_items = bulletize(highlight_seed, minimum=4)

    tool = sanitize_text(extract_section(text, ['Tool of the Week']))
    if not tool:
        tool = sanitize_text(extract_brief_field(brief_text, 'Tool of the Week'))
    if not tool:
        tool = 'Claude Code with Ollama shortens the path from idea to implementation while keeping model choice flexible.'
    tool = dedup_paragraphs(tool)

    workflow = sanitize_text(extract_section(text, ['Workflow', 'Implementation']))
    workflow = dedup_paragraphs(workflow)
    workflow = ensure_workflow_block(workflow)

    cta = sanitize_text(extract_section(text, ['CTA', 'Call to Action']))
    if not cta:
        cta = 'Pick one workflow from this issue, test it with a measurable success metric this week, and only promote it if the gains hold.'
    cta = dedup_paragraphs(cta)
    cta_lines = [line for line in cta.splitlines() if not _is_meta_line(line)]
    cta = '\n'.join(line for line in cta_lines if line.strip()).strip()
    if 'https://forgecore-newsletter.beehiiv.com/' not in cta or 'sponsors@forgecore.co' not in cta.lower() or 'sponsor this issue' not in cta.lower():
        cta = (cta + '\n\n' + CTA_TEMPLATE).strip()

    sources = normalize_sources(extract_section(text, ['Sources']))

    return '\n\n'.join([
        f'# {title}',
        '## Hook\n' + hook.strip(),
        '## Top Story\n' + top_story.strip(),
        '## Why It Matters\n' + '\n'.join(why_items),
        '## Highlights\n' + '\n'.join(highlight_items),
        '## Tool of the Week\n' + tool.strip(),
        '## Workflow\n' + workflow.strip(),
        '## CTA\n' + cta.strip(),
        '## Sources\n' + sources.strip(),
    ]).strip() + '\n'


def ensure_issue_contract(path: Path | None = None) -> Path:
    path = path or latest_issue_path()
    normalized = normalize_issue_text(load_text(path), path)
    write_text(path, normalized)
    return path
