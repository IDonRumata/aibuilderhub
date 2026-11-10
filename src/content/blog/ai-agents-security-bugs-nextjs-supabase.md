---
title: The security bugs your AI coding agent writes on purpose
description: A developer's scanner project found four recurring Next.js and Supabase security bugs that AI coding agents write confidently and mark as done.
pubDate: '2026-11-10'
tags:
- news
- security
- vibe-coding
- nextjs
- ai-agents
author: Andrei Maroz
draft: false
---

## TL;DR

A developer who builds an open-source security scanner [wrote up four bug patterns](https://dev.to/avivgerzhue/four-security-bugs-ai-coding-agents-keep-writing-in-nextjs-supabase-apps-and-4-false-positives-28pk) he kept seeing AI coding agents produce in Next.js and Supabase projects. The bugs aren't typos or forgotten edge cases. They're confidently built endpoints that are missing a whole layer, like authentication, shipped as if the job were finished. If you're shipping anything with a coding agent, read this one before your next deploy.

---

## What the post actually describes

The author works regularly with Claude Code, Cursor, and OpenCode, and says the mistakes an agent makes read differently than the mistakes a tired human makes. A human who's rushing forgets to escape one input, or skips validation on a form field they assumed was safe. An agent, per the post, will write a fully structured API endpoint with no authentication check at all, call the task complete, and move on to the next one.

That's the pattern across all four bugs he describes: missing auth checks on API routes, Supabase row-level security left wide open, agents reaching for service-role keys in places that should only ever see an anonymous key, and client-side data trusted without a server-side recheck. None of these are exotic. A security review would catch them in the first pass.

The author's point is that an agent doesn't skip them out of laziness. It skips them because the task as stated didn't mention them, and the code it wrote satisfies every requirement it was actually given. The endpoint works. It returns the right data in the right shape.

It's also open to anyone who finds the URL.

The author built vibe-shield, an open-source scanner meant to catch exactly these four patterns, and says so directly rather than burying it. The second half of his writeup covers false positives he had to tune out of the scanner, which is a reasonable thing to include if you're being honest about a tool's limits. It's also the pitch. Read the bug patterns as the useful part and the scanner as an option, not a verdict.

---

## Why this keeps happening

The mechanism here lines up with something we've written about before: [intent debt](/blog/intent-debt-agentic-coding), the gap between what you asked an agent to build and what you actually needed it to build. An agent optimizes for the instructions in front of it. If "add an endpoint that returns user orders" doesn't say "and check that the requester is allowed to see those orders," the agent has no reason to add that check, because nothing in its context flagged it as part of the task. The agent isn't guessing wrong. It's answering a narrower question than the one you meant to ask.

This is also why the fix isn't "use a smarter model." A smarter model still only solves the problem you described to it.

What changes the outcome is either reviewing the generated code against a checklist of the stuff agents reliably skip, authentication, row-level security, which keys go where, or running something that checks for it automatically. If you're already thinking about where generated code executes and what it's allowed to touch, this fits alongside the broader case for [running agent code in a sandbox rather than trusting it directly on your server](/blog/ai-agent-code-execution-sandboxes): the problem in both cases is that an agent will do exactly what it was told, including the parts it wasn't told to leave out.

---

## What this means for you

If you're building on Next.js and Supabase with a coding agent doing a meaningful share of the work, the useful move is to stop assuming "done" means "secure," not to distrust the agent in general. Before you ship, run through a short list of the same four things the post flags and the scanner checks for:

- Does every API route actually verify who's calling it, not just return the right shape of data?
- Are your Supabase row-level security policies turned on and scoped, rather than left open?
- Which key shows up where, anon or service-role, because an agent won't always know the difference matters?
- Is any client-side data being trusted without the server rechecking it?

Whether you run a tool like vibe-shield or just work through this list by hand before every deploy, the point is the same: an agent that says a task is done has only confirmed it met the instructions you gave it, not that the endpoint is safe to put in front of strangers.
