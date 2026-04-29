#!/usr/bin/env python3
"""Create a stub issue for today if none exists. Used as CI fallback when OpenAI is unavailable."""
import os
from datetime import datetime, timezone
from pathlib import Path

today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
issues_dir = Path('content/issues')
issues_dir.mkdir(parents=True, exist_ok=True)
path = issues_dir / f'{today}.md'

if path.exists():
    print(f'Issue already exists: {path} -- skipping stub')
else:
    stub = f'''# ForgeCore AI Dispatch -- {today}

## Hook
Today's AI landscape continues to shift rapidly. Operators who build repeatable systems outperform those chasing individual tools.

## Top Story
Operator teams are scaling AI delivery with API-first workflows that keep research, writing, and publishing tightly integrated inside GitHub Actions.

## Why It Matters
- API-first orchestration simplifies governance, observability, and reproducibility.
- Reproducible pipelines matter more than raw model capability for most business tasks.
- Teams that standardize prompts, validation, and release checks compound faster.

## Highlights
- Llama 3 variants continue to lead open-weight benchmarks for instruction following.
- Claude and GPT-4o remain dominant for long-context reasoning tasks.
- Fine-tuned 7B models now match GPT-3.5 on many vertical-specific workflows.

## Tool of the Week
OpenAI API -- use a single hosted model interface across scouting, analysis, authoring, and editorial QA.

## Workflow
Define a repeatable prompt contract for one step in your pipeline (research summary, headline generation, or quality scoring), then run it on each commit in CI.
Measure time saved vs. your current process before expanding the workflow.

## CTA
Pick one OpenAI-powered workflow this week, run it against a real task, and measure output quality against your current process.

## Sources
- No live sources available for this run (offline CI mode).
'''
    path.write_text(stub, encoding='utf-8')
    print(f'Created stub issue: {path}')
