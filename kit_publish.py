#!/usr/bin/env python3
"""
kit_publish.py

Reads the latest generated issue from content/issues/ and broadcasts it
to Kit (formerly ConvertKit) subscribers via the Kit API v4.

Required env vars:
  KIT_API_KEY        - API key from Kit → Settings → Developer → API Key

Optional env vars:
  KIT_SEND_MODE      - 'draft' (default) or 'public' (sends immediately)
  SITE_BASE_URL      - Used to build the web version link
  NEWSLETTER_NAME    - Used as subject fallback
  SPONSOR_EMAIL      - Used in footer

Exit codes:
  0 - sent (or skipped because already sent / no credentials)
  1 - API error
  2 - no issue found
  3 - issue already sent (idempotency guard)
"""

import os
import sys
import json
import re
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    print("[kit] ERROR: 'requests' not installed. Run: pip install requests")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
API_KEY         = os.environ.get("KIT_API_KEY", "").strip()
SEND_MODE       = os.environ.get("KIT_SEND_MODE", "draft").strip()  # draft | public
SITE_BASE_URL   = os.environ.get("SITE_BASE_URL", "https://news.forgecore.co").strip()
NEWSLETTER_NAME = os.environ.get("NEWSLETTER_NAME", "FORGE/DAILY").strip()
SPONSOR_EMAIL   = os.environ.get("SPONSOR_EMAIL", "sponsors@forgecore.co").strip()

API_BASE   = "https://api.kit.com/v4"
STATE_DIR  = Path("state")
SENT_LOG   = STATE_DIR / "kit_sent.json"
ISSUES_DIR = Path("content/issues")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def log(msg: str) -> None:
    print(f"[kit] {msg}", flush=True)


def load_sent_log() -> dict:
    if SENT_LOG.exists():
        try:
            return json.loads(SENT_LOG.read_text())
        except Exception:
            pass
    return {}


def save_sent_log(data: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    SENT_LOG.write_text(json.dumps(data, indent=2), encoding="utf-8")


def find_latest_issue() -> Path | None:
    files = sorted(ISSUES_DIR.glob("*.md"), reverse=True)
    return files[0] if files else None


def parse_frontmatter(text: str) -> tuple[dict, str]:
    meta: dict = {}
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


def inline_md(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__(.+?)__",     r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*",    r"<em>\1</em>",         text)
    text = re.sub(r"_(.+?)_",      r"<em>\1</em>",         text)
    text = re.sub(r"`(.+?)`",      r"<code>\1</code>",     text)
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', text)
    return text


def markdown_to_html(md: str) -> str:
    lines = md.split("\n")
    out: list[str] = []
    in_ul = False

    def close_ul() -> None:
        nonlocal in_ul
        if in_ul:
            out.append("</ul>")
            in_ul = False

    for line in lines:
        hm = re.match(r"^(#{1,6})\s+(.*)", line)
        if hm:
            close_ul()
            lvl = len(hm.group(1))
            out.append(f"<h{lvl}>{inline_md(hm.group(2))}</h{lvl}>")
            continue
        if re.match(r"^[-*_]{3,}\s*$", line):
            close_ul()
            out.append("<hr style='border:none;border-top:1px solid #333;margin:24px 0;'>")
            continue
        bm = re.match(r"^[\-\*\+]\s+(.*)", line)
        if bm:
            if not in_ul:
                out.append("<ul style='padding-left:20px;'>")
                in_ul = True
            out.append(f"<li style='margin-bottom:8px;'>{inline_md(bm.group(1))}</li>")
            continue
        if line.strip() == "":
            close_ul()
            out.append("")
            continue
        close_ul()
        out.append(f"<p style='margin:0 0 14px;'>{inline_md(line)}</p>")

    close_ul()
    return "\n".join(out)


def build_email_html(meta: dict, body_md: str, issue_date: str) -> str:
    web_url = f"{SITE_BASE_URL}/{issue_date}/"
    body_html = markdown_to_html(body_md)
    unsubscribe = "{{ unsubscribe_url }}"
    return f"""
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0d0d0d;">
<div style="max-width:680px;margin:0 auto;padding:32px 24px;font-family:Georgia,serif;color:#e0e0e0;background:#111;">
  <p style="font-size:12px;color:#666;margin-bottom:28px;">
    Can’t see this properly?
    <a href="{web_url}" style="color:#f97316;">Read it on the web</a>.
  </p>

  {body_html}

  <hr style="border:none;border-top:1px solid #222;margin:40px 0;">
  <p style="font-size:11px;color:#555;line-height:1.6;">
    You’re receiving this because you subscribed to {NEWSLETTER_NAME}.<br>
    <a href="{unsubscribe}" style="color:#555;">Unsubscribe</a>
  </p>
</div>
</body>
</html>
""".strip()


# ---------------------------------------------------------------------------
# Kit API v4
# ---------------------------------------------------------------------------
def create_broadcast(subject: str, email_html: str, preview_text: str) -> dict:
    url = f"{API_BASE}/broadcasts"
    headers = {
        "X-Kit-Api-Key": API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    # email_address intentionally omitted — Kit uses the account default sender.
    # Supplying an unregistered address causes a 422 "Email address not found".
    payload: dict = {
        "subject": subject,
        "content": email_html,
        "preview_text": preview_text,
        "public": SEND_MODE == "public",
    }

    log(f"POST {url}")
    log(f"Subject: {subject}")
    log(f"Mode: {SEND_MODE}")

    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    log(f"Response: {resp.status_code}")
    if resp.status_code not in (200, 201):
        log(f"ERROR: {resp.text[:1000]}")
        resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    if not API_KEY:
        log("SKIP: KIT_API_KEY not set. Add it as a GitHub secret to enable auto-send.")
        sys.exit(0)

    issue_path = find_latest_issue()
    if not issue_path:
        log("No issue found in content/issues/ — nothing to publish.")
        sys.exit(2)

    issue_date = issue_path.stem
    log(f"Found issue: {issue_path}")

    sent_log = load_sent_log()
    if issue_date in sent_log:
        log(f"Issue {issue_date} already sent to Kit (broadcast_id={sent_log[issue_date].get('broadcast_id')}). Skipping.")
        sys.exit(3)

    raw = issue_path.read_text(encoding="utf-8")
    meta, body_md = parse_frontmatter(raw)

    title = meta.get("title", f"{NEWSLETTER_NAME} — {issue_date}")
    subject = title or f"{NEWSLETTER_NAME} — {issue_date}"
    preview = meta.get("description", f"{NEWSLETTER_NAME} — {issue_date}")

    email_html = build_email_html(meta, body_md, issue_date)
    result = create_broadcast(subject, email_html, preview)

    broadcast = result.get("broadcast", result)
    broadcast_id = broadcast.get("id", "unknown")

    log(f"SUCCESS — broadcast_id={broadcast_id}")

    sent_log[issue_date] = {
        "broadcast_id": broadcast_id,
        "subject": subject,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "mode": SEND_MODE,
    }
    save_sent_log(sent_log)
    log(f"Recorded in {SENT_LOG}")


if __name__ == "__main__":
    main()
