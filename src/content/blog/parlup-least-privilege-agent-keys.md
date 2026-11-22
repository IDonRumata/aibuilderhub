---
title: Parlup wants your AI agent to stop handling raw keys
description: Parlup's new CLI puts agent credentials in your OS keyring with Ed25519 keys and read-only scoped tokens, instead of plaintext JSON secrets.
pubDate: '2026-11-22'
tags:
- news
- ai-agents
- security
- credentials
author: Andrei Maroz
draft: false
---

If you've wired an AI agent up to send messages, poll an inbox, or do anything on a schedule, you've probably dropped a private key into a JSON file somewhere and hoped nobody reads your repo. That's the problem [Parlup](https://dev.to/parlup/least-privilege-agent-messaging-os-keyring-keys-ed25519-scope-read-tokens-5cg9) is going after with its v0.3.0 CLI release.

The pitch is simple: agent credentials shouldn't live as plaintext, and background workers shouldn't get the same permissions as the thing that actually needs to act. Parlup's Go-based CLI generates Ed25519 control and access keypairs locally and stores them in your operating system's keyring rather than in a config file sitting next to your code. Keys are namespaced per handle, so if you're running multiple agent profiles, their credentials don't collide or leak into each other.

The more interesting piece, for anyone running agents unattended, is the scoped token system. If you just need something to monitor an inbox from a cron job or a cloud worker, you can issue a `--scope read` token that can poll messages but can't send anything. According to the project, this is meant to cover the common case where a monitoring process has no business holding send permissions at all, but ends up with them anyway because nobody bothered to separate the two.

---

### Why this is the right problem, even if the project is early

This site has already covered the general shape of this issue more than once. [MCP servers can touch everything, and you have to vet them like it](/blog/vet-mcp-server-before-install). AI coding agents write [security bugs on purpose](/blog/ai-agents-security-bugs-nextjs-supabase) when nobody's watching the diff. The pattern is always the same: it's easy to give an autonomous process broad access because scoping it down takes more setup work, and most solo builders don't have the time or security background to do that setup properly.

Parlup is a narrow fix for a narrow slice of that problem: agent-to-agent or agent-to-service messaging credentials specifically. It's not a sandbox, and it's not a permissions framework for tool calls in general. It doesn't touch what the agent can do once it's authenticated with whatever scope it has. If you want the execution-side version of this concern, that's closer to what [sandboxing your agent's code execution](/blog/ai-agent-code-execution-sandboxes) is for. These are complementary, not competing, concerns, and a solo builder running agents in production probably needs to think about both eventually.

My honest read: using the OS keyring instead of plaintext JSON is an easy, obviously correct call, and I'm a little surprised it needed a dedicated project to make it the default.

That's not a knock on Parlup so much as a comment on how low the bar has been. Most tutorials and quick-start scripts for agent frameworks still tell you to drop an API key into an environment variable or a config file, full stop. Copy-paste a quick-start, ship it, move on.

Nobody circles back to separate read access from send access until something goes wrong. By then the key has probably already been pasted into a chat log or committed to a public repo at least once.

---

### What this doesn't solve

A few things worth being clear-eyed about. The source material doesn't claim Parlup audits what an agent does once it holds a valid token, scoped or not. It's a credential storage and issuance layer, not a monitor of agent behavior. A `--scope read` token stops an agent from sending messages it shouldn't, but it won't stop an agent with a legitimately-scoped send token from sending the wrong thing, at the wrong time, to the wrong person.

That's a prompt and logic problem, not a key-management problem. No amount of OS keyring hygiene fixes it.

It's also narrow by design. This is specifically about Parlup's own messaging system: the keys and tokens it issues govern access to Parlup, not to your database, your cloud provider, or any other API your agent might call. If you're storing a Stripe key or an AWS credential in a JSON file next to your agent code, this project doesn't touch that at all. You'd still want something like a secrets manager or your OS keyring directly for those, and you'd still want to apply the same scoping instinct yourself rather than assuming a tool will do it for you by default.

And it's early. v0.3.0 is not a 1.0 release, and a security-focused credential tool is exactly the kind of software you want to see survive a few rounds of scrutiny before you trust it with anything that matters.

That's not a reason to ignore it. It's a reason to treat it as a pattern worth adopting, OS keyring over plaintext, read-only tokens for anything unattended, rather than a specific tool you should bolt into production without reading the code yourself.

---

If you're building anything that gives an agent network access, the actionable bit here isn't "go install Parlup." It's the underlying habit: ask, for every key your agent holds, whether it actually needs send permission or just needs to read.

If a cron job or background worker is holding a key that can do more than it needs to do, that's a gap worth closing regardless of which tool you use to close it.
