# FORGE/DAILY — Issue Format Spec

This is the canonical format for all FORGE/DAILY issues authored by Em.
The issue contract (`issue_contract.py`) recognizes this format and will NOT attempt to normalize it.

---

## File naming

```
content/issues/YYYY-MM-DD.md
```

## Required sections (in order)

```markdown
# FORGE/DAILY — [Month Day, Year]
*AI news for people who don't need it explained twice.*

---

## THE STORY
[150-200 words. The one thing that matters today. No hype. Technically literate.]

---

## QUICK HITS
- **[Title]** — [One sentence. What happened. Why it matters or doesn't.]
- **[Title]** — [One sentence.]
- **[Title]** — [One sentence.]
- **[Title]** — [One sentence.]

---

## EM'S TAKE
[50-75 words. Sharp, opinionated, contrarian if warranted. This is the editorial voice.]

---

## ONE THING TO TRY
**[Tool or resource]** — [1-2 sentences. Actionable. Free or low-cost. Developer-relevant.]

---

*FORGE/DAILY is written by Em for ForgeCore.co — news.forgecore.co*
*Published daily. No fluff. No apologies.*
```

## Tone rules

- No "revolutionary", "game-changing", "groundbreaking" unless being sarcastic
- Assume reader knows what an LLM, API, and fine-tuning are
- Dry wit welcome, enthusiasm must be earned
- Opinions required — wishy-washy both-sidesing is not
- Target audience: cynical developers, Reddit power users, technical builders
