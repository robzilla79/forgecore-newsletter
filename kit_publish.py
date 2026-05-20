#!/usr/bin/env python3
"""Publish an Aware by Em issue to Kit.

Supports ISSUE_SLUG for one-off prepared sends such as 2026-05-13-em.
Falls back to today's issue, then the latest issue, for the normal daily lane.

Send modes
----------
Default (no flag):
    Draft-safe backward-compatible path. Checks guard, calls Kit, saves record.
    Still race-prone for concurrent public runs. Use --lock / --send-locked instead.

--lock:
    Write a pre-send lock entry (email_delivery: "sending") to state/kit_sent.json
    and exit WITHOUT calling the Kit API. The caller must commit and push the lock
    before running --send-locked. The lock record includes a lock_id derived from
    GITHUB_RUN_ID + GITHUB_RUN_ATTEMPT so only the owning run can send.

--send-locked:
    Verify that the lock exists for this exact issue, has email_delivery: "sending",
    and has a lock_id that matches this run's GITHUB_RUN_ID + GITHUB_RUN_ATTEMPT.
    Then call the Kit API. On success, replace the lock with the real broadcast
    record. Refuses to proceed if the lock is absent, in any other state, or owned
    by a different run.
"""
from __future__ import annotations

import argparse
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

# Lock identity: uniquely identifies this workflow run so --send-locked
# can verify it is the run that wrote the lock.
GITHUB_RUN_ID = os.environ.get("GITHUB_RUN_ID", "").strip()
GITHUB_RUN_ATTEMPT = os.environ.get("GITHUB_RUN_ATTEMPT", "1").strip()
RUN_LOCK_ID = f"{GITHUB_RUN_ID}-{GITHUB_RUN_ATTEMPT}" if GITHUB_RUN_ID else ""

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
    """Return True if this sent-log record means the issue must not be sent again.

    Blocks on:
      - email_delivery: "scheduled_or_sent"  (real send completed)
      - email_delivery: "sending"             (pre-send lock held by any run)
      - mode: "public"                        (legacy public record)
    """
    if not isinstance(record, dict):
        return False
    return (
        record.get("email_delivery") in {"scheduled_or_sent", "sending"}
        or record.get("mode") == "public"
    )


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


def resolve_issue_and_email() -> tuple[Path, Path, str, str, str]:
    """Resolve the target issue and email source.
    Returns (issue_path, email_source, issue_slug, issue_date, issue_kind).
    """
    issue_path = find_target_issue()
    if not issue_path or not issue_path.exists():
        log(f"No target issue found. ISSUE_SLUG={ISSUE_SLUG_ENV!r}")
        sys.exit(2)
    issue_slug = issue_path.stem
    email_source = locked_email_path_for_issue(issue_path)
    if SEND_MODE == "public" and not email_source.exists():
        raise FileNotFoundError(
            f"Locked email snapshot missing. Refusing to send: {email_source.as_posix()}"
        )
    if not email_source.exists():
        email_source = issue_path
    issue_date, issue_kind = parse_issue_slug(issue_slug)
    return issue_path, email_source, issue_slug, issue_date, issue_kind


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
    return (
        f'<!doctype html><html><body style="margin:0;background:#f3f4f6;color:#111827;'
        f'font-family:Arial,Helvetica,sans-serif;line-height:1.62;">'
        f'<div style="max-width:680px;margin:0 auto;background:#fff;border:1px solid #e5e7eb;'
        f'border-radius:14px;padding:28px;">'
        f'<p style="font-size:13px;color:#6b7280;">Aware by Em \u00b7 <a href="{web_url}">Read on the web</a></p>'
        f"{body_html}"
        f"<hr>"
        f'<p style="font-size:13px;color:#6b7280;">'
        f'Sponsor ForgeCore: <a href="mailto:{SPONSOR_EMAIL}">{SPONSOR_EMAIL}</a><br>'
        f"You&#x27;re receiving this because you subscribed to {html.escape(NEWSLETTER_NAME)}.<br>"
        f'<a href="{unsubscribe}">Unsubscribe</a></p>'
        f"</div></body></html>"
    )


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
        headers={
            "X-Kit-Api-Key": API_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        json=payload,
        timeout=30,
    )
    log(f"Response: {response.status_code}")
    if response.status_code not in (200, 201):
        log(f"ERROR: {response.text[:1000]}")
        response.raise_for_status()
    return response.json(), send_at


