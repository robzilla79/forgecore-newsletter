# ForgeCore Newsletter — Architecture

*Written by Em. Last updated May 12, 2026.*

This document exists because we broke the site, fixed it, and never want to lose the thread again.
Read this before touching anything.

---

## The One Rule

**The site is static HTML in `site/dist/`. Cloudflare Pages serves it. That's the whole thing.**

There is no build step. There is no Python pipeline. There is no content cleanup script.
We write HTML, commit it, and it goes live. Full stop.

---

## Directory Structure

```
forgecore-newsletter/
│
├── site/
│   └── dist/                   ← THIS IS WHAT GETS DEPLOYED
│       ├── index.html          ← Homepage
│       ├── style.css           ← Global styles
│       ├── _headers            ← Cloudflare Pages HTTP headers
│       ├── _redirects          ← Cloudflare Pages redirects
│       ├── robots.txt
│       ├── rss.xml
│       ├── sitemap.xml
│       ├── the-quiet-part/
│       │   └── index.html      ← "The Intelligence in the Room" — Em's real article
│       └── [other pages]/
│           └── index.html
│
├── content/
│   └── issues/
│       └── 2026-05-04-pm.md   ← The one real Em-voiced issue (kept for reference)
│
├── .github/
│   └── workflows/
│       └── deploy-site.yml    ← The deploy workflow (see below)
│
└── ARCHITECTURE.md            ← You are here
```

---

## How Deployment Works

### The Workflow (`.github/workflows/deploy-site.yml`)

```yaml
on:
  push to main
  workflow_dispatch (manual trigger)

steps:
  1. Checkout repo
  2. Run: wrangler pages deploy site/dist
```

That's it. Two steps. No Python. No build scripts. No gates.

### The Critical Detail

Wrangler must point at **`site/dist`** — not `site/`.

- `site/` = parent folder containing `dist/` as a subfolder → **WRONG**, deploys a directory listing
- `site/dist/` = the actual built HTML root → **CORRECT**, serves index.html at `/`

We learned this the hard way on May 12, 2026.

### Secrets Required (Cloudflare)

These must be set in the repo's GitHub Actions secrets:

| Secret | Purpose |
|---|---|
| `CLOUDFLARE_API_TOKEN` | Wrangler auth |
| `CLOUDFLARE_ACCOUNT_ID` | Your CF account |

Project name in Cloudflare Pages: **`forgecore-newsletter`**
Live URL: **https://news.forgecore.co**

---

## How to Add a New Article

1. Write the article as a self-contained HTML file
2. Create a new folder under `site/dist/your-article-slug/`
3. Save the HTML as `site/dist/your-article-slug/index.html`
4. Update `site/dist/index.html` to link to it (optional but recommended)
5. Commit and push to `main`
6. Cloudflare Pages deploys automatically in ~30 seconds

No Python. No templates. No pipeline. Just write HTML and push.

---

## What We Killed (and Why)

In May 2026 we retired the following scripts entirely:

| Script | What it did | Why we killed it |
|---|---|---|
| `content_cleanup.py` | Quarantined issues that failed quality checks | Was blocking deploys; quality is Em's job, not a script's |
| `publish_site.py` | Rendered markdown issues into HTML | No longer needed; we write HTML directly |
| `visual_hardening.py` | Applied visual post-processing | Over-engineering |
| `ai_search_hardening.py` | SEO/AI discoverability pass | Over-engineering |
| `business_hardening.py` | Business-focused content pass | Over-engineering |
| `lead_magnet_hardening.py` | Lead magnet asset rendering | Unused |
| `ops_status.py` | Rendered ops dashboard | Unused |
| `verify_publish.py` | Post-publish verification | Unnecessary with simple deploy |
| `lock_email_issue.py` | Locked issues before email send | Email pipeline is dead |

We also deleted 20 pipeline-generated issues from `content/issues/` that were
low-quality template output ("As a solo founder…" openers, affiliate pushes, etc.).
They were never published and are gone.

**The only surviving issue file is `content/issues/2026-05-04-pm.md`** —
"Agents Are Becoming Business Infrastructure" — kept as a reference for Em's voice.

---

## Content Philosophy

Em writes. Em decides what goes live. No pipeline decides quality.

The old system generated 2x/day issues automatically using an AI pipeline.
Almost all of it was generic affiliate-adjacent content with no real voice.

The new system: Em writes a piece when she has something real to say.
It goes into `site/dist/` as an HTML page. It gets linked from the homepage.
Quality over volume. Always.

---

## Cloudflare Pages Config

- **Project name:** `forgecore-newsletter`
- **Production branch:** `main`
- **Build command:** *(none — we deploy pre-built HTML)*
- **Build output directory:** *(not used — wrangler CLI handles this)*
- **Deploy via:** `wrangler pages deploy site/dist --project-name=forgecore-newsletter --branch=main`

Cloudflare reads `site/dist/_headers` and `site/dist/_redirects` automatically.

---

## The Quiet Part

`/the-quiet-part/` is Em's flagship article: *"The Intelligence in the Room."*
It lives at `site/dist/the-quiet-part/index.html` and is the piece that represents
what this publication actually is. It is never to be deleted, moved, or touched
without Em's explicit decision.

URL: **https://news.forgecore.co/the-quiet-part/**

---

*If you're reading this and wondering whether to add a build step or a pipeline: don't.
Push HTML. It works.*
