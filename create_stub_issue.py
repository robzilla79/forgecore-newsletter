#!/usr/bin/env python3
"""Create a stub issue for today if none exists. Used as CI fallback when Ollama is offline."""
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
Local AI deployment is accelerating as teams look for privacy-preserving, cost-effective alternatives to cloud APIs. Ollama and similar runtimes are at the center of this shift.

## Why It Matters
- Local models eliminate per-token cost and keep sensitive data on-premise.
- Reproducible pipelines matter more than raw model capability for most business tasks.
- Teams building internal tools with open-weight models are compounding faster.

## Highlights
- Llama 3 variants continue to lead open-weight benchmarks for instruction following.
- Claude and GPT-4o remain dominant for long-context reasoning tasks.
- Fine-tuned 7B models now match GPT-3.5 on many vertical-specific workflows.

## Tool of the Week
Ollama -- run Llama, Mistral, Gemma, and others locally with a single CLI command. Ideal for private inference, agent pipelines, and cost control.

## Workflow
Start by pulling a small model and testing it against a task you do manually today:

    ollama pull gemma3:12b
    ollama run gemma3:12b

Measure time saved vs. your current process before expanding the workflow.

## CTA
Pick one local model this week, run it against a real task, and measure the output quality against your current tool.

## Sources
- No live sources available for this run (offline CI mode).
'''
    path.write_text(stub, encoding='utf-8')
    print(f'Created stub issue: {path}')
