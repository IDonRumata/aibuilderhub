---
title: Vercel's AI Gateway can now call your own private models
description: Vercel AI Gateway adds Private Inference, letting teams route self-hosted or fine-tuned models through the same auth, SDKs, and logs as catalog models.
pubDate: '2026-11-17'
tags:
- news
- vercel
- ai-gateway
- infrastructure
- self-hosted-models
author: Andrei Maroz
draft: false
---

## TL;DR

Vercel's AI Gateway now lets you plug in your own model endpoints, not just the catalog of hosted models it already supports. Per the [changelog post](https://vercel.com/changelog/ai-gateway-now-supports-private-inference), this means a fine-tuned, self-hosted, or prerelease model can run through the same authentication, SDKs, APIs, and logging as everything else in the Gateway. For most solo builders this won't matter much. For anyone running a custom model alongside GPT, Claude, or Gemini calls, it closes a real gap.

---

## What actually changed

Until now, if you wanted to call a model you'd fine-tuned or hosted yourself, you had to manage it separately: its own API key, its own client code, its own logging setup, sitting next to whatever you already had wired up for catalog models through the Gateway. Vercel's post describes this as the problem Private Inference solves, by putting private endpoints behind the same Chat Completions, Responses, or Messages interface the catalog models use.

The practical upshot, according to the announcement, is that switching between a private model and a catalog one becomes a matter of changing the model ID, not rewriting integration code. The Gateway translates each request into whatever format your endpoint expects.

That's the part worth paying attention to. The Gateway acts as a translation layer, so your app code doesn't need to know or care whether it's talking to OpenAI's API or your own inference server.

This builds on groundwork Vercel laid with the Gateway's observability features, which I covered when [Vercel AI Gateway added session affinity and spend logs](/blog/vercel-ai-gateway-session-affinity-logs). The pattern with Vercel's Gateway has been consistent: first get every model under one roof for cost and usage tracking, then extend that roof to cover more kinds of models. Private Inference is the second move. If you've already seen Vercel add model after model to its catalog, this is the same consolidation instinct applied to models nobody else is hosting for you.

---

## Who this is actually for

The framing in Vercel's own post leans enterprise: fine-tuned models, prerelease models, self-hosted deployments. That's not accidental. A solo builder running a side project almost never has a private model to call in the first place. If your stack is "call GPT-5 for this, Claude for that," the catalog already covers you, and Private Inference adds nothing.

Where it starts to matter is the smaller set of builders who've done real fine-tuning work, maybe on an open-weights model, and have been running it on their own infrastructure because there was no clean way to fold it into the same billing and logging surface as everything else.

If that's you, this removes a genuine piece of busywork: maintaining a second set of keys, a second client, and a second log stream just because one model in your stack isn't hosted by a big provider.

Teams running prerelease models from smaller labs could also benefit, since those models often show up outside the major catalogs well before landing in them, if they ever do.

Nothing in the source confirms that's the primary use case. It's my own inference from the feature's framing, so treat it as a guess rather than something Vercel stated.

---

## The catch

The obvious limitation: you need a model endpoint of your own for this to do anything. No amount of Gateway integration gives you a private model if you don't already have one running somewhere. This is infrastructure plumbing, not a new capability you can point at a chatbot and expect magic from.

The other thing worth naming is lock-in risk, though it's a mild version of it. The more of your model traffic, private and catalog alike, routes through one vendor's Gateway, the more that vendor's uptime and pricing decisions become your problem.

Vercel's pitch is unification: one auth layer, one API shape, one place to look at logs. That's a real convenience, and I don't think it's a trap exactly, since the underlying model calls still point at your own endpoint.

But it's worth noticing that the translation layer sits in Vercel's infrastructure, not yours.

That's the tradeoff in one sentence.

---

## What to do with this

If you don't have a self-hosted or fine-tuned model, ignore this entirely. Nothing changes for you.

If you do, check whether folding it into the Gateway actually saves you the maintenance it claims to, versus adding a new dependency on top of the one you already have. And watch for the next model category Vercel folds into the Gateway: that's the trend this announcement is actually part of, even if Private Inference itself doesn't touch your stack yet.
