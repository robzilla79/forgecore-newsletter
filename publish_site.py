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
from typing import Any

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
AFFILIATE_REGISTRY_PATH = WORKSPACE / "monetization" / "affiliate-registry.json"
TOOLS_PAGE_SLUG = "ai-tools"
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
    if len(excerpt) > 220:
        excerpt = excerpt[:217].rsplit(" ", 1)[0].rstrip() + "..."
    return excerpt or NEWSLETTER_TAGLINE


def meta_description(value: str) -> str:
    description = " ".join((value or NEWSLETTER_TAGLINE).split())
    if len(description) > 156:
        description = description[:153].rsplit(" ", 1)[0].rstrip() + "..."
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
    value = re.sub(r"\[(.+?)\]\(((?:https?://|mailto:)[^)]+)\)", r'<a href="\2">\1</a>', value)
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
    :root {{ color-scheme: dark; --bg:#080b12; --panel:#111827; --text:#e5e7eb; --muted:#9ca3af; --accent:#38bdf8; --accent-2:#a78bfa; --border:#1f2937; --soft:#0f172a; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background:radial-gradient(circle at top left,#172554 0,#080b12 34%,#05070d 100%); color:var(--text); line-height:1.6; }}
    a {{ color:var(--accent); text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    .wrap {{ width:min(1120px,94vw); margin:0 auto; }}
    header {{ padding:30px 0 24px; border-bottom:1px solid rgba(148,163,184,.14); }}
    .brand {{ font-weight:900; letter-spacing:-0.055em; font-size:clamp(2.2rem,6vw,4.35rem); color:white; line-height:.9; }}
    .tagline {{ color:var(--muted); max-width:760px; font-size:1.04rem; margin:14px 0 0; }}
    .eyebrow {{ color:#bae6fd; font-size:.76rem; letter-spacing:.16em; text-transform:uppercase; font-weight:800; margin-bottom:10px; }}
    .hero {{ display:grid; grid-template-columns:minmax(0,1.25fr) minmax(300px,.75fr); gap:22px; align-items:start; }}
    .hero-title {{ max-width:820px; margin:.1rem 0 .6rem; font-size:clamp(1.85rem,4.2vw,3.35rem); line-height:1.04; letter-spacing:-.045em; }}
    .hero-copy {{ max-width:720px; color:#cbd5e1; font-size:1.08rem; margin-bottom:0; }}
    .cta-bar {{ margin-top:20px; display:flex; gap:10px; flex-wrap:wrap; }}
    .button {{ display:inline-flex; align-items:center; justify-content:center; min-height:42px; padding:10px 15px; border-radius:999px; background:linear-gradient(135deg,var(--accent),var(--accent-2)); color:#04111f; font-weight:900; box-shadow:0 12px 34px rgba(56,189,248,.18); }}
    .button.secondary {{ background:rgba(15,23,42,.55); color:var(--text); border:1px solid rgba(148,163,184,.22); box-shadow:none; }}
    .button.subtle {{ background:rgba(15,23,42,.55); color:#e0f2fe; border:1px solid rgba(56,189,248,.35); box-shadow:none; }}
    main {{ padding:26px 0 54px; }}
    .section-heading {{ margin:28px 0 14px; font-size:clamp(1.35rem,2.6vw,2rem); letter-spacing:-.035em; }}
    .value-grid {{ display:grid; grid-template-columns:1fr; gap:10px; margin:0; }}
    .value-card {{ padding:14px 15px; border:1px solid rgba(148,163,184,.18); border-radius:16px; background:rgba(15,23,42,.58); color:#cbd5e1; font-size:.96rem; }}
    .value-card strong {{ display:block; color:#fff; margin-bottom:2px; }}
    .grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px; }}
    .card {{ padding:20px; border:1px solid rgba(148,163,184,.18); border-radius:20px; background:linear-gradient(180deg,rgba(17,24,39,.9),rgba(15,23,42,.72)); box-shadow:0 18px 46px rgba(0,0,0,.22); }}
    .card:hover {{ border-color:rgba(56,189,248,.45); transform:translateY(-2px); transition:.18s ease; }}
    .date {{ color:#93c5fd; font-size:.76rem; text-transform:uppercase; letter-spacing:.12em; font-weight:800; }}
    .card h2 {{ margin:.4rem 0 .55rem; font-size:1.3rem; line-height:1.16; letter-spacing:-.026em; }}
    .card p {{ color:#cbd5e1; margin:.5rem 0 .85rem; }}
    .read-link {{ font-weight:900; }}
    .article-nav {{ margin-bottom:20px; }}
    article {{ max-width:800px; }}
    article h1 {{ font-size:clamp(2rem,4.6vw,3.65rem); line-height:1.04; letter-spacing:-0.05em; margin:0 0 14px; }}
    article h2 {{ margin-top:2rem; padding-top:1rem; border-top:1px solid rgba(148,163,184,.18); letter-spacing:-.025em; }}
    article p, article li {{ color:#d1d5db; }}
    article li {{ margin:.3rem 0; }}
    .tools-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px; margin-top:18px; }}
    .tool-card {{ padding:20px; border:1px solid rgba(148,163,184,.18); border-radius:20px; background:linear-gradient(180deg,rgba(17,24,39,.94),rgba(15,23,42,.78)); }}
    .tool-card h2 {{ margin:.2rem 0 .45rem; font-size:1.35rem; letter-spacing:-.025em; }}
    .tool-meta {{ display:flex; gap:8px; flex-wrap:wrap; margin:.65rem 0 .9rem; }}
    .pill {{ display:inline-flex; align-items:center; border:1px solid rgba(148,163,184,.22); border-radius:999px; color:#cbd5e1; font-size:.76rem; font-weight:800; padding:4px 9px; text-transform:uppercase; letter-spacing:.08em; }}
    .pill.partner {{ color:#d8b4fe; border-color:rgba(216,180,254,.38); }}
    .tool-card p, .tool-card li {{ color:#cbd5e1; }}
    .tool-card ul {{ padding-left:20px; }}
    .tool-card li {{ margin:.28rem 0; }}
    .disclosure {{ margin-top:24px; padding:16px 18px; border:1px solid rgba(56,189,248,.22); border-radius:18px; background:rgba(8,47,73,.28); color:#cbd5e1; }}
    pre {{ overflow:auto; padding:16px; border-radius:16px; background:#030712; border:1px solid rgba(148,163,184,.18); box-shadow:inset 0 1px 0 rgba(255,255,255,.03); }}
    code {{ color:#bae6fd; }}
    footer {{ border-top:1px solid rgba(148,163,184,.14); padding:24px 0 38px; color:var(--muted); font-size:.95rem; }}
    @media (max-width: 860px) {{ .hero, .grid, .tools-grid {{ grid-template-columns:1fr; }} .value-grid {{ grid-template-columns:repeat(3,minmax(0,1fr)); }} }}
    @media (max-width: 640px) {{ .value-grid {{ grid-template-columns:1fr; }} header {{ padding-top:26px; }} .button {{ width:100%; }} }}
  </style>
</head>
<body>
<header>
  <div class="wrap">
    <a class="brand" href="/">ForgeCore</a>
    <p class="tagline">{html.escape(NEWSLETTER_TAGLINE)}</p>
    <div class="cta-bar">
      <a class="button" href="{html.escape(PRIMARY_CTA_URL)}">{html.escape(PRIMARY_CTA_TEXT)}</a>
      <a class="button subtle" href="/{TOOLS_PAGE_SLUG}/">Browse AI tools</a>
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


def category_label(value: str) -> str:
    return value.replace("_", " ").replace(" and ", " + ").title()


def approved_tool_link(tool: dict[str, Any]) -> str:
    for link in tool.get("approved_links", []) or []:
        if not isinstance(link, dict):
            continue
        url = str(link.get("url", "")).strip()
        if link.get("type") == "affiliate" and url.startswith("https://"):
            return url
    return ""


def load_tool_registry() -> dict[str, Any]:
    if not AFFILIATE_REGISTRY_PATH.exists():
        return {"approved_tools": []}
    try:
        data = json.loads(AFFILIATE_REGISTRY_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"approved_tools": []}
    except Exception:
        return {"approved_tools": []}


def render_tool_cards() -> str:
    registry = load_tool_registry()
    cards: list[str] = []
    tools = [tool for tool in registry.get("approved_tools", []) if isinstance(tool, dict)]
    for tool in tools:
        name = str(tool.get("name", "Unnamed tool")).strip()
        status = str(tool.get("status", "")).strip()
        category = category_label(str(tool.get("category", "AI tool")).strip())
        link = approved_tool_link(tool)
        use_when = [str(item) for item in (tool.get("use_when", []) or [])[:2]]
        avoid_when = [str(item) for item in (tool.get("do_not_use_when", []) or [])[:1]]
        alternatives = [str(item) for item in (tool.get("simpler_alternatives", []) or [])[:3]]
        partner_badge = "Partner link" if link else "Reviewed tool"
        partner_class = " partner" if link else ""
        action = (
            f'<a class="button" href="{html.escape(link)}" rel="sponsored nofollow">Visit {html.escape(name)}</a>'
            if link
            else '<span class="pill">Partner link pending</span>'
        )
        use_list = "".join(f"<li>{html.escape(item)}</li>" for item in use_when)
        avoid_list = "".join(f"<li>{html.escape(item)}</li>" for item in avoid_when)
        alt_text = ", ".join(html.escape(item) for item in alternatives) if alternatives else "a manual checklist or your existing stack"
        cards.append(
            f"""<section class="tool-card">
  <div class="tool-meta">
    <span class="pill">{html.escape(category)}</span>
    <span class="pill{partner_class}">{html.escape(partner_badge)}</span>
  </div>
  <h2>{html.escape(name)}</h2>
  <p><strong>Use it when:</strong></p>
  <ul>{use_list}</ul>
  <p><strong>Do not use it when:</strong></p>
  <ul>{avoid_list}</ul>
  <p><strong>Simpler alternatives:</strong> {alt_text}.</p>
  <div class="cta-bar">{action}</div>
</section>"""
        )
    return "\n".join(cards)


def render_tools_page() -> str:
    description = "A practical AI tools directory for solo operators, with use cases, bad-fit warnings, simpler alternatives, and approved partner links."
    body = f"""<section class="hero">
  <div>
    <div class="eyebrow">ForgeCore AI tools directory</div>
    <h1 class="hero-title">Find AI tools that actually fit the workflow.</h1>
    <p class="hero-copy">Use this directory to choose tools for content repurposing, short-form video, newsletter growth, automation, design, and operator workflows. Every tool includes when to use it, when to skip it, and simpler alternatives.</p>
  </div>
  <div class="value-grid">
    <div class="value-card"><strong>Workflow first</strong>Choose based on the job, not hype.</div>
    <div class="value-card"><strong>Trust rules</strong>Paid tools include bad-fit warnings and simpler alternatives.</div>
    <div class="value-card"><strong>Partner links</strong>Some links may earn ForgeCore a commission.</div>
  </div>
</section>
<div class="disclosure"><strong>Disclosure:</strong> ForgeCore may earn a commission if you buy through approved partner links. Recommendations are based on workflow fit, not payout. If a free checklist, existing app, or simpler tool is enough, use that first.</div>
<h2 class="section-heading">AI tools for solo operators</h2>
<div class="tools-grid">
{render_tool_cards()}
</div>"""
    schema = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": "ForgeCore AI Tools Directory",
        "url": canonical_url(TOOLS_PAGE_SLUG),
        "description": description,
    }
    return base_template(
        "AI Tools Directory for Solo Operators | ForgeCore",
        body,
        description,
        canonical_path=TOOLS_PAGE_SLUG,
        schema=schema,
    )


def render_home(issues: list[dict[str, str]]) -> str:
    cards = []
    for issue in issues[:24]:
        cards.append(
            f"""<section class="card">
  <div class="date">{html.escape(issue['date'])}</div>
  <h2><a href="/{html.escape(issue['slug'])}/">{html.escape(issue['title'])}</a></h2>
  <p>{html.escape(issue['excerpt'])}</p>
  <a class="read-link" href="/{html.escape(issue['slug'])}/">Read the workflow →</a>
</section>"""
        )
    body = """<section class="hero">
  <div>
    <div class="eyebrow">AI workflows for solo operators</div>
    <h1 class="hero-title">Build systems that save time, create leverage, and avoid tool waste.</h1>
    <p class="hero-copy">ForgeCore turns AI tool signals into practical playbooks for builders, creators, consultants, indie hackers, and small business operators.</p>
    <div class="cta-bar"><a class="button subtle" href="/ai-tools/">Browse the AI tools directory</a></div>
  </div>
  <div class="value-grid">
    <div class="value-card"><strong>Make money</strong>Workflows tied to leads, offers, content, and repeatable revenue tasks.</div>
    <div class="value-card"><strong>Save time</strong>Automate admin drag without building fragile, overcomplicated systems.</div>
    <div class="value-card"><strong>Choose tools</strong>Use what fits, avoid bad-fit spend, and know when simpler is enough.</div>
  </div>
</section>
<h2 class="section-heading">Latest operator playbooks</h2>
<div class="grid">
""" + "\n".join(cards) + "\n</div>"
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
    article = f"""<div class="article-nav"><a class="read-link" href="/">← Back to all playbooks</a> · <a class="read-link" href="/ai-tools/">Browse AI tools</a></div>
<article>
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
    urls = [
        f"<url><loc>{SITE_BASE_URL}/</loc><lastmod>{now}</lastmod></url>",
        f"<url><loc>{SITE_BASE_URL}/{TOOLS_PAGE_SLUG}/</loc><lastmod>{now}</lastmod></url>",
    ]
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

    tools_dir = DIST_DIR / TOOLS_PAGE_SLUG
    tools_dir.mkdir(parents=True, exist_ok=True)
    write_text(tools_dir / "index.html", render_tools_page())

    write_text(DIST_DIR / "index.html", render_home(issues))
    write_text(DIST_DIR / "rss.xml", render_rss(issues))
    write_text(DIST_DIR / "sitemap.xml", render_sitemap(issues))
    print(f"Published {len(issues)} issues plus AI tools directory to {DIST_DIR}")


if __name__ == "__main__":
    main()
