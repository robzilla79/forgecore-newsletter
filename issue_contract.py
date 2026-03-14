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

BANNED_TOKENS = [
    'placeholder_image.png',
    'example.com',
    'lorem ipsum',
    'demo link',
    'link to newsletter signup',
    'link to lead magnet',
]


def list_issue_files() -> list[Path]:
    root = WORKSPACE / 'content' / 'issues'
    files = sorted(root.glob('ISSUE-*.md')) + sorted(root.glob('20*.md'))
    return sorted({p.resolve() for p in files if p.is_file()})



def latest_issue_path() -> Path:
    files = list_issue_files()
    if files:
        return sorted(files, key=lambda p: p.name)[-1]
    return WORKSPACE / 'content' / 'issues' / f'ISSUE-{today_str()}.md'



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
    items: list[str] = []
    for line in lines:
        stripped = re.sub(r'^[-*]\s+', '', line).strip()
        if stripped and len(stripped.split()) >= 4:
            items.append(f'- {stripped.rstrip(".")}.' if not stripped.endswith('.') else f'- {stripped}')
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
        deduped.append(fillers[len(deduped)])
    return deduped[: max(minimum, len(deduped))]



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
    text = re.sub(r'!\[[^\]]*\]\([^\)]*\)', '', text)
    text = text.replace('placeholder_image.png', '')
    text = re.sub(r'\[([^\]]+)\]\(https?://example\.com[^\)]*\)', r'\1', text, flags=re.IGNORECASE)
    text = re.sub(r'https?://example\.com\S*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()



def normalize_issue_text(text: str, issue_path: Path | None = None) -> str:
    issue_path = issue_path or latest_issue_path()
    issue_date = issue_date_from_path(issue_path)
    text = sanitize_text(text)
    title = extract_title(text, f'ForgeCore AI Productivity Brief — {issue_date}')
        # Ensure title is unique across issues
    existing_titles: list[str] = []
    for p in list_issue_files():
        if p == issue_path:
            continue
        t = extract_title(load_text(p), p.stem)
        if t:
            existing_titles.append(t.strip().lower())

    if title.strip().lower() in existing_titles:
        # Nudge into a more specific, editor-style headline
        if thesis:
            # Use thesis as the main line, date as dateline-style suffix
            title = f"{thesis.strip()} — {issue_date}"
        elif why_now:
            title = f"{why_now.strip()} — {issue_date}"
        else:
            title = f"{title.strip()} ({issue_date})"

    brief_text = load_text(latest_brief_path())
    raw_text = load_text(latest_raw_intel_path())
    audience = extract_brief_field(brief_text, 'Audience')
    thesis = extract_brief_field(brief_text, 'Core thesis')
    why_now = extract_brief_field(brief_text, 'Why now')
    workflow_idea = extract_brief_field(brief_text, 'Workflow/code idea')
    cta_direction = extract_brief_field(brief_text, 'CTA direction')

    hook = extract_section(text, ['Hook', 'Opening', 'Editor']) or first_paragraph(text)
    if thesis and thesis.lower() not in hook.lower():
        hook = hook.rstrip() + ' ' + thesis

    top_story = extract_section(text, ['Top Story', 'Main Story'])
    if not top_story:
        top_story = paragraphs_from_lines([audience, why_now or first_paragraph(brief_text) or first_paragraph(raw_text) or hook])
    if why_now and why_now.lower() not in top_story.lower():
        top_story += '\n\n' + why_now
    if audience and audience.lower() not in top_story.lower():
        top_story += f'\n\nAudience focus: {audience}'

    why_body = extract_section(text, ['Why It Matters', 'Why this matters'])
    why_lines = [line for line in why_body.splitlines() if line.strip()]
    why_items = bulletize(why_lines or re.findall(r'^[-*]\s+.+$', text, flags=re.MULTILINE), minimum=3)
    if thesis:
        why_items.append(f'- Strategic lens: {thesis}')

    highlights_body = extract_section(text, ['Highlights', 'Quick Hits', 'Takeaways'])
    highlight_lines = [line for line in highlights_body.splitlines() if line.strip()]
    highlight_items = bulletize(highlight_lines or re.findall(r'^[-*]\s+.+$', brief_text + '\n' + raw_text, flags=re.MULTILINE), minimum=3)

    tool = extract_section(text, ['Tool of the Week'])
    if not tool:
        tool_match = re.search(r'##\s+Tool of the Week:?\s*(.+)', text, flags=re.IGNORECASE)
        tool = tool_match.group(1).strip() if tool_match else ''
    if not tool:
        tool = extract_brief_field(brief_text, 'Tool of the Week')
    if not tool:
        tool = 'Claude Code with Ollama is worth watching because it shortens the path from idea to implementation while keeping model choice flexible.'
    if thesis and thesis.lower() not in tool.lower():
        tool += f'\n\nWhy this tool fits the issue: {thesis}'

    workflow = extract_section(text, ['Workflow', 'Implementation'])
    if workflow_idea and workflow_idea.lower() not in workflow.lower():
        workflow = workflow_idea + '\n\n' + workflow
    if '```' not in workflow:
        workflow += (
            '\n\n```bash\n'
            '# 1) Pick one workflow that already exists\n'
            'ollama list\n\n'
            '# 2) Define the success metric before rollout\n'
            'echo "Measure time saved, error rate, and cycle time"\n\n'
            '# 3) Pilot with one team and review results weekly\n'
            'echo "Promote only if the workflow is repeatable"\n'
            '```'
        )

    cta = extract_section(text, ['CTA', 'Call to Action'])
    if not cta:
        cta = cta_direction or 'Pick one workflow from this issue, test it with a real success metric this week, and only promote it into production if the gain is measurable.'
    if cta_direction and cta_direction.lower() not in cta.lower():
        cta += '\n\n' + cta_direction

    sources = extract_section(text, ['Sources'])
    links = extract_research_links()
    if not sources:
        if links:
            sources = '\n'.join(f'- [{label}]({url})' for label, url in links[:5])
        else:
            sources = '- No source links were available for this run.'
    else:
        for label, url in links[:3]:
            if url not in sources:
                sources += f'\n- [{label}]({url})'

    metadata = [
        f'**Date:** {issue_date}',
        f'**Edition:** {slugify(issue_date)}',
    ]

    body = '\n\n'.join([
        f'# {title}',
        '\n'.join(metadata),
        '## Hook\n' + hook.strip(),
        '## Top Story\n' + top_story.strip(),
        '## Why It Matters\n' + '\n'.join(why_items),
        '## Highlights\n' + '\n'.join(highlight_items),
        '## Tool of the Week\n' + tool.strip(),
        '## Workflow\n' + workflow.strip(),
        '## CTA\n' + cta.strip(),
        '## Sources\n' + sources.strip(),
    ])
    return body.strip() + '\n'



def ensure_issue_contract(path: Path | None = None) -> Path:
    path = path or latest_issue_path()
    normalized = normalize_issue_text(load_text(path), path)
    write_text(path, normalized)
    return path
