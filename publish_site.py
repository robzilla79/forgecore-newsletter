#!/usr/bin/env python3
"""Renders newsletter issues to static HTML in AI Secret style."""
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
NEWSLETTER_NAME = os.getenv('NEWSLETTER_NAME', 'ForgeCore')
TAGLINE = os.getenv('NEWSLETTER_TAGLINE', 'Daily AI news and workflows for operators')
PRIMARY_CTA_TEXT = os.getenv('PRIMARY_CTA_TEXT', 'Subscribe Free →')
PRIMARY_CTA_URL = os.getenv('PRIMARY_CTA_URL', SITE_BASE_URL)
BEEHIIV_PUBLICATION_URL = os.getenv('BEEHIIV_PUBLICATION_URL', PRIMARY_CTA_URL)
BEEHIIV_EMBED_HTML = os.getenv('BEEHIIV_EMBED_HTML', '').strip()
SPONSOR_EMAIL = os.getenv('SPONSOR_EMAIL', 'sponsors@forgecore.co')

WPM = 220  # average reading speed for read-time estimate


def signup_html() -> str:
    if BEEHIIV_EMBED_HTML:
        return BEEHIIV_EMBED_HTML
    return (
        f"<a class='btn btn-primary' href='{html.escape(BEEHIIV_PUBLICATION_URL)}'>"
        f"{html.escape(PRIMARY_CTA_TEXT)}</a>"
    )


def read_time(text: str) -> str:
    minutes = max(1, round(len(text.split()) / WPM))
    return f"{minutes} min read"


