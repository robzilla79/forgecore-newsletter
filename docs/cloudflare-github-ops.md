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
.github/workflows/generate-am.yml
.github/workflows/generate-pm.yml
.github/workflows/generate.yml
.github/workflows/deploy-site.yml
```

Important production scripts:

```text
web_research.py
agent_loop.py
improve_until_passes.py
quality_gate.py
affiliate_linker.py
monetization_guard.py
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
1. A scheduled AM/PM workflow or manual workflow starts in GitHub Actions.
2. The pipeline generates or updates issue content.
3. The quality gate validates the issue.
4. Approved affiliate links are activated only if safe.
5. Monetization guard checks disclosure and trust rules.
6. publish_site.py renders static files into site/dist/.
7. verify_publish.py or verify_site_updates.py checks that the site output actually reflects the latest issue.
8. GitHub commits generated content and site output back to main.
9. Wrangler deploys site/dist/ to Cloudflare Pages project forgecore-newsletter.
10. Cloudflare serves the updated site at news.forgecore.co.
```

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
- article template changes

Recommended flow:

```text
1. Create a branch.
2. Make the repo change.
3. Open a pull request.
4. Let GitHub Actions render and verify site output.
5. Review the Cloudflare preview deployment.
6. Approve and merge to main.
7. Confirm production deploy succeeded.
```

---

## Future Cloudflare upgrades

Only add these when they solve a real business problem.

### Cloudflare Workers or Functions

Useful later for:

- newsletter signup proxy
- sponsor inquiry form
- lightweight analytics endpoint
- affiliate click event capture
- lead magnet delivery
- Stripe webhook handling
- R2 signed download links for digital products

### Cloudflare R2

Useful later for:

- downloadable lead magnets
- paid digital products
- media assets
- generated reports or templates

### Build watch paths

Useful later if Cloudflare builds are triggered too often by docs-only or state-only changes.

---

## Operator rules

- GitHub main is canonical.
- Cloudflare serves the output.
- `content/issues/*.md` is the newsletter issue source of truth.
- `site/dist/` is the deploy output.
- Verification must run before deploy.
- Dashboard changes must be documented back in the repo when they affect production behavior.
- Never commit secrets.
- Never hide a broken pipeline by manually editing generated output in Cloudflare.
- Never claim a deploy succeeded until homepage, latest article, RSS, sitemap, and Cloudflare deployment status are verified.

---

## Definition of done

The GitHub and Cloudflare integration is healthy when:

```text
GitHub Actions can deploy site/dist/ to Cloudflare Pages.
Cloudflare Pages project forgecore-newsletter exists.
news.forgecore.co points to the Pages project.
CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID are set as GitHub Actions secrets.
OPENAI_API_KEY is set as a GitHub Actions secret.
No Cloudflare secrets or dashboard account URLs are committed.
Every deploy verifies homepage, latest article, RSS, and sitemap before publishing.
Cloudflare rollback path is documented.
Preview deploy review is available for risky site changes.
```
