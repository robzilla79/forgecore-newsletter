#!/usr/bin/env python3
"""Create or preserve the locked email version for the current AM/PM issue.

ForgeCore operating rule:
- content/issues/YYYY-MM-DD-slot.md is the living web/article source.
- content/email/YYYY-MM-DD-slot.md is the frozen email source.
- Preparation may create the email snapshot before send.
- Once a slot has a public Kit record, the snapshot is never overwritten.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from utils import WORKSPACE, issue_path_for_today, issue_slot, write_text

EMAIL_DIR = WORKSPACE / "content" / "email"
SENT_LOG = WORKSPACE / "state" / "kit_sent.json"
SLOT_ISSUE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(am|pm)$")


def load_sent_log() -> dict:
    if not SENT_LOG.exists():
        return {}
    try:
        data = json.loads(SENT_LOG.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def record_blocks_slot_email(record: dict) -> bool:
    if not isinstance(record, dict):
        return False
    if record.get("email_delivery") == "scheduled_or_sent":
        return True
    if record.get("mode") == "public":
        return True
    return False


def main() -> int:
    slot = issue_slot()
    if slot not in {"am", "pm"}:
        print("[lock_email_issue] SKIP: ISSUE_SLOT is not am or pm.")
        return 0

    source = issue_path_for_today()
    if not source.exists():
        raise SystemExit(f"[lock_email_issue] Source issue missing: {source}")

    slug = source.stem
    if not SLOT_ISSUE_RE.fullmatch(slug):
        raise SystemExit(f"[lock_email_issue] Refusing to lock non-slot issue: {slug}")

    target = EMAIL_DIR / source.name
    sent_log = load_sent_log()
    existing_record = sent_log.get(slug)
    if record_blocks_slot_email(existing_record):
        print(f"[lock_email_issue] SKIP: {slug} already has a public Kit record. Preserving locked email snapshot.")
        if not target.exists():
            raise SystemExit(f"[lock_email_issue] Missing locked snapshot for already-sent slot: {target}")
        return 0

    body = source.read_text(encoding="utf-8")
    header = (
        "<!--\n"
        f"Locked email version for {slug}.\n"
        f"Created by lock_email_issue.py at {datetime.now(timezone.utc).isoformat()}.\n"
        "Web article may improve later in content/issues, but Kit sends from this file.\n"
        "-->\n\n"
    )
    # Replace an existing lock header if preparation reruns before the email is sent.
    body = re.sub(r"^<!--\nLocked email version for .*?\n-->\n\n", "", body, flags=re.DOTALL)
    write_text(target, header + body.strip() + "\n")
    print(f"[lock_email_issue] Locked email snapshot: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
