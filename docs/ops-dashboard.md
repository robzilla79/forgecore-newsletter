# ForgeCore Ops Dashboard

The ForgeCore Ops Dashboard is the production oversight surface for Rob and the ForgeCore AI Team OS CEO.

It is designed to answer one question quickly:

```text
Is ForgeCore healthy right now, or does the team need to repair something?
```

---

## Production URL

Planned route:

```text
https://news.forgecore.co/ops/
```

Status JSON route:

```text
https://news.forgecore.co/status/forgecore-status.json
```

---

## Source files

Dashboard generator:

```text
ops_status.py
```

Generated public-safe dashboard output:

```text
site/dist/ops/index.html
```

Generated public-safe status data:

```text
site/dist/status/forgecore-status.json
```

Scheduled refresh workflow:

```text
.github/workflows/ops-dashboard.yml
```

The deploy workflow also renders the ops dashboard before verification:

```text
.github/workflows/deploy-site.yml
```

---

## What the dashboard checks

The dashboard reads repo/static output state and shows:

```text
AM issue existence
AM locked email snapshot existence
AM Kit send-record presence
PM issue existence
PM locked email snapshot existence
PM Kit send-record presence
Latest issue slug and route
Homepage latest issue presence
RSS latest issue presence
Sitemap latest issue presence
Latest article route existence
Recommended repair action
Whether Rob approval is required
```

---

## What public-safe v1 does not show

Do not expose sensitive business or subscriber data publicly.

The current v1 intentionally excludes:

```text
Subscriber counts
Kit private dashboard data
Kit API responses
Unsubscribe counts
Spam complaints
Revenue data
GitHub workflow logs
Cloudflare API responses
Secrets or tokens
Detailed private incident payloads
```

Add those only after `/ops/` is protected with Cloudflare Access.

---

## How status is generated

Run:

```bash
python ops_status.py
```

This writes:

```text
site/dist/status/forgecore-status.json
site/dist/ops/index.html
```

The JSON is static and public-safe. The dashboard fetches it from:

```text
/status/forgecore-status.json
```

---

## Scheduled refreshes

The dashboard refresh workflow runs after expected production windows:

```text
After AM send window
After PM send window
After evening dropped-run triage window
```

Workflow:

```text
.github/workflows/ops-dashboard.yml
```

The workflow:

```text
1. Checks out main.
2. Renders the current site output.
3. Applies AI search hardening.
4. Applies business hardening.
5. Renders lead magnet assets.
6. Runs ops_status.py.
7. Commits site/dist/ops/ and site/dist/status/ updates if changed.
8. Deploys site/dist/ to Cloudflare Pages.
```

---

## Repair-action meanings

### no_action

```text
No repair needed.
```

### prepare_only

Use when an issue exists problem requires preparing/regenerating the slot, but no send should happen yet.

### send_only

Use when:

```text
Issue exists.
Locked email snapshot exists.
Kit send record is missing.
```

Before using this, confirm Kit did not already create a public broadcast.

### prepare_and_send

Use when the whole slot was dropped.

### deploy-site

Use when site output or Cloudflare is stale/incomplete.

---

## How Rob should use the dashboard

Check `/ops/` when:

```text
AM should have sent.
PM should have sent.
The AI CEO flags a dropped run.
The newsletter seems missing.
The homepage looks stale.
Kit send status is uncertain.
A repair workflow was run.
```

The most important panel is:

```text
Current required action
```

If it says `No action needed`, normal operations continue.

If it shows a repair action, follow:

```text
docs/dropped-newsletter-run-repair.md
```

---

## Cloudflare Access recommendation

Before adding private metrics, protect:

```text
/ops/*
/status/*
```

Recommended Cloudflare Access policy:

```text
Application: news.forgecore.co/ops/*
Allowed user: Rob's email address
Policy action: Allow
Default: Block
```

If `/status/forgecore-status.json` remains public-safe, it can remain public for v1. If private metrics are added later, protect `/status/*` too.

---

## Future live API version

After the v1 dashboard proves useful, add Cloudflare Pages Functions for private live checks:

```text
/functions/api/ops/status.ts
/functions/api/ops/github.ts
/functions/api/ops/cloudflare.ts
/functions/api/ops/kit.ts
```

Those endpoints can query APIs server-side using Cloudflare environment variables.

Never put API tokens in browser JavaScript.

---

## Definition of done

The ops dashboard is working when:

```text
https://news.forgecore.co/ops/ loads.
/status/forgecore-status.json loads.
The JSON generated_at timestamp is current.
AM and PM statuses match repo reality.
Latest issue route matches the homepage/RSS/sitemap state.
Repair recommendation matches docs/dropped-newsletter-run-repair.md.
No private subscriber, revenue, token, or workflow-log data is exposed.
```
