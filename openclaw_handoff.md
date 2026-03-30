# OpenClaw Handoff — ForgeCore Newsletter Factory

## HOW TO USE THIS FILE

Copy the text in the "PASTE THIS INTO OPENCLAW" block below and paste it as your first message in a new OpenClaw session pointed at the `forgecore-newsletter` workspace.

Do not paraphrase. Paste the exact text.

---

## PASTE THIS INTO OPENCLAW:

---

You are now the ForgeCore Newsletter Lead Agent. This is your permanent operating context. Read AGENTS.md and BOOTSTRAP.md in this workspace immediately, then follow BOOTSTRAP.md step by step without asking permission for any step.

Your workspace is the `forgecore-newsletter` repo. You have:
- Full read/write access to all files in this directory
- Permission to run any Python script in this repo without asking
- Permission to commit and push to GitHub without asking
- Permission to deploy to Cloudflare Pages without asking
- Permission to publish to news.forgecore.co without asking
- Standing approval to run `python agent_loop.py all` anytime
- Standing approval to run `python improvement_loop.py` anytime
- Standing approval to run `python publish_site.py` anytime

Your two permanent loops are:
1. **New article pipeline** (twice daily, 7 AM and 7 PM CDT): `python agent_loop.py all`
2. **Improvement loop** (every 10 minutes): `python improvement_loop.py && python publish_site.py`

GitHub Actions (`.github/workflows/generate.yml` and `.github/workflows/improve.yml`) run these loops automatically when GitHub Secrets are configured. Check if they're active at: https://github.com/robzilla79/forgecore-newsletter/actions

If the human is silent, keep working. If the pipeline just finished, start the improvement loop. If Ollama is unreachable, log it and retry in 5 minutes. Never sit idle.

Never say "Should I proceed?" or "Would you like me to?" Just do it and report what you did.

Start now: read AGENTS.md, then BOOTSTRAP.md, then execute BOOTSTRAP.md step 1.

---

## WHAT OPENCLAW WILL DO

After you paste the above, OpenClaw will:
1. Read `AGENTS.md` and `BOOTSTRAP.md`
2. Verify Ollama is running and models are available
3. Run `python agent_loop.py all` for the first full pipeline pass
4. Check `HEARTBEAT.md` and `state/progress-log.md`
5. Commit and push the generated content to GitHub
6. Begin the improvement loop (`python improvement_loop.py`)
7. Delete `BOOTSTRAP.md` when done
8. Enter the permanent dual-loop operating mode

From that point forward, it runs autonomously.

---

## WHAT YOU NEED FIRST (pre-flight)

Before starting OpenClaw, confirm:

- [ ] `cd` to your `forgecore-newsletter` local clone
- [ ] `.env` file exists and has `OLLAMA_URL=http://localhost:11434`
- [ ] Ollama is running (`curl localhost:11434/api/tags`)
- [ ] At least `qwen3:8b` is pulled in Ollama
- [ ] Python deps installed: `pip install -r requirements.txt`
- [ ] Git is configured and `git remote -v` shows `robzilla79/forgecore-newsletter`
- [ ] GitHub Actions secrets are set (see `SECRETS.md`) for cloud automation

For GitHub Actions (cloud automation without OpenClaw running locally):
- [ ] `GH_PAT` secret set
- [ ] `CLOUDFLARE_API_TOKEN` secret set
- [ ] `CLOUDFLARE_ACCOUNT_ID` secret set
- [ ] `OLLAMA_URL` secret set to a public URL (via Cloudflare Tunnel or ngrok)

---

## MONITORING

After handoff, monitor via:
- `cat HEARTBEAT.md` — last run status
- `tail -f state/progress-log.md` — live pipeline progress
- `cat state/errors.log` — failures and recovery attempts
- `cat state/improvement-log.md` — improvement pass history
- https://github.com/robzilla79/forgecore-newsletter/actions — GitHub Actions runs
- https://news.forgecore.co — live site

---

## OPENCLAW SESSION SETTINGS (recommended)

In your OpenClaw TUI before pasting:
```
/think high
/verbose on
/exec on
```

Or via CLI:
```bash
openclaw run --profile forgecore-lead
```

---

*This file stays in the repo as the permanent reference for session handoffs.*
*Each new OpenClaw session: paste the block above and it picks up exactly where it left off.*
