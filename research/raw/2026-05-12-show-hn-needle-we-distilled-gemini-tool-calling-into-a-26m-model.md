# Show HN: Needle: We Distilled Gemini Tool Calling into a 26M Model

- Source: Hacker News Show HN
- Published: Tue, 12 May 2026 18:03:11 +0000
- URL: https://github.com/cactus-compute/needle
- Domain: github.com
- Tags: builders, tools, indie

## Feed summary

Hey HN, Henry here from Cactus. We open-sourced Needle, a 26M parameter function-calling (tool use) model. It runs at 6000 tok/s prefill and 1200 tok/s decode on consumer devices.We were always frustrated by the little effort made towards building agentic models that run on budget phones, so we conducted investigations that led to an observation: agentic experiences are built upon tool calling, and massive models are overkill for it. Tool calling is fundamentally retrieval-and-assembly (match query to tool name, extract argument values, emit JSON), not reasoning. Cross-attention is the right primitive for this, and FFN parameters are wasted at this scale.Simple Attention Networks: the entire model is just attention and gating, no MLPs anywhere. Needle is an experimental run for single-shot function calling for consumer devices (phones, watches, glasses...).Training:
- Pretrained on 200B tokens across 16 TPU v6e (27 hours)
- Post-trained on 2B tokens of synthesized function-calling data (45 minutes)
- Dataset synthesized via Gemini with 15 tool categories (timers, messaging, navigation, smart home, etc.)You can test it right now and finetune on your Mac/PC: https://github.com/cactus-compute/needleThe full writeup on the architecture is here: https://github.com/cactus-compute/needle/blob/main/docs/simp...We found that the "no FFN" finding generalizes beyond function calling to an

## Extracted article text

We distilled Gemini 3.1 into a 26m parameter "Simple Attention Network" that you can even finetune locally on your Mac/PC. In production, Needle runs on Cactus at 6000 toks/sec prefill and 1200 decode speed. Weights are fully open on Cactus-Compute/needle, as well as the dataset generation.
d=512, 8H/4KV, BPE=8192
┌──────────────┐
│ Tool Call │
└──────┬───────┘
┌┴──────────┐
│ Softmax │
└─────┬─────┘
┌─────┴─────┐
│ Linear (T)│ ← tied
└─────┬─────┘
┌─────┴─────┐
│ ZCRMSNorm │
└─────┬─────┘
┌────────┴────────┐
│ Decoder x 8 │
│┌───────────────┐│
││ ZCRMSNorm ││
││ Masked Self ││
││ Attn + RoPE ││
││ Gated Residual││
│├───────────────┤│
┌──────────────┐ ││ ZCRMSNorm ││
│ Encoder x 12 │──────────────────────▶Cross Attn ││
│ │ ││ Gated Residual││
│ ┌──────────┐ │ │└───────────────┘│
│ │ZCRMSNorm │ │ └────────┬────────┘
│ │Self Attn │ │ ┌─────┴─────┐
│ │ GQA+RoPE │ │ │ Embedding │ ← shared
│ │Gated Res │ │ └─────┬─────┘
│ │ │ │ ┌───────┴───────-┐
│ │ (no FFN) │ │ │[EOS]<tool_call>│
│ └──────────┘ │ │ + answer │
│ │ └───────────────-┘
└──────┬───────┘
│
┌────┴──────┐
│ Embedding │
└────┬──────┘
│
┌────┴──────┐
│ Text │
│ query │
└───────────┘
- Pretrained on 16 TPU v6e for 200B tokens (27hrs).
- Post-trained on 2B tokens of single-shot function call dataset (45mins).
Needle is an experimental run for Simple Attention Networks, geared at redefining tiny AI for consumer devies (phones, watches, glasses...). So while it beats FunctionGemma-270m, Qwen-0.6B, Graninte-350m, LFM2.5-350m on single-shot function call for personal AI, Those model are have more scope/capacity and excel in conversational settings. Also, small models can be finicky. Please use the UI in the next section to test on your own tools, and finetune accordingly, at the click of a button.
git clone https://github.com/cactus-compute/needle.git
cd needle && source ./setup
needle playground
Opens a web UI at http://127.0.0.1:7860 where you can test and finetune on your own tools. Weights are auto-downloaded.
from needle import SimpleAttentionNetwork, load_checkpoint, generate, get_tokenizer
params, config = load_checkpoint("checkpoints/needle.pkl")
model = SimpleAttentionNetwork(config)
tokenizer = get_tokenizer()
result = generate(
model, params, tokenizer,
query="What's the weather in San Francisco?",
tools='[{"name":"get_weather","parameters":{"location":"string"}}]',
stream=False,
)
print(result)
# [{"name":"get_weather","arguments":{"location":"San Francisco"}}]
# Playground (generates data via Gemini, trains, evaluates, bundles result)
needle playground
# CLI (auto-downloads weights if not local)
needle finetune data.jsonl
needle playground Test and finetune via web UI
needle finetune <data.jsonl> Finetune on your own data
needle run --query "..." --tools Single inference
needle train Full training run
needle pretrain Pretrain on PleIAs/SYNTH
needle eval --checkpoint <path> Evaluate a checkpoint
needle tokenize Tokenize dataset
needle generate-data Synthesize training data via Gemini
needle tpu <action> TPU management (see docs/tpu.md)
@misc{ndubuaku2026needle,
title={Needle},
author={Henry Ndubuaku, Jakub Mroz, Karen Mosoyan, Roman Shemet, Parkirat Sandhu, Satyajit Kumar, Noah Cylich, Justin H. Lee},
year={2026},
url={https://github.com/cactus-compute/needle}
}
