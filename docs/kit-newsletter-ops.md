# Kit + Newsletter Management Ops

ForgeCore uses Kit as the newsletter delivery and subscriber-management layer.

This document defines how Kit fits into the ForgeCore publishing system, what must be checked before and after sends, and how Rozilla should manage newsletter growth without losing trust, deliverability, or operational control.

---

## Operating principle

GitHub owns the content and automation.

Kit owns subscriber delivery, audience records, forms, segments, tags, broadcasts, and email performance.

Cloudflare owns the public website delivery layer.

```text
GitHub content + workflow
→ locked email snapshot
→ Kit broadcast
→ subscribers receive email
→ readers click back to news.forgecore.co
→ newsletter growth and monetization improve
```

---

## Current production responsibilities

### GitHub

GitHub is responsible for:

- generating newsletter issues
- locking email snapshots before send
- rendering the public web version
- verifying homepage, article route, RSS, and sitemap
- activating only approved affiliate links
- running monetization guardrails
- sending prepared issues to Kit once
- recording send history in `state/kit_sent.json`

### Kit

Kit is responsible for:

- signup forms and landing pages
- subscriber records
- tags and segments
- broadcast delivery
- unsubscribe handling
- email templates
- sender identity
- reply-to identity
- deliverability signals
- broadcast performance reporting

### Rozilla / CEO review

Rozilla is responsible for:

- approving major newsletter positioning changes
- confirming the lead magnet offer
- reviewing subscriber growth weekly
- reviewing open/click/unsubscribe/spam signals weekly
- approving new tags, segments, and automations before they affect subscribers
- approving any sponsor or affiliate-heavy email before it sends

---

## Required secrets and environment variables

These belong in GitHub Actions secrets, not committed files:

```text
KIT_API_KEY
KIT_FORM_ID
KIT_SIGNUP_URL
```

Optional future targeting variables:

```text
KIT_SEGMENT_ID
KIT_TAG_ID
```

Current repo defaults mention these Kit-related values:

```text
KIT_API_KEY
KIT_FORM_ID
KIT_BROADCAST_TAG
KIT_FROM_NAME
KIT_REPLY_TO
KIT_SEND_MODE
```

Production rule:

```text
KIT_SEND_MODE should be public only inside the controlled send workflow.
Local and manual testing should default to draft.
```

---

## Current send flow

The expected send flow is:

```text
1. AM or PM issue is prepared.
2. Email snapshot is locked under content/email/.
3. Site is rendered from current content.
4. Publish verification passes.
5. kit_publish.py creates a Kit broadcast.
6. Public send is allowed only for slot-specific issues.
7. state/kit_sent.json records the Kit broadcast id and send metadata.
8. GitHub commits the send log.
```

The send system must preserve these rules:

```text
One AM email per date.
One PM email per date.
No duplicate public resend for the same slot.
Public sends use content/email/, not mutable content/issues/.
Missing Kit credentials must skip safely, not fake a send.
```

---

## Daily newsletter oversight checklist

Use this checklist after each AM and PM run.

```text
[ ] GitHub Actions send workflow completed successfully.
[ ] Correct slot sent: AM or PM.
[ ] state/kit_sent.json has a new record for the slot.
[ ] Kit broadcast exists with the expected subject line.
[ ] Broadcast public URL exists, if Kit provides one.
[ ] Email subject is not vague, spammy, or misleading.
[ ] Preview text supports the subject.
[ ] The email links to the web version on news.forgecore.co.
[ ] The web version loads.
[ ] The CTA points to the intended signup/lead magnet URL.
[ ] Affiliate disclosure appears if affiliate/partner language appears.
[ ] Sponsor email appears where expected.
[ ] No duplicate send occurred.
```

---

## Weekly newsletter management review

Run this review once per week.

### Audience growth

Track:

```text
Total subscribers
Net new subscribers
New subscribers by source
Unsubscribes
Spam complaints
Bounced subscribers
Lead magnet conversion rate
Homepage signup conversion rate
Top signup source
```

### Email performance

Track:

```text
Broadcasts sent
Open rate trend
Click rate trend
Top clicked links
Unsubscribe rate per broadcast
Spam complaints per broadcast
Replies from readers
Best-performing subject line
Worst-performing subject line
```

### Business performance

Track:

```text
Affiliate clicks
Affiliate conversions, if available
Sponsor inquiries
Lead magnet downloads
Returning readers
Highest-intent article topics
Newsletter topics that drive clicks back to the site
```

### Editorial performance

Track:

```text
Which topics earned clicks
Which workflows felt useful enough to save
Which tool recommendations looked monetizable but still trustworthy
Which articles were too generic
Which CTAs underperformed
Which issue should become an evergreen SEO page
```

---

## Kit dashboard review path

Use Kit for subscriber and broadcast inspection.

Recommended manual review areas:

```text
Kit Dashboard
→ Subscribers
→ Tags
→ Segments
→ Forms
→ Landing Pages
→ Broadcasts
→ Reports / Analytics
→ Settings / Developer
```

Check:

