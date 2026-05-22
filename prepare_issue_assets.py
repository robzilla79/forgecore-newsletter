#!/usr/bin/env python3
"""Prepare a newsletter issue for web publish and locked Kit send.

This script removes the fragile manual handoff between writing an Aware issue
and sending it. Given an issue slug, it:

1. Confirms content/issues/<slug>.md exists.
2. Creates content/email/<slug>.md if missing, using the approved source issue.
3. Renders the static site artifacts through publish_site.py.

It does not call Kit and does not touch state/kit_sent.json.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from utils import WORKSPACE, issue_path_for_today


def latest_issue() -> Path | None:
    issues_dir = WORKSPACE / "content" / "issues"
    if not issues_dir.exists():
        return None
    files = sorted(issues_dir.glob("*.md"), key=lambda p: p.name, reverse=True)
    return files[0] if files else None


def resolve_issue(slug: str | None) -> Path:
    slug = (slug or "").strip()
    if slug:
        path = WORKSPACE / "content" / "issues" / f"{slug}.md"
    else:
        path = issue_path_for_today()
        if not path.exists():
            fallback = latest_issue()
            if fallback:
                path = fallback
    if not path.exists():
        raise FileNotFoundError(f"Issue source not found: {path}")
    return path


def ensure_email_snapshot(issue_path: Path, *, force: bool = False) -> Path:
    email_dir = WORKSPACE / "content" / "email"
    email_dir.mkdir(parents=True, exist_ok=True)
    email_path = email_dir / issue_path.name
    if email_path.exists() and not force:
        print(f"[prepare] Email snapshot already exists: {email_path}")
        return email_path

    source = issue_path.read_text(encoding="utf-8").rstrip() + "\n"
    comment = (
        "<!--\n"
        f"Locked email version for {issue_path.stem}. Generated from {issue_path.as_posix()} by prepare_issue_assets.py.\n"
        "Review source issue before public send.\n"
        "-->\n\n"
    )
    email_path.write_text(comment + source, encoding="utf-8")
    print(f"[prepare] Wrote email snapshot: {email_path}")
    return email_path


def render_site() -> None:
    import publish_site

    print("[prepare] Rendering static site artifacts")
    publish_site.main()


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare Aware issue assets before Kit send")
    parser.add_argument("--issue-slug", default=os.getenv("ISSUE_SLUG", ""), help="Issue slug, e.g. 2026-05-21-em")
    parser.add_argument("--force-email", action="store_true", help="Regenerate the email snapshot even if it exists")
    args = parser.parse_args()

    try:
        issue_path = resolve_issue(args.issue_slug)
        print(f"[prepare] Issue source: {issue_path}")
        ensure_email_snapshot(issue_path, force=args.force_email)
        render_site()
    except Exception as exc:
        print(f"[prepare] ERROR: {exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
