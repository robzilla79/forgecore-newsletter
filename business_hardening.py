#!/usr/bin/env python3
"""Render ForgeCore business-growth pages after the baseline site render.

This script owns business wrapper assets competitors usually have:
- newsletter advertising / sponsor page
- real workflow-pack landing page
- sitemap and llms.txt inclusion for those pages

It is deterministic and safe to run after publish_site.py and ai_search_hardening.py.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST_DIR = ROOT / "site" / "dist"
SITE_BASE = "https://news.forgecore.co"
SIGNUP = "https://forge-daily.kit.com/232bce5a31"
SPONSOR_EMAIL = "sponsors@forgecore.co"
TAGLINE = "Practical AI workflows, tools, and ROI cases for operators"

BUSINESS_PAGES = {
    "newsletter-advertising": "Advertise with ForgeCore",
    "workflow-pack": "The Solo Operator AI Workflow Pack",
}


def safe_json_ld(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def base_page(title: str, description: str, slug: str, body: str, schema: dict) -> str:
    url = f"{SITE_BASE}/{slug}/"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <meta name="description" content="{html.escape(description)}">
  <link rel="canonical" href="{html.escape(url)}">
  <meta property="og:type" content="website">
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
    a {{ color:#38bdf8; }} .wrap {{ width:min(1040px,94vw); margin:0 auto; }}
    header, footer {{ padding:24px 0; border-bottom:1px solid #1f2937; }} footer {{ border-top:1px solid #1f2937; border-bottom:0; color:#9ca3af; }}
    .brand {{ font-weight:900; font-size:2.4rem; color:white; text-decoration:none; }} .tagline {{ color:#9ca3af; }} main {{ padding:32px 0 58px; }}
    h1 {{ font-size:clamp(2.2rem,6vw,4rem); line-height:1.02; letter-spacing:-.05em; margin:.2rem 0 1rem; }}
    h2 {{ margin-top:2rem; padding-top:1rem; border-top:1px solid #1f2937; }}
    .eyebrow {{ color:#93c5fd; text-transform:uppercase; font-size:.76rem; letter-spacing:.14em; font-weight:800; }}
    .hero {{ display:grid; grid-template-columns:minmax(0,1.2fr) minmax(280px,.8fr); gap:24px; align-items:start; }}
    .panel, .card {{ padding:20px; border:1px solid #1f2937; border-radius:20px; background:rgba(15,23,42,.75); }}
    .grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px; margin-top:18px; }}
    .button {{ display:inline-block; padding:11px 16px; border-radius:999px; background:#38bdf8; color:#04111f; font-weight:900; text-decoration:none; }}
    .button.secondary {{ background:#111827; color:#e5e7eb; border:1px solid #334155; }}
    table {{ border-collapse:collapse; width:100%; margin-top:12px; }} th, td {{ border:1px solid #334155; padding:10px; text-align:left; vertical-align:top; }}
    li {{ margin:.35rem 0; }} code, pre {{ background:#030712; border:1px solid #1f2937; border-radius:12px; }} pre {{ padding:14px; overflow:auto; }}
    @media (max-width: 840px) {{ .hero,.grid {{ grid-template-columns:1fr; }} .button {{ width:100%; text-align:center; margin-bottom:8px; }} }}
  </style>
</head>
<body>
<header><div class="wrap"><a class="brand" href="/">ForgeCore</a><p class="tagline">{html.escape(TAGLINE)}</p><p><a class="button" href="{SIGNUP}">Subscribe to the newsletter</a> <a class="button secondary" href="/workflow-pack/">Get the workflow pack</a> <a class="button secondary" href="/ai-tools/">Browse AI tools</a> <a class="button secondary" href="/newsletter-advertising/">Advertise</a></p></div></header>
<main><div class="wrap">{body}</div></main>
<footer><div class="wrap">ForgeCore helps solo operators use AI tools to build systems, save time, and create income. <a href="{SIGNUP}">Subscribe to the newsletter</a>.</div></footer>
</body>
</html>
"""


def write_page(slug: str, html_text: str) -> None:
    out = DIST_DIR / slug / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_text, encoding="utf-8")


