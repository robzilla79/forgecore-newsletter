# Show HN: Send Cold Emails with AI Agents

- Source: Hacker News Show HN
- Published: Tue, 12 May 2026 19:03:34 +0000
- URL: https://github.com/open-salesblink/skill
- Domain: github.com
- Tags: builders, tools, indie

## Feed summary

Article URL: https://github.com/open-salesblink/skill
Comments URL: https://news.ycombinator.com/item?id=48112826
Points: 1
# Comments: 0

## Extracted article text

Run cold email sequences and sales outreach on autopilot via the SalesBlink API. Works with any AI agent.
Grab your key from run.salesblink.io/account/integration/api
.
Any agent (npx)
npx skills add open-salesblink/skill
Claude Code
/plugin marketplace add https://github.com/open-salesblink/skill
/plugin install cold-email-salesblink
OpenClaw / ClawHub
openclaw skills install cold-email-salesblink
export SALESBLINK_API_KEY="key-****"
- "Create a cold email sequence for my SaaS product"
- "Add these leads to a new list and launch a campaign"
- "Check analytics for opens and replies from last week"
- "Run an inbox placement test for my template"
- Cold email campaigns — build sequences, write templates, and launch outreach
- Lead management — create lists, import contacts in bulk, move and update leads
- Sender management — connect Gmail/Outlook via OAuth or SMTP/IMAP accounts
- Inbox & replies — read threads, reply to prospects, mark conversations
- Analytics — track opens, clicks, replies, and sent events
- Deliverability testing — run inbox placement tests across providers
- Workspace & team management — users, roles, folders, and account config
codex plugin marketplace add https://github.com/open-salesblink/skill
Invoke by referencing the plugin namespace.
git clone https://github.com/open-salesblink/skill.git
Load the plugin from the cloned directory in Cursor's plugin settings.
gemini extensions install https://github.com/open-salesblink/skill
Or clone and link locally:
git clone https://github.com/open-salesblink/skill.git
cd skill/.gemini-extension
gemini extensions link .
Restart Gemini CLI after linking. The extension auto-loads GEMINI.md
context.
Visit https://mcp.salesblink.io to connect via MCP.
Note: All platforms above require the same
SALESBLINK_API_KEY
environment variable shown in Step 3.
Base URL
https://run.salesblink.io/api/public/v1.0.0
Authentication
Pass your API key in the Authorization
header with no "Bearer" prefix:
Authorization: key-****
Pagination
- Most list endpoints:
limit
(max 100) andskip
- Activity endpoints (
/sent
,/opens
,/clicks
,/replies
):per_page
(max 100) andpage
(1-indexed)
Always paginate — never assume a single request returns all data.
Error Handling
| Status | Meaning | Action |
|---|---|---|
| 200 | Success | Check success field |
| 400 | Bad request | Re-check payload structure against the reference file |
| 401 | Unauthorized | Verify API key |
| 403 | Forbidden | Insufficient permissions (role too low) |
| 404 | Not found | Verify the ID / endpoint |
| 409 | Conflict | Resource already exists or connection failed |
| 429 | Rate limited | Wait 60s, then retry |
| 500 | Server error | Retry once after 10s |
See references/workflows.md
for full examples. High-level flow:
- Create a list →
POST /lists
- Add contacts →
POST /contacts
(batch up to 500, PascalCase fields) - Create templates →
POST /templates
(merge vars like{{first_name}}
) - Fetch senders →
GET /senders
- Create sequence →
POST /sequences
(steps: email → delay → email …) - Launch →
PATCH /sequences/:id
withpaused: false
&launchTimingMode: "now"
The evals/evals.json
file contains test scenarios covering list creation, bulk contact import, sequence creation, large CSV ingestion, inbox replies with CC, and paginated activity tracking.
- Requires network access to
run.salesblink.io
- Supports any HTTP client (curl, Node.js fetch, Python requests, PowerShell, etc.)
This skill is provided as-is for use with the SalesBlink platform. Refer to SalesBlink's terms of service for API usage policies.
