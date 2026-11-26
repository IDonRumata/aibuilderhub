---
title: Your AI coding agent is only as good as its context file
description: A new open-source tool checks your CLAUDE.md or .cursorrules for the stale, ambiguous rules that quietly cause bad agent behavior.
pubDate: '2026-11-26'
tags:
- news
- ai-coding-agents
- claude-code
- cursor
- developer-tools
author: Andrei Maroz
draft: false
---

## TL;DR

Most debugging sessions for a misbehaving AI coding agent start with the wrong question. You check the model, the prompt, maybe the temperature setting. A developer writing on dev.to argues the real culprit is usually sitting in plain sight: your [CLAUDE.md, AGENTS.md, or .cursorrules file](https://dev.to/vachi/your-agent-is-only-as-good-as-its-context-4dl). If that file is ambiguous, stale, bloated, or unsafe, the agent doesn't stop and ask for clarification. It guesses, confidently, and you pay the cost later when you notice the guess was wrong. To address this, the author built an open-source tool called good-context, described as a Claude Code skill that audits your context file for exactly these problems.

---

## What the post actually argues

The core claim: a flagship model fed a bad context file will still produce bad output, because the model is doing what it was told, not what you meant. The piece names three specific failure modes an agent shows when its instructions are broken rather than when the model is weak. It ignores a rule it should have followed. It hallucinates a command that doesn't exist. It gets stuck in a loop trying to fix a failing test.

In each case, the agent doesn't surface the ambiguity. It fills the gap with a plausible-sounding guess and keeps going, silently.

That's the part worth sitting with. An agent that errors loudly is annoying but cheap to fix. An agent that guesses plausibly and silently is expensive, because you don't find out until something downstream breaks, and by then you've lost the thread of why.

The tool itself, per the author's own description, is pitched as a Claude Code skill that scans your context file for ambiguity, staleness, bloat, and unsafe instructions. That's the author's framing of their own tool, not an independent audit of what it catches.

I haven't run it. The source doesn't include benchmarks or before-and-after numbers, no pass rate, no count of issues caught on a sample file, nothing you could use to size the claim. So I can't tell you how much it actually catches versus how much is left to manual review. Treat it as a first pass, not a guarantee.

---

## Why this matters if you're running an agent on your own project

If you've been iterating on a CLAUDE.md or .cursorrules file for months, there's a good chance it's picked up at least one of the things that make instructions unreliable. A rule that made sense for a feature you ripped out. A rule that contradicts one you added later. A rule so long the agent effectively skims it. None of that shows up as an error message. It shows up as the agent doing something slightly wrong in a way that looks like a model problem.

A stale context file is intent debt made literal. This connects directly to something I've been meaning to put a name to: the gap between what you intended an agent to do and what its actual working instructions tell it to do, which the site has covered before as [intent debt](/blog/intent-debt-agentic-coding). You wrote the rule for a past version of the project, the project moved on, and the rule is still sitting there, confidently wrong.

It's also worth connecting to the broader pattern of agents grading their own work. [Claude Code's /goal feature](/blog/claude-code-goal-judge-false-positives) has the same shape of problem: an agent that's supposed to self-check can only self-check against the instructions it was given, and unclear instructions produce an unreliable self-check.

A context-file auditor doesn't fix that on its own, but it's attacking the right layer. Bad instructions in, bad judgment out, no matter how good the judge is.

---

## What I'd actually do about this

My honest take: you don't need to install this tool to get the benefit. The underlying diagnosis matters more than the tool does. Before you blame the model for a weird output, open your context file and ask whether a rule in there is stale, contradictory, or just long enough that you'd skim it yourself. If the answer is yes, that's almost certainly where the bug started.

The source here is a single developer's blog post describing a tool they built, not an independent evaluation. There's no data on false positive rates, no comparison against just manually rereading your context file once a month, and no sense of how it holds up on a context file that's genuinely large. I'd treat good-context as a useful prompt to think about your own setup rather than a product to trust blind.

If you're maintaining an agent on a real project, the cheap move costs nothing. Reread your context file end to end once, out loud if you have to, and cut anything you wouldn't want a new hire to follow literally. That's the audit this tool is trying to automate. Doing it by hand first will tell you whether you even need the automation.
