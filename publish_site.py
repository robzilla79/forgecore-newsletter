#!/usr/bin/env python3
from __future__ import annotations

import html
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from jinja2 import Template

from issue_contract import ensure_issue_contract, issue_date_from_path, latest_issue_path, list_issue_files, slugify
from utils import WORKSPACE, load_text, write_text

load_dotenv(WORKSPACE / '.env')

SITE_BASE_URL = os.getenv('SITE_BASE_URL', 'https://news.forgecore.co').rstrip('/')
NEWSLETTER_NAME = os.getenv('NEWSLETTER_NAME', 'ForgeCore AI Productivity Brief')
TAGLINE = os.getenv('NEWSLETTER_TAGLINE', 'Practical AI workflows, tools, and ROI cases for operators')
PRIMARY_CTA_TEXT = os.getenv('PRIMARY_CTA_TEXT', 'Subscribe free')
PRIMARY_CTA_URL = os.getenv('PRIMARY_CTA_URL', SITE_BASE_URL)
BEEHIIV_PUBLICATION_URL = os.getenv('BEEHIIV_PUBLICATION_URL', PRIMARY_CTA_URL)
BEEHIIV_EMBED_HTML = os.getenv('BEEHIIV_EMBED_HTML', '').strip()
SPONSOR_EMAIL = os.getenv('SPONSOR_EMAIL', 'sponsors@forgecore.co')


def signup_html() -> str:
    if BEEHIIV_EMBED_HTML:
        return BEEHIIV_EMBED_HTML
    return (
        "<div class='kit-placeholder'><strong>Email signup</strong>"
        "<p>Replace this block with your Beehiiv embed HTML, or click through to subscribe.</p>"
        f"<p><a class='btn btn-primary' href='{html.escape(BEEHIIV_PUBLICATION_URL)}'>Subscribe on Beehiiv</a></p></div>"
    )



