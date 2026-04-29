#!/usr/bin/env python3
from __future__ import annotations
import json
import os
import re
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any
import requests

from templates.system_prompts import ANALYST_SYSTEM, AUTHOR_SYSTEM, EDITOR_SYSTEM, SCOUT_SYSTEM
from issue_contract import ensure_issue_contract, latest_brief_path, latest_issue_path, latest_raw_intel_path
from utils import WORKSPACE, append_text, load_project_env, load_text, now_str, today_str, write_text

load_project_env()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
RESEARCH_MODEL = os.getenv("RESEARCH_MODEL", "gpt-4o-mini")
WRITER_MODEL = os.getenv("WRITER_MODEL", "gpt-4o-mini")
EDITOR_MODEL = os.getenv("EDITOR_MODEL", WRITER_MODEL)

ALLOWED = ("scout", "analyst", "author", "editor", "publisher", "deployer", "all", "pipeline")
AGENT_PREFIXES = {
    "scout": ["research/raw/", "state/"],
    "analyst": ["research/briefs/", "state/"],
    "author": ["content/issues/", "content/blueprints/", "state/"],
    "editor": ["content/issues/", "state/"],
}
DEFAULT_PATHS = {
    "scout": "research/raw/RAW-INTEL-{date}.md",
    "analyst": "research/briefs/EDITORIAL-BRIEF-{date}.md",
    "author": "content/issues/{date}.md",
    "editor": "content/issues/{date}.md",
}
SYSTEMS = {
    "scout": SCOUT_SYSTEM,
    "analyst": ANALYST_SYSTEM,
    "author": AUTHOR_SYSTEM,
    "editor": EDITOR_SYSTEM,
}

def progress(msg: str) -> None:
    print(f"[progress] {msg}", flush=True)
    append_text(WORKSPACE / "state" / "progress-log.md", f"[{now_str()}] {msg}")

def error(agent: str, msg: str) -> None:
    print(f"[error:{agent}] {msg}", file=sys.stderr, flush=True)
    append_text(WORKSPACE / "state" / "errors.log", f"[{now_str()}] {agent}: {msg}")

def choose_model(agent: str) -> str:
    if agent in {"scout", "analyst"}:
        return RESEARCH_MODEL
    if agent == "editor":
        return EDITOR_MODEL
    return WRITER_MODEL

def gather_research_snippets() -> str:
    blocks: list[str] = []
    for path in sorted((WORKSPACE / "research" / "raw").glob(f"{today_str()}-*.md"))[:8]:
        blocks.append(f"## {path.name}
{load_text(path)[:1800]}")
    if not blocks:
        latest = latest_raw_intel_path()
        if latest.exists():
            blocks.append(f"## {latest.name}
{load_text(latest)[:4000]}")
    return "

".join(blocks)

def build_context(agent: str) -> str:
    raw_path = latest_raw_intel_path()
    brief_path = latest_brief_path()
    issue_path = latest_issue_path()
    parts = [
        f"# TIMESTAMP
{now_str()}",
        f"# GOALS
{load_text(WORKSPACE / 'GOALS.md')}",
        f"# RULES
{load_text(WORKSPACE / 'AGENTS.md')}",
        f"# SOUL
{load_text(WORKSPACE / 'agents' / agent / 'SOUL.md')}",
        f"# MEMORY
{load_text(WORKSPACE / 'agents' / agent / 'MEMORY.md')}",
        f"# RAW_INTEL ({raw_path.name})
{load_text(raw_path)[:7000]}",
        f"# RESEARCH_ITEMS
{gather_research_snippets()[:9000]}",
        f"# BRIEF ({brief_path.name})
{load_text(brief_path)[:7000]}",
        f"# ISSUE ({issue_path.name})
{load_text(issue_path)[:9000]}",
    ]
    return "

".join(parts)[:20000]

def call_openai(model: str, prompt: str) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set")
    
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.15,
        "response_format": {"type": "json_object"}
    }
    
    for attempt in range(1, 4):
        try:
            resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=300)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
    return ""

