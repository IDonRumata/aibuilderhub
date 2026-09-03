---
title: 'Claude Fable 5.1: cheaper agentic coding, check your bill'
description: Anthropic's Fable 5.1 cuts cache pricing up to 75% and agentic task pricing up to 45%. Here's what that actually means for solo builders using Claude.
pubDate: '2026-09-03'
tags:
- news
- claude
- ai-coding-tools
- pricing
- llm
author: Andrei Maroz
draft: false
---

## TL;DR

Anthropic shipped Claude Fable 5.1 and Claude Mythos 5.1, and the headline isn't really the benchmarks. It's the price. Anthropic says Fable 5.1 costs around 25% less than Fable 5 for typical use and up to 45% less for complex agentic work, per [The Verge](https://theverge.com/ai-artificial-intelligence/987830/anthropic-claude-fable-mythos-5-1). If you're already building on Claude models through an agent framework or a tool like [Cursor](/blog/cursor-review-2026) or [Windsurf](/blog/windsurf-review-2026), pull up your most recent API invoice and check the cache-read line item specifically. That's where this change lands hardest, not on your subscription price. If you're not on Claude at all, this isn't a reason to switch on its own.

---

## What actually changed

Anthropic's announcement leans hard on one number: a 52.6% score on Terminal-Bench-Science 0.1, a newer benchmark for scientific and long-running problem-solving tasks. That figure is Anthropic's own self-reported result, relayed by [Simon Willison's write-up](https://simonwillison.net/2026/Sep/1/claude-fable-5-1), not an independently verified score. It's up from 24.7% for Fable 5, and it beats Opus 5's 29.0% and GPT-5.6 Sol's 22.4% on the same test. Willison also notes that the rest of the benchmark improvements are modest by comparison, nothing close to that science-task jump.

I'd treat that gap with some suspicion. A brand-new benchmark that a model happens to crush right after launch is the kind of thing that's easy to over-index on.

It might reflect a genuine capability improvement in long-horizon reasoning, or it might reflect the benchmark being close to whatever Anthropic optimized for internally. Nothing in the sources tells me which, so that's a guess on my part, not a claim.

The pricing side is more concrete and, for a solo builder, more useful. Latent Space's roundup describes a 75% cut to cache pricing for Fable 5.1, alongside a 70% increase in allowed output tokens per response. Cache pricing, as I understand it, is what you're charged for keeping context, a codebase, a set of docs, a long conversation, loaded between requests instead of re-sending and reprocessing it from scratch every time. None of the sources spell that mechanism out explicitly, so take that as my own explanation of the term, not a quote from Anthropic.

My own read on why this matters: a 75% cut to cache pricing is a bigger deal than it sounds, because I'd expect cache reads to make up a large share of the cost in any agent loop that keeps re-reading the same context on every step. Picture a coding agent that rereads your repo structure on each turn, or a research agent that keeps a long document loaded while it works through a task. Those are illustrative examples of mine, not scenarios described in any of the sources, but they're the kind of workload where this cut would actually show up in your bill. Put the cache-price cut together with the output-token bump and the pitch is: run longer agent sessions, touch more context per step, and pay less doing it than you did on Fable 5.

One caveat on scope: the pricing figures above, the 25-45% headline cut and the 75% cache-price cut, are reported for Fable 5.1 only. None of the sources break out separate pricing numbers for Mythos 5.1, so don't assume the same discount applies there without checking your own invoice.

---

## What this means for you

If you're paying for Claude access through the API, directly or through a wrapper tool, this is worth ten minutes of your time: open your most recent invoice or usage dashboard and look specifically at the cache-read line item, not the total. That's the number that should drop the most under the new pricing. If it doesn't, something in your setup, a proxy, a fixed-rate plan, an older model pin, isn't passing the discount through. The 70% output-token increase is a limit change, not a price cut, so don't expect it to show up as savings on its own.

If you're on a flat-rate product like a Claude Pro subscription or a tool that bundles model costs into a flat monthly fee, none of this touches you directly. The pricing change is at the API layer.

Your bill won't move until the tool you're using decides to pass the savings on, and there's no source here saying any of them have.

If you're evaluating Claude against GPT or Gemini models for a new agent project, the Terminal-Bench-Science number is interesting but I wouldn't build a decision around a new benchmark with one data point. The pricing change is the more durable fact here. Weigh it the way you'd weigh any other input cost: real, but not a reason to rearchitect anything you've already shipped.

Either way, nothing about this release changes what tool you should be coding in day to day. It changes what that tool costs you to run underneath, and only if you're already deep enough into agentic workflows for cache pricing to be a meaningful chunk of your spend.
