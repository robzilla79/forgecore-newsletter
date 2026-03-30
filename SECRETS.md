# GitHub Actions Secrets Setup

These secrets must be set at:
**https://github.com/robzilla79/forgecore-newsletter/settings/secrets/actions**

---

## Required Secrets

### `GH_PAT`
- **What:** GitHub Personal Access Token
- **Permissions needed:** `repo` (full), `workflow`
- **Create at:** https://github.com/settings/tokens
- **Used for:** Allowing the bot to `git push` generated content back to the repo

### `CLOUDFLARE_API_TOKEN`
- **What:** Cloudflare API Token for Pages deployments
- **Permissions needed:** `Cloudflare Pages: Edit`
- **Create at:** https://dash.cloudflare.com/profile/api-tokens
- **Used for:** Deploying `site/dist/` to Cloudflare Pages via wrangler

### `CLOUDFLARE_ACCOUNT_ID`
- **What:** Your Cloudflare Account ID (not zone ID)
- **Find at:** https://dash.cloudflare.com → right sidebar → Account ID
- **Format:** 32-character hex string (e.g., `85ed3742e092da44ce5dab1fb99add51`)
- **Used for:** Targeting the right Cloudflare account for Pages deploy

### `OLLAMA_URL`
- **What:** Publicly reachable URL for your Ollama instance
- **Example values:**
  - `https://your-ngrok-tunnel.ngrok.io` (if using ngrok)
  - `https://ollama.yourdomain.com` (if using Cloudflare Tunnel)
  - `http://your-vps-ip:11434` (if on a VPS)
- **Why required:** GitHub Actions runners are cloud VMs. They cannot reach `localhost:11434`.
- **Local-only option:** If you don't expose Ollama publicly, the LLM pipeline steps are skipped gracefully. Only `web_research.py` and `publish_site.py` will run, which still produces a site update.

---

## Optional Secrets (override defaults)

### `RESEARCH_MODEL`
- Default: `qwen2.5:14b-instruct`
- Override with any Ollama model tag you have pulled

### `WRITER_MODEL`
- Default: `gemma3:12b`

### `EDITOR_MODEL`
- Default: same as `WRITER_MODEL`

### `FALLBACK_MODEL`
- Default: `qwen3:8b`
- Used when primary model fails or returns invalid JSON

---

## How to expose Ollama publicly (Cloudflare Tunnel method)

This is the recommended approach if your Ollama runs on a home machine with RTX 5070 Ti.

```bash
# Install cloudflared
winget install Cloudflare.cloudflared

# Authenticate
cloudflared tunnel login

# Create a tunnel
cloudflared tunnel create forgecore-ollama

# Route the tunnel
cloudflared tunnel route dns forgecore-ollama ollama.yourdomain.com

# Run the tunnel (points to local Ollama)
cloudflared tunnel run --url http://localhost:11434 forgecore-ollama
```

Then set `OLLAMA_URL=https://ollama.yourdomain.com` as your GitHub Secret.

---

## Cloudflare Pages Project Setup

The project name in generate.yml is `forgecore-newsletter`.

Verify your Pages project exists at:
https://dash.cloudflare.com/pages

If the project doesn't exist, create it:
```bash
npx wrangler pages project create forgecore-newsletter
```

The site will deploy to: `forgecore-newsletter.pages.dev` (and your custom domain `news.forgecore.co` if configured).

---

## Verification

After setting all secrets, manually trigger a test run:
https://github.com/robzilla79/forgecore-newsletter/actions/workflows/generate.yml

Click "Run workflow" → "Run workflow".

Check the run logs for:
- `reachable=true` (Ollama check passed)
- `auto: newsletter issue ... [bot]` (content committed)
- `Deployment successful` (Cloudflare Pages deployed)
