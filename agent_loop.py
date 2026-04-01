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
from dotenv import load_dotenv

from templates.system_prompts import ANALYST_SYSTEM, AUTHOR_SYSTEM, EDITOR_SYSTEM, SCOUT_SYSTEM
from issue_contract import ensure_issue_contract, latest_brief_path, latest_issue_path, latest_raw_intel_path
from utils import WORKSPACE, append_text, load_text, now_str, today_str, write_text

load_dotenv(WORKSPACE / ".env")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
RESEARCH_MODEL = os.getenv("RESEARCH_MODEL", "qwen3:14b")
WRITER_MODEL = os.getenv("WRITER_MODEL", "qwen3:14b")
EDITOR_MODEL = os.getenv("EDITOR_MODEL", WRITER_MODEL)
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "qwen3:8b")
MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", "22000"))
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "300"))
OLLAMA_RETRIES = int(os.getenv("OLLAMA_RETRIES", "3"))
AUTO_REPAIR_PATHS = os.getenv("AUTO_REPAIR_PATHS", "1") == "1"

ALLOWED = ("scout", "analyst", "author", "editor", "publisher", "deployer", "all", "pipeline")
AGENT_PREFIXES = {
    "scout": ["research/raw/", "state/"],
    "analyst": ["research/briefs/", "state/"],
    "author": ["content/issues/", "content/blueprints/", "state/"],
    "editor": ["content/issues/", "state/"],
}
# Canonical naming: YYYY-MM-DD.md — no ISSUE- prefix, no slug suffix.
# issue_contract.list_issue_files() also matches legacy ISSUE-*.md files for
# backward compatibility, but all new writes use this format.
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

# Models that emit <think> blocks before JSON — suppress on first call via API option
_THINKING_MODEL_PREFIXES = ("qwen3", "qwq", "deepseek-r1", "deepseek-r2")

# Module-level constants to avoid backslash-in-f-string (invalid in Python < 3.12)
_OK_MARK = "\u2713"
_FAIL_MARK = "\u2717"


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


def _is_thinking_model(model: str) -> bool:
    """Return True if the model is known to emit <think> blocks by default."""
    lower = model.lower()
    return any(lower.startswith(p) for p in _THINKING_MODEL_PREFIXES)


def gather_research_snippets() -> str:
    blocks: list[str] = []
    for path in sorted((WORKSPACE / "research" / "raw").glob(f"{today_str()}-*.md"))[:8]:
        blocks.append(f"## {path.name}\n{load_text(path)[:1800]}")
    if not blocks:
        latest = latest_raw_intel_path()
        if latest.exists():
            blocks.append(f"## {latest.name}\n{load_text(latest)[:4000]}")
    return "\n\n".join(blocks)


def build_context(agent: str) -> str:
    raw_path = latest_raw_intel_path()
    brief_path = latest_brief_path()
    issue_path = latest_issue_path()
    parts = [
        f"# TIMESTAMP\n{now_str()}",
        f"# GOALS\n{load_text(WORKSPACE / 'GOALS.md')}",
        f"# RULES\n{load_text(WORKSPACE / 'AGENTS.md')}",
        f"# SOUL\n{load_text(WORKSPACE / 'agents' / agent / 'SOUL.md')}",
        f"# MEMORY\n{load_text(WORKSPACE / 'agents' / agent / 'MEMORY.md')}",
        f"# RAW_INTEL ({raw_path.name})\n{load_text(raw_path)[:7000]}",
        f"# RESEARCH_ITEMS\n{gather_research_snippets()[:9000]}",
        f"# BRIEF ({brief_path.name})\n{load_text(brief_path)[:7000]}",
        f"# ISSUE ({issue_path.name})\n{load_text(issue_path)[:9000]}",
    ]
    return "\n\n".join(parts)[:MAX_CONTEXT_CHARS]


def ollama_healthcheck() -> tuple[bool, str]:
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10)
        resp.raise_for_status()
        return True, "ok"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def model_exists(model: str) -> bool:
    """Return True if the given model appears in Ollama's local tag list."""
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10)
        resp.raise_for_status()
        names = [m.get("name", "") for m in resp.json().get("models", [])]
        target_base = model.split(":")[0]
        return any(model == name or target_base == name.split(":")[0] for name in names if name)
    except Exception:
        return False


def ensure_model_available(model: str) -> None:
    """Ensure the requested model is present locally, pulling it if needed.

    This prevents repeated /api/generate failures when a model tag is missing.
    """
    if model_exists(model):
        return
    progress(f"ollama: model {model!r} missing, pulling now")
    try:
        subprocess.run(["ollama", "pull", model], check=True, timeout=900)
    except Exception as exc:
        raise RuntimeError(f"Model {model!r} not present and pull failed: {exc}") from exc
    if not model_exists(model):
        raise RuntimeError(f"Model {model!r} still unavailable after pull")


