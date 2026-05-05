# Dropped Newsletter Run Repair Playbook

Use this playbook when a ForgeCore AM or PM newsletter run is missed, skipped, failed, or only partially completed.

The goal is to let the team repair the publishing system on the fly without creating duplicate Kit emails, stale web output, or hidden manual fixes.

---

## Fast rule

Repair the missing stage only.

```text
If the issue was not generated: prepare it.
If the issue was generated but email was not sent: send it.
If neither happened: prepare and then send.
If email already sent: do not send again.
```

---

## Main repair workflow

Use this workflow for recovery:

```text
.github/workflows/repair-dropped-newsletter-run.yml
```

Manual run path:

```text
GitHub
→ Actions
→ Repair Dropped Newsletter Run
→ Run workflow
```

Inputs:

```text
issue_slot: am | pm
repair_action: prepare_only | send_only | prepare_and_send
reason: short reason for audit trail
```

---

## Choose the right repair action

### prepare_only

Use when:

```text
The AM/PM issue did not generate.
No content/issues/YYYY-MM-DD-slot.md exists.
No content/email/YYYY-MM-DD-slot.md exists.
The scheduled prepare workflow failed before producing a usable issue.
```

Expected result:

```text
content/issues/YYYY-MM-DD-slot.md exists.
content/email/YYYY-MM-DD-slot.md exists.
site/dist/ updates.
Cloudflare deploys the web version.
No Kit email is sent by this repair action.
```

### send_only

Use when:

```text
The issue exists.
The locked email snapshot exists.
The web version is published or ready.
The Kit send did not happen.
state/kit_sent.json does not show a public record for this slot.
```

Expected result:

```text
Kit broadcast is created.
state/kit_sent.json records the broadcast.
No new article generation happens.
```

### prepare_and_send

Use when:

```text
The slot was completely dropped.
There is no generated issue.
There is no sent Kit record.
The team wants to recover both web and email in one run.
```

Expected result:

```text
Issue is generated.
Email snapshot is locked.
Site is rendered and verified.
Cloudflare deploys the web version.
Kit sends once if the send window and duplicate-send guard allow it.
state/kit_sent.json records the send.
```

---

## Before running repair

Check these first:

```text
[ ] Which slot dropped: AM or PM?
[ ] Did content/issues/YYYY-MM-DD-slot.md get created?
[ ] Did content/email/YYYY-MM-DD-slot.md get created?
[ ] Did site/dist/ update?
[ ] Did Cloudflare deploy?
[ ] Did state/kit_sent.json already record a send?
[ ] Did Kit already create the broadcast?
```

Never run a send repair if Kit or `state/kit_sent.json` already shows a public send for the slot.

---

## After running repair

Verify:

```text
[ ] GitHub Actions repair workflow completed successfully.
[ ] Latest issue exists in content/issues/.
[ ] Locked email snapshot exists in content/email/ if email was sent.
[ ] Homepage links the latest issue.
[ ] Latest article route exists.
[ ] RSS includes the latest issue.
[ ] Sitemap includes the latest issue.
[ ] Cloudflare deployment succeeded.
[ ] Kit broadcast exists if send was expected.
[ ] state/kit_sent.json was updated if send was expected.
[ ] No duplicate email was sent.
```

---

## Duplicate-send protection

The send workflow and `kit_publish.py` are designed to block duplicate public emails by date and slot.

The guard checks:

```text
Issue filename is slot-specific: YYYY-MM-DD-am.md or YYYY-MM-DD-pm.md.
ISSUE_SLOT matches the filename slot.
state/kit_sent.json does not already record a public send for the slot.
Only one AM and one PM public send are allowed per issue date.
```

Do not delete or edit `state/kit_sent.json` just to force another send.

If a resend is truly needed, treat it as an incident and get Rozilla approval.

---

## Common repair scenarios

### Scenario 1: AM prepare failed

```text
issue_slot: am
repair_action: prepare_only
reason: AM prepare failed before issue creation
```

Then verify the web version. If email also missed later, run `send_only` after confirming no send record exists.

### Scenario 2: AM issue exists, but Kit did not send

```text
issue_slot: am
repair_action: send_only
reason: AM Kit send failed after prepare succeeded
```

Use only if `state/kit_sent.json` does not already show a public AM send.

### Scenario 3: PM slot completely dropped

```text
issue_slot: pm
repair_action: prepare_and_send
reason: PM schedule did not run
```

Use when both generation and send are missing.

### Scenario 4: Site updated but Cloudflare did not deploy

Do not use the Kit repair workflow first.

Use the site deploy workflow:

```text
.github/workflows/deploy-site.yml
```

Then verify:

```text
news.forgecore.co
latest article route
RSS
sitemap
```

### Scenario 5: Email already sent but article has a typo

Do not resend.

Fix the web article through GitHub, re-render, deploy, and optionally correct the Kit public post if appropriate.

---

## Team escalation rules

Escalate to Rozilla before action if:

```text
A duplicate public email may have gone out.
A sponsor or affiliate issue was sent incorrectly.
The repair would send outside the normal AM/PM cadence.
state/kit_sent.json conflicts with what the Kit dashboard shows.
The team is considering deleting send records.
The repair involves an erratum or apology email.
```

The team may repair without waiting when:

```text
The scheduled prepare workflow failed and no email has sent.
The scheduled send failed and the slot has no public send record.
The Cloudflare deploy failed but the generated site output is valid.
A workflow was cancelled or skipped before subscriber impact.
```

---

## Definition of done

A dropped run is fully repaired when:

```text
The intended AM/PM issue exists.
The site reflects the issue.
Cloudflare served the updated site.
The intended email was either sent once or intentionally skipped.
state/kit_sent.json matches Kit send reality.
No duplicate email was sent.
The failure reason is understood.
A prevention fix is identified if the same failure can recur.
```
