# Show HN: GitGlimpse – CLI for understanding AI-generated Git diffs

- Source: Hacker News Show HN
- Published: Tue, 12 May 2026 20:53:55 +0000
- URL: https://gitglimpse.com
- Domain: gitglimpse.com
- Tags: builders, tools, indie

## Feed summary

Built GitGlimpse — a CLI that helps you understand AI-generated code changes faster.Coding agents can generate huge diffs quickly, but reviewing those changes is getting harder — especially in PRs where the author used an agent and already has the context in their head.GitGlimpse analyzes git diffs and generates contextual summaries of what changed and why, making PR reviews easier and faster.It can also:* generate standups/changelogs
* summarize commits and branches
* run in CI pipelines and automatically post PR context/commentsGitHub: https://github.com/dino-zecevic/gitglimpseWould love feedback from people dealing with AI-generated PRs/code reviews.

Comments URL: https://news.ycombinator.com/item?id=48114398
Points: 1
# Comments: 0

## Extracted article text

Your AI writes the code. Yougitglimpse writes the context.
A CLI that reads your git history, filters noise, groups commits into tasks, and prints PR descriptions, standups, weekly reports, and LLM-ready JSON. No accounts. No tracking. Works offline.
Your git log knows what changed.
It just doesn't tell you.
● Raw git log — noise & shortcuts
● glimpse standup — clean & structured
Four stages between git log and structured output.
No services, no databases, no setup. Just a Python process reading your local repository — running each commit through a deterministic pipeline before ever touching an LLM.
One repo. Many surfaces.
Pick a command — the terminal updates with what you'd actually see in your shell. Pipe it to a file, a Slack channel, or your AI editor.
Every PR gets a context comment. Automatically.
Drop the action into your workflow. The bot posts a single comment per PR and updates it on every push — no duplicates, no babysitting.
- uses: dino-zecevic/gitglimpse@main with: github-token: ${{ secrets.GITHUB_TOKEN }}
- uses: dino-zecevic/gitglimpse@main with: github-token: ${{ secrets.GITHUB_TOKEN }} llm-provider: openai llm-api-key: ${{ secrets.OPENAI_API_KEY }} llm-model: gpt-4o-mini
Also runs on GitLab CI, Bitbucket Pipelines, and any shell. Supports OpenAI, Anthropic, and Gemini — or runs offline against Ollama.
Becomes a slash command in Claude Code & Cursor.
Run glimpse init
. Commit the four generated files. Every developer who pulls the repo gets /standup
, /pr
, /week
, and /report
— no install, no docs, no onboarding.
What you get out of the box.
Noise filtering
Merge commits, lock files, formatting changes — excluded automatically. Mixed-noise commits are kept.
Task grouping
Buckets by branch, splits on 3-hour gaps. Three commits become one task with a derived summary.
Ticket extraction
Branches like feature/AUTH-42-login or feat/gh-15 surface ticket IDs in your output and JSON.
Effort estimation
Heuristic from commit timing — gaps under 2h count, longer ones cap. Labelled as estimated, not tracked.
Multi-project mode
Run from a parent directory to aggregate work across repos. Auto-detects, merges timelines.
Diff analysis
With --context both, sends actual code diffs to the LLM. Summaries describe intent, not file names.
Privacy-first
No accounts. No telemetry. Your commits never leave your machine unless you bring your own LLM key.
PyPI + GitHub Action
pip install for the CLI. The GitHub Action wraps it as one workflow step. Both stay in lockstep.
Bring your own LLM
OpenAI, Anthropic, Gemini, or Ollama running locally on your machine. Or skip the LLM — template mode is offline.
One command.
Structured context for life.
No accounts. No setup. No tracking. Just open source.
PR Summary — AUTH-247
Refactored authentication middleware to support JWT token rotation with automatic refresh handling. Added integration tests covering the new refresh flow and fixed a rate-limiter bypass on batch endpoints.
Changes
auth/middleware.py
(~1h)api/limits.py
batch path (~0.5h)tests/test_auth.py
refresh flow (~0.5h)