def render_advertising_page() -> None:
    slug = "newsletter-advertising"
    title = "Advertise with ForgeCore | Reach AI-Forward Solo Operators"
    description = "Sponsor ForgeCore to reach builders, creators, consultants, indie hackers, and small business operators looking for practical AI workflows."
    schema = {"@context": "https://schema.org", "@graph": [
        {"@type": "WebPage", "name": "Advertise with ForgeCore", "url": f"{SITE_BASE}/{slug}/", "description": description},
        {"@type": "Organization", "name": "ForgeCore", "url": SITE_BASE, "email": SPONSOR_EMAIL},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "ForgeCore", "item": f"{SITE_BASE}/"},
            {"@type": "ListItem", "position": 2, "name": "Advertise", "item": f"{SITE_BASE}/{slug}/"},
        ]},
    ]}
    body = f"""
<section class="hero">
  <div>
    <div class="eyebrow">Sponsor ForgeCore</div>
    <h1>Reach operators who buy tools to save time, build systems, and create income.</h1>
    <p>ForgeCore is built for solo founders, creators, consultants, builders, indie hackers, and small business operators who want practical AI workflows instead of hype.</p>
    <p><a class="button" href="mailto:{SPONSOR_EMAIL}?subject=ForgeCore sponsorship inquiry">Email {SPONSOR_EMAIL}</a> <a class="button secondary" href="{SIGNUP}">Subscribe to see the newsletter</a></p>
  </div>
  <aside class="panel">
    <h2>Best-fit sponsors</h2>
    <ul>
      <li>AI tools for content, automation, sales, research, video, design, or operations.</li>
      <li>SaaS products for solo founders, consultants, creators, and small businesses.</li>
      <li>Workflow templates, courses, communities, and services with clear operator value.</li>
    </ul>
  </aside>
</section>
<h2>Audience</h2>
<div class="grid">
  <section class="card"><h3>Who reads ForgeCore</h3><p>Solo founders, builders, creators, consultants, indie hackers, and small business operators adopting AI workflows.</p></section>
  <section class="card"><h3>What they want</h3><p>Tools and systems that help them make money, save time, automate work, choose better tools, and avoid wasting money.</p></section>
  <section class="card"><h3>Content format</h3><p>Practical playbooks, workflow breakdowns, tool comparisons, bad-fit warnings, and implementation prompts.</p></section>
  <section class="card"><h3>Trust policy</h3><p>ForgeCore prioritizes useful recommendations, disclosure, simpler alternatives, and bad-fit warnings.</p></section>
</div>
<h2>Sponsor placements</h2>
<table>
  <tr><th>Placement</th><th>What sponsor gets</th><th>Best for</th></tr>
  <tr><td>Newsletter sponsor block</td><td>Short native placement with sponsor CTA in an AM or PM issue.</td><td>Tools and offers with broad operator fit.</td></tr>
  <tr><td>Tool of the Week</td><td>Workflow-based mention with use case, bad-fit warning, and simpler alternative.</td><td>AI/SaaS tools with a clear job-to-be-done.</td></tr>
  <tr><td>Workflow page placement</td><td>Longer-term visibility inside a relevant evergreen workflow page.</td><td>Products with strong search-intent alignment.</td></tr>
</table>
<h2>Sample sponsor block</h2>
<pre><code>Sponsored: [Tool Name] helps solo operators [specific outcome]. Use it when [best-fit use case]. Skip it if [bad-fit warning]. Learn more: [sponsor URL]</code></pre>
<h2>Starter package</h2>
<p>Start with one test placement. If the offer fits ForgeCore readers and earns clicks/replies, expand into a recurring placement or workflow-page sponsorship.</p>
<p><a class="button" href="mailto:{SPONSOR_EMAIL}?subject=ForgeCore sponsorship inquiry">Request sponsor details</a></p>
"""
    write_page(slug, base_page(title, description, slug, body, schema))


