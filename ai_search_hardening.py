#!/usr/bin/env python3
"""Post-render AI search hardening for ForgeCore.

publish_site.py owns the baseline static render. This script is intentionally
small and deterministic: it runs after the baseline render and before
verify_publish.py so AI-search assets, trust markers, crawler files, and richer
structured data cannot drift silently.
"""
from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ISSUES_DIR = ROOT / "content" / "issues"
DIST_DIR = ROOT / "site" / "dist"
SITE_BASE = "https://news.forgecore.co"
SIGNUP = "https://forge-daily.kit.com/232bce5a31"
SPONSOR_EMAIL = "sponsors@forgecore.co"
LEAD_MAGNET = "The Solo Operator AI Workflow Pack"
TAGLINE = "Practical AI workflows, tools, and ROI cases for operators"


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


def latest_issue() -> Path:
    files = sorted(ISSUES_DIR.glob("*.md"), key=issue_sort_key)
    if not files:
        raise SystemExit("No issue files found")
    return files[-1]


def title_from_markdown(text: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+)$", text, flags=re.M)
    return match.group(1).strip() if match else fallback


def issue_iso_date(slug: str) -> str:
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})", slug)
    if not match:
        return datetime.now(timezone.utc).date().isoformat()
    return "-".join(match.groups())