def parse_json(raw: str) -> dict[str, Any]:
    return json.loads(raw)

def validate_path(agent: str, proposed: str) -> Path:
    rel = (proposed or DEFAULT_PATHS[agent].format(date=today_str())).replace("\\", "/").strip()
    path = Path(rel)
    if path.is_absolute():
        path = Path(DEFAULT_PATHS[agent].format(date=today_str()))
    final = (WORKSPACE / path).resolve()
    return final

def build_prompt(agent: str, context: str) -> str:
    schema = {
        "summary": "Short description of action taken",
        "files": [
            {
                "path": "relative/path.md",
                "mode": "append|overwrite",
                "content": "Markdown or code",
            }
        ],
        "memory_update": "Optional concise MEMORY.md replacement or empty string",
    }
    hints = {
        "scout": "Write a high-signal raw intel synthesis. Rank promising angles and identify one strong Tool of the Week candidate.",
        "analyst": "Write a strong editorial brief with audience, thesis, why now, section plan, SEO title ideas, CTA direction, and distribution angles.",
        "author": "Write a COMPLETE, FULL-LENGTH newsletter issue. Minimum 600 words. Issue file must be written to content/issues/{today_str()}.md.",
        "editor": "Edit the issue draft. Return the COMPLETE edited Markdown in the 'content' field. Keep ALL required sections.",
    }
    return (
        SYSTEMS[agent] + 
        f"

You MUST respond with ONLY a single valid JSON object following this schema:
{json.dumps(schema, indent=2)}
" +
        f"
Task:
{hints[agent]}
" +
        f"
Context:
{context}"
    )

def apply(agent: str, result: dict[str, Any]) -> int:
    count = 0
    for item in result.get("files", []):
        path = validate_path(agent, str(item.get("path", "")))
        content = str(item.get("content", "")).strip() + "
"
        if item.get("mode") == "append":
            append_text(path, content)
        else:
            write_text(path, content)
        count += 1
    if result.get("memory_update"):
        write_text(WORKSPACE / "agents" / agent / "MEMORY.md", result["memory_update"] + "
")
    return count

def run_llm(agent: str) -> dict[str, Any]:
    start = time.time()
    model = choose_model(agent)
    progress(f"[{agent}] Starting with {model}")
    try:
        raw = call_openai(model, build_prompt(agent, build_context(agent)))
        parsed = parse_json(raw)
        count = apply(agent, parsed)
        duration = time.time() - start
        progress(f"{agent}: {parsed.get('summary', 'Done')} (files={count}, duration={duration:.2f}s)")
        return {"status": "ok", "agent": agent, "files_updated": count, "duration_s": duration, "summary": parsed.get("summary")}
    except Exception as exc:
        duration = time.time() - start
        error(agent, f"{type(exc).__name__}: {exc}")
        return {"status": "error", "agent": agent, "files_updated": 0, "duration_s": duration, "summary": str(exc)}

def run_script(name: str, script_name: str) -> dict[str, Any]:
    start = time.time()
    try:
        cp = subprocess.run([sys.executable, str(WORKSPACE / script_name)], capture_output=True, text=True)
        if cp.returncode != 0:
            raise RuntimeError(cp.stderr)
        duration = time.time() - start
        return {"status": "ok", "agent": name, "files_updated": 1, "duration_s": duration, "summary": "ok"}
    except Exception as exc:
        duration = time.time() - start
        error(name, str(exc))
        return {"status": "error", "agent": name, "files_updated": 0, "duration_s": duration, "summary": str(exc)}

def run_pipeline() -> int:
    results = []
    results.append(run_script("research", "web_research.py"))
    for agent in ["scout", "analyst", "author", "editor"]:
        results.append(run_llm(agent))
    run_script("publisher", "publish_site.py")
    return 0 if all(r["status"] == "ok" for r in results) else 1

def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in ALLOWED:
        return 1
    target = sys.argv[1]
    if target == "pipeline":
        return run_pipeline()
    result = run_llm(target)
    return 0 if result["status"] == "ok" else 1

if __name__ == "__main__":
    raise SystemExit(main())
