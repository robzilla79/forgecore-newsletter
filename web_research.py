#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from typing import Any

import feedparser
import trafilatura
from dotenv import load_dotenv

from utils import WORKSPACE, append_text, dump_json, now_str, today_str

load_dotenv(WORKSPACE / '.env')

MAX_ARTICLES = int(os.getenv('MAX_ARTICLES_PER_RUN', '8'))
MAX_FEED_ITEMS = int(os.getenv('MAX_FEED_ITEMS_PER_SOURCE', '8'))


def slugify(value: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', value.lower()).strip('-')[:80] or 'item'


def fetch_article(url: str) -> dict[str, Any]:
    try:
        downloaded = trafilatura.fetch_url(url)
        text = trafilatura.extract(downloaded, include_links=False, include_images=False) if downloaded else ''
        return {'url': url, 'status': 'ok' if text else 'empty', 'text': (text or '')[:7000]}
    except Exception as exc:
        return {'url': url, 'status': f'error: {exc}', 'text': ''}


def load_sources() -> list[dict[str, Any]]:
    return json.loads((WORKSPACE / 'web_sources.json').read_text(encoding='utf-8')).get('sources', [])


def main() -> int:
    raw_dir = WORKSPACE / 'research' / 'raw'
    raw_dir.mkdir(parents=True, exist_ok=True)
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
                'tags': source.get('tags', []),
                'title': entry.get('title', 'Untitled'),
                'published': entry.get('published', entry.get('updated', '')),
                'link': link,
                'summary': re.sub('<[^>]+>', '', entry.get('summary', ''))[:1400],
            })

    notes: list[str] = []
    manifest: list[dict[str, Any]] = []
    for item in items[:MAX_ARTICLES]:
        article = fetch_article(item['link'])
        slug = slugify(item['title'])
        path = raw_dir / f'{today_str()}-{slug}.md'
        path.write_text(
            (
                f"# {item['title']}\n\n"
                f"- Source: {item['source']}\n"
                f"- Published: {item['published']}\n"
                f"- URL: {item['link']}\n"
                f"- Tags: {', '.join(item['tags'])}\n\n"
                f"## Feed summary\n\n{item['summary']}\n\n"
                f"## Extracted article text\n\n{article['text'] or 'No article text extracted.'}\n"
            ),
            encoding='utf-8',
        )
        notes.append(f"- {item['title']} ({item['source']})")
        manifest.append({**item, **article, 'file': path.relative_to(WORKSPACE).as_posix()})

    append_text(raw_dir / f'RAW-INTEL-{today_str()}.md', f"# Raw intel refresh ({now_str()})\n\n## Items\n" + '\n'.join(notes))
    dump_json(WORKSPACE / 'state' / f'research-manifest-{today_str()}.json', manifest)
    print(f'Fetched {len(manifest)} research items.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
