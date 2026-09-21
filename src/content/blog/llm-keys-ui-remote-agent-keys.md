---
title: A tiny plugin fixes API keys on remote coding agents
description: Simon Willison's llm-keys-ui plugin lets you set API keys on a remote machine through a browser link instead of pasting secrets into a chat app.
pubDate: '2026-09-21'
tags:
- news
- coding-agents
- api-keys
- developer-tools
- llm
author: Andrei Maroz
draft: false
---

If you run coding agents on a machine you're not sitting in front of, you've probably hit this exact annoyance: the agent needs an API key, and the only way to give it one is to paste that key into a chat window, where it sits in plaintext in a session log you didn't ask for.

Simon Willison built a small fix for this. His new plugin, [llm-keys-ui](https://simonwillison.net/2026/Sep/20/llm-keys-ui), is at version 0.1. It gives him a way to set an API key on a remote machine without typing it into the agent's chat interface.

You run a command, the agent hands you back a URL, including local network or Tailscale addresses, per the post, and you open that link in a browser to enter the key directly. The key never touches the conversation. That's the whole trick.

Willison's own use case is specific: he uses Codex Remote to run coding agents on multiple machines while controlling them from his phone, and some of those machines occasionally need a fresh API key configured for whatever LLM project he's hacking on. The command he describes running is `uvx --with llm-keys-ui llm keys-ui --all`, which launches the UI and gives the agent something to report back to him as a link.

---

## Why this is worth 500 words and not zero

This is a small release from one person, solving one person's problem. It's not a platform or a funding round. So why does it matter to a solo builder who isn't running a fleet of remote coding agents off their phone?

Because the underlying problem isn't niche. Anyone running an agentic coding setup, and see our take on [intent debt in agentic coding](/blog/intent-debt-agentic-coding) for another way these workflows accumulate small hidden costs, has had the moment where the agent needs a credential and the path of least resistance is to just type it into the chat. That's fine until it isn't.

Chat logs get saved, shared, or scrolled back through by someone else. A pasted key sitting in plain text is a small but real liability.

Willison's plugin is a demonstration of a pattern I think will show up more as remote and multi-machine agent workflows become normal: pull secrets out of the conversation entirely and hand them to a dedicated, ephemeral interface instead. It's the same instinct behind OAuth flows that pop a browser tab rather than asking you to paste a token into a form.

I think coding agents are starting to catch up to that basic security hygiene. For now it's happening at the tooling layer, in small plugins built by individual developers, rather than as a feature shipped by a big lab. That's my read on one data point, not a trend anyone's measured.

## What this doesn't solve, and what I'd watch for

The plugin is scoped narrowly to Willison's own workflow with `llm` and Codex Remote. It doesn't claim to be a general secrets manager, and there's nothing in the release suggesting it handles key rotation, expiry, or team sharing.

If you're managing API keys across a team or across dozens of environments, this isn't that tool, and nothing here suggests it's trying to be.

My own read is that the interesting part isn't the plugin itself so much as the shape of the problem it's responding to. As more solo builders adopt setups where an agent runs unattended on a server or a spare machine and you check in from a phone, the same shift we saw coming when we covered [OpenAI's Agents API landing on Vercel](/blog/openai-agents-api-vercel-deploy), the gap between "convenient" and "secure" for credential handling is only going to get more visible.

A tool like this doesn't close that gap by itself. It's a one-person patch, not a standard.

You don't need to install this to get the point. If you're running any agent on a remote machine, take five minutes to ask yourself where your API keys actually end up right now, and whether you'd be fine with someone else reading that log. If the answer is no, this plugin, or something like it, is worth having on hand the next time you set one of these machines up.
