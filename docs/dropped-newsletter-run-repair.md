# Dropped Newsletter Run Repair Playbook

Use this playbook when the daily Aware issue is missed, skipped, failed, or only partially completed.

The goal is to repair through the production automation path, not by manually writing source files or hiding a missed run.

---

## Current production path

The live daily publishing path is:

```text
.github/workflows/generate-daily.yml
→ .github/workflows/generate.yml
→ web_research.py
→ agent_loop.py scout / analyst / author / editor
→ quality_gate.py
→ publish_site.py
→ Cloudflare Pages deploy
→ commit generated artifacts
```

The source of truth for issue content remains:

```text
content/issues/*.md
```

The deploy target remains:

```text
site/dist/
```

---

## Automatic recovery guard

The redundant cadence guard is:

```text
.github/workflows/daily-issue-watchdog.yml
```

It runs after the primary daily schedule window and checks whether today's America/Chicago business-date issue artifact exists in `content/issues/`.

It accepts these artifact names:

```text
content/issues/YYYY-MM-DD.md
content/issues/YYYY-MM-DD-em.md
content/issues/YYYY-MM-DD-am.md
content/issues/YYYY-MM-DD-pm.md
```

If a non-empty artifact exists, the watchdog does nothing.

If no non-empty artifact exists, the watchdog dispatches the shared generator:

```text
.github/workflows/generate.yml
issue_slot: ''
force_run: true
```

The watchdog does not write issue content directly, send Kit email directly, or bypass the generator, quality gate, render, or deploy path.

---

## Fast rule

Repair the missing stage only.

```text
If today's issue was not generated: let the watchdog dispatch generate.yml, or manually run generate-daily.yml / generate.yml.
If the issue exists but the site did not update: run the generator/render/deploy path, then verify site artifacts.
If email/broadcast delivery is part of the current system and did not happen: verify state/kit_sent.json and Kit first; never send twice.
If the issue already exists and the site is current: do not generate another issue.
```

---

## Manual recovery path

Use this when the watchdog did not run, did not dispatch, or the business day cannot wait for the next watchdog check.

Preferred manual path:

```text
GitHub
→ Actions
→ Em Prepares Daily Issue
→ Run workflow
→ force_run: true
```

Alternative direct generator path:

```text
GitHub
→ Actions
→ Em Prepares the Issue
→ Run workflow
→ issue_slot: blank
→ force_run: true
```

Use the legacy AM/PM wrappers only for explicit slot testing or legacy recovery. They are no longer the scheduled production cadence.

---

## Before manual recovery

Check these first:

```text
[ ] Does content/issues/YYYY-MM-DD.md exist?
[ ] Does content/issues/YYYY-MM-DD-em.md exist?
[ ] Does any same-day AM/PM artifact exist?
[ ] Did the Daily Issue Watchdog already dispatch generate.yml?
[ ] Is a generate.yml run currently in progress?
[ ] Did site/dist/ update?
[ ] Did Cloudflare deploy?
[ ] If email/broadcast is expected, does state/kit_sent.json already record a send?
[ ] If email/broadcast is expected, did Kit already create or send a broadcast?
```

Never create a manual issue file to paper over the missed run unless Rob explicitly chooses emergency editorial rescue over automation repair.

Never run a send repair if Kit or `state/kit_sent.json` already shows a public send for the date/slot.

---

## After recovery

Verify:

```text
[ ] GitHub Actions generator or watchdog workflow completed successfully.
[ ] Latest issue exists in content/issues/.
[ ] Homepage links the latest issue.
[ ] Latest article route exists.
[ ] RSS includes the latest issue.
[ ] Sitemap includes the latest issue.
[ ] Cloudflare deployment succeeded.
[ ] If email/broadcast is expected, Kit broadcast exists.
[ ] If email/broadcast is expected, state/kit_sent.json was updated.
[ ] No duplicate issue or email was produced.
```

Do not call the issue live until the site route or deploy evidence confirms it.

---

## Duplicate-send protection

If public email/broadcast sending is enabled in the current system, duplicate-send protection is mandatory.

The guard must check:

```text
Issue filename/date matches the intended send date.
state/kit_sent.json does not already record a public send for the date/slot.
Only one public send is allowed for the same date/slot unless Rob explicitly approves an incident resend.
```

Do not delete or edit `state/kit_sent.json` just to force another send.

If a resend is truly needed, treat it as an incident and get Rob approval.

---

## Common repair scenarios

### Scenario 1: Daily issue missing after schedule window

Expected automatic behavior:

```text
Daily Issue Watchdog runs.
No non-empty same-day issue artifact is found.
Watchdog dispatches generate.yml with force_run: true.
Generator produces issue, renders site, deploys, and commits artifacts.
```

Manual fallback:

```text
Run Em Prepares Daily Issue with force_run: true.
```

### Scenario 2: Watchdog found an issue, but site is stale

Do not write a new issue.

Run the generator/render/deploy path or the relevant site deploy path, then verify:

```text
homepage
latest article route
RSS
sitemap
Cloudflare deployment
```

### Scenario 3: Generator failed before producing an issue

Do not patch around it with a hand-written issue by default.

Inspect the failed run artifacts and logs first. Fix the generator, research, model, quality gate, render, or deploy failure that blocked production. Then rerun the daily generator with `force_run: true`.

### Scenario 4: Email/broadcast delivery failed after issue generation

First verify whether email sending is active in the current workflow.

If it is active, check `state/kit_sent.json` and Kit before any resend. If no send exists, run the smallest send-only recovery path available in the current repo. If no send-only workflow exists, treat that as an incident and add one rather than hand-sending from memory.

---

## Removed workflow warning

Do not use this removed workflow:

```text
.github/workflows/repair-dropped-newsletter-run.yml
```

It is a disabled noop retained only as an audit marker. The active recovery path is the daily generator plus `daily-issue-watchdog.yml`.