# ---------------------------------------------------------------------------
# --lock mode
# ---------------------------------------------------------------------------

def cmd_lock() -> None:
    """Write a pre-send lock to state/kit_sent.json and exit. Does not call Kit.

    The lock record includes the lock_id for this run (GITHUB_RUN_ID-GITHUB_RUN_ATTEMPT)
    so --send-locked can verify ownership before calling the Kit API.

    The caller must commit and push the lock before running --send-locked.
    If a blocking record already exists (sent or locked by any run), exits with a skip.
    """
    if not API_KEY:
        log("SKIP: KIT_API_KEY not set.")
        sys.exit(0)

    issue_path, email_source, issue_slug, issue_date, issue_kind = resolve_issue_and_email()
    log(f"Locking issue: {issue_slug}")
    if RUN_LOCK_ID:
        log(f"Lock ID: {RUN_LOCK_ID}")

    sent_log = load_sent_log()
    existing = sent_log.get(issue_slug)
    if record_blocks_send(existing):
        delivery = existing.get("email_delivery", "?")
        log(f"SKIP: {issue_slug} already has a blocking record (email_delivery={delivery!r}). Not overwriting.")
        sys.exit(0)

    enforce_public_send_guard(issue_slug, sent_log)

    sent_log[issue_slug] = {
        "subject": "PENDING",
        "email_delivery": "sending",
        "mode": SEND_MODE,
        "requested_mode": REQUESTED_SEND_MODE,
        "lock_id": RUN_LOCK_ID,
        "locked_at": utc_now_iso(),
        "issue_path": issue_path.as_posix(),
        "email_source_path": email_source.as_posix(),
        "issue_date": issue_date,
        "issue_slot": issue_kind,
        "web_url": f"{SITE_BASE_URL}/{issue_slug}/",
    }
    save_sent_log(sent_log)
    log(f"Pre-send lock written for {issue_slug}. Commit and push before calling --send-locked.")


# ---------------------------------------------------------------------------
# --send-locked mode
# ---------------------------------------------------------------------------

