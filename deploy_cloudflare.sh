#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python publish_site.py
python deploy_cloudflare.py
