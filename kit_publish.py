#!/usr/bin/env python3
"""Publish an Aware by Em issue to Kit.

Supports ISSUE_SLUG for one-off prepared sends such as 2026-05-13-em.
Falls back to today's issue, then the latest issue, for the normal daily lane.
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
    print("[kit] ERROR: requests is not installed")
    sys.exit(1)

from utils import WORKSPACE, issue_path_for_today, load_project_env

load_project_env()

API_KEY = os.environ.get("KIT_API_KEY", "").strip()
REQUESTED_SEND_MODE = os.environ.get("KIT_SEND_MODE", "draft").strip().lower()
ISSUE_SLOT_ENV = os.environ.get("ISSUE_SLOT", "").strip().lower()
ISSUE_SLUG_ENV = os.environ.get("ISSUE_SLUG", "").strip()
GITHUB_ACTIONS = os.environ.get("GITHUB_ACTIONS", "").strip().lower() == "true"
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


def log(msg: str) -> None:
    print(f"[kit] {msg}", flush=True)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_sent_log() -> dict:
    if not SENT_LOG.exists():
        return {}
    try:
        data = json.loads(SENT_LOG.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
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
    if ISSUE_SLUG_ENV:
        return ISSUES_DIR / f"{ISSUE_SLUG_ENV}.md"
    current = issue_path_for_today()
    if current.exists():
        return current
    return find_latest_issue()


def locked_email_path_for_issue(issue_path: Path) -> Path:
    return EMAIL_DIR / issue_path.name


def parse_issue_slug(issue_slug: str) -> tuple[str, str]:
    match = ISSUE_RE.fullmatch(issue_slug.lower())
    if match:
        return match.group(1), match.group(2) or "daily"
    if re.match(r"^\d{4}-\d{2}-\d{2}-em$", issue_slug.lower()):
        return issue_slug[:10], "prepared"
    return issue_slug, "legacy"


def record_blocks_send(record: dict) -> bool:
    return isinstance(record, dict) and (record.get("email_delivery") == "scheduled_or_sent" or record.get("mode") == "public")


def public_records_for_date(sent_log: dict, issue_date: str) -> set[str]:
    kinds: set[str] = set()
    for slug, record in sent_log.items():
        sent_date, sent_kind = parse_issue_slug(str(slug))
        if sent_date == issue_date and record_blocks_send(record):
            kinds.add(sent_kind)
    return kinds


def enforce_public_send_guard(issue_slug: str, sent_log: dict) -> None:
    if SEND_MODE != "public":
        return
    issue_date, issue_kind = parse_issue_slug(issue_slug)
    if issue_kind in {"am", "pm"} and ISSUE_SLOT_ENV and ISSUE_SLOT_ENV != issue_kind:
        log(f"SKIP: ISSUE_SLOT={ISSUE_SLOT_ENV!r} does not match {issue_slug}.")
        sys.exit(0)
    sent_kinds = public_records_for_date(sent_log, issue_date)
    if issue_kind in sent_kinds:
        log(f"SKIP: {issue_slug} already has a public Kit record.")
        sys.exit(0)
    if issue_kind in {"daily", "prepared"} and sent_kinds:
        log(f"SKIP: {issue_date} already has a public Kit record ({', '.join(sorted(sent_kinds))}).")
        sys.exit(0)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    meta: dict = {}
    body = LOCK_COMMENT_RE.sub("", text)
    if body.startswith("---"):
        parts = body.split("---", 2)
        if len(parts) >= 3:
            body = parts[2].strip()
            for line in parts[1].splitlines():
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
        if not stripped or stripped.startswith(("#", "---", "-", "<!--")):
            continue
        if stripped.startswith("*by ") or "Aware by Em" in stripped:
            continue
        return re.sub(r"\s+", " ", stripped)[:180]
    return fallback


def inline_md(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*(.+?)\*", r"<em>\1</em>", escaped)
    escaped = re.sub(r"\[(.+?)\]\((https?://[^\s)]+)\)", r'<a href="\2">\1</a>', escaped)
    return escaped


def markdown_to_html(md: str) -> str:
    chunks: list[str] = []
    for raw in LOCK_COMMENT_RE.sub("", md).splitlines():
        line = raw.strip()
        if not line or line.startswith("<!--"):
            continue
        if line.startswith("# "):
            chunks.append(f"<h1>{inline_md(line[2:].strip())}</h1>")
        elif line == "---":
            chunks.append("<hr>")
        else:
            chunks.append(f"<p>{inline_md(line)}</p>")
    return "\n".join(chunks)


def build_email_html(body_md: str, issue_slug: str) -> str:
    web_url = f"{SITE_BASE_URL}/{issue_slug}/"
    body_html = markdown_to_html(body_md)
    unsubscribe = "{{ unsubscribe_url }}"
    return f"""<!doctype html><html><body style="margin:0;background:#f3f4f6;color:#111827;font-family:Arial,Helvetica,sans-serif;line-height:1.62;"><div style="max-width:680px;margin:0 auto;background:#fff;border:1px solid #e5e7eb;border-radius:14px;padding:28px;"><p style="font-size:13px;color:#6b7280;">Aware by Em · <a href="{web_url}">Read on the web</a></p>{body_html}<hr><p style="font-size:13px;color:#6b7280;">Sponsor ForgeCore: <a href="mailto:{SPONSOR_EMAIL}">{SPONSOR_EMAIL}</a><br>You're receiving this because you subscribed to {html.escape(NEWSLETTER_NAME)}.<br><a href="{unsubscribe}">Unsubscribe</a></p></div></body></html>"""


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
    log(f"POST {API_BASE}/broadcasts")
    log(f"Subject: {subject}")
    log(f"Effective mode: {SEND_MODE}")
    response = requests.post(
        f"{API_BASE}/broadcasts",
        headers={"X-Kit-Api-Key": API_KEY, "Content-Type": "application/json", "Accept": "application/json"},
        json=payload,
        timeout=30,
    )
    log(f"Response: {response.status_code}")
    if response.status_code not in (200, 201):
        log(f"ERROR: {response.text[:1000]}")
        response.raise_for_status()
    return response.json(), send_at


def main() -> None:
    if not API_KEY:
        log("SKIP: KIT_API_KEY not set.")
        sys.exit(0)
    issue_path = find_target_issue()
    if not issue_path or not issue_path.exists():
        log(f"No target issue found. ISSUE_SLUG={ISSUE_SLUG_ENV!r}")
        sys.exit(2)
    issue_slug = issue_path.stem
    log(f"Found web issue: {issue_path}")
    sent_log = load_sent_log()
    existing = sent_log.get(issue_slug)
    if record_blocks_send(existing):
        log(f"Issue {issue_slug} already has a public Kit record. Skipping email.")
        sys.exit(0)
    enforce_public_send_guard(issue_slug, sent_log)
    email_source = locked_email_path_for_issue(issue_path)
    if SEND_MODE == "public" and not email_source.exists():
        raise FileNotFoundError(f"Locked email snapshot missing. Refusing to send: {email_source.as_posix()}")
    if not email_source.exists():
        email_source = issue_path
    log(f"Using email source: {email_source}")
    raw = email_source.read_text(encoding="utf-8")
    meta, body_md = parse_frontmatter(raw)
    subject = meta.get("title") or title_from_markdown(body_md, f"{NEWSLETTER_NAME} — {issue_slug}")
    preview = meta.get("description") or preview_from_markdown(body_md, f"{NEWSLETTER_NAME} — {issue_slug}")
    result, send_at = create_broadcast(subject, build_email_html(body_md, issue_slug), preview)
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
