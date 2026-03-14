from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
from typing import Any

WORKSPACE = Path(os.environ.get('AGENT_WORKSPACE', '.')).resolve()


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def now_str() -> str:
    return utc_now().strftime('%Y-%m-%d %H:%M:%S UTC')


def today_str() -> str:
    return utc_now().strftime('%Y-%m-%d')


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
