#!/usr/bin/env python3
"""Publish the current Aware by Em issue to Kit.

Production rules:
- Daily issues named YYYY-MM-DD.md are valid send targets.
- Legacy slot issues named YYYY-MM-DD-am.md / YYYY-MM-DD-pm.md remain valid.
- Public sends use locked snapshots in content/email/ when present/required.
- state/kit_sent.json remains the idempotency guard.
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

from utils import WORKSPACE, issue_path_for_today, load_project_env

load_project_env()

API_KEY = os.environ.get("KIT_API_KEY", "").strip()
REQUESTED_SEND_MODE = os.environ.get("KIT_SEND_MODE", "draft").strip().lower()
ISSUE_SLOT_ENV = os.environ.get("ISSUE_SLOT", "").strip().lower()
GITHUB_ACTIONS = os.environ.get("GITHUB_ACTIONS", "").strip().lower() == "true"

# Scheduled/manual workflow sends should publish publicly for both daily and legacy slots.
SEND_MODE = "public" if GITHUB_ACTIONS else REQUESTED_SEND_MODE

SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "https://news.forgecore.co").strip().rstrip("/")
NEWSLETTER_NAME = os.environ.get("NEWSLETTER_NAME", "Aware by Em").strip()
SPONSOR_EMAIL = os.environ.get("SPONSOR_EMAIL", "sponsors@forgecore.co").strip()

API_BASE = "https://api.kit.com/v4"
STATE_DIR = WORKSPACE / "state"
SENT_LOG = STATE_DIR / "kit_sent.json"
ISSUES_DIR = WORKSPACE / "content" / "issues"
EMAIL_DIR = WORKSPACE / "content" / "email"
ISSUE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:-(am|pm))?$")
LOCK_COMMENT_RE = re.compile(r"^<!--\nLocked email version for .*?\n-->\n\n", re.DOTALL)
BASE_TEXT = "font-family: Arial, Helvetica, sans-serif; color:#111827; line-height:1.62; font-size:16px;"
LINK_STYLE = "color:#2563eb; text-decoration:underline;"


def log(msg: str) -> None:
    print(f"[kit] {msg}", flush=True)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
    slot_rank = 2 if stem.endswith("-pm") else 1 if stem.endswith("-am") else 0
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


def locked_email_path_for_issue(issue_path: Path) -> Path:
    return EMAIL_DIR / issue_path.name


def find_email_source(issue_path: Path) -> Path:
    locked = locked_email_path_for_issue(issue_path)
    if SEND_MODE == "public":
        if not locked.exists():
            raise FileNotFoundError(f"Locked email snapshot missing. Refusing to send: {locked.as_posix()}")
        return locked
    return locked if locked.exists() else issue_path


def parse_issue_slug(issue_slug: str) -> tuple[str, str]:
    match = ISSUE_RE.fullmatch(issue_slug.lower())
    if not match:
        return issue_slug, "legacy"
    return match.group(1), match.group(2) or "daily"


def record_blocks_send(record: dict) -> bool:
    if not isinstance(record, dict):
        return False
    return record.get("email_delivery") == "scheduled_or_sent" or record.get("mode") == "public"


def public_records_for_date(sent_log: dict, issue_date: str) -> set[str]:
    slots: set[str] = set()
    for slug, record in sent_log.items():
        sent_date, sent_slot = parse_issue_slug(str(slug))
        if sent_date == issue_date and record_blocks_send(record):
            slots.add(sent_slot)
    return slots


def enforce_public_send_guard(issue_slug: str, sent_log: dict) -> None:
    if SEND_MODE != "public":
        return
    issue_date, issue_kind = parse_issue_slug(issue_slug)
    if issue_kind in {"am", "pm"} and ISSUE_SLOT_ENV and ISSUE_SLOT_ENV != issue_kind:
        log(f"SKIP: ISSUE_SLOT={ISSUE_SLOT_ENV!r} does not match issue slug kind {issue_kind!r} for {issue_slug}.")
        sys.exit(0)
    sent_kinds = public_records_for_date(sent_log, issue_date)
    if issue_kind in sent_kinds:
        log(f"SKIP: {issue_slug} already has a public Kit record. Web output may be updated, but this issue will not email again.")
        sys.exit(0)
    if issue_kind == "daily" and sent_kinds:
        log(f"SKIP: {issue_date} already has a public Kit record ({', '.join(sorted(sent_kinds))}). Refusing duplicate daily send.")
        sys.exit(0)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    meta: dict = {}
    body = LOCK_COMMENT_RE.sub("", text)
    if body.startswith("---"):
        parts = body.split("---", 2)
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
        if not stripped or stripped.startswith("#") or stripped.startswith("---") or stripped.startswith("-") or stripped.startswith("<!--"):
            continue
        if stripped.startswith("*by ") or "Aware by Em" in stripped:
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
    lines = LOCK_COMMENT_RE.sub("", md).split("\n")
    out: list[str] = []
    in_ul = False
    in_code = False
    in_comment = False
    code_lines: list[str] = []

    def close_ul() -> None:
        nonlocal in_ul
        if in_ul:
            out.append("</ul>")
            in_ul = False

    for line in lines:
        stripped = line.rstrip()
        if stripped.startswith("<!--"):
            in_comment = not stripped.endswith("-->")
            continue
        if in_comment:
            if stripped.endswith("-->"):
                in_comment = False
            continue
        if stripped.startswith("```"):
            close_ul()
            if in_code:
                code = html.escape("\n".join(code_lines))
                out.append("<pre style='background:#f9fafb;border:1px solid #e5e7eb;border-radius:10px;padding:14px;overflow:auto;color:#111827;font-size:14px;line-height:1.5;'><code>" + code + "</code></pre>")
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
            size = "30px" if lvl == 1 else "22px" if lvl == 2 else "18px"
            tag = "h1" if lvl == 1 else "h2" if lvl == 2 else "h3"
            out.append(f"<{tag} style='color:#0f172a;font-size:{size};line-height:1.25;margin:24px 0 14px;font-weight:800;'>{text}</{tag}>")
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
        out.append("<pre style='background:#f9fafb;border:1px solid #e5e7eb;border-radius:10px;padding:14px;overflow:auto;color:#111827;font-size:14px;line-height:1.5;'><code>" + code + "</code></pre>")
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
  <div style="display:none;max-height:0;overflow:hidden;color:#f3f4f6;opacity:0;">{html.escape(NEWSLETTER_NAME)} — clear noticing about AI, culture, tools, and digital life.</div>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f3f4f6;margin:0;padding:0;">
    <tr><td align="center" style="padding:24px 12px;">
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:680px;background:#ffffff;border:1px solid #e5e7eb;border-radius:14px;">
        <tr><td style="padding:28px 28px 8px;{BASE_TEXT}">
          <p style="font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#6b7280;margin:0 0 18px;">
            Aware by Em · <a href="{web_url}" style="{LINK_STYLE}">Read on the web</a>
          </p>
          {body_html}
          <hr style="border:none;border-top:1px solid #e5e7eb;margin:36px 0 20px;">
          <p style="font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#6b7280;line-height:1.6;margin:0 0 8px;">
            Sponsor ForgeCore: <a href="mailto:{SPONSOR_EMAIL}" style="{LINK_STYLE}">{SPONSOR_EMAIL}</a><br>
            You're receiving this because you subscribed to {html.escape(NEWSLETTER_NAME)}.<br>
            <a href="{unsubscribe}" style="color:#6b7280;text-decoration:underline;">Unsubscribe</a>
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
""".strip()