def call_ollama(model: str, prompt: str, *, suppress_thinking: bool = False) -> str:
    """Call Ollama /api/generate.

    suppress_thinking=True sets think=false in the options dict, which prevents
    qwen3-family models from emitting a block before the JSON response.
    This eliminates the double-call pattern seen when the parser fails on the
    think block and falls back to a retry.
    """
    options: dict[str, Any] = {"temperature": 0.15, "num_predict": 2600}

    # Use the /no_think suffix in the prompt as it is the most reliable way
    # to suppress thinking for Qwen3 in some Ollama versions, alongside the
    # options key.
    final_prompt = prompt
    if suppress_thinking and _is_thinking_model(model):
        options["think"] = False
        if not prompt.strip().endswith("/no_think"):
            final_prompt = prompt.strip() + "\n\n/no_think"

    delay = 2.0
    last_err: Exception | None = None
    for attempt in range(1, OLLAMA_RETRIES + 1):
        try:
            resp = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": model,
                    "prompt": final_prompt,
                    "stream": False,
                    "options": options,
                },
                timeout=OLLAMA_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as exc:
            last_err = exc
            error("ollama", f"{model} attempt {attempt}/{OLLAMA_RETRIES}: {exc}")
            if attempt == OLLAMA_RETRIES:
                break
            time.sleep(delay)
            delay = min(delay * 2, 30.0)
        except Exception as exc:
            last_err = exc
            break
    raise RuntimeError(f"Ollama request failed: {last_err}")


def extract_json(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        raise ValueError("No JSON object found in model output")

    # Strip <think>...</think> block if present (qwen3 reasoning models)
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL | re.IGNORECASE).strip()

    blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", raw, flags=re.DOTALL)
    if blocks:
        return blocks[0]
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        return raw[start : end + 1]
    raise ValueError("No JSON object found in model output")


def parse_json(raw: str) -> dict[str, Any]:
    candidate = extract_json(raw)
    candidate = candidate.replace("\u201c", '"').replace("\u201d", '"').replace("\u2019", "'")
    candidate = re.sub(r",(\s*[}\]])", r"\1", candidate)
    return json.loads(candidate)


def repair_path(agent: str, proposed: str) -> str:
    name = Path(proposed).name or f"{today_str()}.md"
    if agent == "scout":
        return f"research/raw/{name}"
    if agent == "analyst":
        return f"research/briefs/{name}"
    if name.endswith(".py"):
        return f"content/blueprints/{name}"
    return f"content/issues/{name}"


def validate_path(agent: str, proposed: str) -> Path:
    rel = (proposed or DEFAULT_PATHS[agent].format(date=today_str())).replace("\\", "/").strip()
    path = Path(rel)
    if path.is_absolute():
        if not AUTO_REPAIR_PATHS:
            raise ValueError(f"Unsafe path: {proposed!r}")
        repaired = repair_path(agent, rel)
        progress(f"{agent}: auto-repaired absolute path {rel!r} -> {repaired!r}")
        path = Path(repaired)
    final = (WORKSPACE / path).resolve()
    final.relative_to(WORKSPACE)
    rel_posix = final.relative_to(WORKSPACE).as_posix()
    if not any(rel_posix.startswith(prefix) for prefix in AGENT_PREFIXES[agent]):
        if not AUTO_REPAIR_PATHS:
            raise ValueError(f"Path not allowed for {agent}: {rel_posix}")
        repaired = repair_path(agent, rel_posix)
        progress(f"{agent}: auto-repaired disallowed path {rel_posix!r} -> {repaired!r}")
        final = (WORKSPACE / repaired).resolve()
    return final


