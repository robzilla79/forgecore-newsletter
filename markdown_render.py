from __future__ import annotations

"""Shared Markdown → HTML renderer used by both site and email pipelines.

Design goals:
- Escape HTML by default to avoid injection.
- Support headings, unordered lists, code fences, and horizontal rules.
- Keep output small and consistent across publish_site and beehiiv_publish.
"""

import html
import re
from typing import List


def format_inline(text: str) -> str:
    """Escape HTML, then apply inline markdown (bold, italic, code, links)."""
    text = html.escape(text)
    # Bold
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__(.+?)__", r"<strong>\1</strong>", text)
    # Italic (single * or _)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)", r"<em>\1</em>", text)
    # Code
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    # Links
    text = re.sub(
        r"\[([^\]]+)\]\((https?://[^)]+)\)",
        r'<a href="\2">\1</a>',
        text,
    )
    return text


def md_to_html(text: str) -> str:
    """Lightweight Markdown → HTML.

    Supports:
    - #, ##, ### headings
    - Unordered lists (-, *, •)
    - Fenced code blocks (```)
    - Horizontal rules (--- or *** lines)
    - Paragraphs
    """
    out: List[str] = []
    lines = text.splitlines()
    paragraph: List[str] = []
    code_lines: List[str] = []
    in_code = False
    in_list = False

    def flush_para() -> None:
        nonlocal paragraph
        if paragraph:
            joined = " ".join(l.strip() for l in paragraph if l.strip())
            out.append(f"<p>{format_inline(joined)}</p>")
            paragraph = []

    for raw in lines:
        line = raw.rstrip()

        # Code fence
        if line.startswith("```"):
            flush_para()
            if in_list:
                out.append("</ul>")
                in_list = False
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

        # Blank line
        if not line.strip():
            flush_para()
            if in_list:
                out.append("</ul>")
                in_list = False
            continue

        # Bullet
        if line.startswith(("- ", "* ", "\u2022 ")):
            flush_para()
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{format_inline(line[2:].strip())}</li>")
            continue

        if in_list:
            out.append("</ul>")
            in_list = False

        # Headings and horizontal rules
        if line.startswith("### "):
            flush_para()
            out.append(f"<h3>{format_inline(line[4:].strip())}</h3>")
        elif line.startswith("## "):
            flush_para()
            out.append(f"<h2>{format_inline(line[3:].strip())}</h2>")
        elif line.startswith("# "):
            flush_para()
            out.append(f"<h1>{format_inline(line[2:].strip())}</h1>")
        elif re.match(r"^-{3,}$|^\*{3,}$", line):
            flush_para()
            out.append("<hr>")
        else:
            paragraph.append(line)

    flush_para()
    if in_list:
        out.append("</ul>")
    if in_code:
        out.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
    return "\n".join(out)
