#!/usr/bin/env python3
"""ForgeCore newsletter → static site publisher."""
from __future__ import annotations

import html
import os
import re
from datetime import datetime
from pathlib import Path

from jinja2 import Template

from issue_contract import (
    issue_date_from_path,
    latest_issue_path,
    list_issue_files,
    slugify,
)
from utils import WORKSPACE, load_project_env, load_text, write_text

load_project_env()

SITE_BASE_URL = os.getenv("SITE_BASE_URL", "https://news.forgecore.co").rstrip("/")
NEWSLETTER_NAME = os.getenv("NEWSLETTER_NAME", "ForgeCore")
TAGLINE = os.getenv("NEWSLETTER_TAGLINE", "Daily AI news and workflows for operators")
SUBSCRIBE_URL = os.getenv("PRIMARY_CTA_URL", "https://forgecore-newsletter.beehiiv.com/")
SPONSOR_EMAIL = os.getenv("SPONSOR_EMAIL", "sponsors@forgecore.co")
BEEHIIV_EMBED_HTML = os.getenv("BEEHIIV_EMBED_HTML", "").strip()
BEEHIIV_EMBED_HTML = re.sub(r"<script[^>]*>.*?</script>", "", BEEHIIV_EMBED_HTML, flags=re.DOTALL).strip()
BEEHIIV_EMBED_HTML = re.sub(r"<iframe\b[^>]*>.*?</iframe>", "", BEEHIIV_EMBED_HTML, flags=re.DOTALL).strip()
CURRENT_YEAR = datetime.now().year
WPM = 220

# FORGE/DAILY canonical sections
FORGE_DAILY_MARKERS = ["## THE STORY", "## QUICK HITS", "## EM'S TAKE", "## ONE THING TO TRY"]

# Vibe tag heuristics for Quick Hits bullets
VIBE_RULES = [
    (["leak", "breach", "exposed", "dump", "hack", "security"], "💀", "vibe-yikes", "Yikes"),
    (["raise", "valuation", "billion", "funding", "vc", "investor"], "💰", "vibe-money", "Money"),
    (["launch", "ship", "release", "drop", "new model", "new version", "open source", "open-source"], "🔥", "vibe-hot", "Hot"),
    (["watch", "could", "potential", "emerging", "early", "beta", "preview"], "👀", "vibe-watch", "Watch"),
    (["price", "cost", "cheaper", "competitive", "discount", "subscription"], "💡", "vibe-smart", "Smart"),
    (["sf ", "san francisco", "median home", "real estate", "housing"], "🌆", "vibe-vibe", "Vibe check"),
]

def is_forge_daily(text: str) -> bool:
    return any(marker in text for marker in FORGE_DAILY_MARKERS)


def is_valid_issue(text: str) -> bool:
    """Reject empty files and known broken stub patterns."""
    if len(text.strip()) < 200:
        return False
    broken_phrases = [
        "no concrete content returned",
        "missing content",
        "description incomplete in provided content",
        "these appear to be",
    ]
    lowered = text.lower()
    return not any(phrase in lowered for phrase in broken_phrases)


def safe_ensure_contract(path: Path) -> bool:
    """Run contract normalization only on old-format issues. Skip FORGE/DAILY and broken stubs."""
    try:
        text = load_text(path)
        if not is_valid_issue(text):
            print(f"[skip] {path.name} — stub or broken content, skipping")
            return False
        if is_forge_daily(text):
            return True
        from issue_contract import ensure_issue_contract
        ensure_issue_contract(path)
        return True
    except Exception as exc:
        print(f"[warn] {path.name} failed contract check ({exc}), skipping")
        return False


def signup_block_html(heading: str = "Get the next issue", sub: str = "") -> str:
    sub = sub or f"{TAGLINE}. Free."
    cta = (
        BEEHIIV_EMBED_HTML
        if BEEHIIV_EMBED_HTML
        else f"<a class='btn btn-primary' href='{html.escape(SUBSCRIBE_URL)}'>Subscribe Free &rarr;</a>"
    )
    return (
        "<div class='issue-cta'>"
        f"<h2>{html.escape(heading)}</h2>"
        f"<p>{html.escape(sub)}</p>"
        f"{cta}"
        "</div>"
    )


