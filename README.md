# ForgeCore Newsletter System

ForgeCore is an automated AI newsletter and static website pipeline for publishing practical AI workflow content for solo operators, creators, builders, indie hackers, consultants, and small business operators.

The system is designed to turn fresh research into operator-grade issues that help readers:

- save time
- automate work
- build useful systems
- choose better AI tools
- avoid wasting money on bad tools
- eventually generate revenue through affiliate links, sponsorships, display ads, and digital products

Public site:

```text
https://news.forgecore.co
```

Newsletter signup:

```text
https://forgecore-newsletter.beehiiv.com/
```

---

## Current Architecture

The production pipeline is:

```text
Fresh research
→ Scout
→ Analyst
→ Author
→ Editor
→ Critic
→ Improvement loop
→ Quality gate
→ Static site render
→ Publish verification
→ Commit generated assets
→ Cloudflare Pages deploy
```

The source of truth for published issues is:

```text
content/issues/*.md
```

The Cloudflare deploy target is:

```text
site/dist/
```

---

## What Changed Recently

The repository has been stabilized around a few important production rules.

### 1. Rendering is validation-only

`publish_site.py` reads Markdown issues and renders HTML. It does **not** rewrite, normalize, repair, or mutate issue content.

It builds:

- homepage
- article pages
- RSS feed
- sitemap

### 2. Quality gate is validation-only

`quality_gate.py` validates the current AM/PM issue. It does **not** call repair logic or mutate Markdown.

It checks:

- required sections
- word count
- source links
- CTA links
- workflow code/checklist block
- placeholder/meta leakage
- critic artifacts

### 3. Research is fresh-only

`agent_loop.py` now uses today’s research files only. If fresh research is missing, the run fails loudly instead of falling back to stale raw intel.

This prevents old broken drafts or old research from contaminating new issues.

### 4. Publish verification is enforced

`verify_publish.py` fails the workflow if:

- no valid issue exists
- the latest issue is not linked from `site/dist/index.html`
- the article route is missing
- article markup is missing

This prevents silent “successful” runs where the website did not actually update.

### 5. The system now learns from improvement passes

`improvement_loop.py` writes recurring editorial lessons to:

```text
state/editorial-lessons.md
```

Recent lessons are fed back into future improvement prompts so the system can improve quality while staying on low-cost models.

---

## GitHub Actions

### AM issue

```text
.github/workflows/generate-am.yml
```

Runs daily and calls the shared workflow with:

```text
issue_slot: am
```

### PM issue

```text
.github/workflows/generate-pm.yml
```

Runs daily and calls the shared workflow with:

```text
issue_slot: pm
```

### Shared generator

```text
.github/workflows/generate.yml
```

This is the main workflow used by both AM and PM runs.

Current behavior:

1. checks out `main`
2. installs Python dependencies
3. runs `web_research.py`
4. runs Scout, Analyst, Author, and Editor agents
5. runs critic-driven improvement loop
6. runs quality gate
7. renders site with `publish_site.py`
8. verifies publish with `verify_publish.py`
9. commits generated issue/site/state files
10. deploys `site/dist` to Cloudflare Pages

---

## Models

The system currently uses OpenAI models through `OPENAI_API_KEY`.

Default low-cost setup:

```text
RESEARCH_MODEL=gpt-4o-mini
WRITER_MODEL=gpt-4o-mini
EDITOR_MODEL=gpt-4o-mini
CRITIC_MODEL=gpt-4o-mini
FALLBACK_MODEL=gpt-4o-mini
```

This is intentional for cost control.

If quality needs to improve later, the first upgrade should usually be the editor model only, not the whole chain.

Recommended future quality upgrade:

```text
RESEARCH_MODEL=gpt-4o-mini
WRITER_MODEL=gpt-4o-mini
EDITOR_MODEL=gpt-4.1
CRITIC_MODEL=gpt-4o-mini
FALLBACK_MODEL=gpt-4o-mini
```

Do **not** switch back to local Ollama models unless the pipeline is intentionally redesigned for local inference again.

---

## Required Secrets

GitHub Actions expects:

