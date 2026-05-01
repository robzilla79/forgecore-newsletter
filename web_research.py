#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from typing import Any
from urllib.parse import urlparse

import feedparser
import trafilatura
from dotenv import load_dotenv

from utils import WORKSPACE, append_text, dump_json, now_str, today_str

load_dotenv(WORKSPACE / '.env')

MAX_ARTICLES = int(os.getenv('MAX_ARTICLES_PER_RUN', '12'))
MAX_FEED_ITEMS = int(os.getenv('MAX_FEED_ITEMS_PER_SOURCE', '8'))
MIN_DOMAINS = int(os.getenv('MIN_RESEARCH_DOMAINS', '3'))
MAX_PER_DOMAIN = int(os.getenv('MAX_RESEARCH_ITEMS_PER_DOMAIN', '4'))
ISSUE_SLOT = os.getenv('ISSUE_SLOT', '').strip().lower()


def slot_suffix() -> str:
    return f'-{ISSUE_SLOT}' if ISSUE_SLOT in {'am', 'pm'} else ''


def slugify(value: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', value.lower()).strip('-')[:80] or 'item'


def domain_for(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith('www.') else host


def fetch_article(url: str) -> dict[str, Any]:
    try:
        downloaded = trafilatura.fetch_url(url)
        text = trafilatura.extract(downloaded, include_links=False, include_images=False) if downloaded else ''
        return {'url': url, 'status': 'ok' if text else 'empty', 'text': (text or '')[:7000]}
    except Exception as exc:
        return {'url': url, 'status': f'error: {exc}', 'text': ''}


def load_sources() -> list[dict[str, Any]]:
    return json.loads((WORKSPACE / 'web_sources.json').read_text(encoding='utf-8')).get('sources', [])


def collect_feed_items() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in load_sources():
        feed = feedparser.parse(source['url'])
        for entry in feed.entries[:MAX_FEED_ITEMS]:
            link = entry.get('link', '')
            if not link or link in seen:
                continue
            seen.add(link)
            items.append({
                'source': source['name'],
                'source_url': source['url'],
                'domain': domain_for(link),
                'tags': source.get('tags', []),
                'title': entry.get('title', 'Untitled'),
                'published': entry.get('published', entry.get('updated', '')),
                'link': link,
                'summary': re.sub('<[^>]+>', '', entry.get('summary', ''))[:1400],
            })
    return items


def select_diverse_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        by_domain[item.get('domain') or 'unknown'].append(item)

    selected: list[dict[str, Any]] = []
    used_urls: set[str] = set()
    domain_counts: dict[str, int] = defaultdict(int)

    # First pass: take one from as many domains as possible.
    for domain in sorted(by_domain.keys()):
        if len(selected) >= MAX_ARTICLES:
            break
        item = by_domain[domain][0]
        if item['link'] not in used_urls:
            selected.append(item)
            used_urls.add(item['link'])
            domain_counts[domain] += 1

    # Second pass: fill remaining slots without allowing one domain to dominate.
    for item in items:
        if len(selected) >= MAX_ARTICLES:
            break
        domain = item.get('domain') or 'unknown'
        if item['link'] in used_urls or domain_counts[domain] >= MAX_PER_DOMAIN:
            continue
        selected.append(item)
        used_urls.add(item['link'])
        domain_counts[domain] += 1

    unique_domains = {item.get('domain') for item in selected if item.get('domain')}
    if len(unique_domains) < MIN_DOMAINS:
        raise RuntimeError(
            f'Insufficient research source diversity before article fetch: {len(unique_domains)} domains selected; need {MIN_DOMAINS}. '
            f'Available domains: {sorted(by_domain.keys())}'
        )
    return selected[:MAX_ARTICLES]


def write_research_item(raw_dir, item: dict[str, Any], article: dict[str, Any]) -> str:
    slug = slugify(item['title'])
    path = raw_dir / f'{today_str()}-{slug}.md'
    path.write_text(
        (
            f"# {item['title']}\n\n"
            f"- Source: {item['source']}\n"
            f"- Published: {item['published']}\n"
            f"- URL: {item['link']}\n"
            f"- Domain: {item.get('domain', '')}\n"
            f"- Tags: {', '.join(item['tags'])}\n\n"
            f"## Feed summary\n\n{item['summary']}\n\n"
            f"## Extracted article text\n\n{article['text'] or 'No article text extracted.'}\n"
        ),
        encoding='utf-8',
    )
    return path.relative_to(WORKSPACE).as_posix()


def main() -> int:
    raw_dir = WORKSPACE / 'research' / 'raw'
    raw_dir.mkdir(parents=True, exist_ok=True)

    items = collect_feed_items()
    selected_items = select_diverse_items(items)

    notes: list[str] = []
    manifest: list[dict[str, Any]] = []
    for item in selected_items:
        article = fetch_article(item['link'])
        file_path = write_research_item(raw_dir, item, article)
        notes.append(f"- {item['title']} ({item['source']}) — {item.get('domain', '')} — {item['link']}")
        manifest.append({**item, **article, 'file': file_path})

    raw_intel_path = raw_dir / f'RAW-INTEL-{today_str()}{slot_suffix()}.md'
    raw_intel_path.write_text(
        f"# Raw intel refresh ({now_str()})\n\n"
        f"- Issue slot: {ISSUE_SLOT or 'default'}\n"
        f"- Selected items: {len(manifest)}\n"
        f"- Unique domains: {len({item.get('domain') for item in manifest if item.get('domain')})}\n\n"
        "## Items\n" + '\n'.join(notes) + '\n',
        encoding='utf-8',
    )
    # Keep legacy non-slot append only for compatibility, but do not use it as canonical context.
    append_text(raw_dir / f'RAW-INTEL-{today_str()}.md', f"# Raw intel refresh ({now_str()})\n\n## Items\n" + '\n'.join(notes))
    dump_json(WORKSPACE / 'state' / f'research-manifest-{today_str()}{slot_suffix()}.json', manifest)
    print(f"Fetched {len(manifest)} research items from {len({item.get('domain') for item in manifest if item.get('domain')})} domains.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
