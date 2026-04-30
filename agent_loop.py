#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from openai import OpenAI

from templates.system_prompts import ANALYST_SYSTEM, AUTHOR_SYSTEM, EDITOR_SYSTEM, SCOUT_SYSTEM
from issue_contract import latest_brief_path, latest_issue_path, latest_raw_intel_path
from utils import WORKSPACE, append_text, load_project_env, load_text, now_str, today_str, write_text

load_project_env()

RESEARCH_MODEL = os.getenv("RESEARCH_MODEL", "gpt-4o-mini")
WRITER_MODEL = os.getenv("WRITER_MODEL", "gpt-4o-mini")
EDITOR_MODEL = os.getenv("EDITOR_MODEL", WRITER_MODEL)
ISSUE_SLOT = os.getenv("ISSUE_SLOT", "").strip().lower()

ALLOWED = {"scout", "analyst", "author", "editor"}
STRUCTURED_AGENTS = {"scout", "analyst"}
MARKDOWN_AGENTS = {"author", "editor"}
SYSTEMS = {"scout": SCOUT_SYSTEM, "analyst": ANALYST_SYSTEM, "author": AUTHOR_SYSTEM, "editor": EDITOR_SYSTEM}

REQUIRED_SECTIONS = [
    "## Hook",
    "## Top Story",
    "## Why It Matters",
    "## Highlights",
    "## Tool of the Week",
    "## Workflow",
    "## CTA",
    "## Sources",
]


def issue_id() -> str:
    base = today_str()
    return f"{base}-{ISSUE_SLOT}" if ISSUE_SLOT in {"am", "pm"} else base


def issue_file() -> Path:
    return WORKSPACE / "content" / "issues" / f"{issue_id()}.md"


def progress(message: str) -> None:
    print(f"[progress] {message}", flush=True)
    append_text(WORKSPACE / "state" / "progress-log.md", f"[{now_str()}] {message}")


def error(agent: str, message: str) -> None:
    print(f"[error:{agent}] {message}", file=sys.stderr, flush=True)
    append_text(WORKSPACE / "state" / "errors.log", f"[{now_str()}] {agent}: {message}")


def choose_model(agent: str) -> str:
    if agent in {"scout", "analyst"}:
        return RESEARCH_MODEL
    if agent == "editor":
        return EDITOR_MODEL
    return WRITER_MODEL


def gather_research() -> str:
    blocks: list[str] = []
    for path in sorted((WORKSPACE / "research" / "raw").glob(f"{today_str()}-*.md"))[:8]:
        blocks.append(f"## {path.name}\n{load_text(path)[:1800]}")
    if not blocks:
        path = latest_raw_intel_path()
        blocks.append(f"## {path.name}\n{load_text(path)[:4000]}")
    return "\n\n".join(blocks)


def context(agent: str) -> str:
    current_issue = issue_file() if issue_file().exists() else latest_issue_path()
    parts = [
        f"# TIMESTAMP\n{now_str()}",
        f"# ISSUE_SLOT\n{ISSUE_SLOT or 'default'}",
        f"# ISSUE_ID\n{issue_id()}",
        f"# TARGET_ISSUE_PATH\ncontent/issues/{issue_id()}.md",
        f"# GOALS\n{load_text(WORKSPACE / 'GOALS.md')}",
        f"# RULES\n{load_text(WORKSPACE / 'AGENTS.md')}",
        f"# SOUL\n{load_text(WORKSPACE / 'agents' / agent / 'SOUL.md')}",
        f"# MEMORY\n{load_text(WORKSPACE / 'agents' / agent / 'MEMORY.md')}",
        f"# RAW_INTEL\n{load_text(latest_raw_intel_path())[:7000]}",
        f"# RESEARCH_ITEMS\n{gather_research()[:9000]}",
        f"# BRIEF\n{load_text(latest_brief_path())[:7000]}",
        f"# ISSUE\n{load_text(current_issue)[:9000]}",
    ]
    return "\n\n".join(parts)[:22000]


def openai_client() -> OpenAI:
    return OpenAI()


def call_structured_model(model: str, prompt: str) -> str:
    result = openai_client().chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.15,
        response_format={"type": "json_object"},
    )
    return result.choices[0].message.content or "{}"


def call_markdown_model(model: str, prompt: str) -> str:
    result = openai_client().chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return (result.choices[0].message.content or "").strip()