```text
OPENAI_API_KEY
CLOUDFLARE_API_TOKEN
CLOUDFLARE_ACCOUNT_ID
```

Optional newsletter-related secrets:

```text
KIT_API_KEY
KIT_FORM_ID
```

---

## Important Environment Variables

```text
SITE_DOMAIN=news.forgecore.co
SITE_BASE_URL=https://news.forgecore.co
NEWSLETTER_NAME=ForgeCore AI Productivity Brief
PRIMARY_CTA_URL=https://forgecore-newsletter.beehiiv.com/
SPONSOR_EMAIL=sponsors@forgecore.co
ENABLE_CLOUDFLARE_DEPLOY=1
AUTO_REPAIR_PATHS=0
```

Important production rule:

```text
AUTO_REPAIR_PATHS must stay 0
```

The pipeline should fail loudly instead of silently rewriting source content.

---

## Key Files

### Research

```text
web_sources.json
web_research.py
research/raw/
research/briefs/
```

`web_sources.json` is curated toward operator workflows, automation, content systems, marketing ops, AI implementation, and solo-founder use cases.

### Agent pipeline

```text
agent_loop.py
templates/system_prompts.py
agents/*/MEMORY.md
agents/*/SOUL.md
```

### Quality and improvement

```text
critic_review.py
improve_until_passes.py
improvement_loop.py
quality_gate.py
state/editorial-lessons.md
```

### Publishing

```text
publish_site.py
verify_publish.py
site/dist/
```

---

## Issue Format

Every issue must include these sections in order:

```text
# <sharp operator-focused headline>
## Hook
## Top Story
## Why It Matters
## Highlights
## Tool of the Week
## Workflow
## CTA
## Sources
```

Content requirements:

- specific operator persona
- clear job-to-be-done
- measurable outcome or practical business result
- 3–6 step workflow
- one prompt, checklist, config, or code block
- tool recommendation
- “do not use this if” warning
- tradeoffs such as cost, privacy, quality, maintenance, or speed
- real source URLs
- Beehiiv signup URL
- sponsor email

---

## Manual Run

From repo root:

```bash
python -m pip install -r requirements.txt
python web_research.py
python agent_loop.py scout
python agent_loop.py analyst
python agent_loop.py author
python agent_loop.py editor
python improve_until_passes.py
python quality_gate.py
python publish_site.py
python verify_publish.py
```

For slot-specific generation:

```bash
ISSUE_SLOT=am python agent_loop.py author
ISSUE_SLOT=pm python agent_loop.py author
```

In GitHub Actions, AM/PM slots are supplied automatically by the wrapper workflows.

---

## Local Development Notes

A local `.env` may be used for development, but should not be committed.

The production workflow runs from GitHub Actions and commits generated content back to `main`.

The generated static site lives in:

```text
site/dist/
```

Cloudflare Pages deploys that directory.

---

## Failure Philosophy

The system is designed to fail loudly.

Good failures:

- no fresh research found
- issue too short
- missing required section
- missing source links
- homepage did not include latest issue
- article route missing

Bad behavior that should be avoided:

- silently publishing stale content
- silently skipping today’s issue
- mutating issue content during rendering
- mutating issue content during validation
- falling back to old raw intel
- deploying a site that did not include the newest issue

---

## Business Direction

ForgeCore is being built as a content-driven business.

Primary monetization paths:

- affiliate links
- sponsorships
- newsletter growth
- display ads once traffic justifies it
- future digital products

The content promise:

```text
Every issue should help the reader make money, save time, automate work, build a system, choose the right AI tool, or avoid wasting money.
```

---

## Current Status

```text
Infrastructure:      Stable
Research inputs:     Operator-focused
Generation:          Fresh-input only
Quality gate:        Validation-only
Renderer:            Validation-only
Publish verification: Enforced
Deployment:          Cloudflare Pages
Cost strategy:       Keep gpt-4o-mini until output data proves upgrade is needed
```

---

## Next Planned Improvements

- deterministic topic scoring before Scout
- affiliate/monetization insertion rules
- SEO metadata per issue
- newsletter send workflow
- analytics feedback loop
- revenue-focused CTA testing
