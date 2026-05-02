# ForgeCore Monetization Registry

ForgeCore monetization must protect reader trust first.

This directory defines approved monetization rules for the newsletter and `news.forgecore.co` publishing system.

## Files

```text
affiliate-registry.json
```

The registry contains:

- approved affiliate candidates
- approved link placeholders or URLs
- allowed use cases
- bad-fit warnings
- simpler or cheaper alternatives
- disclosure examples
- global monetization rules

## Operating rules

### 1. Never force monetization

An issue should include affiliate language only when the tool genuinely fits the reader's workflow.

Bad:

```text
Mention every partner tool in every issue.
```

Good:

```text
Mention Castmagic only in an issue about turning recordings into newsletters, summaries, or clips.
```

### 2. Disclose clearly

If an issue uses affiliate, partner, referral, commission, or sponsored-link language, it must include disclosure language.

Default disclosure:

```text
Disclosure: ForgeCore may earn a commission if you buy through partner links, but recommendations are based on workflow fit, not payout.
```

### 3. Include a bad-fit warning

Every Tool of the Week should explain when not to use the tool.

Example:

```text
Do not use this if a simple saved prompt or checklist would solve the problem.
```

### 4. Include a simpler alternative

Paid tools should usually include a cheaper or simpler option, especially for beginners.

Example:

```text
If you only process one transcript per month, paste the transcript into ChatGPT before paying for a dedicated repurposing tool.
```

### 5. Use approved links only

Only use affiliate URLs listed in `approved_links`.

If a tool is useful but has no approved link, mention it normally without affiliate language.

### 6. Keep the issue useful without the link

The article must still help the reader even if they never click or buy anything.

## Placeholder links

Some registry URLs are placeholders, such as:

```text
AFFILIATE_CASTMAGIC
AFFILIATE_OPUSCLIP
AFFILIATE_DESCRIPT
AFFILIATE_REPURPOSE_IO
AFFILIATE_CANVA_PRO
```

Replace these with real approved URLs only after Rozilla signs up for the relevant affiliate or partner program.

Do not publish placeholder affiliate URLs as live links.

## Future improvements

Planned monetization improvements:

- replace placeholder links with real partner URLs
- add sponsor inventory and issue categories
- track tool mentions by issue
- add revenue attribution tags
- add display-ad readiness checks once traffic justifies it