def display_date(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%B %-d, %Y")
    except Exception:
        return iso


def excerpt(text: str) -> str:
    body = re.sub(r"^#.*$", "", text, flags=re.M)
    body = re.sub(r"```.*?```", "", body, flags=re.S)
    body = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", body)
    for line in body.splitlines():
        clean = line.strip(" -|")
        if clean and not clean.startswith("#") and len(clean.split()) > 8:
            out = " ".join(clean.split())
            return out[:153].rsplit(" ", 1)[0] + "..." if len(out) > 156 else out
    return TAGLINE


def safe_json_ld(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def inline_markdown(value: str) -> str:
    value = html.escape(value)
    value = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", value)
    value = re.sub(r"\[([^\]]+)\]\(((?:https?://|mailto:)[^)]+)\)", r'<a href="\2">\1</a>', value)
    return value


def markdown_to_html(text: str) -> str:
    blocks: list[str] = []
    in_list = False
    in_code = False
    code_lines: list[str] = []

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            blocks.append("</ul>")
            in_list = False

    for raw in text.splitlines():
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
        elif stripped.startswith("|"):
            close_list()
            blocks.append(f"<p>{inline_markdown(stripped)}</p>")
        else:
            close_list()
            blocks.append(f"<p>{inline_markdown(stripped)}</p>")
    close_list()
    if in_code:
        blocks.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
    return "\n".join(blocks)


def lead_magnet_block() -> str:
    return f"""<section class="lead-magnet"><div><div class="eyebrow">Free operator resource</div><h2>{LEAD_MAGNET}</h2><p>Get practical AI workflow checklists for content, onboarding, automation, research, tool selection, and follow-up systems.</p></div><a class="button" href="{SIGNUP}">Get the workflow pack</a></section>"""


def base_page(title: str, description: str, canonical_path: str, body: str, schema: dict, og_type: str = "website") -> str:
    url = f"{SITE_BASE}/{canonical_path.strip('/')}/" if canonical_path else f"{SITE_BASE}/"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <meta name="description" content="{html.escape(description)}">
  <link rel="canonical" href="{html.escape(url)}">
  <meta property="og:type" content="{html.escape(og_type)}">
  <meta property="og:title" content="{html.escape(title)}">
  <meta property="og:description" content="{html.escape(description)}">
  <meta property="og:url" content="{html.escape(url)}">
  <meta property="og:site_name" content="ForgeCore">
  <meta name="twitter:card" content="summary">
  <meta name="twitter:title" content="{html.escape(title)}">
  <meta name="twitter:description" content="{html.escape(description)}">
  <script type="application/ld+json">{safe_json_ld(schema)}</script>
  <style>
    body {{ margin:0; font-family:Inter, ui-sans-serif, system-ui, sans-serif; background:#080b12; color:#e5e7eb; line-height:1.65; }}
    a {{ color:#38bdf8; }} .wrap {{ width:min(920px,94vw); margin:0 auto; }} header, footer {{ padding:24px 0; border-bottom:1px solid #1f2937; }} footer {{ border-top:1px solid #1f2937; border-bottom:0; color:#9ca3af; }}
    .brand {{ font-weight:900; font-size:2.4rem; color:white; text-decoration:none; }} .tagline {{ color:#9ca3af; }} main {{ padding:28px 0 54px; }} article {{ max-width:820px; }} h1 {{ font-size:clamp(2rem,5vw,3.4rem); line-height:1.05; letter-spacing:-.04em; }} h2 {{ margin-top:2rem; padding-top:1rem; border-top:1px solid #1f2937; }}
    table, th, td {{ border:1px solid #334155; border-collapse:collapse; }} th, td {{ padding:8px; }} pre {{ overflow:auto; padding:16px; background:#030712; border:1px solid #1f2937; border-radius:14px; }}
    .button {{ display:inline-block; padding:10px 14px; border-radius:999px; background:#38bdf8; color:#04111f; font-weight:900; text-decoration:none; }} .lead-magnet {{ margin-top:24px; padding:18px; border:1px solid #164e63; border-radius:18px; background:#082f49; }} .eyebrow,.date {{ color:#93c5fd; text-transform:uppercase; font-size:.76rem; letter-spacing:.12em; font-weight:800; }}
  </style>
</head>
<body>
<header><div class="wrap"><a class="brand" href="/">ForgeCore</a><p class="tagline">{html.escape(TAGLINE)}</p><p><a class="button" href="{SIGNUP}">Subscribe for weekly operator-grade AI workflows</a> <a href="/ai-tools/">Browse AI tools</a> <a href="mailto:{SPONSOR_EMAIL}">Sponsor ForgeCore</a></p></div></header>
<main><div class="wrap">{body}</div></main>
<footer><div class="wrap">ForgeCore helps solo operators use AI tools to build systems, save time, and create income.</div></footer>
</body>
</html>
"""


def render_latest_article() -> None:
    issue = latest_issue()
    slug = issue.stem.lower()
    text = issue.read_text(encoding="utf-8")
    title = title_from_markdown(text, slug.replace("-", " ").title())
    iso = issue_iso_date(slug)
    desc = excerpt(text)
    url = f"{SITE_BASE}/{slug}/"
    schema = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "Article", "headline": title, "description": desc, "keywords": ["local AI", "client data workflow", "AI workflow", "solo operators", "Ollama"], "about": ["Local AI", "Client data management", "AI search trust warnings"], "datePublished": iso, "dateModified": iso, "author": {"@type": "Organization", "name": "ForgeCore"}, "publisher": {"@type": "Organization", "name": "ForgeCore"}, "mainEntityOfPage": {"@type": "WebPage", "@id": url}, "url": url},
            {"@type": "BreadcrumbList", "itemListElement": [{"@type": "ListItem", "position": 1, "name": "ForgeCore", "item": f"{SITE_BASE}/"}, {"@type": "ListItem", "position": 2, "name": title, "item": url}]},
        ],
    }
    body = f"<div class=\"article-nav\"><a class=\"read-link\" href=\"/\">← Back to all playbooks</a> · <a class=\"read-link\" href=\"/ai-tools/\">Browse AI tools</a></div><article><div class=\"date\">{display_date(iso)}</div>{markdown_to_html(text)}</article>{lead_magnet_block()}"
    html_text = base_page(f"{title} | ForgeCore", desc, slug, body, schema, og_type="article")
    out = DIST_DIR / slug / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_text, encoding="utf-8")


def render_ai_search_page() -> None:
    slug = "ai-tools/ai-seo-aeo"
    title = "AI SEO and AEO Workflow | ForgeCore"
    desc = "Audit content for AI search visibility with definitions, sources, examples, comparisons, workflow steps, schema opportunities, and trust warnings."
    url = f"{SITE_BASE}/{slug}/"
    schema = {"@context": "https://schema.org", "@graph": [
        {"@type": "CollectionPage", "name": "AI SEO and AEO Workflow", "url": url, "description": desc},
        {"@type": "HowTo", "name": "AI search visibility audit workflow", "step": [
            {"@type": "HowToStep", "name": "Pick one buyer-intent query cluster"},
            {"@type": "HowToStep", "name": "Check Google, ChatGPT, Perplexity, and one SEO tool"},
            {"@type": "HowToStep", "name": "Record cited URLs and repeated claims"},
            {"@type": "HowToStep", "name": "Add missing definitions, examples, comparisons, sources, warnings, and schema"},
            {"@type": "HowToStep", "name": "Recheck the same query in 30 days"},
        ]},
        {"@type": "BreadcrumbList", "itemListElement": [{"@type": "ListItem", "position": 1, "name": "ForgeCore", "item": f"{SITE_BASE}/"}, {"@type": "ListItem", "position": 2, "name": "AI Tools", "item": f"{SITE_BASE}/ai-tools/"}, {"@type": "ListItem", "position": 3, "name": "AI SEO and AEO Workflow", "item": url}]},
    ]}
    body = f"""
<section class="hero"><div><div class="eyebrow">AI tools by workflow</div><h1>AI SEO and AEO Workflow</h1><p>Build pages that can rank in search and earn citations in answer engines by being useful, specific, sourced, and trustworthy.</p></div></section>
{lead_magnet_block()}
<h2>Definitions</h2>
<ul>
<li><strong>AI search visibility</strong>: the chance that AI answer engines can understand, trust, summarize, cite, or surface a page for a relevant question.</li>
<li><strong>Answer Engine Optimization</strong>: improving visible content so answer engines can extract clear, source-supported answers.</li>
<li><strong>Generative Engine Optimization</strong>: structuring content so generative search systems can understand entities, evidence, examples, and caveats.</li>
<li><strong>Citation-ready page</strong>: a page with a direct answer, examples, comparisons, sources, workflow steps, schema, and trust warnings.</li>
</ul>
<h2>Worked example</h2>
<p>Query: <strong>AI client onboarding workflow</strong>. A citation-ready ForgeCore page should define the workflow, list inputs, show setup steps, compare tool options, include a copyable prompt, cite official tool docs, and warn when automation should stay human-reviewed.</p>
<h2>SEO vs AEO vs GEO vs LLMO</h2>
<p>| Method | Goal | Page asset to add | Bad practice to avoid |</p>
<p>|---|---|---|---|</p>
<p>| SEO | Rank and earn clicks | Search-intent title, internal links, crawlable text | Keyword stuffing |</p>
<p>| AEO | Be extracted as an answer | Definitions, short answers, FAQs, sources | Unsupported claims |</p>
<p>| GEO | Be useful in generated summaries | Examples, comparisons, entities, proof | Fake authority |</p>
<p>| LLMO | Help models parse the site | Clear navigation, llms.txt, canonical hubs | Treating llms.txt as a ranking guarantee |</p>
<h2>Workflow</h2>
<ol><li>Choose one buyer-intent query cluster.</li><li>Check what Google, Perplexity, and ChatGPT cite or summarize.</li><li>Record cited brands, URLs, content format, and repeated claims.</li><li>Compare cited pages against your page.</li><li>Add missing definitions, examples, comparisons, sources, trust warnings, and schema.</li><li>Validate that structured data matches visible page content.</li><li>Recheck the query in 30 days.</li></ol>
<h2>Trust warnings</h2>
<ul><li>Do not invent expertise.</li><li>Do not publish unsupported stats.</li><li>Do not hide affiliate incentives.</li><li>Do not use schema for content that is not visible.</li><li>Do not assume llms.txt is a ranking signal; treat it as a low-cost content map.</li></ul>
<h2>Prompt to copy</h2>
<pre><code>Audit this page for AI search visibility. Identify missing examples, sources, definitions, workflow steps, comparisons, schema opportunities, and trust warnings.</code></pre>
"""
    out = DIST_DIR / slug / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(base_page(title, desc, slug, body, schema), encoding="utf-8")


def write_robots() -> None:
    (DIST_DIR / "robots.txt").write_text("""User-agent: *
Allow: /

User-agent: OAI-SearchBot
Allow: /

User-agent: ChatGPT-User
Allow: /

User-agent: PerplexityBot
Allow: /

Sitemap: https://news.forgecore.co/sitemap.xml
""", encoding="utf-8")


def write_llms() -> None:
    (DIST_DIR / "llms.txt").write_text("""# ForgeCore

ForgeCore helps solo founders, creators, consultants, builders, indie hackers, and small business operators use AI tools to build systems, save time, and create income.

## Start here

- AI Tools Directory: https://news.forgecore.co/ai-tools/
- AI SEO and AEO Workflow: https://news.forgecore.co/ai-tools/ai-seo-aeo/
- AI Content Repurposing Workflow: https://news.forgecore.co/ai-tools/content-repurposing/
- AI Client Onboarding Workflow: https://news.forgecore.co/ai-tools/client-onboarding/
- AI Automation Tools for Solo Operators: https://news.forgecore.co/ai-tools/automation/
- Newsletter Growth Workflow: https://news.forgecore.co/ai-tools/newsletter-growth/

## Best content types

ForgeCore publishes practical AI workflows, tool comparisons, operator playbooks, bad-fit warnings, and monetization-focused AI systems for solo operators.

## Trust policy

ForgeCore recommendations should include workflow fit, simpler alternatives, bad-fit warnings, and disclosure when partner or affiliate links are used. llms.txt is a content map, not a ranking guarantee.
""", encoding="utf-8")


def enrich_rss_pubdates() -> None:
    rss = DIST_DIR / "rss.xml"
    if not rss.exists():
        return
    text = rss.read_text(encoding="utf-8")
    if "<pubDate>" in text:
        return
    def add_pubdate(match: re.Match[str]) -> str:
        item = match.group(0)
        slug_match = re.search(r"https://news\.forgecore\.co/(\d{4}-\d{2}-\d{2})(?:-[a-z]+)?/", item)
        date = slug_match.group(1) if slug_match else datetime.now(timezone.utc).date().isoformat()
        dt = datetime.fromisoformat(date).replace(tzinfo=timezone.utc)
        return item.replace("</guid>", f"</guid><pubDate>{format_datetime(dt)}</pubDate>", 1)
    text = re.sub(r"<item>.*?</item>", add_pubdate, text, flags=re.S)
    rss.write_text(text, encoding="utf-8")


def main() -> int:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    render_latest_article()
    render_ai_search_page()
    write_robots()
    write_llms()
    enrich_rss_pubdates()
    print("AI search hardening applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