def subscriber_filter_payload() -> list[dict] | None:
    segment_id = os.environ.get("KIT_SEGMENT_ID", "").strip()
    tag_id = os.environ.get("KIT_TAG_ID", "").strip()
    if segment_id:
        return [{"segment": segment_id}]
    if tag_id:
        return [{"tag": tag_id}]
    return None


def create_broadcast(subject: str, email_html: str, preview_text: str) -> tuple[dict, str | None]:
    if SEND_MODE not in {"draft", "public"}:
        raise ValueError(f"Unsupported KIT_SEND_MODE={SEND_MODE!r}; expected draft or public")
    url = f"{API_BASE}/broadcasts"
    headers = {"X-Kit-Api-Key": API_KEY, "Content-Type": "application/json", "Accept": "application/json"}
    now = utc_now_iso()
    send_at = now if SEND_MODE == "public" else None
    payload: dict = {
        "subject": subject,
        "content": email_html,
        "description": preview_text,
        "preview_text": preview_text,
        "public": SEND_MODE == "public",
        "published_at": now if SEND_MODE == "public" else None,
        "send_at": send_at,
    }
    filters = subscriber_filter_payload()
    if filters:
        payload["subscriber_filter"] = filters
    log(f"POST {url}")
    log(f"Subject: {subject}")
    log(f"Requested mode: {REQUESTED_SEND_MODE}")
    log(f"Effective mode: {SEND_MODE}")
    log(f"send_at: {send_at or 'null (draft only)'}")
    log(f"subscriber_filter: {'configured' if filters else 'omitted (Kit default audience)'}")
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    log(f"Response: {resp.status_code}")
    if resp.status_code not in (200, 201):
        log(f"ERROR: {resp.text[:1000]}")
        resp.raise_for_status()
    return resp.json(), send_at


