#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime
import os

from utils import WORKSPACE, load_text, write_text

SITE_BASE_URL = os.getenv("SITE_BASE_URL", "https://news.forgecore.co")

def list_issues():
    issues_dir = WORKSPACE / "content" / "issues"
    return sorted(issues_dir.glob("*.md"), reverse=True)

def parse_issue(path):
    text = load_text(path)
    title = text.split("\n")[0].replace("#", "").strip()
    slug = path.stem.lower()
    return {
        "title": title,
        "slug": slug,
        "html": f"<pre>{text}</pre>",
        "date": slug[:10]
    }

def render_home(issues):
    items = ""
    for i in issues:
        items += f"<li><a href='/{i['slug']}/'>{i['title']}</a></li>"

    return f"""
    <h1>ForgeCore</h1>
    <ul>{items}</ul>
    """

def main():
    dist = WORKSPACE / "site" / "dist"
    dist.mkdir(parents=True, exist_ok=True)

    issues = [parse_issue(p) for p in list_issues()]

    for i in issues:
        d = dist / i["slug"]
        d.mkdir(parents=True, exist_ok=True)
        write_text(d / "index.html", f"<h1>{i['title']}</h1>{i['html']}")

    write_text(dist / "index.html", render_home(issues))

    print("Published", len(issues), "issues")

if __name__ == "__main__":
    main()
