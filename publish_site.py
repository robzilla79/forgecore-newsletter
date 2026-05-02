#!/usr/bin/env python3
"""Render ForgeCore Markdown issues into the static site.

The publisher is intentionally validation-only. It must never mutate source
issues or call issue-contract repair logic while rendering. Generation and
quality gates own content creation; this script only reads valid Markdown and
writes static HTML.
"""
from __future__ import annotations

import html
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from utils import WORKSPACE, load_text, write_text

SITE_BASE_URL = os.getenv("SITE_BASE_URL", "https://news.forgecore.co").rstrip("/")
NEWSLETTER_NAME = os.getenv("NEWSLETTER_NAME", "ForgeCore AI Productivity Brief")
NEWSLETTER_TAGLINE = os.getenv(
    "NEWSLETTER_TAGLINE",
    "Practical AI workflows, tools, and ROI cases for operators",
)
PRIMARY_CTA_TEXT = os.getenv("PRIMARY_CTA_TEXT", "Subscribe for weekly operator-grade AI workflows")
PRIMARY_CTA_URL = os.getenv("PRIMARY_CTA_URL", "https://forgecore-newsletter.beehiiv.com/")
SPONSOR_EMAIL = os.getenv("SPONSOR_EMAIL", "sponsors@forgecore.co")

CONTENT_DIR = WORKSPACE / "content" / "issues"
DIST_DIR = WORKSPACE / "site" / "dist"
REQUIRED_SECTIONS = (
    "Hook",
    "Top Story",
    "Why It Matters",
    "Highlights",
    "Tool of the Week",
    "Workflow",
    "CTA",
    "Sources",
)
BAD_MARKERS = (
    "No concrete content returned",
    "Missing Content",
    "description incomplete",
    "raw intel",
    "[EMPTY RESPONSE]",
)


def list_issue_files() -> list[Path]:
    if not CONTENT_DIR.exists():
        return []
    return sorted(CONTENT_DIR.glob("*.md"), key=issue_sort_key, reverse=True)


def issue_sort_key(path: Path) -> tuple[str, int, str]:
    stem = path.stem.lower()
    match = re.search(r"(\d{4}-\d{2}-\d{2})", stem)
    date_key = match.group(1) if match else "0000-00-00"
    if stem.endswith("-pm"):
        slot_rank = 2
    elif stem.endswith("-am"):
        slot_rank = 1
    else:
        slot_rank = 0
    return (date_key, slot_rank, path.name)


def title_from_markdown(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback.replace("-", " ").title()


def issue_iso_date(slug: str) -> str:
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})", slug)
    if not match:
        return datetime.now(timezone.utc).date().isoformat()
    year, month, day = match.groups()
    try:
        return datetime(int(year), int(month), int(day), tzinfo=timezone.utc).date().isoformat()
    except ValueError:
        return datetime.now(timezone.utc).date().isoformat()


def date_from_slug(slug: str) -> str:
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})", slug)
    if not match:
        return slug
    year, month, day = match.groups()
    try:
        return datetime(int(year), int(month), int(day)).strftime("%B %-d, %Y")
    except ValueError:
        return slug


