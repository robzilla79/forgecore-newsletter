from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import dotenv_values

WORKSPACE = Path(os.environ.get('AGENT_WORKSPACE', '.')).resolve()
LOCAL_TZ_NAME = os.environ.get('FORGECORE_TIMEZONE', 'America/Chicago')
LOCAL_TZ = ZoneInfo(LOCAL_TZ_NAME)


def load_project_env() -> list[str]:
    """Load safe project defaults and then local overrides.

    Precedence:
    1. existing process environment
    2. local .env
    3. committed .env.defaults (or .env.example fallback)
    """
    loaded: list[str] = []
    existing_keys = set(os.environ.keys())

    defaults_path = WORKSPACE / '.env.defaults'
    example_path = WORKSPACE / '.env.example'
    real_path = WORKSPACE / '.env'

    source_default = defaults_path if defaults_path.exists() else example_path if example_path.exists() else None
    if source_default and source_default.exists():
        for key, value in dotenv_values(source_default).items():
            if value is not None:
                os.environ.setdefault(key, value)
        loaded.append(source_default.name)

    if real_path.exists():
        for key, value in dotenv_values(real_path).items():
            if value is not None and key not in existing_keys:
                os.environ[key] = value
        loaded.append(real_path.name)

    return loaded


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def local_now() -> dt.datetime:
    return utc_now().astimezone(LOCAL_TZ)


def now_str() -> str:
    return utc_now().strftime('%Y-%m-%d %H:%M:%S UTC')


def local_now_str() -> str:
    return local_now().strftime('%Y-%m-%d %H:%M:%S %Z')


def today_str() -> str:
    """Return the ForgeCore business date in Central time.

    GitHub Actions cron runs in UTC, but ForgeCore's AM/PM newsletter slots are
    a Central-time business cadence. Using UTC here caused late-night Central
    runs to create or send the next day's slot too early.
    """
    return local_now().strftime('%Y-%m-%d')


def issue_slot() -> str:
    return os.getenv('ISSUE_SLOT', '').strip().lower()


def issue_id_for_today() -> str:
    slot = issue_slot()
    base = today_str()
    return f'{base}-{slot}' if slot in {'am', 'pm'} else base


def issue_path_for_today() -> Path:
    return WORKSPACE / 'content' / 'issues' / f'{issue_id_for_today()}.md'


def artifact_suffix_for_issue(path: Path | None = None) -> str:
    target = path or issue_path_for_today()
    return target.stem or 'latest'


def load_text(path: Path, default: str = '') -> str:
    try:
        return path.read_text(encoding='utf-8') if path.exists() else default
    except Exception:
        return default


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def append_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.exists() and path.stat().st_size > 0
    with path.open('a', encoding='utf-8') as fh:
        if existing:
            fh.write('\n\n---\n\n')
        fh.write(text.rstrip() + '\n')


def dump_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
