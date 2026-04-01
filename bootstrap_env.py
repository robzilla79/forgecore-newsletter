#!/usr/bin/env python3
"""Create a local .env from committed safe defaults if one does not exist."""
from __future__ import annotations

from utils import WORKSPACE, load_text, write_text


def main() -> int:
    real_env = WORKSPACE / '.env'
    defaults = WORKSPACE / '.env.defaults'
    example = WORKSPACE / '.env.example'

    if real_env.exists():
        print(f'.env already exists: {real_env}')
        return 0

    source = defaults if defaults.exists() else example
    if not source.exists():
        print('No .env.defaults or .env.example found.')
        return 1

    write_text(real_env, load_text(source))
    print(f'Created {real_env} from {source.name}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
