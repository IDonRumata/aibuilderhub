---
title: Anthropic's revenue is up. Its top model isn't.
description: Anthropic's revenue jumped to $65bn annualized, but a headline says its top model can't attract users. What that means for builders.
pubDate: '2026-08-24'
tags:
- news
- anthropic
- ai-models
- claude
author: Andrei Maroz
draft: false
---

Anthropic's revenue is climbing fast, and according to a Financial Times headline, its flagship model is struggling to attract users at the same time. Those two things sound contradictory. They're not necessarily, and the gap between them is worth a closer look before you draw any conclusion about what to do with Claude.

Per numbers reported by the Financial Times and gathered from people described as familiar with the matter, [as summarized by Simon Willison](https://simonwillison.net/2026/Aug/23/anthropics-best-ai-model-struggles-to-attract-users-as-cheaper-t), Anthropic's annualized revenue rose from $47 billion to $65 billion over a recent two-month stretch. The same summary reports that Anthropic told investors it expects its next quarter to be profitable, using the same accounting approach it used to call the prior quarter profitable, though the underlying FT reporting isn't itself linked here, so treat that specific framing as relayed secondhand through Willison's post rather than something I've verified against the original article. Anthropic also says it has 6,000 customers spending $100,000 or more a year with it. Willison's post notes OpenAI's quarter-to-date annualized revenue is reported elsewhere to have grown 35 percent to over $40 billion, for comparison, though that figure comes from the same secondhand chain of reporting rather than a source I can point to directly.

So Anthropic is bringing in more money than OpenAI on an annualized basis, at least by these figures, and has thousands of high-spending enterprise accounts. That doesn't sound like a company whose best model can't find users. But revenue and adoption are different measurements, and the FT headline, as relayed by Willison, is pointing at the second one, not the first.

---

### What's actually going on

The source gives us the headline claim and the revenue figures, but not the reasoning behind the headline. So here's my own read, clearly labeled as such: the most likely explanation is that Anthropic's top-tier model is having a harder time pulling in everyday users because cheaper alternatives are good enough for most tasks, while its revenue keeps growing through a smaller number of very large accounts.

That's speculation on my part. It's built from the numbers, not stated anywhere in the reporting.

The 6,000-customer figure is the only concrete data point we have on where the money is coming from. The source doesn't compare it against any trend in individual or consumer adoption, so I can't confirm the split I'm describing. I'm inferring it, not reading it off the page.

If that read is right, it's not a contradiction, it's a business model. If your revenue comes from a smaller number of very large customers, you can grow revenue substantially while your top model is losing the everyday-user popularity contest to something a tenth of the price. Cheaper tools winning on volume and a premium model winning on revenue per account can both be true at once.

I'd read this as a sign that the market is stratifying rather than consolidating around one winner. Something similar is playing out on pricing across the model market more broadly: the [Gemini 3.7 Flash release](/blog/gemini-3-7-flash-coding-agents) is another example of a cheaper model undercutting a pricier one on cost while remaining good enough for most day-to-day coding tasks. It's a different company and a different specific claim, but the same underlying force: cheap, good-enough models take the volume, and expensive frontier models get pushed toward the harder end of the work.

---

### What this means if you're building on Claude

If you're a solo builder paying for Claude API access or a Claude subscription, none of this is a reason to panic or switch. A company reporting profitability, even using its own accounting method rather than an audited figure, plus 6,000 customers paying six figures a year, is a company with a strong financial reason to keep investing in its highest-end model rather than letting it languish. That's specific to Anthropic's situation here, not a general rule about profitable companies.

What I'd actually watch for is pricing. If cheaper models are winning the volume game, the competitive pressure on Anthropic to either cut prices on its flagship model or push harder on a genuinely cheaper tier is going to keep building. That's good news for you as a buyer over time, even if it's an awkward growth story for Anthropic to tell investors.

The part I can't tell from this alone is how much of that enterprise revenue is Claude-the-chat-product versus Claude-the-API-embedded-in-someone-else's-tool. That distinction isn't something the source discusses at all. It's a question I'm raising myself, not a gap the reporting hints at. Those are very different growth stories. If most of the growth is API revenue flowing through coding tools and agents rather than direct subscriptions, that's the more durable pattern, because it means Claude is becoming infrastructure rather than a destination people have to choose to visit.

---

The honest read is this: Anthropic's business is growing quickly by revenue, its flagship model may be losing the popularity contest against cheaper options for casual use, and both facts can be true without either one being spin.

If you're paying for Claude, don't read the headline as a reason to leave. Watch what Anthropic does with pricing on its flagship tier over time. That's where this story will actually show up for you.
