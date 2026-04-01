#!/usr/bin/env python3
"""ForgeCore newsletter → static site publisher."""
from __future__ import annotations

import html
import os
import re
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from jinja2 import Template

from issue_contract import (
    ensure_issue_contract,
    issue_date_from_path,
    latest_issue_path,
    list_issue_files,
    slugify,
)
from utils import WORKSPACE, load_text, write_text

load_dotenv(WORKSPACE / ".env")

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
        f"<p class='feed-subscribe-text'>Join operators building with AI &mdash; free weekly rundown.</p>"
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

        if line.startswith(("- ", "* ", "• ")):
            flush_para()
            if not in_list:
                out.append("<ul>")
                in_list = True
            body = re.sub(r"^[-*•]\s+", "", line)
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
        elif re.match(r"^-{3,}$|^\*{3,}$", line):
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


def extract_summary(text: str) -> str:
    hook_match = re.search(r"^## Hook\n(.+?)(?=^## |\Z)", text, flags=re.MULTILINE | re.DOTALL)
    if hook_match:
        summary = strip_markdown(hook_match.group(1))
        return summary[:180]
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
        "read_time": read_time(text),
        "html": md_to_html(text),
    }


def feed_item_html(meta: dict[str, str]) -> str:
    return (
        "<li class='feed-item'>"
        f"<div class='feed-item-meta'>{html.escape(meta['date'])} &bull; {html.escape(meta['read_time'])}</div>"
        f"<div class='feed-item-title'><a href='/{meta['slug']}/'>{html.escape(meta['clean_title'])}</a></div>"
        f"<div class='feed-item-sub'>{html.escape(meta['desc'])}</div>"
        "</li>"
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


def build_issue_page(meta: dict[str, str], related_items: str) -> str:
    return f"""
<article class="issue-page">
  <div class="issue-eyebrow">
    <span>{html.escape(meta['date'])}</span>
    <span>&bull;</span>
    <span>{html.escape(meta['read_time'])}</span>
    <span>&bull;</span>
    <span class="issue-tag">DAILY RUNDOWN</span>
  </div>

  <h1 class="issue-h1">{html.escape(meta['clean_title'])}</h1>
  <p class="issue-subtitle">{html.escape(meta['desc'])}</p>
  <hr class="issue-divider">

  <div class="issue-sponsor">
    <div class="issue-sponsor-label">Sponsored</div>
    <h2>Reach operators building with AI</h2>
    <p>Sponsor slot &mdash; <a href="mailto:{html.escape(SPONSOR_EMAIL)}">{html.escape(SPONSOR_EMAIL)}</a></p>
  </div>

  <div class="issue-body">
    {meta['html']}
  </div>

  {signup_block_html()}

  <div class="related-section">
    <div class="related-label">You might also like&hellip;</div>
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
  <div class="feed-header-title">Join the ForgeCore community &mdash; 1 email, daily, free</div>
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
  <h1 class="page-title">AI for people who need it to do real work</h1>
  <p class="page-sub">{html.escape(TAGLINE)}</p>
</div>
<div class="page-body">
  <p>{html.escape(NEWSLETTER_NAME)} is a daily newsletter for operators, founders, consultants, and technical teams who want AI to improve execution &mdash; not just generate noise.</p>
  <p>Every issue covers practical workflows, deployable tooling, and ROI-focused ideas you can act on today.</p>
  <div style="margin-top:28px">{signup_block_html()}</div>
</div>
"""


def build_advertise() -> str:
    return f"""
<div class="page-header">
  <div class="page-eyebrow">Advertise</div>
  <h1 class="page-title">Reach operators building with AI</h1>
  <p class="page-sub">Sponsor a practical publication read by builders evaluating real AI systems.</p>
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
    ensure_issue_contract(latest_issue_path())
    dist = WORKSPACE / "site" / "dist"
    dist.mkdir(parents=True, exist_ok=True)

    template = Template((WORKSPACE / "templates" / "site_template.html").read_text(encoding="utf-8"))

    def render(title: str, desc: str, canonical: str, body: str) -> str:
        return template.render(
            title=title,
            meta_description=desc,
            canonical=canonical,
            subscribe_url=SUBSCRIBE_URL,
            year=CURRENT_YEAR,
            body=body,
        )

    issues: list[dict[str, str]] = []
    for path in sorted(list_issue_files(), key=lambda p: p.name, reverse=True):
        ensure_issue_contract(path)
        text = load_text(path)
        issues.append(issue_meta(path, text))

    for meta in issues:
        related_html = "\n".join(
            related_item_html(other) for other in issues if other["slug"] != meta["slug"]
        )
        out_dir = dist / meta["slug"]
        out_dir.mkdir(parents=True, exist_ok=True)
        write_text(
            out_dir / "index.html",
            render(
                title=f"{meta['clean_title']} — {NEWSLETTER_NAME}",
                desc=meta["desc"],
                canonical=f"{SITE_BASE_URL}/{meta['slug']}/",
                body=build_issue_page(meta, related_html),
            ),
        )

    write_text(
        dist / "index.html",
        render(NEWSLETTER_NAME, TAGLINE, f"{SITE_BASE_URL}/", build_home(issues)),
    )

    (dist / "archive").mkdir(exist_ok=True)
    write_text(
        dist / "archive" / "index.html",
        render(
            f"Archive — {NEWSLETTER_NAME}",
            f"Browse every issue of {NEWSLETTER_NAME}.",
            f"{SITE_BASE_URL}/archive/",
            build_archive(issues),
        ),
    )

    (dist / "about").mkdir(exist_ok=True)
    write_text(
        dist / "about" / "index.html",
        render(
            f"About — {NEWSLETTER_NAME}",
            f"About {NEWSLETTER_NAME}.",
            f"{SITE_BASE_URL}/about/",
            build_about(),
        ),
    )

    (dist / "advertise").mkdir(exist_ok=True)
    write_text(
        dist / "advertise" / "index.html",
        render(
            f"Advertise — {NEWSLETTER_NAME}",
            f"Sponsor {NEWSLETTER_NAME}.",
            f"{SITE_BASE_URL}/advertise/",
            build_advertise(),
        ),
    )

    write_text(dist / "style.css", load_text(WORKSPACE / "static" / "style.css"))
    write_text(
        dist / "_headers",
        "/*\n  X-Content-Type-Options: nosniff\n  X-Frame-Options: DENY\n  Referrer-Policy: strict-origin-when-cross-origin\n",
    )
    write_text(
        dist / "_redirects",
        "/archive /archive/ 301\n/about /about/ 301\n/advertise /advertise/ 301\n",
    )

    print(f"Published {len(issues)} issue(s) to {dist}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
