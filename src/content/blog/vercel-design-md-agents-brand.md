---
title: 'Vercel''s design.md: teaching coding agents your brand rules'
description: Vercel open-sourced how its agents follow brand guidelines with a design.md skill file. Here's what that actually means for solo builders using AI tools.
pubDate: '2026-09-01'
tags:
- news
- vercel
- ai-coding-tools
- design-systems
- vibe-coding
author: Andrei Maroz
draft: false
---

## TL;DR

Vercel published details on [design.md](https://vercel.com/blog/how-our-agents-build-on-brand-pages-with-design-md), a skill file its internal coding agents use to keep AI-generated pages on-brand instead of drifting toward generic AI-app-builder looks. It's not a product you can buy. It's a pattern: a document that lives in your codebase and tells any agent working in it how your design system actually works, not just what components exist. There's nothing to install, but if you're building with AI tools and tired of generic-looking output, the pattern itself is worth stealing, with one caveat: it only works if you already have real design decisions written down somewhere.

---

## What Vercel actually built

Per the [company's blog post](https://vercel.com/blog/how-our-agents-build-on-brand-pages-with-design-md), Vercel uses coding agents across its own teams to design and build pages that need to look and feel like Vercel, not like a plausible imitation of a modern SaaS site. The company says it already had a broader skill called product-design that teaches agents how Vercel designs when they work inside its own codebases. design.md is described as the more specific piece: a file that lives alongside the code it governs and explains how an agent can find and understand the design system and product guidelines relevant to whatever it's building right then.

The problem Vercel says it's solving is one anyone using an AI app builder will recognize: agents produce working code fast, but left to their own judgment they tend to converge on the same generic defaults instead of a specific brand's visual language.

That's my read on the underlying problem, not a specific claim from Vercel's post. The post doesn't name particular defaults or give a before-and-after count of pages affected. Vercel frames design.md as the fix for its own repos specifically, and it says the pattern works well when agents are working inside a codebase that already has the design system documented in a form the agent can read and act on.

Vercel doesn't claim the file works as a general-purpose fix for every agent in every codebase. The source excerpt available doesn't spell out what happens when a repo's design system is thin or undocumented.

My guess is that describes most repos. That's speculation on my part, not something the post addresses.

---

## Why this isn't really about Vercel

Strip away the branding and design.md is a straightforward idea: instead of hoping an agent infers your visual taste from a few example files, you write down the rules once, type scale, spacing units, color roles, when to use which button variant, and point every agent at that file before it touches your code.

That's it. No new model, no new product, no pricing tier.

Which is exactly why it's worth paying attention to if you're not Vercel. You don't need Vercel's tooling to do this. If you're using [Cursor](/blog/cursor-review-2026), [Windsurf](/blog/windsurf-review-2026), or [Lovable](/blog/lovable-review-2026) and you keep getting output that looks like every other AI-generated app, the fix isn't a better prompt for each session. It's a persistent file, call it design.md, or DESIGN.md, or whatever your tool of choice will actually read, that lives in the project and gets referenced automatically instead of re-explained by hand every time.

Concretely, that file needs to say more than "we use Tailwind" or "primary color is #0070F3." The whole point, per Vercel's framing, is that agents need to understand *why* the system works the way it does, not just what the tokens are: which spacing scale to default to for a marketing page versus a dashboard, when a heavier font weight is appropriate, which layout patterns are off-limits. A component library alone doesn't carry that judgment. A README written for humans usually doesn't either, because it assumes context an agent doesn't have.

---

## The catch

Here's the part that doesn't make it into the announcement: this only works if the design judgment already exists somewhere in writing before you ask an agent to follow it. Vercel can write a design.md that captures real decisions because Vercel has a design team and years of shipped pages to draw the rules from. A solo builder starting from scratch doesn't have that.

You'd be writing the rulebook and the product at the same time.

That's a real cost, not a free upgrade.

If your project doesn't have a documented design system yet, writing design.md is really writing a design system, and that's a few hours of real work, not a five-minute setup step. It also needs upkeep: a stale design.md that still points agents toward a layout or color rule you abandoned will actively mislead them, which is worse than having no file at all.

So treat it as a two-step decision, not a one-line fix. If you already have a real design system somewhere, even informally, in a Figma file, a style guide, or just consistent habits you could describe in a page, write it down as design.md and point your AI tool at it before your next session. If you don't have that yet, don't fake it. Spend an hour making three or four real decisions about type, spacing, and color first, write those down, and only then hand the file to an agent. A design.md built on decisions you haven't actually made yet is worse than no design.md at all.
