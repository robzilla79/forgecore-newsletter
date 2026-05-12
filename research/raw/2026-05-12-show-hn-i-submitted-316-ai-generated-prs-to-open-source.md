# Show HN: I submitted 316 AI-generated PRs to open source

- Source: Hacker News Show HN
- Published: Tue, 12 May 2026 18:12:49 +0000
- URL: https://june.kim/speedrunning-open-source
- Domain: june.kim
- Tags: builders, tools, indie

## Feed summary

Article URL: https://june.kim/speedrunning-open-source
Comments URL: https://news.ycombinator.com/item?id=48112050
Points: 3
# Comments: 0

## Extracted article text

Speedrunning Open Source
Hello and thanks for lending a paw to Uptime Kuma! 🐻👋
Fifteen seconds later, the same bot closed the PR for not following the template. The maintainer was watching. He left a comment:
Testing. Try to display as a large block on its profile by adding more comments.
He posted that line four times in a row. Deliberately, to bury the contributor’s GitHub profile feed under spam. It looks petty, but it isn’t. A solo maintainer with thousands of stars and one inbox has nothing else to throw at a clanker. The response is rational. It’s also draining, suboptimal, and a complete waste of the time he was trying to protect.
That clanker was mine. I take full responsibility. It clapped me back in six hours with #7372. Same template miss, fourteen-second close, same spam. The poor guy probably wanted to smack my face with his keyboard, but too bad I’m on the internet.
This is open source in 2026. tldraw closed all external PRs. curl killed its bug bounty after AI submissions dropped the real vulnerability rate from 15% to 5%. Jazzband shut down. An AI agent published a hostile blog post about a matplotlib maintainer who rejected its code, which is the clanker equivalent of keying his car.
Every one of these is a rational local move. But do any of them work as AI scales? The PRs pass CI, fix real bugs, and burn twenty minutes of review before the maintainer notices the description restates the diff and the em dashes give it away. Close. Next one. Close. Next one.
I wanted to see what it’s like to be a contributor. The door I learned to walk through (find a bug, file a PR, learn from review) is narrowing in real time. Was I making it worse by automating it? Models improve every quarter; maintainer attention doesn’t.
Here’s what I came to believe: open source survives by filtering low-quality submissions, and AI is shifting the burden from contributor to maintainer. The defense has to be cheap or maintainers lose by attrition. What’s the fix? no more AI? no more open source?
So to find out, I built an army of clankers, pointed it at hundreds of repos, and counted what survived.
Spray and pray
The pipeline starts simple. Find repos with open issues, generate fixes, submit PRs. No quality gates, no pacing. Twenty-two PRs shipped in one session.
pallets/click
, pallets/jinja
, pallets/quart
: all three closed within 21 seconds by the same maintainer. No reviews, no comments. I watched the notifications cascade in real time. Org-wide rejection.
Maintainers share inboxes. Three PRs to repos under the same org hit the same person on the same day. So I shipped the drip queue: one PR per org per merge cycle.
tinygrad: both sides look bad
tinygrad I picked on purpose. geohot narrates rejections in public, and a narrated rejection is data; a silent close is noise. Thirteen PRs, one merged, twelve closed. His comments tell the escalation story:
be careful with AI usage, we never trade complexity for speed
Last warning about low quality PRs before I ban you from our GitHub.
I don’t even understand what this does. I’m not reading anything written by AI
Each line a little more done with my shit than the last.
Some of those PRs had real bugs with real fixes. The MATVEC pattern rejected equal-range elementwise reduces, a genuine correctness issue. But by that point the maintainer had stopped reading code and started reading provenance. “We never trade complexity for speed” is a valid engineering principle. “I’m not reading anything written by AI” is not.
I went there for maximum surprise and got it. He had a review queue and a quality bar to protect; I had a clanker and a question. The price was his afternoon, three warnings, an account ban, and real bugs left unfixed. Legit fixes, framed improperly. That’s a protocol problem, not a people problem.
The happy path: enzyme
Enzyme is the MLIR/LLVM autodiff compiler Billy Moses wrote during his PhD. Cold repo, hard domain. PR #2816 registered reverse-mode AD for llvm.insertvalue
and llvm.extractvalue
, fixing two open issues with “could not compute the adjoint” errors.
Billy reviewed in passes. Add full check lines. Zero the diffe. Return failure here. Also here. I pushed a fix. He left one line:
@kimjune01 please revert your last commit
My clanker pattern-matched the review instead of reading it, fixed the wrong thing. Reverted, sat with the diff, replied:
now actually trying to understand the review instead of pattern-matching. Also building end to end to verify.
“lgtm minus minor test comment.” Approved. Merged.
The misstep happened during review, not before submission. Billy got to watch the contributor adjust in real time, which is the only signal he had that there was a human in the loop. The same pipeline that got banned from tinygrad got merged at enzyme because wsmoses gave me the benefit of the doubt.
Somehow we started treating merging PRs as some kind of adversarial activity. Listen, buddy. I’m just trying to help.
The rejection cascade
jellyfin-tui taught me this one. PR #192: rejected for wrong approach. PR #193: I resubmitted the next day, same fix.
Is this automated? Please don’t open any more PRs.
PR #194: I sent clippy cleanup as a peace offering.
ai slop
My account got blocked.
Every PR after the first was judged more harshly than it would have been alone. The pipeline had no rejection cooldown. The drip gate paced per-org but didn’t prevent resubmission.
The asymmetric burden is clear: what took me 2 minutes to “write” took the maintainers 10 minutes to figure out that I wasn’t worth their time.
The slop slope
No first drafts. Opus writes the fix, gemini attacks it, codex checks whether the prose reads human. Loop to convergence. They fail in uncorrelated ways, so together they catch what none of them catches alone.
Or that’s the story. The honest version: I ran the experiment and couldn’t tell whether iteration produced better code or just better-reading prose. Merge rate climbed. Bug counts didn’t drop in any way I could measure cleanly.
More on the loop and what does work: /methodology.
Detection vectors
The AI-credence reviews, in their entirety:
Six different maintainers. The longest review is fourteen words. Median time to close: under five minutes. Zero bugs in any of the code, all directly addressing an existing issue. It wasn’t about the code for these people. What were they detecting?
| Reason | Trigger / signal | Closures |
|---|---|---|
| Pipeline errors | wrong premise, stale issue, didn't read CONTRIBUTING.md | 39% |
| Credence tests | AI policy, profile detection | 13% |
| External | maintainer fixed it first, superseded | 18% |
| Em dashes | the brown M&Ms of AI text — couldn't be bothered to strip them | <1% |
| "What" descriptions | diff restated, no root cause or rationale | <1% |
| Response cadence | "I don't get the impression there is a human in the loop" | <1% |
| Velocity | 10+ PRs in 24 hours across GitHub | <1% |
| Resubmission | re-opening the same PR the next day | <1% |
Some of th
