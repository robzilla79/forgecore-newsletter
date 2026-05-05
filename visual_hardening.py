#!/usr/bin/env python3
"""Add lightweight ForgeCore visuals to rendered newsletter pages.

Post-render only: this script does not mutate source issues. It updates
site/dist after publish_site.py and before verification/deploy.
"""
from __future__ import annotations

import html
import re
from pathlib import Path

from utils import WORKSPACE, write_text

DIST_DIR = WORKSPACE / "site" / "dist"
VISUAL_DIR = DIST_DIR / "images" / "visuals"
CSS_MARKER = "/* forgecore visual hardening */"
ARTICLE_MARKER = "<!-- forgecore-article-visuals -->"
OG_IMAGE_URL = "https://news.forgecore.co/images/visuals/default-workflow.svg"

VISUAL_CSS = f"""
{CSS_MARKER}
.card::before {{
  content:"";
  display:block;
  height:118px;
  margin:-2px -2px 16px;
  border-radius:16px;
  border:1px solid rgba(56,189,248,.22);
  background:
    radial-gradient(circle at 18% 20%, rgba(56,189,248,.36), transparent 28%),
    radial-gradient(circle at 82% 18%, rgba(167,139,250,.28), transparent 30%),
    linear-gradient(135deg, rgba(15,23,42,.96), rgba(8,47,73,.62));
  box-shadow:inset 0 1px 0 rgba(255,255,255,.04);
}}
.tool-card::before {{ display:none; }}
.fc-article-visual {{
  position:relative;
  overflow:hidden;
  margin:22px 0 24px;
  min-height:260px;
  border:1px solid rgba(56,189,248,.26);
  border-radius:24px;
  background:
    radial-gradient(circle at 18% 18%, rgba(56,189,248,.36), transparent 28%),
    radial-gradient(circle at 84% 16%, rgba(167,139,250,.30), transparent 30%),
    linear-gradient(135deg, #020617, #0f172a 54%, #082f49);
  box-shadow:0 22px 70px rgba(0,0,0,.28);
}}
.fc-article-visual::before {{
  content:"";
  position:absolute;
  inset:0;
  opacity:.18;
  background-image:
    linear-gradient(rgba(148,163,184,.18) 1px, transparent 1px),
    linear-gradient(90deg, rgba(148,163,184,.18) 1px, transparent 1px);
  background-size:32px 32px;
  mask-image:linear-gradient(to bottom, black, transparent 92%);
}}
.fc-article-visual-inner {{
  position:relative;
  display:flex;
  min-height:260px;
  flex-direction:column;
  justify-content:flex-end;
  padding:clamp(20px,4vw,36px);
}}
.fc-visual-label {{
  margin:0 0 8px;
  color:#67e8f9;
  font-size:.74rem;
  font-weight:900;
  letter-spacing:.16em;
  text-transform:uppercase;
}}
.fc-article-visual h2 {{
  max-width:760px;
  margin:0;
  color:#fff;
  font-size:clamp(1.65rem,4vw,3.1rem);
  line-height:1.04;
  letter-spacing:-.05em;
  border:0;
  padding:0;
}}
.fc-visual-pills {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:18px; }}
.fc-visual-pills span {{
  border:1px solid rgba(125,211,252,.35);
  border-radius:999px;
  background:rgba(15,23,42,.62);
  color:#e0f2fe;
  font-size:.72rem;
  font-weight:900;
  letter-spacing:.08em;
  padding:6px 10px;
  text-transform:uppercase;
}}
.fc-workflow-visual {{
  display:grid;
  gap:16px;
  margin:20px 0 28px;
  padding:18px;
  border:1px solid rgba(56,189,248,.22);
  border-radius:20px;
  background:linear-gradient(135deg, rgba(15,23,42,.94), rgba(8,47,73,.38));
}}
.fc-workflow-visual h2 {{ margin:0; padding:0; border:0; color:#fff; letter-spacing:-.035em; }}
.fc-workflow-steps {{ display:grid; gap:10px; margin:0; padding:0; list-style:none; }}
.fc-workflow-steps li {{
  display:grid;
  grid-template-columns:auto 1fr;
  gap:10px;
  align-items:center;
  margin:0;
  padding:12px;
  border:1px solid rgba(148,163,184,.18);
  border-radius:14px;
  background:rgba(2,6,23,.42);
}}
.fc-step-number {{
  display:inline-grid;
  width:34px;
  height:34px;
  place-items:center;
  border-radius:11px;
  background:rgba(56,189,248,.16);
  color:#bae6fd;
  font-size:.72rem;
  font-weight:900;
}}
@media (min-width:760px) {{
  .fc-workflow-visual {{ grid-template-columns:.9fr 1.1fr; align-items:center; }}
}}
@media (max-width:640px) {{
  .card::before {{ height:92px; }}
  .fc-article-visual, .fc-article-visual-inner {{ min-height:210px; }}
}}
"""

