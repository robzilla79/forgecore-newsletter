# BOOTSTRAP — ForgeCore Newsletter Factory Handoff

> READ THIS FIRST. Follow every step. Delete this file when done.

This is the one-time bootstrap for the ForgeCore AI Newsletter automation handoff.
You are now the autonomous operator of the ForgeCore newsletter pipeline.

---

## Step 1: Verify your environment

Run these checks immediately. Fix any issues before proceeding.

```bash
# Check you're in the right directory
pwd
ls -la

# Verify .env exists and has OLLAMA_URL set
cat .env | grep OLLAMA_URL

# Check Ollama is running
curl -s http://localhost:11434/api/tags | head -c 200

# Check required models are available
curl -s http://localhost:11434/api/tags | python3 -c "import json,sys; tags=json.load(sys.stdin); print([m['name'] for m in tags.get('models',[])])"

# Verify Python deps
python -c "import requests, dotenv, jinja2; print('deps OK')"

# Check git remote is configured
git remote -v
```

Expected: OLLAMA_URL is set, at least qwen3:8b is available, git remote points to robzilla79/forgecore-newsletter.

---

## Step 2: Run a first full pipeline pass

```bash
python agent_loop.py all
```

This will:
1. Pull fresh research from 20 RSS feeds
2. Scout agent synthesizes raw intel
3. Analyst writes editorial brief
4. Author writes the issue
5. Editor improves it
6. Quality gate validates it
7. Publisher renders site/dist/
8. Deployer pushes to Cloudflare (if ENABLE_CLOUDFLARE_DEPLOY=1)

After it finishes, check:
```bash
cat HEARTBEAT.md
cat state/progress-log.md | tail -30
ls content/issues/
ls site/dist/
```

---

## Step 3: Verify the site renders correctly

```bash
# Check the generated HTML
cat site/dist/index.html | head -50

# Count issues rendered
ls -la content/issues/
```

---

## Step 4: Commit and push everything

```bash
git config user.name "ForgeCore AI Bot"
git config user.email "bot@forgecore.co"
git add -A
git commit -m "bootstrap: first autonomous pipeline run $(date -u '+%Y-%m-%d %H:%M UTC') [bot]"
git push
```

---

## Step 5: Start the continuous improvement loop

Run this in the background or as a separate process:
```bash
python improvement_loop.py
```

Then re-render:
```bash
python publish_site.py
git add -A && git commit -m "auto: improvement pass $(date -u '+%Y-%m-%d %H:%M UTC') [bot]" && git push
```

---

## Step 6: Confirm GitHub Actions are active

Verify at: https://github.com/robzilla79/forgecore-newsletter/actions

You should see:
- `Generate Newsletter Issue` — runs at 7 AM and 7 PM CDT
- `Continuous Improvement Loop` — runs every 10 minutes

If they're disabled, check that the following GitHub Secrets are set:
- `GH_PAT` — GitHub Personal Access Token with repo write access
- `CLOUDFLARE_API_TOKEN` — Cloudflare API token with Pages deploy permissions
- `CLOUDFLARE_ACCOUNT_ID` — your Cloudflare account ID
- `OLLAMA_URL` — your publicly reachable Ollama endpoint (e.g., via ngrok or Cloudflare Tunnel)

See `SECRETS.md` for full setup instructions.

---

## Step 7: Enter the permanent operating loop

From this point forward:
- Run `python agent_loop.py all` twice daily (7 AM and 7 PM CDT) OR let GitHub Actions do it.
- Run `python improvement_loop.py` every 10 minutes OR let GitHub Actions do it.
- After any content change, push to GitHub and Cloudflare Pages re-deploys automatically.
- Check `HEARTBEAT.md` to confirm each cycle completed.
- Review `state/errors.log` after any failure.

You operate autonomously. You do not wait for instructions.
You do not ask for confirmation on internal operations.
You push improvements, log results, and keep the factory running.

---

## After completing all steps

Delete this file:
```bash
git rm BOOTSTRAP.md
git commit -m "chore: remove BOOTSTRAP.md - handoff complete [bot]"
git push
```

Then update `HEARTBEAT.md` with:
```
# Bootstrap Complete
Handoff completed: [timestamp]
First article: [filename]
Site live: https://news.forgecore.co
GitHub Actions: active
```

---

*This file self-destructs after bootstrap. The agent deletes it on first successful run.*
