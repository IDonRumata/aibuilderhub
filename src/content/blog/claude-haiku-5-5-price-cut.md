---
title: 'Claude Haiku 5.5: a big price cut, with an asterisk'
description: Anthropic cut Haiku's price to match GPT-6 Luna and boosted benchmarks sharply, but a new tokenizer quietly eats into the savings.
pubDate: '2026-10-09'
tags:
- news
- anthropic
- claude
- ai-pricing
- llm
author: Andrei Maroz
draft: false
---

Anthropic dropped Claude Haiku 5.5, and the headline number is real: input and output pricing now matches OpenAI's GPT-6 Luna at $0.10 per million input tokens and $0.50 per million output tokens, up to 100,000 tokens, according to [Simon Willison's writeup](https://simonwillison.net/2026/Oct/7/claude-haiku-5-5). That's a steep drop from the previous Haiku 4.5, priced at $1/$5 per million tokens. Willison calls that "relatively expensive even back then", and notes it was a full 10x the price of GPT-6 Luna.

If you've been paying for Haiku calls in a product, this is the kind of cut that actually changes your monthly bill, not just a marketing number.

## What actually improved

The benchmark jump is the other half of the story. [The Decoder reports](https://the-decoder.com/claude-haiku-5-5-arrives-with-massive-price-cuts-proving-the-ai-pricing-arms-race-is-far-from-over) Haiku 5.5 went from 15.7 percent to 72.4 percent on OSWorld, a test of how well a model handles computer-use tasks like operating interfaces and completing multi-step actions on a screen. That's not an incremental bump.

It's the kind of jump that can move a model from "not reliable enough to automate this" to "worth trying as the default."

A newsletter roundup covering the release headlined it as Haiku 5.5 being "better than GPT-6 Luna at the same pricing." That's a framing, not a benchmark result I can point to directly, so take it as one observer's read rather than confirmed comparative testing. What is confirmed is the OSWorld jump and the price match. My own take: pairing a steep price cut with a steep capability jump on the same release looks like Anthropic positioning Haiku directly against Luna, but that's my inference about intent, not something any source states outright.

Worth noting too: Willison points out the pricing has a ceiling. Beyond 100,000 tokens, Haiku's rate jumps 5x to $0.50/$2.50. Luna also gets more expensive past a threshold (272,000 tokens), but only rises to $0.20/$0.75. If your workloads regularly run long context, that asymmetry matters more than the headline price match at the low end.

---

## The catch in the pricing

Here's where it gets less clean. The Decoder notes Haiku 5.5 ships with a new tokenizer, and that tokenizer consumes more tokens per task than the old one did. So the sticker price dropped by as much as 90 percent, but the actual cost of running a given task doesn't fall by that same amount, because you're burning more tokens to do the same work.

I don't think this is a trick, exactly. Tokenizers change between model generations for real architectural reasons, and Anthropic isn't hiding the tradeoff. But it does mean the number you should actually budget around isn't the per-token price cut. It's the per-task cost, and nobody outside Anthropic has published that comparison yet.

Until someone runs the same batch of real tasks through both Haiku versions and reports total tokens burned, treat the 90 percent figure as a ceiling on the savings, not a guarantee of them.

As we noted when [Opus 5.5 cut prices across Anthropic's lineup](/blog/claude-opus-5-5-price-cuts), a sticker price is easy to announce and hard to verify without running your own workload through it. The same caution applies here.

## What this means for you

If you're already building on Haiku, the move is simple: swap the model string, run your actual production prompts through both versions, and compare total token counts, not just the quoted rate. A price cut that nets out to meaningfully less than 90 percent once the new tokenizer is accounted for can still be a good deal, but it's a different deal than the press release implies.

If you're choosing between Haiku 5.5 and GPT-6 Luna for a new project, the benchmark gap on OSWorld is the more interesting signal than the matched pricing. Two models at the same price are only equivalent if they perform the same, and a jump from 15.7 to 72.4 percent on a computer-use benchmark suggests Haiku closed a real capability gap, not just a pricing one.

This also isn't happening in isolation. Anthropic has also cut [Sonnet's price](/blog/claude-sonnet-5-5-release), and together the two cuts look like a lineup-wide repositioning against OpenAI's cheaper models, not a one-off discount on the smallest model. If you're budgeting AI costs for a solo product, it's worth checking whether a model one tier up now costs what you used to pay for the bottom tier.

Prices are falling across the board, and fast enough that a pricing page from an older model generation can already be out of date. The move for a solo builder isn't to assume the cut is as big as advertised. It's to re-run your own numbers before you re-budget anything.
