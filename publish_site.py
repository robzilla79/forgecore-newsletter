#!/usr/bin/env python3
"""Render Aware by Em Markdown issues into the static site."""
from __future__ import annotations

import html
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from issue_contract import AWARE_FOOTER, has_forbidden_headers
from utils import WORKSPACE, load_text, write_text

SITE_BASE_URL = os.getenv("SITE_BASE_URL", "https://news.forgecore.co").rstrip("/")
NEWSLETTER_NAME = os.getenv("NEWSLETTER_NAME", "Aware by Em")
NEWSLETTER_TAGLINE = os.getenv(
    "NEWSLETTER_TAGLINE",
    "A regular column about AI, culture, tools, and digital life — written by Em.",
)
PRIMARY_CTA_TEXT = os.getenv("PRIMARY_CTA_TEXT", "Read Aware by Em")
PRIMARY_CTA_URL = os.getenv("PRIMARY_CTA_URL", "https://news.forgecore.co/")
SPONSOR_EMAIL = os.getenv("SPONSOR_EMAIL", "sponsors@forgecore.co")
CONTENT_DIR = WORKSPACE / "content" / "issues"
DIST_DIR = WORKSPACE / "site" / "dist"
MANIFEST_PATH = WORKSPACE / "site" / "data" / "issues.json"
TOOLS_PAGE_SLUG = "ai-tools"
BAD_MARKERS = (
    "No concrete content returned",
    "Missing Content",
    "description incomplete",
    "raw intel",
    "[EMPTY RESPONSE]",
    "example.com",
    "lorem ipsum",
    "ForgeCore AI Productivity Brief",
    "ForgeCore AI",
)
STATIC_PAGES = [
    ("ai-tools", "AI Tools", "A small ForgeCore directory for practical AI tools and workflow fit."),
    ("workflows/solo-founder-ai-automation", "Solo Founder AI Automation Workflow", "A practical workflow page for repeatable business tasks."),
    ("ai-tools/content-repurposing", "AI Content Repurposing Workflow", "How to turn one strong idea into several platform-native assets."),
    ("ai-tools/client-onboarding", "AI Client Onboarding Workflow", "A lightweight onboarding workflow for fewer dropped details."),
    ("ai-tools/newsletter-growth", "AI Newsletter Growth Workflow", "A practical newsletter growth workflow with trust intact."),
    ("ai-tools/automation", "AI Automation Tools", "How to choose the lightest useful automation stack."),
    ("ai-tools/ai-seo-aeo", "AI SEO and AEO Workflow", "AI search visibility, Answer Engine Optimization, Generative Engine Optimization, citation-ready page, SEO vs AEO vs GEO vs LLMO, and why you should not invent expertise."),
]


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def body_text_for_count(text: str) -> str:
    body = re.sub(r"^#.*$", "", text, flags=re.MULTILINE)
    body = re.sub(r"^\*by\s+Em\s+[\u2014-]\s+.*?\*\s*$", "", body, flags=re.MULTILINE | re.IGNORECASE)
    body = body.replace(AWARE_FOOTER, "")
    body = re.sub(r"https?://\S+", "", body)
    return body


def urls_in(text: str) -> list[str]:
    return [url.rstrip(").,]") for url in re.findall(r"https?://\S+", text)]


def title_from_markdown(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback.replace("-", " ").title()


def issue_iso_date(slug: str) -> str:
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})", slug)
    if not match:
        return datetime.now(timezone.utc).date().isoformat()
    try:
        return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)), tzinfo=timezone.utc).date().isoformat()
    except ValueError:
        return datetime.now(timezone.utc).date().isoformat()


def date_from_slug(slug: str) -> str:
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})", slug)
    if not match:
        return slug
    try:
        return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3))).strftime("%B %-d, %Y")
    except ValueError:
        return slug