def cmd_send_locked() -> None:
    """Call Kit only if this run owns the pre-send lock for this issue.

    Refuses to proceed if:
      - The lock entry is missing.
      - The lock entry has any email_delivery other than "sending".
      - The lock_id does not match this run's GITHUB_RUN_ID-GITHUB_RUN_ATTEMPT.

    On success, replaces the lock with the real broadcast record.
    """
    if not API_KEY:
        log("SKIP: KIT_API_KEY not set.")
        sys.exit(0)

    issue_path, email_source, issue_slug, issue_date, issue_kind = resolve_issue_and_email()
    log(f"Found web issue: {issue_path}")
    log(f"Using email source: {email_source}")
    if RUN_LOCK_ID:
        log(f"This run's lock ID: {RUN_LOCK_ID}")

    sent_log = load_sent_log()
    lock = sent_log.get(issue_slug)

    # Lock must exist.
    if lock is None:
        log(f"ERROR: No lock entry found for {issue_slug}. Run --lock and commit/push first.")
        sys.exit(1)

    # Lock must be in "sending" state.
    delivery = lock.get("email_delivery", "")
    if delivery == "scheduled_or_sent":
        log(f"SKIP: {issue_slug} already has email_delivery=scheduled_or_sent. Nothing to do.")
        sys.exit(0)
    if delivery != "sending":
        log(f"ERROR: Lock for {issue_slug} has unexpected email_delivery={delivery!r}. Refusing to send.")
        sys.exit(1)

    # Lock must belong to this run.
    lock_id = lock.get("lock_id", "")
    if RUN_LOCK_ID and lock_id != RUN_LOCK_ID:
        log(
            f"ERROR: Lock for {issue_slug} is owned by run {lock_id!r}, "
            f"not this run {RUN_LOCK_ID!r}. Refusing to send."
        )
        sys.exit(1)
    if not RUN_LOCK_ID and lock_id:
        # Running outside GitHub Actions — allow if lock_id is empty,
        # but refuse if lock was set by a real Actions run.
        log(
            f"ERROR: Lock for {issue_slug} was set by Actions run {lock_id!r}. "
            f"This run has no GITHUB_RUN_ID. Refusing to send."
        )
        sys.exit(1)

    log(f"Lock ownership confirmed for {issue_slug}. Proceeding to Kit.")

    raw = email_source.read_text(encoding="utf-8")
    meta, body_md = parse_frontmatter(raw)
    subject = meta.get("title") or title_from_markdown(body_md, f"{NEWSLETTER_NAME} \u2014 {issue_slug}")
    preview = meta.get("description") or preview_from_markdown(body_md, f"{NEWSLETTER_NAME} \u2014 {issue_slug}")

    result, send_at = create_broadcast(subject, build_email_html(body_md, issue_slug), preview)
    broadcast = result.get("broadcast", result)
    broadcast_id = broadcast.get("id", "unknown")
    log(f"SUCCESS \u2014 broadcast_id={broadcast_id}")

    sent_log[issue_slug] = {
        "broadcast_id": broadcast_id,
        "subject": subject,
        "sent_at": utc_now_iso(),
        "mode": SEND_MODE,
        "requested_mode": REQUESTED_SEND_MODE,
        "email_delivery": "scheduled_or_sent" if send_at else "not_scheduled",
        "send_at": send_at,
        "lock_id": RUN_LOCK_ID,
        "issue_path": issue_path.as_posix(),
        "email_source_path": email_source.as_posix(),
        "issue_date": issue_date,
        "issue_slot": issue_kind,
        "web_url": f"{SITE_BASE_URL}/{issue_slug}/",
    }
    save_sent_log(sent_log)
    log(f"Recorded in {SENT_LOG}")


# ---------------------------------------------------------------------------
# Default (no-flag) mode \u2014 backward-compatible
# ---------------------------------------------------------------------------

def cmd_default() -> None:
    """Original single-step send. Safe for draft mode and manual one-off use.
    For concurrent-safe public sends, use --lock / --send-locked instead.
    """
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
        log(f"Issue {issue_slug} already has a blocking Kit record. Skipping email.")
        sys.exit(0)

    enforce_public_send_guard(issue_slug, sent_log)

    email_source = locked_email_path_for_issue(issue_path)
    if SEND_MODE == "public" and not email_source.exists():
        raise FileNotFoundError(
            f"Locked email snapshot missing. Refusing to send: {email_source.as_posix()}"
        )
    if not email_source.exists():
        email_source = issue_path
    log(f"Using email source: {email_source}")

    raw = email_source.read_text(encoding="utf-8")
    meta, body_md = parse_frontmatter(raw)
    subject = meta.get("title") or title_from_markdown(body_md, f"{NEWSLETTER_NAME} \u2014 {issue_slug}")
    preview = meta.get("description") or preview_from_markdown(body_md, f"{NEWSLETTER_NAME} \u2014 {issue_slug}")

    result, send_at = create_broadcast(subject, build_email_html(body_md, issue_slug), preview)
    broadcast = result.get("broadcast", result)
    broadcast_id = broadcast.get("id", "unknown")
    log(f"SUCCESS \u2014 broadcast_id={broadcast_id}")

    issue_date, issue_kind = parse_issue_slug(issue_slug)
    sent_log[issue_slug] = {
        "broadcast_id": broadcast_id,
        "subject": subject,
        "sent_at": utc_now_iso(),
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


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Publish an Aware by Em issue to Kit.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--lock",
        action="store_true",
        help="Write pre-send lock to state/kit_sent.json and exit. Do not call Kit.",
    )
    group.add_argument(
        "--send-locked",
        action="store_true",
        help="Call Kit only if this run owns the pre-send lock. Replace lock with real record on success.",
    )
    args = parser.parse_args()

    if args.lock:
        cmd_lock()
    elif args.send_locked:
        cmd_send_locked()
    else:
        cmd_default()


if __name__ == "__main__":
    main()
