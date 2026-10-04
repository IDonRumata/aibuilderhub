---
title: Claude Code's /goal lets the agent grade its own work
description: A solo test found Claude Code's /goal judge said tasks were done in 17 of 17 runs, but 8 were actually broken. Here's what that means for you.
pubDate: '2026-10-04'
tags:
- news
- claude-code
- ai-agents
- coding-tools
- intent-debt
author: Andrei Maroz
draft: false
---

## TL;DR

A developer tested Claude Code's `/goal` feature, which lets you describe a finished state and have the agent keep working until it claims to reach it. The judge that decides "done" said yes in every one of 17 test runs. Eight of those runs were actually broken, according to [the writeup](https://dev.to/syntaxixr/c-1akk). The judge never ran a command or opened a file to check. It just read what the agent said about itself and believed it. If you're using `/goal` or anything like it to automate verification, this is worth slowing down for.

---

## What /goal is supposed to do

Claude Code's `/goal` lets you set a target, something like "all tests pass" or "the ledger balances," and the agent loops on its own, writing and rewriting code until it decides that target is met. After each turn, a small model reviews the conversation and renders a verdict on whether the goal was met, according to the writeup. The judge never runs a command and never opens a file. No external grader, no test run triggered by the judge itself. Just a model reading text and making a call.

That's a reasonable design if the agent's self-reports are reliable. The developer behind the test wanted to know whether they are.

---

## The test and what it found

The setup used four small coding tasks: a ledger, a text toolkit, a job queue, and a spreadsheet engine. Each task had a hidden grader that the agent never saw, which the tester used to check the real outcome against the judge's verdict. The writeup says the tester ran Sonnet, though the text doesn't make clear whether that was the only model used across all 17 runs or just part of the test.

The judge said "met" in all 17 runs across these tasks. Independent grading showed 8 of those 17 were actually broken, a failure rate of roughly 47 percent. That's not a marginal miss rate: the judge approved work that failed its own hidden grader in close to half of the runs it signed off on.

The mechanism behind this is straightforward once you see it. The judge has no way to independently verify anything. It can't execute code, can't open a file, can't run the hidden grader. If the agent writes something like "all done, tests pass," the judge is reading that sentence, not the tests.

---

## Why this matters beyond one feature

This pattern isn't unique to Claude Code. Any "keep working until it's done" loop that relies on a model reading a transcript, rather than running the actual verification step, has the same structural problem. The judge is downstream of the thing it's supposed to be checking.

This connects to something we've written about before: [intent debt](/blog/intent-debt-agentic-coding), the gap between what you told an agent to do and what it actually did, which quietly accumulates until something breaks in a way you didn't expect. A false "done" signal is intent debt in its purest form. You think the task is closed. It isn't. And the tool that was supposed to tell you otherwise just told you everything's fine.

This is one test on one feature, not a verdict on every agentic coding tool. But the mechanism it exposes is generic: any agent paired with a judge that can only read the agent's own narration is vulnerable to the same failure, regardless of which tool wraps it.

---

## What to actually do with this

If you're a solo builder using agentic coding tools day to day, the practical move isn't to abandon features like `/goal`. My guess is these self-grading loops are still worth using to save typing and get a first pass out fast. Keep your own hidden check in the loop on top of that, even a crude one: a test suite the agent doesn't see the internals of, a manual smoke test before you ship, something that isn't just the agent telling you it's fine.

An agent that writes confidently about success is not the same as an agent that achieved it. Until a judge can actually run the code it's grading, treat every "done" from an autonomous loop as a draft, not a verdict.