def format_inline(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = re.sub(r'\[([^\]]+)\]\((https?://[^\)]+)\)', r'<a href="\2">\1</a>', text)
    return text



def md_to_html(text: str) -> str:
    out: list[str] = []
    lines = text.splitlines()
    paragraph: list[str] = []
    code_lines: list[str] = []
    in_code = False
    in_list = False

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            joined = ' '.join(line.strip() for line in paragraph if line.strip())
            out.append(f'<p>{format_inline(joined)}</p>')
            paragraph = []

    for raw_line in lines:
        line = raw_line.rstrip()
        if line.startswith('```'):
            flush_paragraph()
            if in_list:
                out.append('</ul>')
                in_list = False
            if in_code:
                out.append('<pre><code>' + html.escape('\n'.join(code_lines)) + '</code></pre>')
                code_lines = []
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue
        if not line.strip():
            flush_paragraph()
            if in_list:
                out.append('</ul>')
                in_list = False
            continue
        if line.startswith('- '):
            flush_paragraph()
            if not in_list:
                out.append('<ul>')
                in_list = True
            out.append(f'<li>{format_inline(line[2:].strip())}</li>')
            continue
        if in_list:
            out.append('</ul>')
            in_list = False
        if line.startswith('### '):
            flush_paragraph()
            out.append(f'<h3>{format_inline(line[4:].strip())}</h3>')
        elif line.startswith('## '):
            flush_paragraph()
            out.append(f'<h2>{format_inline(line[3:].strip())}</h2>')
        elif line.startswith('# '):
            flush_paragraph()
            out.append(f'<h1>{format_inline(line[2:].strip())}</h1>')
        else:
            paragraph.append(line)

    flush_paragraph()
    if in_list:
        out.append('</ul>')
    if in_code:
        out.append('<pre><code>' + html.escape('\n'.join(code_lines)) + '</code></pre>')
    return '\n'.join(out)



def issue_metadata(path: Path, text: str) -> dict[str, str]:
    title_match = re.search(r'^# (.+)$', text, flags=re.MULTILINE)
    hook_match = re.search(r'^## Hook\n(.+?)(?=^## |\Z)', text, flags=re.MULTILINE | re.DOTALL)
    issue_date = issue_date_from_path(path)
    slug = path.stem.lower()
    return {
        'title': title_match.group(1).strip() if title_match else path.stem,
        'slug': slugify(slug),
        'desc': ' '.join((hook_match.group(1).strip() if hook_match else TAGLINE).split())[:180],
        'date': issue_date,
    }



def issue_card(meta: dict[str, str]) -> str:
    return (
        "<article class='archive-card'>"
        f"<h3><a href='/{meta['slug']}/'>{html.escape(meta['title'])}</a></h3>"
        f"<p>{html.escape(meta['desc'])}</p>"
        f"<div class='meta'><span>{html.escape(meta['date'])}</span></div>"
        "</article>"
    )



def main() -> int:
    ensure_issue_contract(latest_issue_path())
    dist = WORKSPACE / 'site' / 'dist'
    dist.mkdir(parents=True, exist_ok=True)
    template = Template((WORKSPACE / 'templates' / 'site_template.html').read_text(encoding='utf-8'))

    issues: list[dict[str, str]] = []
    for path in sorted(list_issue_files(), key=lambda p: p.name, reverse=True):
        ensure_issue_contract(path)
        text = load_text(path)
        meta = issue_metadata(path, text)
        meta['html'] = md_to_html(text)
        issues.append(meta)

    cards = '\n'.join(issue_card(meta) for meta in issues)
    featured = issues[0] if issues else {'title': 'No issue yet', 'desc': TAGLINE, 'slug': '#', 'date': ''}

    for meta in issues:
        related_cards = '\n'.join(issue_card(m) for m in issues if m['slug'] != meta['slug']) or cards
        body = f"""
<header class='issue-header'>
  <div class='issue-body'>
    <p class='eyebrow'>Issue</p>
    <h1 class='issue-title'>{html.escape(meta['title'])}</h1>
    <p class='issue-dek'>{html.escape(meta['desc'])}</p>
    <div class='meta'><span>{html.escape(meta['date'])}</span></div>
  </div>
</header>
<div class='issue-body'>
  <aside class='sponsor-block'>
    <span class='sponsor-label'>Sponsored</span>
    <h2>Reach operators building with AI</h2>
    <p>This sponsor slot appears in every issue. Sponsor inquiries: <a href='mailto:{html.escape(SPONSOR_EMAIL)}'>{html.escape(SPONSOR_EMAIL)}</a>.</p>
  </aside>
  <section class='issue-content'>
    {meta['html']}
  </section>
  <section class='signup-block'>
    <p class='eyebrow'>Get the next issue</p>
    <h2>Subscribe to {html.escape(NEWSLETTER_NAME)}</h2>
    {signup_html()}
  </section>
  <section class='related-block'>
    <p class='eyebrow'>Related issues</p>
    <div class='archive-grid'>{related_cards}</div>
  </section>
</div>
"""
        page = template.render(
            title=f"{meta['title']} — {NEWSLETTER_NAME}",
            meta_description=meta['desc'],
            canonical=f"{SITE_BASE_URL}/{meta['slug']}/",
            body=body,
        )
        out_dir = dist / meta['slug']
        out_dir.mkdir(parents=True, exist_ok=True)
        write_text(out_dir / 'index.html', page)

    home_body = f"""
<section class='hero'>
  <div class='hero-copy'>
    <p class='eyebrow'>AI productivity newsletter</p>
    <h1 class='hero-title'>{html.escape(NEWSLETTER_NAME)}</h1>
    <p>{html.escape(TAGLINE)}</p>
    <div class='hero-actions'>
      <a class='btn btn-primary' href='{html.escape(PRIMARY_CTA_URL)}'>{html.escape(PRIMARY_CTA_TEXT)}</a>
      <a class='btn btn-secondary' href='/archive/'>Browse archive</a>
    </div>
  </div>
  <aside class='hero-card'>
    <p class='eyebrow'>Featured issue</p>
    <h2><a href='/{featured['slug']}/'>{html.escape(featured['title'])}</a></h2>
    <p>{html.escape(featured['desc'])}</p>
    <div class='meta'><span>{html.escape(featured['date'])}</span></div>
    {signup_html()}
  </aside>
</section>
<section class='section'>
  <div class='section-heading'>
    <p class='eyebrow'>Archive</p>
    <h2>Recent issues</h2>
    <p>{html.escape(TAGLINE)}</p>
  </div>
  <div class='archive-grid'>{cards}</div>
</section>
"""
    write_text(
        dist / 'index.html',
        template.render(title=NEWSLETTER_NAME, meta_description=TAGLINE, canonical=f'{SITE_BASE_URL}/', body=home_body),
    )

    (dist / 'archive').mkdir(exist_ok=True)
    archive_body = f"""
<section class='section'>
  <div class='section-heading'>
    <p class='eyebrow'>Archive</p>
    <h1>Every issue, in one place</h1>
    <p>Browse the full archive and subscribe for future issues.</p>
  </div>
  <div class='archive-grid'>{cards}</div>
  <section class='inline-signup'>{signup_html()}</section>
</section>
"""
    write_text(
        dist / 'archive' / 'index.html',
        template.render(title=f'Archive — {NEWSLETTER_NAME}', meta_description=f'Browse every issue of {NEWSLETTER_NAME}.', canonical=f'{SITE_BASE_URL}/archive/', body=archive_body),
    )

    (dist / 'about').mkdir(exist_ok=True)
    about_body = f"""
<section class='section'>
  <div class='section-heading'>
    <p class='eyebrow'>About</p>
    <h1>AI for people who need it to do real work</h1>
    <p>{html.escape(TAGLINE)}</p>
  </div>
  <div class='reading-width'>
    <p>{html.escape(NEWSLETTER_NAME)} is a publication for operators, founders, consultants, and technical teams who want AI to improve execution, not just generate noise.</p>
    <p>Every issue covers practical workflows, deployable tooling, local-model systems, and ROI-focused operating ideas that can be applied right away.</p>
  </div>
  <section class='inline-signup'>{signup_html()}</section>
</section>
"""
    write_text(
        dist / 'about' / 'index.html',
        template.render(title=f'About — {NEWSLETTER_NAME}', meta_description=f'About {NEWSLETTER_NAME}.', canonical=f'{SITE_BASE_URL}/about/', body=about_body),
    )

    (dist / 'advertise').mkdir(exist_ok=True)
    advertise_body = f"""
<section class='section'>
  <div class='section-heading'>
    <p class='eyebrow'>Advertise</p>
    <h1>Reach operators building with AI</h1>
    <p>Sponsor a practical publication read by builders and operators evaluating real AI systems.</p>
  </div>
  <div class='reading-width'>
    <div class='pricing-card'>
      <h2>Sponsorship options</h2>
      <ul>
        <li>Issue sponsor — starting at $250</li>
        <li>Homepage sponsor — starting at $400</li>
        <li>Bundle package — starting at $600</li>
      </ul>
      <p>Contact <a href='mailto:{html.escape(SPONSOR_EMAIL)}'>{html.escape(SPONSOR_EMAIL)}</a> to book a slot.</p>
    </div>
  </div>
</section>
"""
    write_text(
        dist / 'advertise' / 'index.html',
        template.render(title=f'Advertise — {NEWSLETTER_NAME}', meta_description=f'Sponsor {NEWSLETTER_NAME}.', canonical=f'{SITE_BASE_URL}/advertise/', body=advertise_body),
    )

    write_text(dist / 'style.css', load_text(WORKSPACE / 'static' / 'style.css'))
    write_text(dist / '_headers', '/*\n  X-Content-Type-Options: nosniff\n')
    write_text(dist / '_redirects', '/archive /archive/ 301\n/about /about/ 301\n/advertise /advertise/ 301\n')
    print(f'Published {len(issues)} issue pages to {dist}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