def main() -> None:
    if not API_KEY:
        log("SKIP: KIT_API_KEY not set. Add it as a GitHub secret to enable Kit publishing.")
        sys.exit(0)
    issue_path = find_target_issue()
    if not issue_path:
        log("No issue found in content/issues/ — nothing to publish.")
        sys.exit(2)
    issue_slug = issue_path.stem
    log(f"Found web issue: {issue_path}")
    sent_log = load_sent_log()
    existing = sent_log.get(issue_slug)
    if isinstance(existing, dict) and record_blocks_send(existing):
        log(f"Issue {issue_slug} already has a public Kit record (broadcast_id={existing.get('broadcast_id')}). Skipping email.")
        sys.exit(0)
    enforce_public_send_guard(issue_slug, sent_log)
    email_source = find_email_source(issue_path)
    log(f"Using email source: {email_source}")
    raw = email_source.read_text(encoding="utf-8")
    meta, body_md = parse_frontmatter(raw)
    title = meta.get("title") or title_from_markdown(body_md, f"{NEWSLETTER_NAME} — {issue_slug}")
    subject = title or f"{NEWSLETTER_NAME} — {issue_slug}"
    preview = meta.get("description") or preview_from_markdown(body_md, f"{NEWSLETTER_NAME} — {issue_slug}")
    email_html = build_email_html(body_md, issue_slug)
    result, send_at = create_broadcast(subject, email_html, preview)
    broadcast = result.get("broadcast", result)
    broadcast_id = broadcast.get("id", "unknown")
    log(f"SUCCESS — broadcast_id={broadcast_id}")
    issue_date, issue_kind = parse_issue_slug(issue_slug)
    sent_log[issue_slug] = {
        "broadcast_id": broadcast_id,
        "subject": subject,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "mode": SEND_MODE,
        "requested_mode": REQUESTED_SEND_MODE,
        "email_delivery": "scheduled_or_sent" if send_at else "not_scheduled",
        "send_at": send_at,
        "issue_path": issue_path.as_posix(),
        "email_source_path": email_source.as_posix(),
        "issue_date": issue_date,
        "issue_slot": issue_kind,
        "web_url": f"{SITE_BASE_URL}/{issue_slug}/",
    }
    save_sent_log(sent_log)
    log(f"Recorded in {SENT_LOG}")


if __name__ == "__main__":
    main()
