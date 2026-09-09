---
title: 'ChatGPT Images 2.5: what changed and who should care'
description: ChatGPT Images 2.5 adds faster, more consistent edits and a sketch-to-image feature. What it means for solo builders using AI images.
pubDate: '2026-09-09'
tags:
- news
- openai
- chatgpt
- ai-images
- product-updates
author: Andrei Maroz
draft: false
---

OpenAI shipped a new version of its image tool, and the headline feature is one you can actually picture: you draw a rough doodle inside ChatGPT, describe what you want it to become, and it turns your scribble into a finished image. That feature is called Sketch, and [The Verge reports](https://theverge.com/ai-artificial-intelligence/991727/openai-chatgpt-images-2-5-sketch) it lets you draw directly in the chat window and then tell ChatGPT how to render it.

The bigger update sits underneath that, in the model itself. Per [Simon Willison's writeup](https://simonwillison.net/2026/Sep/8/introducing-chatgpt-images-25), ChatGPT Images 2.5 is pitched as an upgrade to instruction-following across multiple turns, meaning it should hold onto what you told it two or three edits ago instead of drifting. OpenAI also claims faster response times and better preservation of subjects from reference photos, so if you upload a photo of yourself or a product and ask for variations, the thing in the photo should stay recognizably itself.

---

## What's new, concretely

Two new model IDs showed up in the API: `gpt-image-2.5-sunburst` and `gpt-image-2.5-flare`. Willison's post lays out the intended split: Sunburst is positioned for editing precision, Flare for faster everyday generation. Willison favors Sunburst as the stronger general default, going by how OpenAI frames the two rather than a head-to-head test. That's still a useful data point if you need to pick a default rather than swap models for every task.

OpenAI also disclosed usage scale for context: per Willison's post, the company says its image models have generated more than 3 billion images across ChatGPT Images and the GPT-Image API models combined. That's a scale number, not a quality number.

But it does tell you this isn't a side project. It's a product line getting continued investment, which matters if you're deciding whether to build a workflow around it or hold off.

---

## What this means if you build with AI images

If you use ChatGPT Images for product mockups, marketing assets, or app icons, the multi-turn consistency improvement is the part worth testing first. The old failure mode with iterative image editing was that the fourth revision would forget a constraint from the first one: the wrong color would creep back in, or a face would drift from the reference photo. If OpenAI's claim about holding context across turns holds up in your own use, that's fewer redo cycles, which is the actual cost most solo builders care about, not raw image quality.

Nobody outside OpenAI has verified that claim independently. Treat it as a thing to test against your own repeated-edit workflow, not something to assume.

Sketch is the more interesting update for people who aren't confident writing detailed prompts. Prompting is a translation problem: you're converting an image in your head into words precise enough that the model doesn't guess wrong, and a lot of AI image friction comes from that gap rather than from the model itself. A layout sketch, even a bad one, communicates spatial relationships that are awkward to describe in a sentence: where an element sits relative to another, what's foreground versus background.

If you've ever tried to prompt your way into a specific composition and gotten three unrelated layouts back, Sketch is aimed directly at that problem.

None of this changes what image generation is good for. It's still not a replacement for a designer when brand consistency or pixel-level control matters, and OpenAI hasn't claimed otherwise. What it does is lower the cost of the in-between assets: a placeholder hero image while you validate an idea, an icon set for an MVP. If that's the kind of image work you do, this release is worth a look. If you're producing anything that needs to survive contact with a paying client's brand guidelines, keep your existing tools in the loop.

For solo builders juggling AI tools generally, this is also a reminder to separate the announcement from the verified claim. "Better at preserving subjects" and "faster" are OpenAI's words until you or someone else runs the comparison.

Two new model IDs. A claimed 3 billion images generated across the product line. Those are the two concrete facts here, and everything about quality is still an OpenAI claim, not a measurement. If you're validating a product idea with AI-generated mockups as part of your [startup validation process](/blog/how-to-validate-startup-idea-with-ai-2026), or building landing pages that need quick visual assets as covered in our [guide to building a SaaS landing page with AI](/blog/build-saas-landing-page-ai-2026), test the new version on your actual workflow before you trust the marketing copy.

Don't switch a working pipeline over one blog post's worth of claims.
