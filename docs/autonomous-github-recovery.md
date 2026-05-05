# Autonomous GitHub Recovery

ForgeCore needs GitHub to recover safe newsletter failures even when Rob is not present.

This document defines what GitHub is allowed to repair autonomously, what must still escalate to Rob, and how duplicate-send risk is controlled.

---

## Primary workflow

Autonomous recovery workflow:

```text
.github/workflows/autonomous-newsletter-recovery.yml
```

Manual repair workflow:

```text
.github/workflows/repair-dropped-newsletter-run.yml
```

The autonomous workflow is the first line of safe recovery. The manual repair workflow remains the operator control surface.

---

## What GitHub may do autonomously

GitHub may autonomously repair safe, routine publishing failures:

```text
Prepare a missing AM issue after the AM prepare window.
Prepare a missing PM issue after the PM prepare window.
Send an existing AM issue after the AM send window if no public Kit send record exists.
Send an existing PM issue after the PM send window if no public Kit send record exists.
Prepare and send a slot after the send window if the whole slot was dropped and no public send record exists.
Refresh the ops dashboard after recovery.
Deploy the repaired site output through the existing Cloudflare Pages deploy path.
```

Autonomous recovery must use the existing reusable workflows:

```text
.github/workflows/generate.yml
.github/workflows/send.yml
```

It must not bypass:

```text
quality_gate.py
monetization_guard.py
lock_email_issue.py
publish_site.py
verify_publish.py
kit_publish.py
state/kit_sent.json
```

---

## What GitHub must not do autonomously

GitHub must not autonomously:

```text
Delete or edit state/kit_sent.json to force a resend.
Bypass kit_publish.py.
Send a correction, apology, sponsor make-good, or erratum email.
Force a second public email for the same date/slot.
Publish affiliate-heavy content that fails the monetization guard.
Ignore a failed quality gate.
Commit secrets, private dashboard URLs, workflow logs with sensitive data, or private Kit API data.
Rollback Cloudflare production without a documented incident reason.
Create or change Kit tags, segments, forms, or automations.
```

---

## Recovery windows

The detector uses America/Chicago time gates.

```text
AM prepare can be recovered after 7:45 AM CT.
AM send can be recovered after 10:35 AM CT.
PM prepare can be recovered after 1:45 PM CT.
PM send can be recovered after 4:50 PM CT.
```

The workflow runs on scheduled checks after expected production windows and can also be triggered manually.

---

## Decision logic

For each slot, autonomous recovery checks:

```text
content/issues/YYYY-MM-DD-slot.md
content/email/YYYY-MM-DD-slot.md
state/kit_sent.json
current America/Chicago time
allow_send setting
```

Then it chooses:

```text
no_action
prepare_only
send_only
prepare_and_send
investigate
```

### no_action

Use when the slot is already complete or not due yet.

### prepare_only

Use when the issue or locked email snapshot is missing after the prepare window, but email should not be sent yet.

### send_only

Use when the issue and locked email snapshot exist, the send window has passed, and no public Kit send record exists.

### prepare_and_send

Use when the issue is missing after the send window, `allow_send=true`, and no public Kit send record exists.

### investigate

Use when state is inconsistent and a human review is required.

---

## Duplicate-send protection

The autonomous workflow does not directly call the Kit API.

It uses:

```text
.github/workflows/send.yml
kit_publish.py
state/kit_sent.json
```

`kit_publish.py` enforces slot/date idempotency and blocks public resends when a date/slot already has a public Kit record.

Autonomous recovery is allowed to attempt safe send recovery only because the send workflow and `kit_publish.py` remain the authority.

---

## Rob approval required

Escalate to Rob before action if:

```text
A public email may have been sent twice.
Kit dashboard and state/kit_sent.json disagree.
A resend is being considered.
A correction or apology email is being considered.
A sponsor or affiliate mistake was sent.
A failed quality gate would need to be bypassed.
A workflow appears green but the site/email/dashboard is wrong.
Private metrics or API data would need to be exposed publicly.
```

---

## How to use manual autonomous recovery

Path:

```text
GitHub → Actions → Autonomous Newsletter Recovery → Run workflow
```

Inputs:

```text
issue_slot: all | am | pm
allow_send: true | false
reason: short audit note
```

Examples:

```text
issue_slot: am
allow_send: true
reason: AM issue missing after send window
```

```text
issue_slot: pm
allow_send: false
reason: Prepare missing PM issue but do not email yet
```

---

## Relationship to the ops dashboard

The ops dashboard shows current public-safe state:

```text
https://news.forgecore.co/ops/
https://news.forgecore.co/status/forgecore-status.json
```

If the dashboard says repair is needed, autonomous recovery should either repair it on the next scheduled check or provide a clear summary in GitHub Actions.

---

## Definition of done

Autonomous GitHub recovery is working when:

```text
A dropped AM prepare is repaired without Rob needing to be present.
A dropped PM prepare is repaired without Rob needing to be present.
A missed Kit send is attempted only through the guarded send workflow.
Duplicate public sends remain blocked.
The ops dashboard updates after recovery.
Failures that require judgment escalate instead of being forced.
Rob can inspect the GitHub Actions summary afterward and understand what happened.
```
