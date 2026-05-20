# Cloudflare + GitHub Ops Map

ForgeCore uses GitHub as the source of truth and Cloudflare as the hosting and deployment control plane.

This document explains what belongs in GitHub, what belongs in Cloudflare, how production deploys work, and how to verify or recover a deployment.

---

## Operating principle

GitHub owns the publishing system.

Cloudflare serves the built site.

Do not treat the Cloudflare dashboard as the source of truth for content, rendering, editorial rules, affiliate rules, or publish validation. Those belong in the repo.

---

## Production architecture

```text
content/issues/*.md
→ research + agent pipeline
→ quality gate
→ affiliate linker
→ monetization guard
→ publish_site.py
→ verify_publish.py
→ site/dist/
→ Cloudflare Pages
→ news.forgecore.co
```

The source of truth for published newsletter issues is:

```text
content/issues/*.md
```

The Cloudflare Pages deployment target is:

```text
site/dist/
```

The production Cloudflare Pages project is:

```text
forgecore-newsletter
```

The public production site is:

```text
news.forgecore.co
```

Important distinction:

```text
index.html        = repo-root landing page source
site/dist/        = deployed Cloudflare output for news.forgecore.co
publish_site.py   = renderer that writes site/dist/
```

Editing repo-root `index.html` alone does not update `news.forgecore.co`. To update production, run the rebuild workflow so `publish_site.py` regenerates `site/dist/` and deploys that folder.

---

## GitHub responsibilities

GitHub should handle:

- issue source content
- research artifacts
- writing pipeline logic
- editorial quality gates
- monetization and affiliate guardrails
- static site rendering
- publish verification
- commit history
- pull requests
- release notes
- rollback commits when source changes need to be reverted

Important production workflows:

```text
.github/workflows/generate.yml
.github/workflows/generate-daily.yml
.github/workflows/rebuild-site.yml
.github/workflows/deploy-site.yml
```

Legacy/manual-only workflows may still exist for AM/PM history, but the Aware daily site path should use `rebuild-site.yml` for manual site deploys.

Important production scripts:

```text
web_research.py
agent_loop.py
quality_gate.py
publish_site.py
verify_publish.py
verify_site_updates.py
```

---

## Cloudflare responsibilities

Cloudflare should handle:

- Pages hosting
- production deployment history
- preview deployments, when enabled
- custom domain mapping
- DNS
- SSL/TLS
- cache and edge delivery
- deployment rollback from the Cloudflare Pages dashboard
- future Workers or Functions if ForgeCore adds dynamic systems

Cloudflare should not be used as the canonical place to edit content, issue logic, editorial rules, affiliate behavior, or rendering logic.

---

## Required GitHub Actions secrets

These secrets must live in GitHub Actions settings, not in committed files:

```text
OPENAI_API_KEY
CLOUDFLARE_API_TOKEN
CLOUDFLARE_ACCOUNT_ID
```

Optional newsletter and conversion secrets:

```text
KIT_API_KEY
KIT_FORM_ID
KIT_SIGNUP_URL
```

Security rule:

```text
Do not commit Cloudflare API tokens, account-specific dashboard URLs, local .env files, or private deployment credentials.
```

---

## Current deploy path

The expected production deploy flow is:

```text
1. A scheduled or manual GitHub Actions workflow starts.
2. The pipeline generates or updates issue content.
3. The quality gate validates the issue.
4. publish_site.py renders static files into site/dist/.
5. verify_publish.py or verify_site_updates.py checks that the site output reflects the latest issue.
6. GitHub commits generated content and site output back to main when applicable.
7. Wrangler deploys site/dist/ to Cloudflare Pages project forgecore-newsletter.
8. Cloudflare serves the updated site at news.forgecore.co.
```

---

## Manual update: news.forgecore.co

Use this when the site copy, homepage layout, issue archive, or rendered article page needs to be refreshed on Cloudflare without sending email.

Workflow:

```text
GitHub → Actions → Rebuild & Deploy Site
```

Direct workflow file:

```text
.github/workflows/rebuild-site.yml
```

Input:

```text
issue_slot: 2026-05-13-em
```

Or leave blank to auto-detect the newest issue.

What this does:

```text
python publish_site.py
pages deploy site/dist --project-name=forgecore-newsletter --commit-dirty=true --branch=main
```

Use this workflow for `news.forgecore.co` updates.

Do not use send workflows for site-only changes.

Do not expect repo-root `index.html` to deploy by itself; Cloudflare production serves the generated `site/dist/` output.

---

## Manual Cloudflare dashboard checks

Use the Cloudflare dashboard for inspection and recovery, not as the source of truth.

Check these areas:

```text
Cloudflare Dashboard
→ Workers & Pages
→ Pages
→ forgecore-newsletter
```

Verify:

- latest production deployment completed successfully
- production branch is `main`
- custom domain includes `news.forgecore.co`
- deployment source or Wrangler deploy history looks current
- environment variables are not replacing repo-owned logic
- preview deployments are available if PR review previews are enabled

Do not paste account-specific Cloudflare dashboard URLs into public repo docs.

---

## Production deploy verification checklist

Every production deploy is done only when all of these are true:

```text
GitHub Actions workflow finished successfully.
site/dist/index.html was rendered.
The latest issue is linked from the homepage.
The latest issue appears first on the homepage.
The latest issue appears first in RSS.
The latest issue appears first in sitemap issue URLs.
The article route exists in site/dist/.
Cloudflare Pages deployment succeeded.
news.forgecore.co loads the updated site.
```

If any of these fail, treat the deploy as failed even if one platform shows a green status.

---

## Rollback procedure

Use Cloudflare rollback when the deployed static site is bad but the repo needs time for a proper fix.

```text
1. Open Cloudflare Dashboard.
2. Go to Workers & Pages.
3. Open Pages project forgecore-newsletter.
4. Open Deployments.
5. Choose the most recent known-good production deployment.
6. Roll back production to that deployment.
7. Open GitHub and create or commit the real repo fix.
8. Re-run the GitHub workflow after the fix is merged.
9. Verify news.forgecore.co, RSS, sitemap, and latest article route.
```

Cloudflare rollback is an emergency recovery tool. The repo still needs the root-cause fix.

---

## Recommended preview workflow

Use preview deployments for risky changes such as:

- homepage layout changes
- newsletter CTA changes
- lead magnet changes
- affiliate block changes
- sponsor placement changes
- SEO rendering changes
- RSS or sitemap changes

Preview deployments should come from GitHub source and generated output, not hand-edits in Cloudflare.