def format_inline(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', text)
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
        if line.startswith('- ') or line.startswith('* '):
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
        elif line.startswith('---'):
            flush_paragraph()
            out.append('<hr class="issue-divider">')
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
    dek_match = re.search(r'^(?!#|Good [Mm]orning|---)(\S.{20,})', text, flags=re.MULTILINE)
    raw_title = title_match.group(1).strip() if title_match else path.stem
    clean_title = re.sub(r'^[\U00010000-\U0010ffff\u2600-\u27ff\ufe0f\s]+', '', raw_title).strip()
    return {
        'title': raw_title,
        'clean_title': clean_title or raw_title,
        'slug': slugify(path.stem.lower()),
        'desc': ' '.join((dek_match.group(1).strip() if dek_match else TAGLINE).split())[:180],
        'date': issue_date_from_path(path),
        'read_time': read_time(text),
    }


def issue_card(meta: dict[str, str]) -> str:
    return (
        "<article class='archive-card'>"
        f"<div class='archive-card-date'>{html.escape(meta['date'])}</div>"
        f"<h3><a href='/{meta['slug']}/'>{html.escape(meta['title'])}</a></h3>"
        f"<p>{html.escape(meta['desc'])}</p>"
        "</article>"
    )


def build_issue_page(meta: dict[str, str], related_cards: str) -> str:
    return f"""
<div class='issue-meta'>
  <span class='issue-tag'>DAILY RUNDOWN</span>
  <span class='issue-date'>{html.escape(meta['date'])}</span>
  <span class='issue-read-time'>&bull; {html.escape(meta['read_time'])}</span>
</div>
<h1 class='issue-headline'>{html.escape(meta['title'])}</h1>
<p class='issue-dek'>{html.escape(meta['desc'])}</p>
<hr class='issue-divider'>

<div class='sponsor-block'>
  <span class='sponsor-label'>Sponsored</span>
  <h2>Reach operators building with AI</h2>
  <p>Sponsor slot. Contact <a href='mailto:{html.escape(SPONSOR_EMAIL)}'>{html.escape(SPONSOR_EMAIL)}</a> to book.</p>
</div>

<div class='issue-content'>
  {meta['html']}
</div>

<div class='signup-block'>
  <h2>Get the next issue</h2>
  <p>Daily AI news and workflows for operators. Free.</p>
  {signup_html()}
</div>

<div class='related-block'>
  <p class='section-eyebrow'>More issues</p>
  <div class='archive-grid'>{related_cards}</div>
</div>
"""


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
    featured = issues[0] if issues else {
        'title': 'No issue yet', 'desc': TAGLINE, 'slug': '#', 'date': '', 'read_time': ''
    }

    # Individual issue pages
    for meta in issues:
        related = '\n'.join(issue_card(m) for m in issues if m['slug'] != meta['slug'])
        body = build_issue_page(meta, related or cards)
        page = template.render(
            title=f"{meta['clean_title']} \u2014 {NEWSLETTER_NAME}",
            meta_description=meta['desc'],
            canonical=f"{SITE_BASE_URL}/{meta['slug']}/",
            subscribe_url=PRIMARY_CTA_URL,
            body=body,
        )
        out_dir = dist / meta['slug']
        out_dir.mkdir(parents=True, exist_ok=True)
        write_text(out_dir / 'index.html', page)

    # Homepage
    home_body = f"""
<section class='hero'>
  <div class='hero-copy'>
    <p class='hero-eyebrow'>AI Productivity Newsletter</p>
    <h1 class='hero-title'>&#9881;&#65039; {html.escape(NEWSLETTER_NAME)}</h1>
    <p class='hero-sub'>{html.escape(TAGLINE)}</p>
    <div class='hero-actions'>
      <a class='btn btn-primary' href='{html.escape(PRIMARY_CTA_URL)}'>{html.escape(PRIMARY_CTA_TEXT)}</a>
      <a class='btn btn-secondary' href='/archive/'>Browse archive</a>
    </div>
  </div>
  <aside class='hero-card'>
    <span class='issue-tag'>Latest issue</span>
    <h2><a href='/{featured['slug']}/'>{html.escape(featured['title'])}</a></h2>
    <p>{html.escape(featured['desc'])}</p>
    <div class='meta'>{html.escape(featured['date'])}</div>
    <br>{signup_html()}
  </aside>
</section>
<section style='margin-top:0'>
  <p class='section-eyebrow'>Archive</p>
  <h2 class='section-title'>Recent issues</h2>
  <p class='section-sub'>{html.escape(TAGLINE)}</p>
  <div class='archive-grid'>{cards}</div>
</section>
"""
    write_text(
        dist / 'index.html',
        template.render(
            title=NEWSLETTER_NAME,
            meta_description=TAGLINE,
            canonical=f'{SITE_BASE_URL}/',
            subscribe_url=PRIMARY_CTA_URL,
            body=home_body,
        ),
    )

    # Archive page
    (dist / 'archive').mkdir(exist_ok=True)
    archive_body = f"""
<section>
  <p class='section-eyebrow'>Archive</p>
  <h1 class='section-title'>Every issue, in one place</h1>
  <p class='section-sub'>Browse the full archive and subscribe for future issues.</p>
  <div class='archive-grid'>{cards}</div>
  <div style='margin-top:32px'>{signup_html()}</div>
</section>
"""
    write_text(
        dist / 'archive' / 'index.html',
        template.render(
            title=f'Archive \u2014 {NEWSLETTER_NAME}',
            meta_description=f'Browse every issue of {NEWSLETTER_NAME}.',
            canonical=f'{SITE_BASE_URL}/archive/',
            subscribe_url=PRIMARY_CTA_URL,
            body=archive_body,
        ),
    )

    # About page
    (dist / 'about').mkdir(exist_ok=True)
    about_body = f"""
<section>
  <p class='section-eyebrow'>About</p>
  <h1 class='section-title'>AI for people who need it to do real work</h1>
  <p class='section-sub'>{html.escape(TAGLINE)}</p>
  <div class='reading-width'>
    <p>{html.escape(NEWSLETTER_NAME)} is a daily newsletter for operators, founders, consultants, and technical teams who want AI to improve execution \u2014 not just generate noise.</p>
    <p>Every issue covers practical workflows, deployable tooling, and ROI-focused ideas you can act on today.</p>
  </div>
  <div style='margin-top:28px'>{signup_html()}</div>
</section>
"""
    write_text(
        dist / 'about' / 'index.html',
        template.render(
            title=f'About \u2014 {NEWSLETTER_NAME}',
            meta_description=f'About {NEWSLETTER_NAME}.',
            canonical=f'{SITE_BASE_URL}/about/',
            subscribe_url=PRIMARY_CTA_URL,
            body=about_body,
        ),
    )

    # Advertise page
    (dist / 'advertise').mkdir(exist_ok=True)
    advertise_body = f"""
<section>
  <p class='section-eyebrow'>Advertise</p>
  <h1 class='section-title'>Reach operators building with AI</h1>
  <p class='section-sub'>Sponsor a practical publication read by builders evaluating real AI systems.</p>
  <div class='reading-width'>
    <div class='pricing-card'>
      <h2>Sponsorship options</h2>
      <ul>
        <li>Issue sponsor \u2014 starting at $250</li>
        <li>Homepage sponsor \u2014 starting at $400</li>
        <li>Bundle package \u2014 starting at $600</li>
      </ul>
      <p>Contact <a href='mailto:{html.escape(SPONSOR_EMAIL)}'>{html.escape(SPONSOR_EMAIL)}</a> to book a slot.</p>
    </div>
  </div>
</section>
"""
    write_text(
        dist / 'advertise' / 'index.html',
        template.render(
            title=f'Advertise \u2014 {NEWSLETTER_NAME}',
            meta_description=f'Sponsor {NEWSLETTER_NAME}.',
            canonical=f'{SITE_BASE_URL}/advertise/',
            subscribe_url=PRIMARY_CTA_URL,
            body=advertise_body,
        ),
    )

    # Static assets
    write_text(dist / 'style.css', load_text(WORKSPACE / 'static' / 'style.css'))
    write_text(dist / '_headers', '/*\n  X-Content-Type-Options: nosniff\n  X-Frame-Options: DENY\n')
    write_text(dist / '_redirects', '/archive /archive/ 301\n/about /about/ 301\n/advertise /advertise/ 301\n')

    print(f'Published {len(issues)} issue(s) to {dist}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
