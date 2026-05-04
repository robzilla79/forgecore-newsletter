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
https://news.forgecore.co/
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
→ Affiliate linker
→ Monetization guard
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
- AI tools directory
- evergreen workflow landing pages
- RSS feed
- sitemap
- canonical URLs
- meta descriptions
- Open Graph/Twitter metadata
- JSON-LD `WebSite`, `CollectionPage`, and `Article` schema

### 2. Quality gate is validation-only

`quality_gate.py` validates the current AM/PM issue. It does **not** call repair logic or mutate Markdown.

It checks:

- required sections
- duplicate required sections
- malformed or glued section headings
- word count
- source links
- CTA links
- workflow code/checklist block
- tool recommendation strength
- trust warning / “do not use this if” language
- affiliate or partner disclosure when monetization language appears
- placeholder/meta leakage
- critic artifacts

### 3. Research is fresh-only

`agent_loop.py` now uses today’s research files only. If fresh research is missing, the run fails loudly instead of falling back to stale raw intel.

This prevents old broken drafts or old research from contaminating new issues.

### 4. Publish verification is enforced

`verify_publish.py` fails the workflow if:

- no valid issue exists
- the latest issue is not linked from `site/dist/index.html`
- the latest issue is not first on the homepage
- the latest issue is not first in RSS
- the latest issue is not first in the sitemap issue URLs
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
7. runs affiliate linker
8. runs monetization guard
9. renders site with `publish_site.py`
10. verifies publish with `verify_publish.py`
11. commits generated issue/site/state files
12. deploys `site/dist` to Cloudflare Pages

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
KIT_SIGNUP_URL
```

---

## Important Environment Variables

```text
SITE_DOMAIN=news.forgecore.co
SITE_BASE_URL=https://news.forgecore.co
NEWSLETTER_NAME=ForgeCore AI Productivity Brief
PRIMARY_CTA_URL=https://news.forgecore.co/
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

### Monetization

```text
monetization/affiliate-registry.json
SPONSORSHIP.md
```

`monetization/affiliate-registry.json` is the approved-tool registry for trust-safe affiliate recommendations. It stores each tool’s category, operator use case, bad-fit warning, approved partner links, simpler alternatives, and disclosure requirements.

`SPONSORSHIP.md` defines ForgeCore’s sponsor inventory, audience fit, placement types, sample sponsor block, and editorial trust policy.

---

## Evergreen Traffic Pages

`publish_site.py` renders indexable workflow landing pages designed for search traffic and newsletter conversion:

```text
/workflows/solo-founder-ai-automation/
/ai-tools/content-repurposing/
/ai-tools/client-onboarding/
/ai-tools/newsletter-growth/
/ai-tools/automation/
/ai-tools/ai-seo-aeo/
```

These pages should be practical, evergreen, and tied to buyer-intent workflows. They should link to the AI tools directory and the newsletter/lead magnet CTA.

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
- Kit signup URL or owned-site newsletter signup URL
- sponsor email

---

## SEO and Monetization Guardrails

ForgeCore monetization must help the reader first.

### SEO rendering rules

`publish_site.py` must render each valid issue with:

- a canonical URL using `SITE_BASE_URL`
- a concise meta description generated from the issue excerpt
- Open Graph title, description, URL, site name, and type
- Twitter summary card metadata
- JSON-LD `Article` schema on article pages
- JSON-LD `WebSite` schema on the homepage
- JSON-LD `CollectionPage` schema on tool and workflow pages

These are rendering outputs only. The renderer must not rewrite source Markdown to create metadata.

### Trust-safe monetization rules

The issue may include affiliate, sponsor, partner, referral, or paid-tool language only when it is useful to the reader.

Required safeguards:

- Tool recommendations must be tied to the job-to-be-done.
- Paid or affiliate tools should include a cheaper, simpler, or free alternative when useful.
- Any affiliate, partner, referral, sponsor, or commission mention must include plain disclosure language.
- The issue must include a “do not use this if” / “not a fit if” warning so readers avoid bad-fit tools.
- Monetization should never turn a practical workflow into a link farm.

Suggested disclosure language:

```text
Disclosure: ForgeCore may earn a commission if you buy through partner links, but recommendations are based on workflow fit, not payout.
```

### Approved-tool registry

Affiliate or paid-tool mentions should use the approved-tool registry when possible:

```text
monetization/affiliate-registry.json
```

A tool in the registry is not automatically recommended. It is only eligible for recommendation when the issue’s workflow, reader persona, and job-to-be-done make the tool useful.

When using a registry tool, include:

- why it fits the workflow
- who it is best for
- who should avoid it
- a free, cheaper, or simpler alternative when useful
- disclosure language if affiliate, sponsor, partner, referral, or commission language appears

### Sponsor inventory

Sponsor positioning and placement rules live in:

```text
SPONSORSHIP.md
```

Use this file when preparing sponsor outreach, sponsor blocks, dedicated tool teardowns, or paid placements.

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
python affiliate_linker.py
python monetization_guard.py
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
- duplicate or malformed section heading
- missing source links
- missing tool recommendation
- missing trust warning
- affiliate/partner language without disclosure
- homepage did not include latest issue
- homepage/RSS/sitemap did not list latest issue first
- article route missing

Bad behavior that should be avoided:

- silently publishing stale content
- silently skipping today’s issue
- mutating issue content during rendering
- mutating issue content during validation
- hiding affiliate incentives
- forcing monetized tools into bad-fit workflows
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

Lead magnet positioning:

```text
The Solo Operator AI Workflow Pack
```

This should be the default conversion promise on homepage, workflow pages, and article pages until a dedicated digital product exists.

---

## Current Status

```text
Infrastructure:       Stable
Research inputs:      Operator-focused
Generation:           Fresh-input only
Quality gate:         Validation-only
Renderer:             Validation-only + SEO metadata + evergreen pages
Publish verification: Enforced
Monetization guardrails: Trust-safe affiliate/sponsor checks
Deployment:           Cloudflare Pages
Cost strategy:        Keep gpt-4o-mini until output data proves upgrade is needed
```

---

## Next Planned Improvements

- deterministic topic scoring before Scout
- newsletter send workflow
- analytics connector integration once traffic data source is available
- revenue-focused CTA testing
- add more approved affiliate URLs to the registry
- add sponsor placement templates to issue generation
