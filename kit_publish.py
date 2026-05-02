#!/usr/bin/env python3
"""
kit_publish.py

Publishes the current ForgeCore issue to Kit (formerly ConvertKit) as a
broadcast draft by default.

Required env vars:
  KIT_API_KEY        - API key from Kit -> Settings -> Developer -> API Key

Optional env vars:
  KIT_SEND_MODE      - 'public' (sends/publishes immediately) or 'draft'
  ISSUE_SLOT         - am | pm; used to select content/issues/YYYY-MM-DD-am.md or -pm.md
  SITE_BASE_URL      - Used to build the web version link
  NEWSLETTER_NAME    - Used as subject fallback
  SPONSOR_EMAIL      - Used in footer

Exit codes:
  0 - created, skipped because already sent, or skipped because no credentials
  1 - API error
  2 - no issue found
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    print("[kit] ERROR: 'requests' not installed. Run: pip install requests")
    sys.exit(1)

from utils import issue_path_for_today, load_project_env

load_project_env()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
API_KEY = os.environ.get("KIT_API_KEY", "").strip()
SEND_MODE = os.environ.get("KIT_SEND_MODE", "draft").strip().lower()  # public | draft
SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "https://news.forgecore.co").strip().rstrip("/")
NEWSLETTER_NAME = os.environ.get("NEWSLETTER_NAME", "ForgeCore AI Productivity Brief").strip()
SPONSOR_EMAIL = os.environ.get("SPONSOR_EMAIL", "sponsors@forgecore.co").strip()

API_BASE = "https://api.kit.com/v4"
STATE_DIR = Path("state")
SENT_LOG = STATE_DIR / "kit_sent.json"
ISSUES_DIR = Path("content/issues")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def log(msg: str) -> None:
    print(f"[kit] {msg}", flush=True)


def load_sent_log() -> dict:
    if SENT_LOG.exists():
        try:
            data = json.loads(SENT_LOG.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            pass
    return {}


def save_sent_log(data: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    SENT_LOG.write_text(json.dumps(data, indent=2), encoding="utf-8")


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


def find_latest_issue() -> Path | None:
    if not ISSUES_DIR.exists():
        return None
    files = sorted(ISSUES_DIR.glob("*.md"), key=issue_sort_key, reverse=True)
    return files[0] if files else None


def find_target_issue() -> Path | None:
    current = issue_path_for_today()
    if current.exists():
        return current
    return find_latest_issue()


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


def title_from_markdown(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def preview_from_markdown(text: str, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("---") or stripped.startswith("-"):
            continue
        preview = re.sub(r"\s+", " ", stripped)
        return preview[:180]
    return fallback


def inline_md(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__(.+?)__", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"_(.+?)_", r"<em>\1</em>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', text)
    return text


def markdown_to_html(md: str) -> str:
    lines = md.split("\n")
    out: list[str] = []
    in_ul = False
    in_code = False
    code_lines: list[str] = []

    def close_ul() -> None:
        nonlocal in_ul
        if in_ul:
            out.append("</ul>")
            in_ul = False

    for line in lines:
        stripped = line.rstrip()
        if stripped.startswith("```"):
            close_ul()
            if in_code:
                out.append("<pre style='background:#050505;border:1px solid #333;border-radius:12px;padding:14px;overflow:auto;'><code>" + "\n".join(code_lines) + "</code></pre>")
                code_lines = []
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code_lines.append(stripped)
            continue
        hm = re.match(r"^(#{1,6})\s+(.*)", stripped)
        if hm:
            close_ul()
            lvl = len(hm.group(1))
            out.append(f"<h{lvl}>{inline_md(hm.group(2))}</h{lvl}>")
            continue
        if re.match(r"^[-*_]{3,}\s*$", stripped):
            close_ul()
            out.append("<hr style='border:none;border-top:1px solid #333;margin:24px 0;'>")
            continue
        bm = re.match(r"^[\-\*\+]\s+(.*)", stripped)
        if bm:
            if not in_ul:
                out.append("<ul style='padding-left:20px;'>")
                in_ul = True
            out.append(f"<li style='margin-bottom:8px;'>{inline_md(bm.group(1))}</li>")
            continue
        if stripped.strip() == "":
            close_ul()
            out.append("")
            continue
        close_ul()
        out.append(f"<p style='margin:0 0 14px;'>{inline_md(stripped)}</p>")

    close_ul()
    if in_code:
        out.append("<pre style='background:#050505;border:1px solid #333;border-radius:12px;padding:14px;overflow:auto;'><code>" + "\n".join(code_lines) + "</code></pre>")
    return "\n".join(out)


def build_email_html(body_md: str, issue_slug: str) -> str:
    web_url = f"{SITE_BASE_URL}/{issue_slug}/"
    body_html = markdown_to_html(body_md)
    unsubscribe = "{{ unsubscribe_url }}"
    return f"""
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0d0d0d;">
<div style="max-width:680px;margin:0 auto;padding:32px 24px;font-family:Arial,Helvetica,sans-serif;color:#e5e7eb;background:#111827;line-height:1.6;">
  <p style="font-size:12px;color:#9ca3af;margin-bottom:28px;">
    Can't see this properly?
    <a href="{web_url}" style="color:#38bdf8;">Read it on the web</a>.
  </p>

  {body_html}

  <hr style="border:none;border-top:1px solid #374151;margin:40px 0;">
  <p style="font-size:12px;color:#9ca3af;line-height:1.6;">
    Sponsor ForgeCore: <a href="mailto:{SPONSOR_EMAIL}" style="color:#38bdf8;">{SPONSOR_EMAIL}</a><br>
    You're receiving this because you subscribed to {NEWSLETTER_NAME}.<br>
    <a href="{unsubscribe}" style="color:#9ca3af;">Unsubscribe</a>
  </p>
