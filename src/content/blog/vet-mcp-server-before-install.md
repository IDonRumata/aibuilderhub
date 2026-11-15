---
title: MCP servers can touch everything. Vet them like it
description: MCP servers give AI clients a shell, your files, and signed-in accounts. A new checklist spells out four things to check before you install one.
pubDate: '2026-11-15'
tags:
- news
- mcp
- ai-agents
- security
- vibe-coding
author: Andrei Maroz
draft: false
---

MCP has quietly become the plugin layer for every AI coding tool you use: Claude Code, Cursor, VS Code, and the rest. It's the thing that lets your AI client reach outside the chat window and actually do stuff. The trouble is that "do stuff" covers a lot of ground, and most people install MCP servers the way they install npm packages. They shouldn't.

A [checklist on dev.to](https://dev.to/stackregistry/how-to-vet-an-mcp-server-before-you-install-it-a-10-minute-checklist-29gn) makes the comparison explicit: installing an MCP server is closer to installing a browser extension with full permissions than to adding a library to your project. The post's short answer is four things to check before you add one: who maintains it, exactly what it can touch, where its secrets live, and whether it can change after you've approved it. The post frames this as a ten-minute pass per server. Then it suggests you go back through your existing config and keep only the servers whose install snippet came straight from the maintainer's own README, not from a random blog post or a forum copy-paste.

---

## Why this matters more than it sounds like it should

An MCP server isn't a sandboxed function. Per the post, it can hand your AI client a shell, access to your files, a browser session that's already signed into your accounts. That's the whole point of MCP: it exists so your agent can do real things instead of just suggesting text.

But "real things" is exactly where the risk lives, and it's the same territory covered in our piece on [why your AI agent needs a sandbox, not your server](/blog/ai-agent-code-execution-sandboxes). An MCP server with shell access and no sandbox around it is a server that can do anything you can do, at agent speed, without you watching every step.

The maintainer question is the one I'd weight heaviest. A library you don't trust mostly risks your build. An MCP server you don't trust risks your accounts, your files, and whatever credentials it can reach.

The checklist's point about install snippets is a quiet but sharp one. Copy-pasting a config block from a tutorial instead of the official repo is how you end up granting permissions you never meant to grant, to a server that isn't the one you thought you were installing.

"Can it change after you approve it" is the detail most people skip. You check a server once, decide it's fine, and move on.

But if that server auto-updates or pulls remote config, the version doing the approving isn't necessarily the version doing the running down the line. That's a supply chain problem wearing a different hat, and it's the same shape of issue we've covered in how [AI agents end up shipping security bugs](/blog/ai-agents-security-bugs-nextjs-supabase) nobody asked for: the gap between what you reviewed and what's actually running.

---

## What I'd actually do with this

If you're running Claude Code, Cursor, or any client with MCP support, you almost certainly have more servers installed than you remember approving. Most people add one for a specific task, forget about it, and never revisit the list.

The checklist's suggestion to scan your existing config, not just vet new installs, is the more useful habit of the two. New installs you're already paying attention to. Old ones are where the risk quietly accumulates.

My honest read: the checklist covers four specific checks, maintainer, permissions, secrets, and update behavior, and that's a reasonable floor, not a ceiling. It'll catch the obvious cases: an unmaintained fork, a server asking for filesystem access it has no business needing, a snippet from a sketchy source. It won't catch a well-maintained, popular server that's doing something subtly wrong, because "who maintains it" only tells you reputation, not behavior.

Nothing in the source addresses how you'd audit what a server actually does once it's running. That's the harder and more useful problem.

There's also no universal registry or verification system here. This is one person's checklist, not a standard the MCP ecosystem has agreed on, and I wouldn't expect that to change fast given how young the protocol still is.

If you've been treating MCP installs like npm installs, that's the thing to fix first. Ten minutes per server is cheap. Finding out after the fact that one had shell access to a machine with your production credentials on it is not.
