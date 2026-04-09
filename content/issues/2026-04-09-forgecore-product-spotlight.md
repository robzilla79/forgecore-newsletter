---
title: "We Built a Thing: HN Lead Automator"
date: "2026-04-09"
slug: "2026-04-09-forgecore-product-spotlight"
description: "ForgeCore just shipped its first product: an n8n + Claude 3.7 workflow that turns Hacker News into a live lead feed. Here's exactly how it works."
---

# We Built a Thing
*A ForgeCore product spotlight.*

## What It Does

Hacker News is full of people describing problems they can't solve. "Is there a tool that does X?" "We've been doing Y manually for two years." "Switching from Z — what do people actually use now?"

Those posts are warm leads. Most developers never see them because reading HN consistently enough to catch them is a part-time job.

So we automated it.

The **[HN Lead Magnet Automator](https://forgecorestore.gumroad.com/l/hn-lead-automator)** is an n8n workflow pack that:

1. Pulls new Show HN and Ask HN posts every 6 hours via RSS
2. Sends each post to Claude 3.7 with a scoring prompt — the model reads the post, assigns a lead score from 1–10, and extracts the key pain point
3. Routes anything scoring 7+ to a Notion CRM database with full context
4. Triggers a Gmail draft for high-intent leads so you can respond in one click
5. Pings Telegram with a summary so you always know what came in

## What's In the Pack

- **`hn-lead-automator.json`** — The main workflow. Import directly into n8n.
- **`hn-pain-detector.json`** — A bonus workflow that runs weekly and produces a digest of unmet developer needs extracted from HN comments. Good for product idea mining.
- **`README.md`** — Setup guide. 15 minutes, no fluff. Covers n8n self-hosting, Claude API key config, Notion database schema, and Gmail OAuth.

## What It Costs to Run

- **n8n**: Free if self-hosted (one-command Docker setup)
- **Claude API**: ~$0.36/month at 6-hour polling intervals
- **Notion, Gmail, Telegram**: Free tiers are fine

Total ongoing cost: under $0.50/month.

## Who It's For

If you're building something — a SaaS, an agency, a dev tool — and you want a consistent trickle of warm leads from the most technically literate community on the internet, this workflow does that without requiring you to be glued to HN.

It is not a scraper. It doesn't spam anyone. It reads public posts, scores intent, and tells you which ones are worth your time.

## Get It

**[$29 one-time → forgecorestore.gumroad.com/l/hn-lead-automator](https://forgecorestore.gumroad.com/l/hn-lead-automator)**

No subscription. No upsell. Files delivered on purchase.

---

*Built by ForgeCore — AI systems for developers who ship.*