def excerpt_from_markdown(text: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("---"):
            continue
        if stripped.startswith("-") or stripped.startswith("*"):
            continue
        lines.append(stripped)
        if len(" ".join(lines)) > 210:
            break
    excerpt = " ".join(lines)
    if len(excerpt) > 240:
        excerpt = excerpt[:237].rstrip() + "..."
    return excerpt or NEWSLETTER_TAGLINE


def meta_description(value: str) -> str:
    description = " ".join((value or NEWSLETTER_TAGLINE).split())
    if len(description) > 156:
        description = description[:153].rstrip() + "..."
    return description


def canonical_url(path: str = "") -> str:
    clean_path = path.strip("/")
    return f"{SITE_BASE_URL}/{clean_path}/" if clean_path else f"{SITE_BASE_URL}/"


def is_valid_issue(text: str) -> bool:
    if len(text.split()) < 350:
        return False
    if any(marker.lower() in text.lower() for marker in BAD_MARKERS):
        return False
    if not text.lstrip().startswith("# "):
        return False
    lower = text.lower()
    return all(f"## {section}".lower() in lower for section in REQUIRED_SECTIONS)


def inline_markdown(value: str) -> str:
    value = html.escape(value)
    value = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", value)
    value = re.sub(r"\[(.+?)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', value)
    return value


def markdown_to_html(markdown: str) -> str:
    blocks: list[str] = []
    in_list = False
    in_code = False
    code_lines: list[str] = []

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            blocks.append("</ul>")
            in_list = False

    for raw in markdown.splitlines():
        line = raw.rstrip()
        stripped = line.strip()

        if stripped.startswith("```"):
            close_list()
            if in_code:
                blocks.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
                code_lines = []
                in_code = False
            else:
                in_code = True
            continue

        if in_code:
            code_lines.append(line)
            continue

        if not stripped:
            close_list()
            continue

        if stripped.startswith("# "):
            close_list()
            blocks.append(f"<h1>{inline_markdown(stripped[2:].strip())}</h1>")
        elif stripped.startswith("## "):
            close_list()
            blocks.append(f"<h2>{inline_markdown(stripped[3:].strip())}</h2>")
        elif stripped.startswith("### "):
            close_list()
            blocks.append(f"<h3>{inline_markdown(stripped[4:].strip())}</h3>")
        elif stripped.startswith(("- ", "* ")):
            if not in_list:
                blocks.append("<ul>")
                in_list = True
            blocks.append(f"<li>{inline_markdown(stripped[2:].strip())}</li>")
        else:
            close_list()
            blocks.append(f"<p>{inline_markdown(stripped)}</p>")

    close_list()
    if in_code:
        blocks.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
    return "\n".join(blocks)


def safe_json_ld(schema: dict) -> str:
    return json.dumps(schema, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def base_template(
    title: str,
    body: str,
    description: str = "",
    *,
    canonical_path: str = "",
    og_type: str = "website",
    schema: dict | None = None,
) -> str:
    description = meta_description(description)
    url = canonical_url(canonical_path)
    escaped_title = html.escape(title)
    escaped_description = html.escape(description)
    escaped_url = html.escape(url)
    schema_html = ""
    if schema:
        schema_html = f'<script type="application/ld+json">{safe_json_ld(schema)}</script>'
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_title}</title>
  <meta name="description" content="{escaped_description}">
  <link rel="canonical" href="{escaped_url}">
  <meta property="og:type" content="{html.escape(og_type)}">
  <meta property="og:title" content="{escaped_title}">
  <meta property="og:description" content="{escaped_description}">
  <meta property="og:url" content="{escaped_url}">
  <meta property="og:site_name" content="ForgeCore">
  <meta name="twitter:card" content="summary">
  <meta name="twitter:title" content="{escaped_title}">
  <meta name="twitter:description" content="{escaped_description}">
  {schema_html}
  <style>
    :root {{ color-scheme: dark; --bg:#080b12; --panel:#111827; --text:#e5e7eb; --muted:#9ca3af; --accent:#38bdf8; --border:#1f2937; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background:radial-gradient(circle at top left,#152033 0,#080b12 42%); color:var(--text); line-height:1.65; }}
    a {{ color:var(--accent); text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    .wrap {{ width:min(980px,92vw); margin:0 auto; }}
    header {{ padding:42px 0 28px; border-bottom:1px solid var(--border); }}
    .brand {{ font-weight:800; letter-spacing:-0.04em; font-size:clamp(2rem,5vw,4rem); color:white; }}
    .tagline {{ color:var(--muted); max-width:720px; font-size:1.08rem; }}
    .cta-bar {{ margin-top:22px; display:flex; gap:12px; flex-wrap:wrap; }}
    .button {{ display:inline-block; padding:11px 16px; border-radius:999px; background:var(--accent); color:#04111f; font-weight:800; }}
    .button.secondary {{ background:transparent; color:var(--text); border:1px solid var(--border); }}
    main {{ padding:34px 0 56px; }}
    .grid {{ display:grid; gap:18px; }}
    .card {{ padding:22px; border:1px solid var(--border); border-radius:18px; background:rgba(17,24,39,.82); box-shadow:0 20px 50px rgba(0,0,0,.22); }}
    .date {{ color:var(--muted); font-size:.92rem; text-transform:uppercase; letter-spacing:.08em; }}
    .card h2 {{ margin:.35rem 0 .6rem; font-size:1.45rem; line-height:1.2; }}
    article {{ max-width:780px; }}
    article h1 {{ font-size:clamp(2rem,5vw,3.6rem); line-height:1.05; letter-spacing:-0.04em; margin:0 0 12px; }}
    article h2 {{ margin-top:2rem; padding-top:1rem; border-top:1px solid var(--border); }}
    article p, article li {{ color:#d1d5db; }}
    pre {{ overflow:auto; padding:16px; border-radius:14px; background:#030712; border:1px solid var(--border); }}
    code {{ color:#bae6fd; }}
    footer {{ border-top:1px solid var(--border); padding:26px 0 42px; color:var(--muted); font-size:.95rem; }}
  </style>
</head>
<body>
<header>
  <div class="wrap">
    <a class="brand" href="/">ForgeCore</a>
    <p class="tagline">{html.escape(NEWSLETTER_TAGLINE)}</p>
    <div class="cta-bar">
      <a class="button" href="{html.escape(PRIMARY_CTA_URL)}">{html.escape(PRIMARY_CTA_TEXT)}</a>
      <a class="button secondary" href="mailto:{html.escape(SPONSOR_EMAIL)}">Sponsor ForgeCore</a>
    </div>
  </div>
</header>
<main>
  <div class="wrap">
{body}
  </div>
</main>
<footer>
  <div class="wrap">ForgeCore helps solo operators use AI tools to build systems, save time, and create income.</div>
</footer>
</body>
</html>
"""


def issue_meta(path: Path) -> dict[str, str]:
    text = load_text(path)
    slug = path.stem.lower()
    return {
        "slug": slug,
        "title": title_from_markdown(text, slug),
        "date": date_from_slug(slug),
        "iso_date": issue_iso_date(slug),
        "excerpt": excerpt_from_markdown(text),
        "text": text,
    }


def render_home(issues: list[dict[str, str]]) -> str:
    cards = []
    for issue in issues[:24]:
        cards.append(
            f"""<section class="card">
  <div class="date">{html.escape(issue['date'])}</div>
  <h2><a href="/{html.escape(issue['slug'])}/">{html.escape(issue['title'])}</a></h2>
  <p>{html.escape(issue['excerpt'])}</p>
</section>"""
        )
    body = "<h1>Latest ForgeCore Issues</h1>\n<div class=\"grid\">\n" + "\n".join(cards) + "\n</div>"
    schema = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": "ForgeCore",
        "url": canonical_url(),
        "description": NEWSLETTER_TAGLINE,
    }
    return base_template(f"ForgeCore | {NEWSLETTER_NAME}", body, NEWSLETTER_TAGLINE, schema=schema)


def render_issue(issue: dict[str, str]) -> str:
    article_url = canonical_url(issue["slug"])
    article = f"""<article>
  <div class="date">{html.escape(issue['date'])}</div>
  {markdown_to_html(issue['text'])}
</article>"""
    schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": issue["title"],
        "description": meta_description(issue["excerpt"]),
        "datePublished": issue["iso_date"],
        "dateModified": datetime.now(timezone.utc).date().isoformat(),
        "author": {"@type": "Organization", "name": "ForgeCore"},
        "publisher": {"@type": "Organization", "name": "ForgeCore"},
        "mainEntityOfPage": {"@type": "WebPage", "@id": article_url},
        "url": article_url,
    }
    return base_template(
        f"{issue['title']} | ForgeCore",
        article,
        issue["excerpt"],
        canonical_path=issue["slug"],
        og_type="article",
        schema=schema,
    )


def render_rss(issues: list[dict[str, str]]) -> str:
    items = []
    for issue in issues[:20]:
        url = f"{SITE_BASE_URL}/{issue['slug']}/"
        items.append(
            f"""<item>
<title>{html.escape(issue['title'])}</title>
<link>{html.escape(url)}</link>
<guid>{html.escape(url)}</guid>
<description>{html.escape(issue['excerpt'])}</description>
</item>"""
        )
    return f"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0"><channel>
<title>{html.escape(NEWSLETTER_NAME)}</title>
<link>{html.escape(SITE_BASE_URL)}</link>
<description>{html.escape(NEWSLETTER_TAGLINE)}</description>
{''.join(items)}
</channel></rss>
"""


def render_sitemap(issues: list[dict[str, str]]) -> str:
    now = datetime.now(timezone.utc).date().isoformat()
    urls = [f"<url><loc>{SITE_BASE_URL}/</loc><lastmod>{now}</lastmod></url>"]
    for issue in issues:
        urls.append(f"<url><loc>{SITE_BASE_URL}/{html.escape(issue['slug'])}/</loc><lastmod>{now}</lastmod></url>")
    return "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n" + "\n".join(urls) + "\n</urlset>\n"


def main() -> None:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    issues = []
    for path in list_issue_files():
        text = load_text(path)
        if not is_valid_issue(text):
            print(f"[skip] {path.name} — invalid or broken content")
            continue
        issues.append(issue_meta(path))

    if not issues:
        raise SystemExit("No valid issues found; refusing to publish empty site")

    for issue in issues:
        issue_dir = DIST_DIR / issue["slug"]
        issue_dir.mkdir(parents=True, exist_ok=True)
        write_text(issue_dir / "index.html", render_issue(issue))

    write_text(DIST_DIR / "index.html", render_home(issues))
    write_text(DIST_DIR / "rss.xml", render_rss(issues))
    write_text(DIST_DIR / "sitemap.xml", render_sitemap(issues))
    print(f"Published {len(issues)} issues to {DIST_DIR}")


if __name__ == "__main__":
    main()