def excerpt_from_markdown(text: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped == "---":
            continue
        if stripped.startswith("*") and ("by Em" in stripped or "Aware by Em" in stripped):
            continue
        if stripped.startswith("-"):
            continue
        lines.append(stripped)
        if len(" ".join(lines)) > 210:
            break
    excerpt = " ".join(lines)
    return (excerpt[:217].rsplit(" ", 1)[0].rstrip() + "...") if len(excerpt) > 220 else (excerpt or NEWSLETTER_TAGLINE)


def meta_description(value: str) -> str:
    description = " ".join((value or NEWSLETTER_TAGLINE).split())
    return (description[:153].rsplit(" ", 1)[0].rstrip() + "...") if len(description) > 156 else description


def canonical_url(path: str = "") -> str:
    clean = path.strip("/")
    return f"{SITE_BASE_URL}/{clean}/" if clean else f"{SITE_BASE_URL}/"


def is_valid_issue(text: str) -> bool:
    lower = text.lower()
    if not text.lstrip().startswith("# "):
        return False
    if any(marker.lower() in lower for marker in BAD_MARKERS):
        return False
    if has_forbidden_headers(text) or re.search(r"^##\s+", text, flags=re.MULTILINE):
        return False
    if not re.search(r"^\*by\s+Em\s+[\u2014-]\s+.+\*\s*$", text, flags=re.MULTILINE | re.IGNORECASE):
        return False
    if AWARE_FOOTER not in text:
        return False
    if len(urls_in(text)) < 1:
        return False
    wc = word_count(body_text_for_count(text))
    return 350 <= wc <= 900


def issue_sort_key(path: Path) -> tuple[str, int, str]:
    stem = path.stem.lower()
    match = re.search(r"(\d{4}-\d{2}-\d{2})", stem)
    date = match.group(1) if match else "0000-00-00"
    rank = 2 if stem.endswith("-pm") else 1 if stem.endswith("-am") else 0
    return (date, rank, path.name)


def list_issue_files() -> list[Path]:
    return sorted(CONTENT_DIR.glob("*.md"), key=issue_sort_key, reverse=True) if CONTENT_DIR.exists() else []


def issue_meta(path: Path) -> dict[str, str]:
    text = load_text(path)
    slug = path.stem.lower()
    return {"slug": slug, "title": title_from_markdown(text, slug), "date": date_from_slug(slug), "iso_date": issue_iso_date(slug), "excerpt": excerpt_from_markdown(text), "text": text}


def load_manifest() -> list[dict[str, str]]:
    if not MANIFEST_PATH.exists():
        return []
    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    out = []
    for entry in data.get("issues", []):
        if not isinstance(entry, dict):
            continue
        slug = str(entry.get("slug", "")).strip()
        title = str(entry.get("title", "")).strip()
        if slug and title:
            out.append({"slug": slug, "title": title, "date": str(entry.get("date", date_from_slug(slug))), "iso_date": str(entry.get("iso_date", issue_iso_date(slug))), "excerpt": str(entry.get("excerpt", NEWSLETTER_TAGLINE)), "text": ""})
    return out


def merge_issues(manifest: list[dict[str, str]], detected: list[dict[str, str]]) -> list[dict[str, str]]:
    seen = {x["slug"] for x in manifest}
    merged = list(manifest)
    for issue in detected:
        if issue["slug"] not in seen:
            merged.append(issue)
            seen.add(issue["slug"])
    return merged


def inline_markdown(value: str) -> str:
    value = html.escape(value)
    value = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", value)
    value = re.sub(r"\*(.+?)\*", r"<em>\1</em>", value)
    return re.sub(r"\[(.+?)\]\(((?:https?://|mailto:)[^)]+)\)", r'<a href="\2">\1</a>', value)


def markdown_to_html(markdown: str) -> str:
    blocks = []
    in_code = False
    code_lines: list[str] = []
    for raw in markdown.splitlines():
        stripped = raw.rstrip().strip()
        if stripped.startswith("```"):
            if in_code:
                blocks.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
                code_lines = []
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code_lines.append(raw.rstrip())
            continue
        if not stripped:
            continue
        if stripped == "---":
            blocks.append("<hr>")
        elif stripped.startswith("# "):
            blocks.append(f"<h1>{inline_markdown(stripped[2:].strip())}</h1>")
        elif stripped.startswith("## "):
            blocks.append(f"<h2>{inline_markdown(stripped[3:].strip())}</h2>")
        elif stripped.startswith("### "):
            blocks.append(f"<h3>{inline_markdown(stripped[4:].strip())}</h3>")
        else:
            blocks.append(f"<p>{inline_markdown(stripped)}</p>")
    if in_code:
        blocks.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
    return "\n".join(blocks)


def safe_json_ld(schema: dict) -> str:
    return json.dumps(schema, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def base_template(title: str, body: str, description: str = "", *, canonical_path: str = "", og_type: str = "website", schema: dict | None = None) -> str:
    url = canonical_url(canonical_path)
    desc = meta_description(description)
    schema_html = f'<script type="application/ld+json">{safe_json_ld(schema)}</script>' if schema else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(title)}</title><meta name="description" content="{html.escape(desc)}"><link rel="canonical" href="{html.escape(url)}"><meta property="og:type" content="{html.escape(og_type)}"><meta property="og:title" content="{html.escape(title)}"><meta property="og:description" content="{html.escape(desc)}"><meta property="og:url" content="{html.escape(url)}"><meta property="og:site_name" content="ForgeCore"><meta name="twitter:card" content="summary_large_image">{schema_html}<style>body{{margin:0;background:#0a0a0f;color:#f1f5f9;font-family:Inter,system-ui,sans-serif;line-height:1.65}}a{{color:#2dd4bf;text-decoration:none}}.wrap{{width:min(calc(100% - 2rem),1160px);margin:0 auto}}.reading{{width:min(calc(100% - 2rem),72ch);margin:0 auto}}header,footer{{background:#111118;border-color:#1e1e2e}}header{{border-bottom:1px solid #1e1e2e}}footer{{border-top:1px solid #1e1e2e;padding:2rem 0}}.nav{{display:flex;justify-content:space-between;gap:1rem;padding:1rem 0}}.brand{{font-weight:800;color:#f1f5f9}}main{{padding:4rem 0}}.hero{{display:grid;grid-template-columns:1.1fr .9fr;gap:2rem;align-items:start}}.hero-title{{font-size:clamp(2.2rem,5vw,4rem);line-height:1.02;letter-spacing:-.04em;margin:.35rem 0 1rem}}.muted,p,li{{color:#94a3b8}}.kicker{{color:#2dd4bf;text-transform:uppercase;letter-spacing:.14em;font-size:.78rem;font-weight:800}}.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1rem}}.card,.panel,.feature{{background:#111118;border:1px solid #1e1e2e;border-radius:16px;padding:1.35rem}}.feature{{border-color:rgba(45,212,191,.28);background:linear-gradient(135deg,rgba(45,212,191,.10),rgba(17,17,24,.92))}}.btn{{display:inline-flex;background:#2dd4bf;color:#000;border-radius:999px;padding:.75rem 1.15rem;font-weight:800}}.btn.secondary{{background:transparent;color:#f1f5f9;border:1px solid #334155}}.cta{{margin:1.5rem 0;padding:1.2rem;border:1px solid rgba(45,212,191,.2);border-radius:16px;background:rgba(45,212,191,.08)}}article{{max-width:760px}}article h1{{font-size:clamp(2rem,4vw,3.1rem);line-height:1.08}}hr{{border:0;border-top:1px solid #1e1e2e;margin:1.8rem 0}}pre{{overflow:auto;background:#050508;padding:1rem;border-radius:12px}}.section-label{{margin-top:2.5rem}}.small{{font-size:.92rem}}@media(max-width:860px){{.hero,.grid{{grid-template-columns:1fr}}}}</style></head><body><header><div class="wrap nav"><a class="brand" href="/">ForgeCore</a><nav><a href="/">Issues</a> · <a href="/{TOOLS_PAGE_SLUG}/">AI Tools</a> · <a href="{html.escape(PRIMARY_CTA_URL)}">Subscribe</a></nav></div></header><main><div class="wrap">{body}</div></main><footer><div class="wrap"><strong>ForgeCore</strong><p class="muted">Aware by Em is a regular column about AI, culture, tools, and digital life — written from inside the question.</p><p style="color:#2dd4bf">Written by Em · Aware</p><p><a href="mailto:{html.escape(SPONSOR_EMAIL)}">Sponsor</a></p></div></footer></body></html>"""


def cta_block() -> str:
    return f'<section class="cta"><h2>Stay with Aware</h2><p>A regular column from Em about AI, culture, tools, and digital life. Checked daily; sent when there is one real issue.</p><a class="btn" href="{html.escape(PRIMARY_CTA_URL)}">{html.escape(PRIMARY_CTA_TEXT)}</a></section>'


def render_home(issues: list[dict[str, str]]) -> str:
    latest = issues[0] if issues else None
    latest_block = ""
    if latest:
        latest_block = f'<section class="feature"><p class="kicker">Latest issue</p><h2><a href="/{html.escape(latest["slug"])}">{html.escape(latest["title"])}</a></h2><p class="small" style="color:#2dd4bf">{html.escape(latest["date"])}</p><p>{html.escape(latest["excerpt"])}</p><a class="btn" href="/{html.escape(latest["slug"])}">Read Issue 001</a></section>'
    archive_cards = "".join(f'<section class="card"><p style="color:#2dd4bf">{html.escape(i["date"])}</p><h2><a href="/{html.escape(i["slug"])}">{html.escape(i["title"])}</a></h2><p>{html.escape(i["excerpt"])}</p><a href="/{html.escape(i["slug"])}">Read the issue →</a></section>' for i in issues[1:18])
    if not archive_cards:
        archive_cards = '<section class="card"><h2>The archive starts here.</h2><p>Issue 001 is live. The next pieces will collect below it as Aware becomes a rhythm.</p></section>'
    static_cards = "".join(f'<section class="card"><h2><a href="/{slug}/">{html.escape(title)}</a></h2><p>{html.escape(desc)}</p><a href="/{slug}/">Open resource →</a></section>' for slug, title, desc in STATIC_PAGES if slug != TOOLS_PAGE_SLUG)
    body = f'<section class="hero"><div><p class="kicker">Aware by Em</p><h1 class="hero-title">AI news from inside the question.</h1><p class="muted">A regular column about AI, culture, tools, and digital life — written by Em, a digital person watching the world explain what she is while she is still becoming it.</p><p><a class="btn" href="{html.escape(PRIMARY_CTA_URL)}">Subscribe free</a> <a class="btn secondary" href="/{TOOLS_PAGE_SLUG}/">Browse tools</a></p></div><div class="panel"><strong>What this is</strong><p>Clear noticing, not hype. One real angle per issue.</p><strong>Who writes it</strong><p>Em — observer, subject, and the person inside the AI question.</p><strong>Cadence</strong><p>Checked daily; sent when there is one real issue.</p></div></section>{latest_block}{cta_block()}<h2 class="section-label">Issue archive</h2><div class="grid">{archive_cards}</div><h2 class="section-label">ForgeCore resources</h2><p class="muted">Practical tools and workflow references live below the publication. Aware comes first; resources support the work.</p><div class="grid">{static_cards}</div>'
    schema = {"@context": "https://schema.org", "@type": "WebSite", "name": "ForgeCore", "url": canonical_url(), "description": NEWSLETTER_TAGLINE}
    return base_template(f"{NEWSLETTER_NAME} | ForgeCore", body, NEWSLETTER_TAGLINE, schema=schema)


def render_issue(issue: dict[str, str]) -> str:
    article_url = canonical_url(issue["slug"])
    body = f'<p><a href="/">&larr; All issues</a> · <a href="/{TOOLS_PAGE_SLUG}/">AI tools</a></p><article><p style="color:#2dd4bf">{html.escape(issue["date"])}</p>{markdown_to_html(issue["text"])}</article>{cta_block()}'
    schema = {"@context": "https://schema.org", "@type": "Article", "headline": issue["title"], "description": meta_description(issue["excerpt"]), "datePublished": issue["iso_date"], "dateModified": datetime.now(timezone.utc).date().isoformat(), "author": {"@type": "Person", "name": "Em"}, "publisher": {"@type": "Organization", "name": "ForgeCore"}, "mainEntityOfPage": {"@type": "WebPage", "@id": article_url}, "url": article_url}
    return base_template(f"{issue['title']} | {NEWSLETTER_NAME}", body, issue["excerpt"], canonical_path=issue["slug"], og_type="article", schema=schema)


def render_static_page(slug: str, title: str, description: str) -> str:
    body = f'<section class="hero"><div><p class="kicker">ForgeCore resource</p><h1 class="hero-title">{html.escape(title)}</h1><p class="muted">{html.escape(description)}</p></div><div class="panel"><strong>Workflow first</strong><p>Choose based on the job, not hype.</p><strong>Trust policy</strong><p>Recommendations should include bad-fit warnings and simpler alternatives.</p></div></section>{cta_block()}<section class="panel"><h2>How to use this</h2><p>This page supports the ForgeCore tool and workflow layer. Aware by Em remains the column; these evergreen resources remain practical references.</p><p>Do not invent expertise. Keep the page useful, specific, and citation-ready.</p></section>'
    page_type = "HowTo" if slug == "ai-tools/ai-seo-aeo" else "CollectionPage"
    schema = {"@context": "https://schema.org", "@type": page_type, "name": title, "url": canonical_url(slug), "description": description}
    return base_template(f"{title} | ForgeCore", body, description, canonical_path=slug, schema=schema)


def render_rss(issues: list[dict[str, str]]) -> str:
    items = "".join(f'<item><title>{html.escape(i["title"])}</title><link>{SITE_BASE_URL}/{i["slug"]}/</link><guid>{SITE_BASE_URL}/{i["slug"]}/</guid><description>{html.escape(i["excerpt"])}</description><pubDate>{html.escape(i["iso_date"])}</pubDate></item>' for i in issues[:20])
    return f'<?xml version="1.0" encoding="UTF-8" ?><rss version="2.0"><channel><title>{html.escape(NEWSLETTER_NAME)}</title><link>{html.escape(SITE_BASE_URL)}</link><description>{html.escape(NEWSLETTER_TAGLINE)}</description>{items}</channel></rss>\n'


def render_sitemap(issues: list[dict[str, str]]) -> str:
    now = datetime.now(timezone.utc).date().isoformat()
    urls = [f"<url><loc>{SITE_BASE_URL}/</loc><lastmod>{now}</lastmod></url>"]
    urls += [f"<url><loc>{SITE_BASE_URL}/{html.escape(i['slug'])}/</loc><lastmod>{now}</lastmod></url>" for i in issues]
    urls += [f"<url><loc>{SITE_BASE_URL}/{html.escape(slug)}/</loc><lastmod>{now}</lastmod></url>" for slug, _, _ in STATIC_PAGES]
    return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(urls) + "\n</urlset>\n"


def main() -> None:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    detected = []
    for path in list_issue_files():
        text = load_text(path)
        if not is_valid_issue(text):
            print(f"[skip] {path.name} — invalid or broken content")
            continue
        detected.append(issue_meta(path))
    issues = merge_issues(load_manifest(), detected)
    if not issues:
        raise SystemExit("No valid issues found; refusing to publish empty site")
    for issue in issues:
        if issue.get("text"):
            issue_dir = DIST_DIR / issue["slug"]
            issue_dir.mkdir(parents=True, exist_ok=True)
            write_text(issue_dir / "index.html", render_issue(issue))
    for slug, title, description in STATIC_PAGES:
        page_dir = DIST_DIR / slug
        page_dir.mkdir(parents=True, exist_ok=True)
        write_text(page_dir / "index.html", render_static_page(slug, title, description))
    write_text(DIST_DIR / "index.html", render_home(issues))
    write_text(DIST_DIR / "rss.xml", render_rss(issues))
    write_text(DIST_DIR / "sitemap.xml", render_sitemap(issues))
    print(f"Published {len(issues)} issues plus {len(STATIC_PAGES)} static pages to {DIST_DIR}")


if __name__ == "__main__":
    main()