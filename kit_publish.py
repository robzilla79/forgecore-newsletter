#!/usr/bin/env python3
"""
kit_publish.py

Publishes the current ForgeCore issue to Kit (formerly ConvertKit).

Default behavior is to create a broadcast draft. In production AM/PM
newsletter runs, set KIT_SEND_MODE=public to publish/send immediately.

Required env vars:
  KIT_API_KEY        - API key from Kit -> Settings -> Developer -> API Key

Optional env vars:
  KIT_SEND_MODE      - 'public' (sends/publishes immediately) or 'draft'
  ISSUE_SLOT         - am | pm; used to select content/issues/YYYY-MM-DD-am.md or -pm.md
  SITE_BASE_URL      - Used to build the web version link
  NEWSLETTER_NAME    - Used as subject fallback
  SPONSOR_EMAIL      - Used in footer

Safety rules for KIT_SEND_MODE=public:
  - only slot-specific issues may send: YYYY-MM-DD-am.md or YYYY-MM-DD-pm.md
  - ISSUE_SLOT must match the issue slot
  - only one AM and one PM issue may be sent per issue date
  - already-sent issue slugs are skipped idempotently

Exit codes:
  0 - created, skipped because already sent, skipped by send guard, or skipped because no credentials
  1 - API error
  2 - no issue found
"""

from __future__ import annotations

import html
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

API_KEY = os.environ.get("KIT_API_KEY", "").strip()
SEND_MODE = os.environ.get("KIT_SEND_MODE", "draft").strip().lower()
ISSUE_SLOT_ENV = os.environ.get("ISSUE_SLOT", "").strip().lower()
SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "https://news.forgecore.co").strip().rstrip("/")
NEWSLETTER_NAME = os.environ.get("NEWSLETTER_NAME", "ForgeCore AI Productivity Brief").strip()
SPONSOR_EMAIL = os.environ.get("SPONSOR_EMAIL", "sponsors@forgecore.co").strip()

API_BASE = "https://api.kit.com/v4"
STATE_DIR = Path("state")
SENT_LOG = STATE_DIR / "kit_sent.json"
ISSUES_DIR = Path("content/issues")
SLOT_ISSUE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(am|pm)$")

BASE_TEXT = "font-family: Arial, Helvetica, sans-serif; color:#111827; line-height:1.62; font-size:16px;"
LINK_STYLE = "color:#2563eb; text-decoration:underline;"


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


def parse_slot_issue_slug(issue_slug: str) -> tuple[str, str] | None:
    match = SLOT_ISSUE_RE.fullmatch(issue_slug.lower())
    if not match:
        return None
    return match.group(1), match.group(2)


def sent_public_slots_for_date(sent_log: dict, issue_date: str) -> set[str]:
    slots: set[str] = set()
    for slug, record in sent_log.items():
        parsed = parse_slot_issue_slug(str(slug))
        if not parsed:
            continue
        sent_date, sent_slot = parsed
        if sent_date != issue_date:
            continue
        if isinstance(record, dict) and record.get("mode") == "public":
            slots.add(sent_slot)
    return slots


