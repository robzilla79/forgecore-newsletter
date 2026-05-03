#!/usr/bin/env python3
"""Render ForgeCore lead magnet assets.

Lean purpose: make the Solo Operator AI Workflow Pack a real public asset,
not just landing-page copy.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST_DIR = ROOT / "site" / "dist"
PACK_SOURCE = ROOT / "lead-magnets" / "solo-operator-ai-workflow-pack.md"
PACK_SLUG = "downloads/solo-operator-ai-workflow-pack"
SITE_BASE = "https://news.forgecore.co"
PACK_URL = f"{SITE_BASE}/{PACK_SLUG}/"
SIGNUP = "https://forge-daily.kit.com/232bce5a31"


def safe_json_ld(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def inline_md(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return text


def markdown_to_html(md: str) -> str:
    out: list[str] = []
    in_ul = False
    in_ol = False
    in_code = False
    code_lines: list[str] = []

    def close_lists() -> None:
        nonlocal in_ul, in_ol
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            out.append("</ol>")
            in_ol = False

    for raw in md.splitlines():
        line = raw.rstrip()
        if line.startswith("```"):
            close_lists()
            if in_code:
                out.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
                code_lines = []
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue
        if not line.strip():
            close_lists()
            continue
        if line.startswith("# "):
            close_lists()
            out.append(f"<h1>{inline_md(line[2:].strip())}</h1>")
            continue
        if line.startswith("## "):
            close_lists()
            out.append(f"<h2>{inline_md(line[3:].strip())}</h2>")
            continue
        if line.startswith("---"):
            close_lists()
            out.append("<hr>")
            continue
        if line.startswith("| ") and line.endswith("|"):
            close_lists()
            # Keep markdown tables readable without complex parsing.
            out.append(f"<pre><code>{html.escape(line)}</code></pre>")
            continue
        bullet = re.match(r"^-\s+(.*)", line)
        if bullet:
            if not in_ul:
                close_lists()
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{inline_md(bullet.group(1))}</li>")
            continue
        numbered = re.match(r"^\d+\.\s+(.*)", line)
        if numbered:
            if not in_ol:
                close_lists()
                out.append("<ol>")
                in_ol = True
            out.append(f"<li>{inline_md(numbered.group(1))}</li>")
            continue
        close_lists()
        out.append(f"<p>{inline_md(line)}</p>")

    close_lists()
    if in_code:
        out.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
    return "\n".join(out)


def render_pack_page() -> None:
    if not PACK_SOURCE.exists():
        raise SystemExit(f"Missing lead magnet source: {PACK_SOURCE}")
    md = PACK_SOURCE.read_text(encoding="utf-8")
    body = markdown_to_html(md)
    schema = {
        "@context": "https://schema.org",
        "@type": "CreativeWork",
        "name": "The Solo Operator AI Workflow Pack",
        "url": PACK_URL,
        "description": "A practical AI workflow pack with checklists, prompts, a tool decision matrix, and bad-fit warnings for solo operators.",
        "audience": {"@type": "Audience", "audienceType": "Solo founders, creators, consultants, builders, and small business operators"},
    }
    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>The Solo Operator AI Workflow Pack | ForgeCore</title>
  <meta name="description" content="A practical AI workflow pack with checklists, prompts, a tool decision matrix, and bad-fit warnings for solo operators.">
  <link rel="canonical" href="{PACK_URL}">
  <script type="application/ld+json">{safe_json_ld(schema)}</script>
  <style>
    body {{ margin:0; font-family:Inter, ui-sans-serif, system-ui, sans-serif; background:#080b12; color:#e5e7eb; line-height:1.65; }}
    a {{ color:#38bdf8; }} .wrap {{ width:min(920px,94vw); margin:0 auto; }}
    header, footer {{ padding:24px 0; border-bottom:1px solid #1f2937; }} footer {{ border-top:1px solid #1f2937; border-bottom:0; color:#9ca3af; }}
    main {{ padding:28px 0 64px; }} h1 {{ font-size:clamp(2.1rem,5vw,3.5rem); line-height:1.04; letter-spacing:-.04em; }}
    h2 {{ margin-top:2rem; padding-top:1rem; border-top:1px solid #1f2937; }}
    pre {{ background:#030712; border:1px solid #1f2937; border-radius:14px; padding:14px; overflow:auto; }}
    code {{ background:#030712; padding:2px 4px; border-radius:5px; }}
    .button {{ display:inline-block; padding:11px 16px; border-radius:999px; background:#38bdf8; color:#04111f; font-weight:900; text-decoration:none; }}
    .secondary {{ background:#111827; color:#e5e7eb; border:1px solid #334155; }}
  </style>
</head>
<body>
<header><div class="wrap"><p><a href="/">ForgeCore</a> / Workflow Pack</p><p><a class="button" href="{SIGNUP}">Subscribe to ForgeCore</a> <a class="button secondary" href="/workflow-pack/">Back to pack landing page</a></p></div></header>
<main><div class="wrap">{body}</div></main>
<footer><div class="wrap">ForgeCore helps solo operators use AI tools to build systems, save time, and create income.</div></footer>
</body>
</html>
"""
    out = DIST_DIR / PACK_SLUG / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")


def add_url_to_file(path: Path, line: str) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    if line in text:
        return
    path.write_text(text.rstrip() + "\n" + line + "\n", encoding="utf-8")


def patch_discovery_files() -> None:
    sitemap = DIST_DIR / "sitemap.xml"
    if sitemap.exists():
        text = sitemap.read_text(encoding="utf-8")
        if PACK_URL not in text:
            insert = f"<url><loc>{PACK_URL}</loc></url>"
            text = text.replace("</urlset>", insert + "</urlset>") if "</urlset>" in text else text.rstrip() + "\n" + insert + "\n"
            sitemap.write_text(text, encoding="utf-8")
    add_url_to_file(DIST_DIR / "llms.txt", f"- Solo Operator AI Workflow Pack asset: {PACK_URL}")


def patch_workflow_pack_landing() -> None:
    page = DIST_DIR / "workflow-pack" / "index.html"
    if not page.exists():
        return
    text = page.read_text(encoding="utf-8")
    if "/downloads/solo-operator-ai-workflow-pack/" in text:
        return
    cta = '<p><a class="button secondary" href="/downloads/solo-operator-ai-workflow-pack/">Read the workflow pack now</a></p>'
    text = text.replace("<h2>Get the pack</h2>", cta + "\n<h2>Get the pack</h2>", 1)
    page.write_text(text, encoding="utf-8")


def main() -> int:
    render_pack_page()
    patch_discovery_files()
    patch_workflow_pack_landing()
    print(f"Rendered lead magnet: {PACK_URL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
