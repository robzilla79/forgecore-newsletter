#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import subprocess
from dotenv import load_dotenv
from utils import WORKSPACE

load_dotenv(WORKSPACE / ".env")
PROJECT = os.getenv("CLOUDFLARE_PAGES_PROJECT", "forgecore-newsletter")


def find_wrangler_cmd() -> list[str]:
    candidates = [
        ["wrangler.cmd"],
        ["wrangler"],
        ["npx.cmd", "wrangler"],
        ["npx", "wrangler"],
    ]
    for cmd in candidates:
        if shutil.which(cmd[0]):
            return cmd
    raise FileNotFoundError(
        "Could not find Wrangler. Install Node.js and run `npm install -g wrangler`, "
        "or ensure npx is on PATH."
    )


def main() -> int:
    dist_dir = WORKSPACE / "site" / "dist"
    if not dist_dir.exists():
        print(f"[ERROR] Build output not found: {dist_dir}")
        return 1

    base = find_wrangler_cmd()
    cmd = base + [
        "pages",
        "deploy",
        str(dist_dir),
        "--project-name",
        PROJECT,
    ]

    print("[INFO] Running:", " ".join(cmd))
    cp = subprocess.run(cmd, cwd=WORKSPACE, shell=False)
    return cp.returncode


if __name__ == "__main__":
    raise SystemExit(main())