SVG_ASSETS = {
    "default-workflow.svg": """<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"1600\" height=\"900\" viewBox=\"0 0 1600 900\"><defs><linearGradient id=\"bg\" x1=\"0\" x2=\"1\" y1=\"0\" y2=\"1\"><stop offset=\"0\" stop-color=\"#020617\"/><stop offset=\".55\" stop-color=\"#0f172a\"/><stop offset=\"1\" stop-color=\"#082f49\"/></linearGradient></defs><rect width=\"1600\" height=\"900\" fill=\"url(#bg)\"/><circle cx=\"320\" cy=\"180\" r=\"300\" fill=\"#22d3ee\" opacity=\".24\"/><circle cx=\"1320\" cy=\"170\" r=\"260\" fill=\"#a78bfa\" opacity=\".22\"/><text x=\"110\" y=\"145\" fill=\"#67e8f9\" font-family=\"Inter,Arial,sans-serif\" font-size=\"34\" font-weight=\"800\" letter-spacing=\"8\">FORGECORE</text><text x=\"110\" y=\"235\" fill=\"#fff\" font-family=\"Inter,Arial,sans-serif\" font-size=\"78\" font-weight=\"900\">Operator Workflow</text><text x=\"112\" y=\"300\" fill=\"#cbd5e1\" font-family=\"Inter,Arial,sans-serif\" font-size=\"32\">Turn AI tool noise into one repeatable system.</text><g transform=\"translate(120 460)\"><rect width=\"350\" height=\"170\" rx=\"34\" fill=\"#0f172a\" stroke=\"#22d3ee\"/><rect x=\"505\" width=\"350\" height=\"170\" rx=\"34\" fill=\"#0f172a\" stroke=\"#a78bfa\"/><rect x=\"1010\" width=\"350\" height=\"170\" rx=\"34\" fill=\"#0f172a\" stroke=\"#2dd4bf\"/><text x=\"48\" y=\"102\" fill=\"#fff\" font-family=\"Inter,Arial,sans-serif\" font-size=\"34\" font-weight=\"800\">Pick job</text><text x=\"553\" y=\"102\" fill=\"#fff\" font-family=\"Inter,Arial,sans-serif\" font-size=\"34\" font-weight=\"800\">Choose tool</text><text x=\"1058\" y=\"102\" fill=\"#fff\" font-family=\"Inter,Arial,sans-serif\" font-size=\"34\" font-weight=\"800\">Ship system</text></g></svg>""",
    "default-warning.svg": """<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"1600\" height=\"900\" viewBox=\"0 0 1600 900\"><rect width=\"1600\" height=\"900\" fill=\"#020617\"/><circle cx=\"1240\" cy=\"180\" r=\"300\" fill=\"#f59e0b\" opacity=\".18\"/><text x=\"110\" y=\"145\" fill=\"#fcd34d\" font-family=\"Inter,Arial,sans-serif\" font-size=\"34\" font-weight=\"800\" letter-spacing=\"8\">FORGECORE</text><text x=\"110\" y=\"235\" fill=\"#fff\" font-family=\"Inter,Arial,sans-serif\" font-size=\"78\" font-weight=\"900\">Bad-Fit Warning</text><text x=\"112\" y=\"300\" fill=\"#cbd5e1\" font-family=\"Inter,Arial,sans-serif\" font-size=\"32\">Use simpler systems before paid tool spend.</text><path d=\"M800 370L1020 720H580L800 370Z\" fill=\"#0f172a\" stroke=\"#f59e0b\" stroke-width=\"10\"/><text x=\"800\" y=\"615\" text-anchor=\"middle\" fill=\"#fcd34d\" font-family=\"Inter,Arial,sans-serif\" font-size=\"150\" font-weight=\"900\">!</text></svg>""",
}


