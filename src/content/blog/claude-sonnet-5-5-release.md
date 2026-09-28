---
title: 'Claude Sonnet 5.5: a cheaper, faster middle model'
description: Anthropic's Sonnet 5.5 nearly matches Opus 5.5 on benchmarks at up to 30% less cost per task, and it's already in GitHub Copilot.
pubDate: '2026-09-28'
tags:
- news
- anthropic
- claude
- github-copilot
- llm-pricing
author: Andrei Maroz
draft: false
---

## What actually shipped

Sonnet 5.5 is the second model in Anthropic's Claude 5.5 family, following Opus 5.5, which we covered when [its price cuts landed](/blog/claude-opus-5-5-price-cuts). The Decoder reports a jump on Terminal-Bench, a coding-focused benchmark, from 10.3 to 70.6 percent. That's a big swing for what Anthropic still positions as its mid-range model, not its flagship.

[TechCrunch reports](https://techcrunch.com/2026/09/28/anthropic-releases-sonnet-5-5-which-it-calls-a-significantly-cheaper-faster-work-partner) that Anthropic itself is calling this a "significantly cheaper, faster work partner." Nobody's claiming Sonnet 5.5 beats Opus 5.5 outright. The framing backs that up. The implied pitch is that it gets close enough on knowledge-work tasks that the gap stops mattering for a lot of everyday use, while costing less and returning answers faster.

GitHub's own changelog backs that framing up. It describes Sonnet 5.5 as built for "well-scoped everyday work like building features and fixing bugs," which is a precise way of saying this isn't the model you reach for on your hardest architectural problem. It's the one you reach for on the twenty routine tickets you clear in a normal week, and that's most of what a solo builder's coding agent actually does, day to day.

The Decoder also notes that Anthropic has announced Haiku 5.5, which would give it a direct counterpart to each of OpenAI's three GPT-6 models. That model isn't out yet, so the lineup isn't complete. It explains the timing, though: Anthropic is filling out a full price ladder, not just shipping a single upgrade.

---

## Why the benchmark jump matters less than the price cut

A jump from 10.3 to 70.6 percent on Terminal-Bench sounds like the story. It probably isn't, for most readers of this site. Terminal-Bench measures an agent's ability to complete tasks in a command-line environment, which correlates with coding-agent usefulness but isn't a number you'll feel directly unless you're running Sonnet inside an agentic coding tool.

What you will feel, if you're already paying for Claude access through an API or through a tool like GitHub Copilot, is the cost line. Up to 30 percent less per task, on a model that was already the practical choice for most day-to-day coding work, compounds fast if you're running an agent for hours at a stretch.

If you've been tracking [intent debt](/blog/intent-debt-agentic-coding) in your own agentic workflows, a faster, cheaper mid-tier model doesn't fix that problem.

It does lower the cost of the trial-and-error loop that produces it in the first place, which is worth something even if it isn't a fix. Treat the benchmark numbers as evidence that the smaller model closed a real capability gap, and treat the pricing numbers as the part that shows up on your invoice.

---

## What this means for you

If you're already using Claude Sonnet through GitHub Copilot, you don't need to do anything. The upgrade is already live and it's a straightforward better deal: faster responses, lower per-task cost, similar or better output on the kind of well-scoped work Copilot is built around.

If you're picking a model fresh, or you default to Opus 5.5 for routine work out of habit, this is a good moment to check whether Sonnet 5.5 covers what you actually need. Opus still makes sense for the hardest problems: a gnarly refactor, a genuinely ambiguous spec, a bug that's resisted three other models. Everything below that bar is now cheaper to hand to Sonnet, and the gap between the two has visibly narrowed.

This isn't a release that changes how you build. It's a release that changes what building costs.

Worth acting on if you're running an agent for hours a day. Not worth switching tools over if you're not.
