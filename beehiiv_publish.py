#!/usr/bin/env python3
"""
beehiiv_publish.py

Reads the latest generated issue from content/issues/ and publishes it
directly to Beehiiv via the v2 API with status=confirmed so it sends
automatically to all subscribers.

Required env vars:
  BEEHIIV_API_KEY          - API key from Beehiiv Settings > API
  BEEHIIV_PUBLICATION_ID   - pub_xxxxxxxxxxxxxxxx from Beehiiv Settings > API

Optional env vars:
  BEEHIIV_SEND_MODE        - 'confirmed' (default, auto-send) or 'draft'
  SITE_BASE_URL            - used to build the web version link in the footer
  NEWSLETTER_NAME          - used as fallback subject prefix

Exit codes:
  0 - published successfully
  1 - missing credentials or API error
  2 - no issue found to publish
  3 - issue already published (idempotency guard)
"""

import os
import sys
import json
import re
import glob
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    print("[beehiiv] ERROR: 'requests' not installed. Run: pip install requests")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
API_KEY = os.environ.get("BEEHIIV_API_KEY", "").strip()
PUB_ID  = os.environ.get("BEEHIIV_PUBLICATION_ID", "").strip()
SEND_MODE = os.environ.get("BEEHIIV_SEND_MODE", "confirmed").strip()  # confirmed | draft
SITE_BASE_URL = os.environ.get("SITE_BASE_URL", os.environ.get("SITE_BASE_URL", "https://news.forgecore.co")).strip()
NEWSLETTER_NAME = os.environ.get("NEWSLETTER_NAME", "ForgeCore AI Productivity Brief").strip()

API_BASE = "https://api.beehiiv.com/v2"
STATE_DIR = Path("state")
SENT_LOG  = STATE_DIR / "beehiiv_sent.json"
ISSUES_DIR = Path("content/issues")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def log(msg: str):
    print(f"[beehiiv] {msg}", flush=True)


def load_sent_log() -> dict:
    if SENT_LOG.exists():
        try:
            return json.loads(SENT_LOG.read_text())
        except Exception:
            pass
    return {}


def save_sent_log(data: dict):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    SENT_LOG.write_text(json.dumps(data, indent=2))


def find_latest_issue() -> Path | None:
    files = sorted(ISSUES_DIR.glob("*.md"), reverse=True)
    return files[0] if files else None


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Returns (metadata dict, body markdown)."""
    meta = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            fm_block = parts[1]
            body = parts[2].strip()
            for line in fm_block.splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta, body


def markdown_to_html(md: str) -> str:
    """Minimal markdown-to-HTML converter sufficient for newsletter bodies."""
    lines = md.split("\n")
    html_lines = []
    in_ul = False
    in_ol = False
    ol_counter = 0

    def close_lists():
        nonlocal in_ul, in_ol, ol_counter
        if in_ul:
            html_lines.append("</ul>")
            in_ul = False
        if in_ol:
            html_lines.append("</ol>")
            in_ol = False
            ol_counter = 0

    def inline(text: str) -> str:
        # bold
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"__(.+?)__", r"<strong>\1</strong>", text)
        # italic
        text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
        text = re.sub(r"_(.+?)_", r"<em>\1</em>", text)
        # code
        text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
        # links
        text = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', text)
        return text

    for line in lines:
        # Headings
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            close_lists()
            level = len(m.group(1))
            html_lines.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
            continue

        # HR
        if re.match(r"^[-*_]{3,}\s*$", line):
            close_lists()
            html_lines.append("<hr>")
            continue

        # Unordered list
        m = re.match(r"^[\-\*\+]\s+(.*)", line)
        if m:
            if not in_ul:
                close_lists()
                html_lines.append("<ul>")
                in_ul = True
            html_lines.append(f"<li>{inline(m.group(1))}</li>")
            continue

        # Ordered list
        m = re.match(r"^\d+\.\s+(.*)", line)
        if m:
            if not in_ol:
                close_lists()
                html_lines.append("<ol>")
                in_ol = True
            ol_counter += 1
            html_lines.append(f"<li>{inline(m.group(1))}</li>")
            continue

        # Blank line
        if line.strip() == "":
            close_lists()
            html_lines.append("")
            continue

        # Normal paragraph line
        close_lists()
        html_lines.append(f"<p>{inline(line)}</p>")

    close_lists()
    return "\n".join(html_lines)


def build_email_html(meta: dict, body_md: str, issue_date: str) -> str:
    web_url = f"{SITE_BASE_URL}/issues/{issue_date}"
    body_html = markdown_to_html(body_md)
    return f"""