def enforce_public_send_guard(issue_slug: str, sent_log: dict) -> None:
    """Exit safely when a public send would violate ForgeCore send policy."""
    if SEND_MODE != "public":
        return

    parsed = parse_slot_issue_slug(issue_slug)
    if not parsed:
        log(
            "SKIP: KIT_SEND_MODE=public is only allowed for slot-specific issues "
            "named YYYY-MM-DD-am.md or YYYY-MM-DD-pm.md."
        )
        sys.exit(0)

    issue_date, issue_slot = parsed
    if ISSUE_SLOT_ENV not in {"am", "pm"}:
        log("SKIP: KIT_SEND_MODE=public requires ISSUE_SLOT=am or ISSUE_SLOT=pm.")
        sys.exit(0)

    if ISSUE_SLOT_ENV != issue_slot:
        log(
            f"SKIP: ISSUE_SLOT={ISSUE_SLOT_ENV!r} does not match issue slug slot "
            f"{issue_slot!r} for {issue_slug}."
        )
        sys.exit(0)

    sent_slots = sent_public_slots_for_date(sent_log, issue_date)
    if issue_slot in sent_slots:
        log(f"SKIP: {issue_date} {issue_slot.upper()} was already sent publicly.")
        sys.exit(0)

    if len(sent_slots) >= 2:
        log(
            f"SKIP: {issue_date} already has two public sends recorded "
            f"({', '.join(sorted(sent_slots)).upper()})."
        )
        sys.exit(0)

    allowed_after_send = sent_slots | {issue_slot}
    if not allowed_after_send.issubset({"am", "pm"}) or len(allowed_after_send) > 2:
        log("SKIP: public send would exceed the one-AM/one-PM daily send policy.")
        sys.exit(0)


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
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"__(.+?)__", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*(.+?)\*", r"<em>\1</em>", escaped)
    escaped = re.sub(r"_(.+?)_", r"<em>\1</em>", escaped)
    escaped = re.sub(r"`(.+?)`", r"<code style='background:#f3f4f6;color:#111827;padding:2px 4px;border-radius:4px;'>\1</code>", escaped)
    escaped = re.sub(r"\[(.+?)\]\((https?://[^\s)]+)\)", rf'<a href="\2" style="{LINK_STYLE}">\1</a>', escaped)
    return escaped


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
                code = html.escape("\n".join(code_lines))
                out.append(
                    "<pre style='background:#f9fafb;border:1px solid #e5e7eb;border-radius:10px;"
                    "padding:14px;overflow:auto;color:#111827;font-size:14px;line-height:1.5;'><code>"
                    + code
                    + "</code></pre>"
                )
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
            text = inline_md(hm.group(2))
            if lvl == 1:
                out.append(f"<h1 style='color:#0f172a;font-size:30px;line-height:1.2;margin:24px 0 18px;font-weight:800;'>{text}</h1>")
            elif lvl == 2:
                out.append(f"<h2 style='color:#111827;font-size:22px;line-height:1.3;margin:30px 0 12px;font-weight:750;'>{text}</h2>")
            else:
                out.append(f"<h3 style='color:#111827;font-size:18px;line-height:1.35;margin:22px 0 10px;font-weight:700;'>{text}</h3>")
            continue
        if re.match(r"^[-*_]{3,}\s*$", stripped):
            close_ul()
            out.append("<hr style='border:none;border-top:1px solid #e5e7eb;margin:28px 0;'>")
            continue
        bm = re.match(r"^[\-\*\+]\s+(.*)", stripped)
        if bm:
            if not in_ul:
                out.append("<ul style='padding-left:22px;margin:0 0 18px;color:#111827;'>")
                in_ul = True
            out.append(f"<li style='margin-bottom:9px;color:#111827;'>{inline_md(bm.group(1))}</li>")
            continue
        if stripped.strip() == "":
            close_ul()
            continue
        close_ul()
        out.append(f"<p style='{BASE_TEXT} margin:0 0 16px;'>{inline_md(stripped)}</p>")

    close_ul()
    if in_code:
        code = html.escape("\n".join(code_lines))
        out.append(
            "<pre style='background:#f9fafb;border:1px solid #e5e7eb;border-radius:10px;"
            "padding:14px;overflow:auto;color:#111827;font-size:14px;line-height:1.5;'><code>"
            + code
            + "</code></pre>"
        )
    return "\n".join(out)


def build_email_html(body_md: str, issue_slug: str) -> str:
    web_url = f"{SITE_BASE_URL}/{issue_slug}/"
    body_html = markdown_to_html(body_md)
    unsubscribe = "{{ unsubscribe_url }}"
    return f"""
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f3f4f6;color:#111827;">
  <div style="display:none;max-height:0;overflow:hidden;color:#f3f4f6;opacity:0;">{html.escape(NEWSLETTER_NAME)} — practical AI workflows for operators.</div>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f3f4f6;margin:0;padding:0;">
    <tr>
      <td align="center" style="padding:24px 12px;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:680px;background:#ffffff;border:1px solid #e5e7eb;border-radius:14px;">
          <tr>
            <td style="padding:28px 28px 8px;{BASE_TEXT}">
              <p style="font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#6b7280;margin:0 0 18px;">
                ForgeCore AI Productivity Brief ·
                <a href="{web_url}" style="{LINK_STYLE}">Read on the web</a>
              </p>
              {body_html}
              <hr style="border:none;border-top:1px solid #e5e7eb;margin:36px 0 20px;">
              <p style="font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#6b7280;line-height:1.6;margin:0 0 8px;">
                Sponsor ForgeCore: <a href="mailto:{SPONSOR_EMAIL}" style="{LINK_STYLE}">{SPONSOR_EMAIL}</a><br>
                You're receiving this because you subscribed to {html.escape(NEWSLETTER_NAME)}.<br>
                <a href="{unsubscribe}" style="color:#6b7280;text-decoration:underline;">Unsubscribe</a>
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
""".strip()


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


def main() -> None:
    if not API_KEY:
        log("SKIP: KIT_API_KEY not set. Add it as a GitHub secret to enable Kit publishing.")
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

    enforce_public_send_guard(issue_slug, sent_log)

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
        "issue_slot": parse_slot_issue_slug(issue_slug)[1] if parse_slot_issue_slug(issue_slug) else "legacy",
        "web_url": f"{SITE_BASE_URL}/{issue_slug}/",
    }
    save_sent_log(sent_log)
    log(f"Recorded in {SENT_LOG}")


if __name__ == "__main__":
    main()