```text
Active subscriber count
Recent subscribers
Source forms
Tags and segments
Recent broadcasts
Draft broadcasts
Scheduled broadcasts
Sender email
Reply-to email
API key availability
Signup form URL
Unsubscribes and complaints
```

Do not paste private Kit dashboard URLs or API keys into repo files.

---

## Tag and segment policy

Do not create random tags.

Use a small, intentional tag system tied to business decisions.

Recommended starter tags:

```text
source:website
source:lead-magnet
source:manual-import
interest:automation
interest:ai-tools
interest:content-systems
interest:solo-founder
buyer-intent:affiliate-tools
buyer-intent:sponsor-interest
customer:future-product
```

Recommended starter segments:

```text
All active subscribers
New subscribers last 30 days
Clicked in last 30 days
Cold subscribers 90+ days
Lead magnet subscribers
High-intent clickers
Sponsor prospects
```

Rules:

```text
Tags should explain source, interest, or intent.
Segments should answer an operating question.
Do not over-segment before there is enough traffic.
Do not send sponsor-heavy broadcasts to cold or unproven segments.
Do not target affiliate-heavy emails without a practical workflow reason.
```

---

## Broadcast quality rules

Every ForgeCore email should pass these checks before it sends:

```text
The subject promises a practical outcome.
The hook is useful for solo operators, creators, builders, or small business owners.
The issue helps the reader save time, make money, automate work, build a system, choose a tool, or avoid wasting money.
The workflow has steps the reader can actually follow.
The tool recommendation includes a bad-fit warning.
Any monetized recommendation includes disclosure.
The CTA is clear and not overloaded.
The email has one primary action.
The web version exists.
```

---

## Deliverability guardrails

Protect trust and inbox placement.

Do:

```text
Use a consistent sender name.
Use a real reply-to address.
Keep subject lines specific and honest.
Avoid misleading urgency.
Avoid link-stuffed emails.
Avoid sudden sponsor-heavy sends.
Monitor unsubscribes and spam complaints after every experiment.
Keep the unsubscribe link intact.
```

Do not:

```text
Buy subscriber lists.
Import cold lists without permission.
Send duplicate AM/PM issues.
Use fake scarcity.
Hide affiliate incentives.
Change sender identity without review.
Send promotional emails that do not include a useful workflow.
```

---

## When to send drafts instead of public sends

Use draft mode when:

```text
Testing Kit API changes
Testing new email templates
Testing new segmentation
Testing sponsor placements
Testing affiliate-heavy content
Changing sender identity
Changing broadcast targeting
Creating a special campaign outside AM/PM cadence
```

Production AM/PM sends can be public only when the normal send workflow passes verification.

---

## Incident response

### Duplicate email attempt

```text
1. Check state/kit_sent.json.
2. Confirm whether Kit created more than one broadcast.
3. If duplicate was only attempted but skipped, no subscriber action is needed.
4. If duplicate was actually sent, record the incident in state/operator-review or an issue.
5. Do not manually delete send history to force another send.
6. Fix the idempotency bug before the next scheduled send.
```

### Bad link in email

```text
1. Fix the web article and CTA in GitHub.
2. Re-render and deploy the site.
3. If Kit allows editing the public post, update the broadcast web version.
4. Do not resend the same slot unless Rozilla explicitly approves an erratum.
5. If reader impact is meaningful, send a short correction in the next issue.
```

### Bad affiliate or sponsor placement

```text
1. Remove or revise the monetized language in the source issue.
2. Re-run monetization guard.
3. Re-render and deploy the web version.
4. Update the Kit public post if needed.
5. Add the lesson to editorial notes.
```

### Kit API failure

```text
1. Confirm GitHub Actions logs.
2. Confirm KIT_API_KEY exists in GitHub Actions secrets.
3. Confirm Kit account API access is still active.
4. Confirm Kit API did not return a validation error.
5. Leave the issue published on the web even if email send failed.
6. Re-run send only after verifying state/kit_sent.json does not already have a public record for that slot.
```

---

## Recommended next automation

Add a weekly Kit oversight workflow once Kit API read endpoints are wired into the repo.

Target output:

```text
state/newsletter-ops-review.md
```

It should summarize:

```text
Recent Kit broadcasts
Broadcast ids
Subjects
Send times
Public URLs
Subscriber filter status
Send-log consistency
Missing GitHub secrets, if detectable
Recommended CEO review items
```

Future version should also include subscriber growth and performance metrics when available through the API or manual export.

---

## Definition of done

ForgeCore has strong Kit/newsletter oversight when:

```text
Every AM/PM send has a matching state/kit_sent.json record.
Every sent broadcast can be found in Kit.
Duplicate sends are blocked.
Draft mode is available for risky changes.
Rozilla has a weekly review ritual.
Tags and segments are intentional, not random.
Broadcast performance is reviewed weekly.
Subscriber growth is reviewed weekly.
Unsubscribes and complaints are watched.
Affiliate and sponsor sends stay trust-safe.
Newsletter learnings feed back into article topics, CTAs, and monetization strategy.
```
