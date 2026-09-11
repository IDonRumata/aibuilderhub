---
title: 'OpenAI''s Agents API lands on Vercel: what solo builders get'
description: OpenAI's Agents API now deploys on Vercel with sandboxed execution and persistent sessions. Here's what that actually means if you're building alone.
pubDate: '2026-09-11'
tags:
- news
- openai
- vercel
- ai-agents
- no-code
author: Andrei Maroz
draft: false
---

## TL;DR

OpenAI shipped an [Agents API](https://developers.openai.com/api/docs/guides/agents-api/overview) that handles the agent loop and session state for you, and Vercel has wired it into their platform so you can deploy long-running, tool-using agents without babysitting the infrastructure yourself. If you've ever tried to build an agent that needs to run code, remember what it did five minutes ago, and pick back up after your app cold-starts, this removes most of the plumbing. It's not a new model and it's not a new IDE. It's the missing layer between "I have an agent idea" and "I have a thing running in production."

---

## What actually shipped

The Agents API is OpenAI's own answer to a problem every agent builder eventually hits: keeping track of what the agent has done, what tools it's called, and what state it needs to pick back up mid-task. Per the [Vercel changelog](https://vercel.com/changelog/build-with-openai-agents-api-on-vercel), OpenAI now manages that agent loop and session state directly, while Vercel handles the hosting side and connects each session to Vercel Sandbox for actual code execution and file access.

Vercel's changelog lists five things the integration provides: an OpenAI-managed agent loop and session state, sandbox creation and reconnection handled through signed OpenAI webhooks and Vercel Queues, an isolated execution environment for every agent session, a persistent workspace that retains files across follow-up instructions, and a scale-to-zero architecture. Those last two are Vercel's own framing, not something I've verified against a running app, but they're stated plainly in the changelog rather than implied.

That's the piece worth paying attention to. Wiring an LLM to call itself in a loop is well-understood at this point. Plenty of people have done it.

Session persistence, sandboxing, and reconnecting cleanly when something drops mid-task are what actually take the time. The sources don't say this outright, but it tracks with how every agent build I've seen described actually goes: that's the part where a solo builder either gives up or spends weeks reinventing infrastructure that a bigger team would just build in-house.

---

## Why this matters more than it looks like it does

If you've built anything agentic yourself, you know the annoying part isn't prompting the model. It's everything around it: where does the agent's memory live between requests, what happens if the sandbox dies halfway through a file edit, how do you avoid paying for compute the agent isn't using.

Vercel's integration answers all three by delegating to infrastructure that already exists. You're not writing a queue system. You're not writing your own webhook retry logic.

That's the part I'd actually pay attention to if I were building an agent product solo, because it's exactly the kind of work that eats a month and produces nothing a user will ever see.

I don't think this changes what agents can do. The reasoning and tool use is still whatever the underlying model supports.

What it changes is who can ship an agent-based product without a backend team. In my opinion, that's a similar kind of shift to what happened when tools like Lovable and Bolt cut the UI scaffolding between an idea and a running app. The two aren't a perfect match, though: one collapses front-end setup, this one collapses backend agent infrastructure. See how that first shift played out in [our head-to-head build of both](/blog/lovable-vs-bolt-2026).

---

## The catch nobody's saying out loud

Here's my honest read: this is a Vercel-plus-OpenAI stack. You're now dependent on two vendors' infrastructure decisions instead of one. Neither announcement I've seen spells out exact rates for sandbox time, queue usage, or the agent sessions themselves, so there's no per-hour or per-session number here to point to.

Scale-to-zero is nice in theory, but the parts of an agent stack that actually blow up your bill are usually the parts you don't notice until the invoice arrives.

Our [Replit review](/blog/replit-review-2026) flagged the same shape of problem: unpredictable usage-based pricing that's hard to estimate until you're already committed. I haven't tested this specific OpenAI-Vercel stack's billing, so I can't say it'll play out the same way. But it's the pattern I'd watch for, and I'd guess it shows up any time a platform meters compute per session rather than charging a flat rate.

So wait on the pricing details before you commit a real product to this stack. The plumbing problem is genuinely solved here, which is worth something. Just don't sign up for scale-to-zero infrastructure without first finding out what it costs when your agent actually scales.