def render_workflow_pack_page() -> None:
    slug = "workflow-pack"
    title = "The Solo Operator AI Workflow Pack | ForgeCore"
    description = "A practical AI workflow pack for solo operators with checklists, prompts, tool decisions, and automation readiness guidance."
    schema = {"@context": "https://schema.org", "@graph": [
        {"@type": "WebPage", "name": "The Solo Operator AI Workflow Pack", "url": f"{SITE_BASE}/{slug}/", "description": description},
        {"@type": "CreativeWork", "name": "The Solo Operator AI Workflow Pack", "description": description, "audience": {"@type": "Audience", "audienceType": "Solo founders, creators, consultants, builders, and small business operators"}},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "ForgeCore", "item": f"{SITE_BASE}/"},
            {"@type": "ListItem", "position": 2, "name": "Workflow Pack", "item": f"{SITE_BASE}/{slug}/"},
        ]},
    ]}
    body = f"""
<section class="hero">
  <div>
    <div class="eyebrow">Free operator resource</div>
    <h1>The Solo Operator AI Workflow Pack</h1>
    <p>A practical pack for turning AI tools into repeatable systems. Built for people who need leverage, not another list of shiny apps.</p>
    <p><a class="button" href="{SIGNUP}">Subscribe and get the pack</a> <a class="button secondary" href="{SIGNUP}">Subscribe to the newsletter</a></p>
  </div>
  <aside class="panel">
    <h2>Built for</h2>
    <ul>
      <li>Solo founders</li>
      <li>Creators and newsletter operators</li>
      <li>Consultants and freelancers</li>
      <li>Indie hackers and small business operators</li>
    </ul>
  </aside>
</section>
<h2>What is inside</h2>
<div class="grid">
  <section class="card"><h3>10 workflow checklists</h3><p>Content repurposing, client onboarding, sales follow-up, newsletter growth, research, tool selection, automation, local AI, lead magnets, and weekly review.</p></section>
  <section class="card"><h3>10 copy/paste prompts</h3><p>Prompts designed to turn messy business tasks into clear steps, drafts, summaries, and decision tables.</p></section>
  <section class="card"><h3>Tool decision matrix</h3><p>Choose between manual checklist, ChatGPT, no-code automation, local AI, or a dedicated SaaS tool.</p></section>
  <section class="card"><h3>Bad-fit warning checklist</h3><p>A trust guardrail that helps you avoid buying tools when a simpler workflow is enough.</p></section>
</div>
<h2>How to use it</h2>
<ol>
  <li>Pick one workflow that repeats every week.</li>
  <li>Run it manually once using the checklist.</li>
  <li>Use the prompt to turn the workflow into a repeatable system.</li>
  <li>Only automate the stable steps.</li>
  <li>Review outputs before trusting the system with client-facing work.</li>
</ol>
<h2>Get the pack</h2>
<p>Join ForgeCore and get the workflow pack plus future operator-grade AI workflows. This signup also subscribes you to the ForgeCore newsletter.</p>
<p><a class="button" href="{SIGNUP}">Subscribe and get the pack</a></p>
"""
    write_page(slug, base_page(title, description, slug, body, schema))


def ensure_sitemap_pages() -> None:
    sitemap = DIST_DIR / "sitemap.xml"
    if not sitemap.exists():
        return
    text = sitemap.read_text(encoding="utf-8")
    additions = []
    for slug in BUSINESS_PAGES:
        loc = f"{SITE_BASE}/{slug}/"
        if loc not in text:
            additions.append(f"<url><loc>{loc}</loc></url>")
    if additions:
        text = text.replace("</urlset>", "".join(additions) + "</urlset>") if "</urlset>" in text else text + "\n" + "\n".join(additions)
        sitemap.write_text(text, encoding="utf-8")


def ensure_llms_pages() -> None:
    llms = DIST_DIR / "llms.txt"
    if not llms.exists():
        return
    text = llms.read_text(encoding="utf-8")
    lines = {
        "- Workflow Pack: https://news.forgecore.co/workflow-pack/",
        "- Advertise with ForgeCore: https://news.forgecore.co/newsletter-advertising/",
    }
    missing = [line for line in sorted(lines) if line not in text]
    if missing:
        text = text.rstrip() + "\n" + "\n".join(missing) + "\n"
        llms.write_text(text, encoding="utf-8")


def ensure_homepage_links() -> None:
    homepage = DIST_DIR / "index.html"
    if not homepage.exists():
        return
    text = homepage.read_text(encoding="utf-8")
    # Normalize any lead-magnet CTA that incorrectly points straight to the Kit form.
    text = text.replace(f'href="{SIGNUP}">Get the workflow pack</a>', 'href="/workflow-pack/">Get the workflow pack</a>')
    text = text.replace(f'href="{SIGNUP}">Get the Solo Operator AI Workflow Pack</a>', 'href="/workflow-pack/">Get the Solo Operator AI Workflow Pack</a>')
    if "Subscribe to the newsletter" not in text and "</header>" in text:
        text = text.replace("</header>", f'<div class="wrap"><p><a class="button" href="{SIGNUP}">Subscribe to the newsletter</a> <a class="button secondary" href="/workflow-pack/">Get the workflow pack</a></p></div></header>', 1)
    if "/newsletter-advertising/" in text and "/workflow-pack/" in text and "Subscribe to the newsletter" in text:
        homepage.write_text(text, encoding="utf-8")
        return
    block = """
<section class="lead-magnet"><div><div class="eyebrow">Build the business wrapper</div><h2>Subscribe to ForgeCore or get the workflow pack</h2><p>Subscribe for practical AI workflows, or preview the free Solo Operator AI Workflow Pack before joining.</p></div><a class="button" href="https://forge-daily.kit.com/232bce5a31">Subscribe to the newsletter</a> <a class="button secondary" href="/workflow-pack/">Get the workflow pack</a> <a class="button secondary" href="/newsletter-advertising/">Advertise</a></section>
"""
    text = text.replace("</div></main>", block + "</div></main>", 1) if "</div></main>" in text else text + block
    homepage.write_text(text, encoding="utf-8")


def main() -> int:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    render_advertising_page()
    render_workflow_pack_page()
    ensure_sitemap_pages()
    ensure_llms_pages()
    ensure_homepage_links()
    print("Business hardening applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
