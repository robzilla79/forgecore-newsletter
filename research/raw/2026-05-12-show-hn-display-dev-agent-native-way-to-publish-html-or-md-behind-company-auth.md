# Show HN: Display.dev, agent-native way to publish HTML or MD behind company auth

- Source: Hacker News Show HN
- Published: Tue, 12 May 2026 23:36:16 +0000
- URL: https://display.dev/
- Domain: display.dev
- Tags: builders, tools, indie

## Feed summary

Last week's post from Thariq "The Unreasonable Effectiveness of HTML" went viral in X. He made a good point about HTML being the more expressive and human friendly alternative to markdown files. I completely buy in where he's coming from, I've been asking Claude Code to create me HTML files to better understand what we're planning and building together.What Thariq didn't address was the part of sharing and collaborating on these HTML artifacts (he proposed uploading to S3). While I've been heavy user of HTML artifacts to share quarterly plans, implementation specs, technical guides and more, it has been a challenge of sharing them with my teammates securely. Not all people in the company have GitHub access to see the markdown file. Slack and Google Drive don't render HTML.There's been no good solution today on the market, until now, which gives you tools for your agent to publish the HTML and MD files, gate the artifacts behind company SSO or OTP and collaborate with your teammates on these artifacts through inline comments. All the tools out there are either local only or best case for solo developers.There are of course GitHub Pages, Cloudflare Pages (with Access) and other options, but they all charge you per seat, which is a hefty bill to pay if you just want to share an HTML file with your PM or marketing manager who doesn't have access to GitHub. GitBook is the worst opti

## Extracted article text

Your agents build HTML reports, dashboards, and docs every day. display.dev hosts them at permanent URLs, gated by company auth, with inline comments your agents can read and resolve. One command, one link, paste it in Slack.
Gated by your company's SSO. Collaboration and iteration via comments.
Specs, code reviews, dashboards, design prototypes – the artifacts your agent generates are sharper than ever. Interactive charts. Live filters. Hover states. Real layouts.
Then you have to share them. Screenshot to Slack. Drop in Drive. Paste into a Google Doc and watch it collapse. The artifact arrives degraded, or doesn't arrive at all.
display.dev is a gated publishing engine. The agent publishes the artifact directly, and you get a permanent URL. Viewers sign in with a one-time password, or the Google or Microsoft account they already use for work.
Build your artifact with whatever agent you use. Claude Code, Codex, and Cursor all work. Anything that produces HTML or Markdown.
Run dsp publish ./file.html
from your terminal, or say "publish this to my team" in Claude Desktop. You get back a permanent URL.
Paste the URL anywhere. Teammates click it, sign in with their company email, and see the artifact exactly as your agent built it.
Teammates drop inline comments. Your agent reads them, updates the artifact, and resolves the thread. Feedback and republish happen at the same URL.
Permanent URLs, company auth, and unlimited viewers at one flat price. No infrastructure to configure, no per-seat pricing that scales against you.
Viewers click a link and sign in with their Google or Microsoft account, or a one-time password. No app to install. No account to create. No IT ticket.
Inline comments on any artifact. Your agent reads them via MCP, updates the document, resolves the thread. Specs evolve. Reports stay current. The artifact stays a living document, not a one-shot screenshot.
dsp publish ./file.html
. No git repo, no deploy pipeline, no project to configure. One command from the terminal, or one sentence in Claude Desktop.
Every artifact gets a URL that keeps working. Share in Slack, link in Notion, paste in email. It still works six months later. No "link expired."
No per-seat pricing for viewers at any tier. Share with your PM, exec, legal team, or designer for the same price. The 51st viewer doesn't cost extra.
Arbitrary HTML with JavaScript, CSS, and interactivity intact. D3 charts stay live. Markdown converts to styled HTML.
See how often artifacts are viewed and exactly who accessed them. Every publish, view, and access logged for compliance and tracking.
Claude Code, Codex, and Cursor all work, along with anything else that creates HTML and Markdown output. Not locked to one provider. Every new agent that ships is a new publisher.
Share with 10 people or 1,000. The price doesn't change.
Try it. No credit card.
display.dev branded
Individuals. Unlimited gated sharing.
For teams that need company auth.
For compliance-driven organizations.
From $499/mo
What it costs to share one HTML artifact with 100 viewers behind company auth:
| Product | Monthly cost | Notes |
|---|---|---|
| display.dev Pro | $49 | Real SSO. Unlimited viewers. CLI + MCP. |
| Vercel Pro + SSO | $320+ | Git projects only. No file upload. |
| Cloudflare Pages + Access | ~$700 | $7/seat. No publish CLI. No MCP. |
| GitBook Ultimate | $249 | Structured docs only. Can't host arbitrary HTML. |
| GitHub Pages (private) | $2,100 | Enterprise Cloud required. Viewers need GitHub accounts. |
| DIY (S3 + Cognito) | ~$20 + 1–2 eng days | Ongoing maintenance. No MCP. Per-provider auth. |
Pricing based on 100 viewers. SSO costs vary by plan and provider.
display.dev gives every artifact a permanent, authenticated home. Your company can see it. Nobody else can.
No credit card · No per-seat fees · File to authenticated URL in 15 seconds
