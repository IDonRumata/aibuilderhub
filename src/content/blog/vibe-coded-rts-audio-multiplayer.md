---
title: Simon Willison's vibe coded RTS game shows the real ceiling
description: A developer built a working RTS game with audio-based multiplayer using Claude. Here's what it actually reveals about vibe coding's limits today.
pubDate: '2026-10-21'
tags:
- news
- vibe-coding
- claude
- game-dev
- ai-tools
author: Andrei Maroz
draft: false
---

## TL;DR

Simon Willison built a Command & Conquer style real-time strategy game almost entirely by prompting Claude, down to multiplayer that syncs game state between nearby devices using audio. **It's a genuinely impressive result, but it's also close to the best-case scenario for vibe coding**: a closed system with immediate feedback and no production data or paying users to break. It doesn't tell you vibe coding is ready for running a real business, and nothing in Willison's own writeup claims that either.

---

The game is called Battle Drones, and [Willison's writeup](https://simonwillison.net/2026/Oct/20/battledrones) walks through five versions: an initial prototype, a version with full sprites, one with varied terrain, a "fun update," and the build he has now. By his own account, he's "somewhat embarrassed to admit" that the fun version came from telling Claude to "Make it a LOT more fun" and having that actually work. My read on that: it suggests the gain came from iterating and steering in plain language, not from some clever prompt engineering trick.

The multiplayer detail is the one worth sitting with. It supports play between nearby devices using audio to synchronize game state. Willison doesn't spell out the networking details beyond that, so it's worth not reading more into the mechanism than what he's actually said. Either way, it's a notable feature to land inside a project built mostly through conversational prompting.

## What actually happened here

Willison is not a beginner. He's a well-known developer who writes carefully about what LLMs can and can't do for code. So when he says this is, unlike his previous experiments, actually fun to play, that's a meaningful data point. It's his own comparison against his own prior work, and by that comparison this one clears a bar the others didn't.

Syncing game state over audio between devices is a hard problem to get working at all, let alone inside a vibe-coded side project. Willison doesn't go into the technical details of how it holds up under real-world conditions. Take that as my inference about the difficulty, not something his post measures.

## Why this matters beyond one game

A vibe-coded game is close to the ideal case for these tools. It's a closed system. The rules are self-contained, the feedback loop is immediate, does it play well or doesn't it, and there's no legacy codebase, no other team's conventions, and no production data to break. That's a very different environment from maintaining a real SaaS product with paying customers.

I don't think this means vibe coding is suddenly ready for building and running a business end to end. Nothing in Willison's post claims that.

What it does show is that for greenfield, well-bounded projects, iterating purely through natural-language instructions can get you to something polished and even technically ambitious, not just a rough demo.

The fun update is the detail I keep coming back to. "Make it a lot more fun" is about as vague as a prompt gets. That it worked suggests the model had enough context about what makes a strategy game engaging, things like pacing, feedback, and tension, that a vague steer in the right direction was enough to get a usable result. That's encouraging for builders who don't have a precise technical vocabulary for what they want. It's also a reminder that these tools reward iteration over one-shot perfection.

Willison went through five named versions to get there: an initial prototype, full sprites, varied terrain, the fun update, and the current build. He didn't get here on the first prompt.

He got here on the fifth.

## What I'd actually take from this

If you're a solo builder with an idea for a small, self-contained tool or game, this is a decent signal that the gap between "idea" and "playable prototype" has gotten smaller. That's especially true for the kind of project where the rules live entirely in the code and don't depend on messy real-world integrations.

If you've been putting off a side project because you don't code, the lesson from Willison's process isn't "write the perfect prompt." It's "ship a rough version, play it, and tell the model what's wrong with it in plain language." That loop, repeated across five named versions, prototype, sprites, terrain, fun update, current build, is what got him to something actually fun to play.

The gap this doesn't close is the one that matters for anyone building a product, not a game. There's no mention here of ongoing maintenance, no error handling for real users doing unexpected things, no integration with a payment processor or a flaky third-party API, and no paying customers who'll notice when something breaks. Vibe coding a fun prototype and vibe coding something you depend on for income are different exercises, and this post doesn't settle that question either way.

If you want a broader sense of where vibe coding creates problems once a project grows past the prototype stage, [this site's piece on intent debt](/blog/intent-debt-agentic-coding) is worth reading before you assume a game-building win generalizes to your own project.