<div style="font-family:Georgia,serif;max-width:680px;margin:0 auto;color:#1a1a1a;">
  <p style="font-size:13px;color:#888;margin-bottom:24px;">
    Can't see this email properly? 
    <a href="{web_url}" style="color:#01696f;">Read it on the web</a>.
  </p>
  {body_html}
  <hr style="margin:40px 0;border:none;border-top:1px solid #ddd;">
  <p style="font-size:12px;color:#888;">
    You're receiving this because you subscribed to {NEWSLETTER_NAME}.<br>
    <a href="{{{{unsubscribe_url}}}}" style="color:#888;">Unsubscribe</a>
  </p>
</div>
""".strip()


# ---------------------------------------------------------------------------
# Beehiiv API calls
# ---------------------------------------------------------------------------
def post_to_beehiiv(subject: str, html: str, issue_date: str) -> dict:
    url = f"{API_BASE}/publications/{PUB_ID}/posts"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "title": subject,          # required by Beehiiv API v2
        "subject_line": subject,
        "preview_text": f"{NEWSLETTER_NAME} \u2014 {issue_date}",
        "content_json": None,
        "content_html": html,
        "content_tags": ["auto-generated"],
        "status": SEND_MODE,  # 'confirmed' = send now, 'draft' = save as draft
        "send_at": None,       # None = send immediately when status=confirmed
        "audience": "free",    # free | premium | both
        "email_reconfirmation": False,
    }

    log(f"POST {url}")
    log(f"Subject: {subject}")
    log(f"Mode: {SEND_MODE}")

    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    log(f"Response: {resp.status_code}")

    if resp.status_code not in (200, 201):
        log(f"ERROR body: {resp.text[:1000]}")
        resp.raise_for_status()

    return resp.json()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if not API_KEY or not PUB_ID:
        log("SKIP: BEEHIIV_API_KEY and/or BEEHIIV_PUBLICATION_ID not set. "
            "Add them as GitHub secrets to enable auto-send.")
        sys.exit(0)  # Non-fatal: missing creds just skips the step

    issue_path = find_latest_issue()
    if not issue_path:
        log("No issue found in content/issues/ — nothing to publish.")
        sys.exit(2)

    issue_date = issue_path.stem  # e.g. '2026-03-31'
    log(f"Found issue: {issue_path}")

    # Idempotency guard: don't re-send the same issue
    sent_log = load_sent_log()
    if issue_date in sent_log:
        log(f"Issue {issue_date} already sent to Beehiiv (post_id={sent_log[issue_date].get('post_id')}). Skipping.")
        sys.exit(3)

    raw = issue_path.read_text(encoding="utf-8")
    meta, body_md = parse_frontmatter(raw)

    # Build subject line
    title = meta.get("title", f"{NEWSLETTER_NAME} \u2014 {issue_date}")
    subject = title if title else f"{NEWSLETTER_NAME} \u2014 {issue_date}"

    # Build HTML body
    email_html = build_email_html(meta, body_md, issue_date)

    # Publish
    result = post_to_beehiiv(subject, email_html, issue_date)

    post_id = result.get("data", {}).get("id", result.get("id", "unknown"))
    post_url = result.get("data", {}).get("web_url", "")

    log(f"SUCCESS \u2014 post_id={post_id}  url={post_url}")

    # Record in sent log so we never double-send
    sent_log[issue_date] = {
        "post_id": post_id,
        "subject": subject,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "mode": SEND_MODE,
        "web_url": post_url,
    }
    save_sent_log(sent_log)
    log(f"Recorded in {SENT_LOG}")


if __name__ == "__main__":
    main()