</div>
</body>
</html>
""".strip()


# ---------------------------------------------------------------------------
# Kit API v4
# ---------------------------------------------------------------------------
def create_broadcast(subject: str, email_html: str, preview_text: str) -> dict:
    if SEND_MODE not in {"draft", "public"}:
        raise ValueError(f"Unsupported KIT_SEND_MODE={SEND_MODE!r}; expected draft or public")

    url = f"{API_BASE}/broadcasts"
    headers = {
        "X-Kit-Api-Key": API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
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
        log("SKIP: KIT_API_KEY not set. Add it as a GitHub secret to enable Kit drafts.")
        sys.exit(0)

    issue_path = find_target_issue()
    if not issue_path:
        log("No issue found in content/issues/ — nothing to publish.")
        sys.exit(2)

    issue_slug = issue_path.stem
    log(f"Found issue: {issue_path}")

    sent_log = load_sent_log()
    if issue_slug in sent_log:
        log(f"Issue {issue_slug} already sent to Kit (broadcast_id={sent_log[issue_slug].get('broadcast_id')}). Skipping.")
        sys.exit(0)

    raw = issue_path.read_text(encoding="utf-8")
    meta, body_md = parse_frontmatter(raw)

    title = meta.get("title") or title_from_markdown(body_md, f"{NEWSLETTER_NAME} — {issue_slug}")
    subject = title or f"{NEWSLETTER_NAME} — {issue_slug}"
    preview = meta.get("description") or preview_from_markdown(body_md, f"{NEWSLETTER_NAME} — {issue_slug}")

    email_html = build_email_html(body_md, issue_slug)
    result = create_broadcast(subject, email_html, preview)

    broadcast = result.get("broadcast", result)
    broadcast_id = broadcast.get("id", "unknown")

    log(f"SUCCESS — broadcast_id={broadcast_id}")

    sent_log[issue_slug] = {
        "broadcast_id": broadcast_id,
        "subject": subject,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "mode": SEND_MODE,
        "issue_path": issue_path.as_posix(),
        "web_url": f"{SITE_BASE_URL}/{issue_slug}/",
    }
    save_sent_log(sent_log)
    log(f"Recorded in {SENT_LOG}")


if __name__ == "__main__":
    main()
