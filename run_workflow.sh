#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python agent_loop.py all