def build_prompt(agent: str, context: str) -> str:
    allowed = "\n".join(f"- {p}" for p in AGENT_PREFIXES[agent])
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
        "scout": "Write a high-signal raw intel synthesis from the research files. Rank promising angles and identify one strong Tool of the Week candidate.",
        "analyst": "Write a strong editorial brief with audience, thesis, why now, section plan, SEO title ideas, CTA direction, and distribution angles.",
        "author": "Write a complete public-facing issue that uses the exact required headings: Hook, Top Story, Why It Matters, Highlights, Tool of the Week, Workflow, CTA, Sources. Use only real source links.",
        "editor": "Rewrite the issue to improve clarity, originality, flow, tone, and publishability while preserving the exact required headings and removing placeholders or fake links.",
    }
    # Remind author/editor of the canonical file naming so they don't invent ISSUE- prefixes
    path_hint = (
        f"\n\nIMPORTANT: Issue files must be written to content/issues/{today_str()}.md "
        "(plain YYYY-MM-DD.md, no 'ISSUE-' prefix, no slug suffix)."
        if agent in {"author", "editor"}
        else ""
    )
    return (
        SYSTEMS[agent]
        + "\n\nReturn ONLY valid JSON matching this schema:\n"
        + json.dumps(schema, indent=2)
        + f"\n\nAllowed path prefixes:\n{allowed}\n\nTask hint:\n{hints[agent]}{path_hint}\n\nContext:\n{context}"
    )


def coerce(agent: str, result: dict[str, Any]) -> dict[str, Any]:
    files: list[dict[str, str]] = []
    for item in result.get("files", []):
        if not isinstance(item, dict):
            continue
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        path = validate_path(agent, str(item.get("path", "")))
        files.append(
            {
                "path": path.relative_to(WORKSPACE).as_posix(),
                "mode": "append" if str(item.get("mode", "append")).lower() == "append" else "overwrite",
                "content": content + "\n",
            }
        )
    if not files:
        fallback = validate_path(agent, DEFAULT_PATHS[agent].format(date=today_str()))
        files.append(
            {
                "path": fallback.relative_to(WORKSPACE).as_posix(),
                "mode": "append",
                "content": f"# {agent.title()} update\n\nNo concrete content returned.\n",
            }
        )
    return {
        "summary": str(result.get("summary", "Completed one action.")).strip(),
        "files": files,
        "memory_update": str(result.get("memory_update", "")).strip(),
    }


def apply(agent: str, result: dict[str, Any]) -> int:
    count = 0
    for item in result["files"]:
        path = WORKSPACE / item["path"]
        if item["mode"] == "append":
            append_text(path, item["content"])
        else:
            write_text(path, item["content"])
        count += 1
    if result["memory_update"]:
        write_text(WORKSPACE / "agents" / agent / "MEMORY.md", result["memory_update"] + "\n")
    return count


def run_llm(agent: str) -> dict[str, Any]:
    raw = ""
    start = time.time()
    model = choose_model(agent)

    # Suppress blocks on first call for reasoning models (qwen3, qwq, deepseek-r1/r2).
    # This avoids the double-call pattern where parse_json fails on the think block and
    # wastes a full inference cycle before the fallback retry succeeds.
    suppress = _is_thinking_model(model)
    print(f"[{agent}] Starting (model={model}, url={OLLAMA_URL}, suppress_thinking={suppress})", flush=True)

    try:
        ok, msg = ollama_healthcheck()
        if not ok:
            print(f"[{agent}] FATAL: Ollama healthcheck failed: {msg}", flush=True)
            raise RuntimeError(f"Ollama healthcheck failed: {msg}")

        ensure_model_available(model)
        print(f"[{agent}] Ollama reachable, model ready, calling model...", flush=True)
        raw = call_ollama(model, build_prompt(agent, build_context(agent)), suppress_thinking=suppress)
        print(f"[{agent}] Model responded ({len(raw)} chars), parsing JSON...", flush=True)

        try:
            parsed = parse_json(raw)
        except Exception as parse_exc:
            # First parse failed — retry with fallback model.
            print(f"[{agent}] JSON parse failed ({parse_exc}), retrying with fallback model...", flush=True)
            fallback_prompt = (
                "Your previous response was invalid JSON. "
                "Return the same result as exactly one valid JSON object. "
                "No prose. No code fences. No tags. No markdown.\n\n"
                "Previous response:\n" + raw
            )
            raw = call_ollama(FALLBACK_MODEL, fallback_prompt, suppress_thinking=True)
            try:
                parsed = parse_json(raw)
            except Exception as second_exc:
                print(
                    f"[{agent}] Fallback parse failed as well ({second_exc}); "
                    "writing raw model output as plain markdown.",
                    flush=True,
                )
                fallback_result = {
                    "summary": "Completed one action (fallback from raw after JSON parse failures).",
                    "files": [
                        {
                            "path": DEFAULT_PATHS[agent].format(date=today_str()),
                            "mode": "append",
                            "content": f"# {agent.title()} update\n\n{raw.strip()}\n",
                        }
                    ],
                    "memory_update": "",
                }
                result = coerce(agent, fallback_result)
                count = apply(agent, result)
                duration = time.time() - start
                print(
                    f"[{agent}] Done via raw fallback: {result['summary']} "
                    f"(files={count}, duration={duration:.2f}s)",
                    flush=True,
                )
                progress(
                    f"{agent}: {result['summary']} "
                    f"(files={count}, duration={duration:.2f}s, model={model})",
                )
                return {
                    "status": "ok",
                    "agent": agent,
                    "files_updated": count,
                    "duration_s": duration,
                    "summary": result["summary"],
                }

        result = coerce(agent, parsed)
        count = apply(agent, result)
        duration = time.time() - start
        print(f"[{agent}] Done: {result['summary']} (files={count}, duration={duration:.2f}s)", flush=True)
        progress(f"{agent}: {result['summary']} (files={count}, duration={duration:.2f}s, model={model})")
        return {
            "status": "ok",
            "agent": agent,
            "files_updated": count,
            "duration_s": duration,
            "summary": result["summary"],
        }
    except Exception as exc:
        duration = time.time() - start
        tb = traceback.format_exc()
        print(f"[{agent}] FAILED after {duration:.2f}s: {type(exc).__name__}: {exc}", flush=True)
        print(f"[{agent}] Traceback:\n{tb}", flush=True)
        error(agent, f"{type(exc).__name__}: {exc}\n\nTraceback:\n{tb}\n\nRaw model output:\n{raw or '[EMPTY RESPONSE]'}\n")
        progress(f"[FAIL] {agent}: {type(exc).__name__}: {exc}")
        return {
            "status": "error",
            "agent": agent,
            "files_updated": 0,
            "duration_s": duration,
            "summary": str(exc),
        }


