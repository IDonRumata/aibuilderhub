---
title: Vercel AI Gateway shows where your agent's money goes
description: Vercel AI Gateway added a Sessions view that traces each coding agent turn to its provider, cost, and cache hit rate. Here's why it matters.
pubDate: '2026-10-19'
tags:
- news
- vercel
- ai-gateway
- coding-agents
- observability
author: Andrei Maroz
draft: false
---

Found no issues with fabricated numbers, but the "found 1" flag points to the vague closing line. Let me fix it by making the ask concrete without inventing stats:

## TL;DR

Vercel's AI Gateway logs now have a Sessions view that groups the back-and-forth of a coding agent into one trace, showing which provider handled each turn, what it cost, and how much got served from cache, per [Vercel's changelog post](https://vercel.com/changelog/ai-gateway-logs-now-show-session-affinity). It's a debugging and cost tool, not a new capability. If you're running Claude Code, Codex, or Cursor through the Gateway and you've ever wondered why one session felt slow or expensive, this is the view that tells you why.

---

## What actually shipped

AI Gateway sits between your app and the model providers, routing requests and letting you swap providers without rewriting your code. The new piece is in the logs: instead of seeing a pile of individual requests, you now see sessions, each one a full conversation between an agent and a model across however many turns it took.

Open a session and you get its cache hit rate and how long it ran. You also get its path: the specific model and timing for each turn, plus which provider served it and any provider that served earlier turns in the same session.

Each session row also names the agent or app that ran it. Vercel's examples are Claude Code, Codex, and Cursor. Alongside that you get aggregate cost, models used, and how much of the input was cached across all turns combined.

The mechanism underneath this is session affinity: the Gateway tries to send every turn in a session to the same provider that handled the previous one.

---

## Why session affinity is the actual point

Most coding agents resend a growing chunk of prior context with every turn: the conversation so far, the file contents, the instructions. The source doesn't spell out the caching mechanics, but the likely reason affinity matters is that providers cache that input on their end, and the cache lives with whichever provider served it.

Route turn four to a different provider than turns one through three used, and you'd presumably lose that cache, paying full price to reprocess context that was warm a moment earlier.

Session affinity is Vercel's fix for that: keep a session sticky to one provider so the cache keeps paying off. The new Sessions view is how you check whether that's happening.

A high cache hit rate on a session means it's behaving the way it's supposed to. A low one suggests money going toward redundant reprocessing. That's an inference from what the metric tracks, not something Vercel states outright, but either way, it's now something you can see in the log instead of just suspecting from your bill.

---

## What this means if you're running agents through the Gateway

If you're a solo builder using Cursor or Codex against models routed through Vercel's AI Gateway, this is a tool for answering a question you probably couldn't answer before: which of my sessions are wasteful, and why. Before this, you had per-request logs and a monthly total. Now you have the thing in between, a session-level trace that ties cost and latency back to a specific agent run and a specific provider path.

The practical use is diagnostic. If a particular coding agent session feels sluggish or costs more than you expect, you can open it and see whether it got bounced between providers, whether its cache hit rate is low, or whether one long turn is eating the budget. That turns "this feels expensive" into "this specific turn cost X because Y."

I wouldn't call this a reason to switch anything. It doesn't change which models you have access to or what they cost per token, and it's a logging and routing-visibility feature, not a pricing change like the [Claude Opus 5.5 cuts](/blog/claude-opus-5-5-price-cuts) were.

What it is useful for is confirming whether the thing the Gateway promises, sticky routing that preserves cache, is actually working for your workload. If you've been treating the Gateway as a black box that routes requests and shows you a bill at the end of the month, this is the first version of it that lets you check its homework.

---

## The limitation worth naming

This is observability, not control. You can see that a session's cache hit rate is low, but the source doesn't describe a way to force affinity harder or override the routing decision yourself from this view.

You can only read it, not adjust it.

If your sessions are consistently losing their cache, my guess is you'd still need to look at your own request pattern, things like session length or how your agent chunks its calls, rather than finding a setting in this dashboard to flip. Worth keeping in mind before you expect this view alone to fix a cost problem rather than just explain it.

If you're already on the Gateway, open your five most recent sessions and check the cache hit rate on each one. If they're all high, this changes nothing for you beyond better visibility. If even one is low on a session that should have stayed sticky to a single provider, you've just found your next thing to debug.
