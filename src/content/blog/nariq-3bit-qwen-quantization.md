---
title: NariQ claims a 10 GB file holds a 27B model's full quality
description: Nari Labs says its 3-bit quantization of Qwen3.8-27B keeps near-BF16 scores on benchmarks. Here's what that means for local models.
pubDate: '2026-11-24'
tags:
- news
- local-models
- quantization
- open-source
- llm-tools
author: Andrei Maroz
draft: false
---

**Nari Labs says it shrank a 27B model down to a 10 GB file without the usual quality collapse, and the benchmarks it published back that up through 3-bit, with a real cliff at 2-bit.** If you've been priced out of running a model this size locally, it's worth downloading and testing against your own workload. If you're happy on a hosted API, there's no urgency here.

That's the claim behind NariQ, a set of quantizations of Qwen3.8-27B released by [Nari Labs on Hugging Face](https://huggingface.co/nari-labs/Qwen3.8-27B-NariQ-GGUF).

Quantization is the standard trick for shrinking a model: you store its weights in fewer bits, the file gets smaller, and it runs faster and cheaper, usually at some cost to quality. Go low enough, 3-bit or below, and that cost usually becomes obvious fast. Nari Labs says NariQ is the first 3-bit-or-lower quantization to hold BF16-level performance on long-horizon agentic tasks specifically, which is the category where quantized models have historically fallen apart hardest. Multi-step tool use and extended reasoning chains are exactly where small errors compound, so if that claim holds up under outside testing, it's the more interesting part of this release, not the file size.

## What the numbers actually say

Nari Labs published benchmark comparisons across BF16, 3-bit, 2.5-bit, and 2-bit versions. A few of the figures they report:

- DeepSWE: 39.8 (BF16) versus 41.0 (3-bit), 41.9 (2.5-bit), and 28.6 (2-bit)
- Terminal-Bench 2.1: 62.6 versus 63.8, 60.2, and 52.4
- AIME 25+26: 97.7 versus 98.3, 96.5, and 86.0
- MSGM: 94.0 versus 93.1, 91.8, and 90.6

A couple of things jump out. First, the 3-bit and even 2.5-bit versions aren't just close to BF16 on these tasks, they occasionally score higher, which is a little suspicious since quantization is a lossy process and shouldn't reliably beat the unquantized baseline. Nothing in the source explains the gap, so take the headline parity claim seriously but don't read too much into the exact decimal points.

Second, the real breakdown shows up at 2-bit. That's where every benchmark listed drops meaningfully, DeepSWE falls from 39.8 to 28.6, AIME drops from 97.7 to 86.0. So the honest version of the claim isn't "you can quantize this model infinitely for free." It's "3-bit and maybe 2.5-bit hold up surprisingly well, and then it falls off a cliff at 2-bit." That's still a genuinely useful result if it replicates, just not quite the unconditional win the headline implies.

## Why this matters if you run models yourself

If you've been keeping a local model around for drafting, coding help, or agentic tasks, file size is the thing that decides whether it fits on your machine at all. The source doesn't state a full-precision file size for Qwen3.8-27B, but quantization down to 3-bit or below always represents a substantial cut from full precision, and getting a usable 27B-class model down to roughly 10 GB is the kind of reduction that can be the difference between "needs a dedicated GPU rig" and "runs on a decent laptop or a cheap cloud box."

That matters most for solo builders who want agentic behavior, tool calling, multi-step tasks, without routing every request through a hosted API. If you've read our piece on [why your AI agent needs a sandbox, not your server](/blog/ai-agent-code-execution-sandboxes), you already know that running agents locally raises its own set of control questions. A smaller, cheaper-to-host model that still performs on agentic benchmarks is one more option for builders who'd rather keep that execution loop on infrastructure they control, as an alternative to routing everything through a hosted inference provider like the ones available through [Vercel's AI Gateway](/blog/vercel-ai-gateway-private-inference).

I wouldn't treat this as a reason to rip out a hosted model you're already happy with. Benchmark numbers from the team that built the quantization are not the same as independent, adversarial testing, and "near-BF16 on these five benchmarks" doesn't guarantee the model holds up on whatever narrow, weird task your product actually needs. The gap between official benchmarks and the long tail of real usage is exactly where quantized models tend to surprise you, and nothing in this release speaks to that long tail one way or the other.

The 2-bit cliff is a useful data point on its own: it's a concrete reminder that "quantized" isn't one category, it's a spectrum, and the marketing number for the best tier on the chart is not the number you get if you squeeze the file size further to save another few gigabytes.