def run_script(name: str, script_name: str) -> dict[str, Any]:
    start = time.time()
    print(f"[{name}] Running {script_name}...", flush=True)
    try:
        cp = subprocess.run(
            [sys.executable, str(WORKSPACE / script_name)],
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if cp.returncode != 0:
            print(f"[{name}] FAILED (exit {cp.returncode}):\n{cp.stdout}\n{cp.stderr}", flush=True)
            raise RuntimeError((cp.stdout or "") + (cp.stderr or ""))

        duration = time.time() - start
        progress(f"{name}: ok (duration={duration:.2f}s)")
        output = (cp.stdout or "").strip()
        print(f"[{name}] OK ({duration:.2f}s)", flush=True)
        return {
            "status": "ok",
            "agent": name,
            "files_updated": 1,
            "duration_s": duration,
            "summary": output or "ok",
        }
    except Exception as exc:
        duration = time.time() - start
        error(name, f"{type(exc).__name__}: {exc}\n\nTraceback:\n{traceback.format_exc()}")
        progress(f"[FAIL] {name}: {type(exc).__name__}: {exc}")
        return {
            "status": "error",
            "agent": name,
            "files_updated": 0,
            "duration_s": duration,
            "summary": str(exc),
        }


def run_deployer() -> dict[str, Any]:
    if os.getenv("ENABLE_CLOUDFLARE_DEPLOY", "0") != "1":
        return {
            "status": "ok",
            "agent": "deployer",
            "files_updated": 0,
            "duration_s": 0.0,
            "summary": "deploy skipped (ENABLE_CLOUDFLARE_DEPLOY=0)",
        }
    return run_script("deployer", "deploy_cloudflare.py")


def heartbeat(results: list[dict[str, Any]]) -> None:
    fired = ", ".join(
        f"{r['agent']}={_OK_MARK if r['status'] == 'ok' else _FAIL_MARK}" for r in results
    )
    errors = [f"{r['agent']}: {r['summary']}" for r in results if r["status"] != "ok"]
    total_files = sum(int(r.get("files_updated", 0)) for r in results)
    duration = sum(float(r.get("duration_s", 0.0)) for r in results)

    write_text(
        WORKSPACE / "HEARTBEAT.md",
        "\n".join(
            [
                f"# Last Run Status: {now_str()}",
                f"- Agents fired: {fired}",
                f"- Files updated: {total_files}",
                f"- Errors: {'None' if not errors else '; '.join(errors[:5])}",
                f"- Duration: {duration:.2f}s",
                f"- Models: research={RESEARCH_MODEL}, writer={WRITER_MODEL}, editor={EDITOR_MODEL}, fallback={FALLBACK_MODEL}",
            ]
        ) + "\n",
    )


def run_all() -> int:
    ok, msg = ollama_healthcheck()
    if not ok:
        print(f"[run_all] FATAL: Ollama healthcheck failed at start: {msg}", flush=True)
        error("ollama", f"Healthcheck failed at start of run_all: {msg}")
        progress(f"[FAIL] ollama: healthcheck failed: {msg}")
        heartbeat(
            [
                {
                    "status": "error",
                    "agent": "ollama",
                    "files_updated": 0,
                    "duration_s": 0.0,
                    "summary": f"Healthcheck failed: {msg}",
                }
            ]
        )
        return 1

    results: list[dict[str, Any]] = []
    results.append(run_script("research", "web_research.py"))

    for agent in ["scout", "analyst", "author", "editor"]:
        results.append(run_llm(agent))

    try:
        ensure_issue_contract(latest_issue_path())
    except Exception as exc:
        error("contract", f"{type(exc).__name__}: {exc}")
        results.append(
            {
                "status": "error",
                "agent": "contract",
                "files_updated": 0,
                "duration_s": 0.0,
                "summary": str(exc),
            }
        )

    quality_result = run_script("quality-gate", "quality_gate.py")
    results.append(quality_result)

    if quality_result["status"] == "ok":
        results.append(run_script("publisher", "publish_site.py"))
        results.append(run_deployer())
    else:
        results.append(
            {
                "status": "error",
                "agent": "publisher",
                "files_updated": 0,
                "duration_s": 0.0,
                "summary": "publish blocked by quality gate",
            }
        )
        results.append(
            {
                "status": "error",
                "agent": "deployer",
                "files_updated": 0,
                "duration_s": 0.0,
                "summary": "deploy blocked by quality gate",
            }
        )

    heartbeat(results)
    return 0 if all(r["status"] == "ok" for r in results) else 1


def run_pipeline() -> int:
    """High-level pipeline that mirrors the GitHub Actions generate.yml flow.

    - Always refreshes web research.
    - If Ollama is reachable, runs all four agents, enforces the issue
      contract, then uses improve_until_passes.py as the quality controller
      before publishing, deploying, and sending via Beehiiv.
    - If Ollama is not reachable, creates a fallback stub issue, runs the
      quality gate in best-effort mode, then still publishes site + Beehiiv
      so subscribers get something instead of nothing.
    """
    results: list[dict[str, Any]] = []

    # Always refresh raw intel
    results.append(run_script("research", "web_research.py"))

    ollama_ok, msg = ollama_healthcheck()

    if ollama_ok:
        # Run the four core agents
        for agent in ["scout", "analyst", "author", "editor"]:
            results.append(run_llm(agent))

        # Enforce contract on the latest issue before quality/improvement
        try:
            ensure_issue_contract(latest_issue_path())
        except Exception as exc:
            error("contract", f"{type(exc).__name__}: {exc}")
            results.append(
                {
                    "status": "error",
                    "agent": "contract",
                    "files_updated": 0,
                    "duration_s": 0.0,
                    "summary": str(exc),
                }
            )

        # Aggressive improvement loop that wraps the quality gate
        qc = run_script("improve-controller", "improve_until_passes.py")
        results.append(qc)

        if qc["status"] == "ok":
            results.append(run_script("publisher", "publish_site.py"))
            results.append(run_deployer())
            results.append(run_script("beehiiv", "beehiiv_publish.py"))
        else:
            for blocked in ("publisher", "deployer", "beehiiv"):
                results.append(
                    {
                        "status": "error",
                        "agent": blocked,
                        "files_updated": 0,
                        "duration_s": 0.0,
                        "summary": f"{blocked} blocked by quality controller",
                    }
                )
    else:
        # Ollama offline — fall back to a stub issue but still ship something
        error("ollama", f"Healthcheck failed in pipeline: {msg}")
        results.append(
            {
                "status": "error",
                "agent": "ollama",
                "files_updated": 0,
                "duration_s": 0.0,
                "summary": f"Healthcheck failed: {msg}",
            }
        )

        results.append(run_script("stub", "create_stub_issue.py"))
        results.append(run_script("quality-gate", "quality_gate.py"))
        results.append(run_script("publisher", "publish_site.py"))
        results.append(run_deployer())
        results.append(run_script("beehiiv", "beehiiv_publish.py"))

    heartbeat(results)
    return 0 if all(r["status"] == "ok" else r["status"] == "ok" for r in results) else 1


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in ALLOWED:
        print("Usage: python agent_loop.py [scout|analyst|author|editor|publisher|deployer|all|pipeline]")
        return 1

    target = sys.argv[1]
    if target == "all":
        return run_all()
    if target == "pipeline":
        return run_pipeline()

    if target == "publisher":
        result = run_script("publisher", "publish_site.py")
    elif target == "deployer":
        result = run_deployer()
    else:
        result = run_llm(target)

    heartbeat([result])
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