def write_visual_assets() -> None:
    VISUAL_DIR.mkdir(parents=True, exist_ok=True)
    for name, svg in SVG_ASSETS.items():
        write_text(VISUAL_DIR / name, svg)


def add_visual_css(text: str) -> str:
    if CSS_MARKER in text:
        return text
    return text.replace("</style>", VISUAL_CSS + "\n  </style>", 1)


def add_social_image_meta(text: str) -> str:
    if 'property="og:image"' not in text:
        text = text.replace(
            '<meta property="og:site_name" content="ForgeCore">',
            '<meta property="og:site_name" content="ForgeCore">\n'
            f'  <meta property="og:image" content="{OG_IMAGE_URL}">',
            1,
        )
    text = text.replace(
        '<meta name="twitter:card" content="summary">',
        '<meta name="twitter:card" content="summary_large_image">',
        1,
    )
    if 'name="twitter:image"' not in text:
        text = text.replace(
            '<meta name="twitter:description" content=',
            f'<meta name="twitter:image" content="{OG_IMAGE_URL}">\n  <meta name="twitter:description" content=',
            1,
        )
    return text


def clean_title(raw_title: str) -> str:
    return html.unescape(re.sub(r"<.*?>", "", raw_title)).strip()


def article_visual(title: str) -> str:
    safe_title = html.escape(title)
    return f"""\n{ARTICLE_MARKER}
<section class="fc-article-visual" aria-label="ForgeCore visual summary">
  <div class="fc-article-visual-inner">
    <p class="fc-visual-label">ForgeCore operator playbook</p>
    <h2>{safe_title}</h2>
    <div class="fc-visual-pills"><span>Workflow</span><span>AI tools</span><span>Operator leverage</span></div>
  </div>
</section>
<section class="fc-workflow-visual" aria-label="Operator workflow diagram">
  <div><p class="fc-visual-label">Use this path</p><h2>The operator workflow</h2></div>
  <ol class="fc-workflow-steps">
    <li><span class="fc-step-number">01</span><span>Pick the business job this article helps solve.</span></li>
    <li><span class="fc-step-number">02</span><span>Use the lightest AI tool or checklist that gets the result.</span></li>
    <li><span class="fc-step-number">03</span><span>Review the first outputs before automating more.</span></li>
  </ol>
</section>
"""


def add_article_visuals(text: str) -> str:
    if ARTICLE_MARKER in text or "<article" not in text:
        return text
    match = re.search(r"<article[^>]*>.*?<h1>(.*?)</h1>", text, flags=re.DOTALL)
    if not match:
        return text
    title = clean_title(match.group(1))
    insert_at = match.end()
    return text[:insert_at] + article_visual(title) + text[insert_at:]


def process_html(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    text = add_visual_css(original)
    text = add_social_image_meta(text)
    text = add_article_visuals(text)
    if text == original:
        return False
    write_text(path, text)
    return True


def main() -> None:
    if not DIST_DIR.exists():
        raise SystemExit("site/dist does not exist; run publish_site.py first")
    write_visual_assets()
    changed = 0
    for path in DIST_DIR.rglob("*.html"):
        if process_html(path):
            changed += 1
    print(f"visual_hardening: updated {changed} html files and wrote {len(SVG_ASSETS)} visual assets")


if __name__ == "__main__":
    main()