def build_structured_prompt(agent: str) -> str:
    schema = {
        "summary": "Short description of action taken",
        "files": [{"path": "relative/path.md", "mode": "append|overwrite", "content": "Markdown or code"}],
        "memory_update": "Optional concise MEMORY.md replacement or empty string",
    }
    hints = {
        "scout": "Write a high-signal raw intel synthesis. Rank promising operator-first angles and identify one strong Tool of the Week candidate.",
        "analyst": "Write a strong editorial brief with thesis, why now, section plan, CTA direction, and distribution angles.",
    }
    return SYSTEMS[agent] + "\n\nReturn only one valid JSON object matching this schema:\n" + json.dumps(schema, indent=2) + f"\n\nTask:\n{hints[agent]}\n\nContext:\n{context(agent)}"


def build_markdown_prompt(agent: str) -> str:
    target = f"content/issues/{issue_id()}.md"
    if agent == "author":
        task = f"Write the full final newsletter issue as Markdown for {target}. Return ONLY Markdown. Do not wrap it in JSON. Do not include file paths, notes, explanations, or code fences around the whole article."
    else:
        task = f"Edit the existing draft for {target}. Return ONLY the complete final Markdown issue. Do not wrap it in JSON. Do not include notes, explanations, or file-operation text."
    return SYSTEMS[agent] + f"\n\nTask:\n{task}\n\nContext:\n{context(agent)}"


def output_path(agent: str, proposed: str) -> Path:
    if agent in MARKDOWN_AGENTS:
        return issue_file()
    rel = proposed.strip().replace("\\", "/")
    if not rel:
        rel = "research/raw/RAW-INTEL-{date}.md" if agent == "scout" else "research/briefs/EDITORIAL-BRIEF-{date}.md"
        rel = rel.format(date=today_str())
    path = Path(rel)
    if path.is_absolute():
        path = Path(path.name)
    return (WORKSPACE / path).resolve()


def apply_structured(agent: str, result: dict[str, Any]) -> int:
    count = 0
    for item in result.get("files", []):
        path = output_path(agent, str(item.get("path", "")))
        content = str(item.get("content", "")).strip() + "\n"
        if item.get("mode") == "append":
            append_text(path, content)
        else:
            write_text(path, content)
        count += 1
    memory = str(result.get("memory_update", "")).strip()
    if memory:
        write_text(WORKSPACE / "agents" / agent / "MEMORY.md", memory + "\n")
    return count


def clean_markdown(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```markdown"):
        cleaned = cleaned[len("```markdown"):].strip()
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:].strip()
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()
    return cleaned + "\n"


def validate_markdown(agent: str, text: str) -> None:
    if not text.strip().startswith("# "):
        raise ValueError(f"{agent} did not return a Markdown issue title")
    missing = [section for section in REQUIRED_SECTIONS if section not in text]
    if missing:
        raise ValueError(f"{agent} Markdown missing required sections: {', '.join(missing)}")
    if len(text.split()) < 500:
        raise ValueError(f"{agent} Markdown too short: {len(text.split())} words")


def run(agent: str) -> int:
    start = time.time()
    model = choose_model(agent)
    progress(f"[{agent}] Starting with {model} (issue={issue_id()})")
    try:
        if agent in MARKDOWN_AGENTS:
            markdown = clean_markdown(call_markdown_model(model, build_markdown_prompt(agent)))
            validate_markdown(agent, markdown)
            write_text(issue_file(), markdown)
            count = 1
            summary = f"Wrote Markdown issue to content/issues/{issue_id()}.md"
        else:
            raw = call_structured_model(model, build_structured_prompt(agent))
            parsed = json.loads(raw)
            count = apply_structured(agent, parsed)
            summary = str(parsed.get("summary", "Done"))
        progress(f"{agent}: {summary} (files={count}, duration={time.time() - start:.2f}s)")
        return 0
    except Exception as exc:
        error(agent, f"{type(exc).__name__}: {exc}")
        return 1


def main() -> int:
    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is not set in GitHub Actions secrets.", file=sys.stderr)
        return 1
    if len(sys.argv) != 2 or sys.argv[1] not in ALLOWED:
        print("Usage: agent_loop.py <scout|analyst|author|editor>", file=sys.stderr)
        return 1
    return run(sys.argv[1])


if __name__ == "__main__":
    raise SystemExit(main())