def feed_subscribe_html() -> str:
    return (
        f"<p class='feed-subscribe-text'>Join the FORGE/DAILY community &mdash; 1 email, daily, free.</p>"
        f"<form class='feed-subscribe' action='{html.escape(SUBSCRIBE_URL)}' method='get'>"
        "<input type='email' name='email' placeholder='Your email address' required>"
        "<button type='submit'>SUBSCRIBE</button>"
        "</form>"
    )


def read_time(text: str) -> str:
    return f"{max(1, round(len(text.split()) / WPM))} min read"


def strip_markdown(text: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^\)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", text)
    text = re.sub(r"^[-*]\s+", "", text, flags=re.MULTILINE)
    return " ".join(text.split()).strip()


def format_inline(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', text)
    return text


def md_to_html(text: str) -> str:
    out: list[str] = []
    lines = text.splitlines()
    paragraph: list[str] = []
    code_lines: list[str] = []
    in_code = False
    in_list = False

    def flush_para() -> None:
        nonlocal paragraph
        if paragraph:
            joined = " ".join(line.strip() for line in paragraph if line.strip())
            out.append(f"<p>{format_inline(joined)}</p>")
            paragraph = []

    for raw in lines:
        line = raw.rstrip()
        if line.startswith("```"):
            flush_para()
            if in_list:
                out.append("</ul>")
                in_list = False
            if in_code:
                out.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
                code_lines = []
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue
        if not line.strip():
            flush_para()
            if in_list:
                out.append("</ul>")
                in_list = False
            continue
        if line.startswith(("- ", "* ", "\u2022 ")):
            flush_para()
            if not in_list:
                out.append("<ul>")
                in_list = True
            body = re.sub(r"^[-*\u2022]\s+", "", line)
            out.append(f"<li>{format_inline(body.strip())}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        if line.startswith("### "):
            flush_para()
            out.append(f"<h3>{format_inline(line[4:].strip())}</h3>")
        elif line.startswith("## "):
            flush_para()
            out.append(f"<h2>{format_inline(line[3:].strip())}</h2>")
        elif line.startswith("# "):
            flush_para()
            out.append(f"<h1>{format_inline(line[2:].strip())}</h1>")
        elif re.match(r"^-{3,}$|\*{3,}$", line):
            flush_para()
            out.append("<hr>")
        else:
            paragraph.append(line)

    flush_para()
    if in_list:
        out.append("</ul>")
    if in_code:
        out.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
    return "\n".join(out)


def parse_date(date_str: str) -> dict[str, str]:
    for fmt in ("%B %d, %Y", "%Y-%m-%d", "%b %d, %Y"):
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return {"month": dt.strftime("%b").upper(), "day": str(dt.day)}
        except ValueError:
            continue
    parts = date_str.strip().split()
    return {"month": (parts[0][:3]).upper() if parts else "?", "day": parts[1].rstrip(",") if len(parts) > 1 else "?"}


def date_to_iso(date_str: str) -> str:
    for fmt in ("%B %d, %Y", "%Y-%m-%d", "%b %d, %Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


def extract_hero_image(text: str) -> str:
    match = re.search(r"!\[[^\]]*\]\((https?://[^\)]+)\)", text)
    return match.group(1) if match else ""


def extract_summary(text: str) -> str:
    story_match = re.search(r"^## THE STORY\n(.+?)(?=^## |\Z)", text, flags=re.MULTILINE | re.DOTALL)
    if story_match:
        return strip_markdown(story_match.group(1))[:180]
    hook_match = re.search(r"^## Hook\n(.+?)(?=^## |\Z)", text, flags=re.MULTILINE | re.DOTALL)
    if hook_match:
        return strip_markdown(hook_match.group(1))[:180]
    top_story_match = re.search(r"^## Top Story\n(.+?)(?=^## |\Z)", text, flags=re.MULTILINE | re.DOTALL)
    if top_story_match:
        return strip_markdown(top_story_match.group(1))[:180]
    return TAGLINE[:180]


def issue_meta(path: Path, text: str) -> dict[str, str]:
    title_match = re.search(r"^# (.+)$", text, flags=re.MULTILINE)
    raw_title = title_match.group(1).strip() if title_match else path.stem
    clean_title = re.sub(r"^title:\s*", "", raw_title, flags=re.IGNORECASE).strip() or raw_title
    date_str = issue_date_from_path(path)
    issue_slug = slugify(path.stem.lower())
    desc = extract_summary(text)
    return {
        "title": raw_title,
        "clean_title": clean_title,
        "slug": issue_slug,
        "desc": desc,
        "date": date_str,
        "pub_date": date_to_iso(date_str),
        "hero_image": extract_hero_image(text),
        "read_time": read_time(text),
        "html": md_to_html(text),
        "raw": text,
    }


def hero_block_html(meta: dict[str, str]) -> str:
    if meta.get("hero_image"):
        return (
            "<figure class='issue-hero'>"
            f"<img src='{html.escape(meta['hero_image'])}'"
            f" alt='{html.escape(meta['clean_title'])}'"
            " width='880' height='367'"
            " loading='eager' decoding='async'>"
            "</figure>"
        )
    return (
        "<div class='issue-hero'>"
        "<div class='issue-hero-placeholder'>"
        "<svg viewBox='0 0 80 80' fill='none' xmlns='http://www.w3.org/2000/svg' aria-hidden='true'>"
        "<path d='M40 8L12 24V56L40 72L68 56V24L40 8Z' stroke='currentColor' stroke-width='3' stroke-linejoin='round'/>"
        "<path d='M40 8V72M12 24H68' stroke='currentColor' stroke-width='3' stroke-linecap='round'/>"
        "</svg>"
        "</div>"
        "</div>"
    )


def feed_item_html(meta: dict[str, str]) -> str:
    thumb = (
        f"<img class='feed-item-thumb' src='{html.escape(meta['hero_image'])}'"
        f" alt='{html.escape(meta['clean_title'])}' width='88' height='64' loading='lazy'>"
        if meta.get("hero_image")
        else ""
    )
    return (
        "<li class='feed-item'>"
        "<div class='feed-item-body'>"
        f"<div class='feed-item-meta'>{html.escape(meta['date'])} &bull; {html.escape(meta['read_time'])}</div>"
        f"<div class='feed-item-title'><a href='/{meta['slug']}/'>{html.escape(meta['clean_title'])}</a></div>"
        f"<div class='feed-item-sub'>{html.escape(meta['desc'])}</div>"
        "</div>"
        + thumb
        + "</li>"
    )


def related_item_html(meta: dict[str, str]) -> str:
    dp = parse_date(meta["date"])
    return (
        "<li class='related-item'>"
        "<div class='related-date'>"
        f"<span class='related-date-month'>{dp['month']}</span>"
        f"<span class='related-date-day'>{dp['day']}</span>"
        "</div>"
        "<div class='related-info'>"
        f"<div class='related-title'><a href='/{meta['slug']}/'>{html.escape(meta['clean_title'])}</a></div>"
        f"<div class='related-read-time'>{html.escape(meta['read_time'])}</div>"
        "</div>"
        "</li>"
    )


# ── FORGE/DAILY section parsers ────────────────────────────────────────────────

def _extract_section(text: str, heading: str) -> str:
    """Pull body of a ## HEADING section (stops at next ## or end)."""
    pat = rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)"
    m = re.search(pat, text, flags=re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else ""


def _vibe_tag(bullet: str) -> tuple[str, str, str]:
    """Return (emoji, css-class, label) for a Quick Hit bullet."""
    lower = bullet.lower()
    for keywords, emoji, css, label in VIBE_RULES:
        if any(k in lower for k in keywords):
            return emoji, css, label
    return "📌", "vibe-default", "Noted"


def render_story_card(story_text: str) -> str:
    """THE STORY → a punchy callout card with the bold lede as a pull-quote."""
    lines = [l.strip() for l in story_text.splitlines() if l.strip()]
    if not lines:
        return ""
    # First bold line is the lede
    lede = ""
    body_lines = []
    for i, line in enumerate(lines):
        m = re.match(r"^\*\*(.+?)\*\*$", line)
        if m and not lede:
            lede = m.group(1)
        else:
            body_lines.append(line)
    body_html = md_to_html("\n\n".join(body_lines)) if body_lines else ""
    lede_html = f"<p class='story-lede'>{format_inline(lede)}</p>" if lede else ""
    return (
        "<section class='fd-section fd-story' id='the-story'>"
        "<div class='fd-section-label'>The Story</div>"
        f"<div class='story-card'>{lede_html}{body_html}</div>"
        "</section>"
    )


def render_quick_hits(hits_text: str) -> str:
    """QUICK HITS → scannable chip cards with auto vibe tags."""
    bullets = re.findall(r"^[-*]\s+(.+)$", hits_text, flags=re.MULTILINE)
    if not bullets:
        return ""
    items_html = ""
    for bullet in bullets:
        emoji, css, label = _vibe_tag(bullet)
        # Split on first em-dash or colon to get headline vs body
        parts = re.split(r"\s*[—–]\s*|\*\*(.+?)\*\*\s*—\s*", bullet, maxsplit=1)
        rendered = format_inline(bullet)
        items_html += (
            f"<li class='hit-item'>"
            f"<span class='hit-vibe {css}' title='{html.escape(label)}'>{emoji}</span>"
            f"<span class='hit-body'>{rendered}</span>"
            f"</li>"
        )
    return (
        "<section class='fd-section fd-hits' id='quick-hits'>"
        "<div class='fd-section-label'>Quick Hits</div>"
        f"<ul class='hits-list'>{items_html}</ul>"
        "</section>"
    )


def render_ems_take(take_text: str) -> str:
    """EM'S TAKE → sticky-note sidebar card."""
    if not take_text.strip():
        return ""
    body_html = md_to_html(take_text)
    return (
        "<section class='fd-section fd-take' id='ems-take'>"
        "<div class='fd-section-label'>Em&rsquo;s Take</div>"
        f"<div class='take-card'>{body_html}</div>"
        "</section>"
    )


def render_one_thing(try_text: str) -> str:
    """ONE THING TO TRY → terminal-style card with copy button."""
    if not try_text.strip():
        return ""
    # Detect inline code command (backtick)
    cmd_match = re.search(r"`([^`]+)`", try_text)
    cmd = cmd_match.group(1) if cmd_match else ""
    body_html = md_to_html(try_text)
    copy_btn = ""
    if cmd:
        safe_cmd = html.escape(cmd)
        copy_btn = (
            f"<button class='try-copy' onclick=\"navigator.clipboard.writeText('{safe_cmd}');"
            "this.textContent='Copied!';setTimeout(()=>this.textContent='Copy',1500)\" "
            f"aria-label='Copy command'>Copy</button>"
        )
    return (
        "<section class='fd-section fd-try' id='one-thing'>"
        "<div class='fd-section-label'>One Thing to Try</div>"
        f"<div class='try-card'>{body_html}{copy_btn}</div>"
        "</section>"
    )


def build_forge_daily_body(raw: str, meta: dict[str, str]) -> str:
    """Build the full ADHD-optimised issue body from raw markdown."""
    story   = _extract_section(raw, "THE STORY")
    hits    = _extract_section(raw, "QUICK HITS")
    take    = _extract_section(raw, "EM'S TAKE")
    try_    = _extract_section(raw, "ONE THING TO TRY")

    # Skip-nav strip at the top
    skip_nav = (
        "<div class='fd-skip-nav'>"
        "<a href='#the-story'>Story</a>"
        "<a href='#quick-hits'>Hits</a>"
        "<a href='#ems-take'>Take</a>"
        "<a href='#one-thing'>Try&nbsp;It</a>"
        f"<span class='fd-read-time'>{html.escape(meta['read_time'])}</span>"
        "</div>"
    )

    return (
        skip_nav
        + render_story_card(story)
        + render_quick_hits(hits)
        + render_ems_take(take)
        + render_one_thing(try_)
    )


# ── Page builders ──────────────────────────────────────────────────────────────

def build_issue_page(meta: dict[str, str], related_items: str) -> str:
    raw = meta.get("raw", "")
    if is_forge_daily(raw):
        issue_body = build_forge_daily_body(raw, meta)
    else:
        issue_body = f"<div class='issue-body'>{meta['html']}</div>"

    return f"""
{hero_block_html(meta)}

<article class="issue-page">
  <div class="issue-eyebrow">
    <span>{html.escape(meta['date'])}</span>
    <span>&bull;</span>
    <span>{html.escape(meta['read_time'])}</span>
    <span>&bull;</span>
    <span class="issue-tag">FORGE/DAILY</span>
  </div>

  <h1 class="issue-h1">{html.escape(meta['clean_title'])}</h1>
  <p class="issue-subtitle">{html.escape(meta['desc'])}</p>
  <hr class="issue-divider">

  <div class="issue-sponsor">
    <div class="issue-sponsor-label">Sponsored</div>
    <h2>Reach developers building with AI</h2>
    <p>Sponsor slot &mdash; <a href="mailto:{html.escape(SPONSOR_EMAIL)}">{html.escape(SPONSOR_EMAIL)}</a></p>
  </div>

  <div class="issue-body fd-body">
    {issue_body}
  </div>

  {signup_block_html()}

  <div class="related-section">
    <div class="related-label">Previous issues</div>
    <ul class="related-list">
      {related_items}
    </ul>
  </div>
</article>
"""


def build_home(issues: list[dict[str, str]]) -> str:
    items = "\n".join(feed_item_html(meta) for meta in issues)
    return f"""
<div class="feed-header">
  <div class="feed-header-title">AI news for people who don't need it explained twice.</div>
  {feed_subscribe_html()}
</div>

<div class="section-label">Latest</div>
<ul class="feed-list">
  {items}
</ul>
"""


def build_archive(issues: list[dict[str, str]]) -> str:
    items = "\n".join(feed_item_html(meta) for meta in issues)
    return f"""
<div class="page-header">
  <div class="page-eyebrow">Archive</div>
  <h1 class="page-title">Every issue, in one place</h1>
  <p class="page-sub">Browse the full archive and subscribe for future issues.</p>
</div>
<ul class="feed-list" style="max-width:640px;margin:0 auto">
  {items}
</ul>
<div style="max-width:640px;margin:32px auto 0">
  {signup_block_html('Never miss an issue', TAGLINE)}
</div>
"""


def build_about() -> str:
    return f"""
<div class="page-header">
  <div class="page-eyebrow">About</div>
  <h1 class="page-title">AI news for people who don't need it explained twice.</h1>
  <p class="page-sub">{html.escape(TAGLINE)}</p>
</div>
<div class="page-body">
  <p>{html.escape(NEWSLETTER_NAME)} is a daily newsletter for developers, Reddit power users, and technical builders who want signal, not hype.</p>
  <p>Every issue covers what actually matters today in AI \u2014 written by Em, ForgeCore's resident pattern-hunter and chaos-adjacent editorial AI.</p>
  <div style="margin-top:28px">{signup_block_html()}</div>
</div>
"""


def build_advertise() -> str:
    return f"""
<div class="page-header">
  <div class="page-eyebrow">Advertise</div>
  <h1 class="page-title">Reach developers building with AI</h1>
  <p class="page-sub">Sponsor a no-fluff publication read by technical builders and AI-forward developers.</p>
</div>
<div class="page-body">
  <div class="pricing-card">
    <h2>Sponsorship options</h2>
    <ul>
      <li>Issue sponsor &mdash; starting at $250</li>
      <li>Homepage sponsor &mdash; starting at $400</li>
      <li>Bundle package &mdash; starting at $600</li>
    </ul>
    <p style="margin-top:14px">Contact <a href="mailto:{html.escape(SPONSOR_EMAIL)}">{html.escape(SPONSOR_EMAIL)}</a> to book a slot.</p>
  </div>
</div>
"""


def main() -> int:
    dist = WORKSPACE / "site" / "dist"
    dist.mkdir(parents=True, exist_ok=True)

    template = Template((WORKSPACE / "templates" / "site_template.html").read_text(encoding="utf-8"))

    def render(
        title: str,
        desc: str,
        canonical: str,
        body: str,
        og_type: str = "website",
        hero_image: str = "",
        pub_date: str = "",
        issue_number: str = "",
    ) -> str:
        return template.render(
            title=title,
            meta_description=desc,
            canonical=canonical,
            subscribe_url=SUBSCRIBE_URL,
            year=CURRENT_YEAR,
            body=body,
            og_type=og_type,
            hero_image=hero_image,
            pub_date=pub_date,
            issue_number=issue_number,
        )

    issues: list[dict[str, str]] = []
    for path in sorted(list_issue_files(), key=lambda p: p.name, reverse=True):
        if not safe_ensure_contract(path):
            continue
        text = load_text(path)
        if not is_valid_issue(text):
            continue
        issues.append(issue_meta(path, text))

    if not issues:
        print("[warn] No valid issues found. Nothing to publish.")
        return 0

    for idx, meta in enumerate(issues):
        related_html = "\n".join(related_item_html(other) for other in issues if other["slug"] != meta["slug"])
        out_dir = dist / meta["slug"]
        out_dir.mkdir(parents=True, exist_ok=True)
        write_text(
            out_dir / "index.html",
            render(
                title=f"{meta['clean_title']} \u2014 {NEWSLETTER_NAME}",
                desc=meta["desc"],
                canonical=f"{SITE_BASE_URL}/{meta['slug']}/",
                body=build_issue_page(meta, related_html),
                og_type="article",
                hero_image=meta.get("hero_image", ""),
                pub_date=meta.get("pub_date", ""),
                issue_number=str(len(issues) - idx),
            ),
        )

    write_text(dist / "index.html", render(NEWSLETTER_NAME, TAGLINE, f"{SITE_BASE_URL}/", build_home(issues)))

    (dist / "archive").mkdir(exist_ok=True)
    write_text(
        dist / "archive" / "index.html",
        render(f"Archive \u2014 {NEWSLETTER_NAME}", f"Browse every issue of {NEWSLETTER_NAME}.", f"{SITE_BASE_URL}/archive/", build_archive(issues)),
    )

    (dist / "about").mkdir(exist_ok=True)
    write_text(
        dist / "about" / "index.html",
        render(f"About \u2014 {NEWSLETTER_NAME}", f"About {NEWSLETTER_NAME}.", f"{SITE_BASE_URL}/about/", build_about()),
    )

    (dist / "advertise").mkdir(exist_ok=True)
    write_text(
        dist / "advertise" / "index.html",
        render(f"Advertise \u2014 {NEWSLETTER_NAME}", f"Sponsor {NEWSLETTER_NAME}.", f"{SITE_BASE_URL}/advertise/", build_advertise()),
    )

    write_text(dist / "style.css", load_text(WORKSPACE / "static" / "style.css"))
    write_text(dist / "_headers", "/*\n  X-Content-Type-Options: nosniff\n  X-Frame-Options: DENY\n  Referrer-Policy: strict-origin-when-cross-origin\n")
    write_text(dist / "_redirects", "/archive /archive/ 301\n/about /about/ 301\n/advertise /advertise/ 301\n")

    print(f"Published {len(issues)} issue(s) to {dist}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
