# Workflow

1. `web_research.py` pulls fresh source material.
2. `agent_loop.py scout` asks Ollama to write a raw intel memo.
3. `agent_loop.py analyst` asks Ollama for an editorial brief.
4. `agent_loop.py author` asks Ollama for a full issue.
5. `agent_loop.py editor` asks Ollama to rewrite the issue for publication quality.
6. `quality_gate.py` blocks weak issues.
7. `publish_site.py` builds the public site for `news.forgecore.co`.
8. `deploy_cloudflare.py` pushes `site/dist` to Cloudflare Pages when enabled.
