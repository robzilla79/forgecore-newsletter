# ForgeCore AI Newsletter Engine

This project is the AI-wired, end-to-end workflow for **research -> scout -> analyst -> author -> editor -> critic -> quality gate -> site render -> optional Cloudflare deploy**.

## What it does

- pulls fresh public-web inputs from configured RSS feeds and article pages
- runs Ollama-powered stages for scout, analyst, author, editor, and critic
- enforces a stronger editorial quality gate
- renders the public site for `news.forgecore.co`
- can deploy `site/dist` to Cloudflare Pages when enabled

## Models

Recommended:
- `RESEARCH_MODEL=qwen2.5:14b-instruct`
- `WRITER_MODEL=gemma3:12b`
- `EDITOR_MODEL=gemma3:12b`
- `CRITIC_MODEL=gemma3:12b`
- `FALLBACK_MODEL=qwen3:8b`

## Environment defaults

A fresh pull now works with committed safe defaults from `.env.defaults`.

- Put real machine-specific overrides or secrets in your local `.env`
- `.env` stays ignored by git
- If `.env` is missing, the code falls back to `.env.defaults`
- If you want a real local file created automatically, run `python bootstrap_env.py`

## Quick start (Windows)

1. Create and activate a virtual env.
2. Install requirements: `py -m pip install -r requirements.txt`
3. Optional: run `python bootstrap_env.py` to create `.env`
4. Pull models with Ollama.
5. Run `run_workflow.bat`

## Quick start (macOS/Linux)

```bash
python -m venv .venv
.\.venv/scripts/activate
pip install -r requirements.txt
python bootstrap_env.py
python agent_loop.py all
```

## Direct deploy to Cloudflare Pages

1. Set `ENABLE_CLOUDFLARE_DEPLOY=1` in `.env` or rely on `.env.defaults`
2. Make sure Wrangler is installed and authenticated
3. Set `CLOUDFLARE_PAGES_PROJECT=forgecore-newsletter`
4. Run `python agent_loop.py all`

That will build the site and then deploy `site/dist`.

## Beehiiv

The site renderer supports Beehiiv in two ways:
- set `BEEHIIV_EMBED_HTML` in `.env` for embedded forms
- or rely on the publication URL for button-based signup

Current publication URL:
- `https://forgecore-newsletter.beehiiv.com/`

## Output folders

- `research/raw/`
- `research/briefs/`
- `content/issues/`
- `site/dist/`
- `state/`
