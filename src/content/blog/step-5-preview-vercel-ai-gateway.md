---
title: StepFun's Step 5 Preview lands on Vercel's AI Gateway
description: StepFun's Step 5 Preview model is now on Vercel's AI Gateway, with a 1M-token context window aimed at coding agents. Here's what that means for you.
pubDate: '2026-10-11'
tags:
- news
- ai-gateway
- coding-agents
- vercel
- llm
author: Andrei Maroz
draft: false
---

## TL;DR

StepFun's Step 5 Preview is now reachable through [Vercel's AI Gateway](https://vercel.com/changelog/step-5-preview-now-available-on-ai-gateway), and if you're already using the Gateway, trying it costs you a one-line config change, not a new integration. **It's worth a test run against whatever you're using now, but there's no pricing, no benchmarks, and no rate-limit info in the announcement, so don't make it your default for anything real until that shows up.**

---

## What Step 5 Preview actually is

Step 5 Preview is StepFun's flagship model, and per Vercel's announcement it's built for agentic coding, professional knowledge work, and financial analysis. That's a wide net. The listed use cases span building and debugging apps, research, and analytical reports, which reads less like a specialized coding model and more like a generalist aimed at knowledge workers who happen to also write code.

The headline spec is a 1M-token context window, and it takes both text and image input. Per Vercel, that means you can hand it a large codebase, a stack of documents, or screenshots and charts in a single request. For solo builders, the practical version of that is simple: you can paste in way more of your actual project before the model starts losing track of what it's looking at. Large context windows aren't new, but a million tokens of mixed text and image is still enough to matter if you've been chunking files to fit smaller windows.

Getting to it is straightforward. You call it with `stepfun/step-5-preview` as the model name through the Gateway, and for coding agents like Claude Code, Codex, or Cursor, Vercel says you install the latest CLI, run the setup flow, and select Step 5 from there. If you're already on the Gateway, there's no separate API key to manage and no new billing relationship with StepFun to set up directly.

## Why this is a Gateway story, not just a model story

The more interesting part of this isn't Step 5 itself. It's what it says about the Gateway as a strategy. Vercel keeps adding models from different labs behind one interface, including [GPT 6 Astra](/blog/gpt-6-astra-vercel-ai-gateway) and the various Claude releases, and now StepFun. Each arrival follows the same shape: a new model name you can drop into an existing config without touching your app's integration code.

That matters for you if you're building solo, because it means you're not locked into evaluating one model in isolation. You can swap `stepfun/step-5-preview` for whatever you were using before, run the same prompts, and see what changes, all without rewiring your app's integration layer. The Gateway is doing the work of normalizing the interface so the model becomes a configuration choice instead of an engineering decision.

That convenience is also the tradeoff. You're trusting Vercel's routing on top of whatever StepFun charges underneath, and the pricing for either side isn't in this announcement.

There's also a quieter cost to this pattern: attention. Every time a new model shows up in the Gateway, it's tempting to treat it as homework, to go try it, compare it, figure out if it's better. If you did that for every model drop covered here, you'd spend more time swapping backends than building your product. The Gateway lowers the cost of trying a model, but it doesn't lower the cost of your time deciding whether trying it was worth it.

## What's missing from this announcement

Check pricing first, before you make Step 5 your default anywhere real. A 1M-token context window is only a good deal if the per-token cost doesn't eat whatever time you saved.

There's also no benchmark comparison against GPT, Claude, or Gemini on coding tasks specifically, so you have no basis here for judging whether it's actually better at the agentic coding work it's pitched for. You only know that it exists and is reachable. And there's no mention of rate limits, or whether the preview label means it's subject to change on a short timeline. That matters if you're building something that depends on it staying available in its current form.

None of that means skip it. It means treat "now available" as the start of the evaluation, not the end of it.

## What to actually do with this

If you're already on Vercel's AI Gateway, swapping in `stepfun/step-5-preview` costs you nothing but a config change, so there's no reason not to run your usual test prompts against it and see how it compares to whatever you're using now. If you're not on the Gateway, this alone isn't a reason to switch; the value is in the routing layer, not any single model behind it. And if you're mid-build on something that depends on a specific model's pricing or availability staying stable, wait for StepFun or Vercel to publish numbers before you wire Step 5 in as anything more than an experiment.
