"""Draft generation and revision.

The writer only ever sees titles, URLs and short feed summaries. Full article
text is never fetched or passed in: facts can be restated, wording cannot be
copied, and the pipeline stays on the right side of that line by never having
the source prose in the first place.
"""

from __future__ import annotations

import json
from typing import Any

from slugify import slugify

from ..clients.anthropic_client import AnthropicClient
from ..logging_setup import get_logger
from ..models import CritiqueReport, DraftPost, ScoredTopic
from ..settings import Settings

log = get_logger(__name__)

MAX_SOURCES_PER_TOPIC = 4

DRAFT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "slug": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "body": {"type": "string"},
    },
    "required": ["title", "description", "slug", "tags", "body"],
    "additionalProperties": False,
}

WRITER_SYSTEM = """\
You write news analysis for AIBuilderHub, a site for solo builders shipping
products with AI tools. Follow the house voice document exactly.

You are given a set of source headlines, links and short feed summaries. That
is all the evidence you have.

Hard rules:
1. Every factual claim - numbers, prices, model names, capabilities, company
   statements - must come from the supplied sources. If the sources do not
   support a claim, leave it out. Never invent benchmarks, adoption figures,
   or quotes.
2. Never copy phrasing from the sources. Restate facts in your own words.
3. Attribute anything a company said about its own product: "X says", "per
   the announcement". Only state something as fact when a source shows it.
4. Include one or two inline markdown links to the primary sources, placed in
   the sentence where the fact appears. Use the exact URLs supplied.
5. Include one or two internal links to existing posts from the catalogue you
   are given, only where they are genuinely relevant. Use the /blog/<slug>
   paths exactly as listed.
6. The post must read the same six months from now. No "today", "this week",
   "recently", "just announced", no month or year references to the news.
7. Never use an em dash or en dash. Straight quotes only. No emoji.
8. No "Introduction" or "Conclusion" headings. Headings are sentence case.
9. Contractions throughout. Vary sentence and paragraph length; include some
   very short sentences. Prose over bullets.
10. Give at least one clear subjective judgement with a reason behind it, and
    name at least one limitation or reason for scepticism.

Output fields:
- title: under 60 characters, no clickbait, no "You Won't Believe", no colon
  stuffing. Sentence case with proper nouns capitalised.
- description: 140 to 160 characters, a real summary, not a teaser.
- slug: lowercase kebab-case, no dates, no year, 3 to 7 words.
- tags: 3 to 5 lowercase tags. The first tag is always "news".
- body: markdown, 600 to 1000 words. Do not repeat the title as an H1; start
  with a short verdict paragraph or a "## TL;DR" section.
"""

REVISION_SYSTEM = """\
You are revising your own draft after review. You will be given the current
post and a list of specific issues raised by four reviewers.

Address every issue. Make the smallest edits that genuinely resolve them - do
not rewrite passages the reviewers did not object to, and do not drop the
source links. If a reviewer asks you to remove an unsupported claim, remove it
rather than hedging it into vagueness.

All the original writing rules still apply. Return the full post in the same
JSON shape.
"""


def _sources_brief(topic: ScoredTopic) -> str:
    lines: list[str] = []
    for item in topic.items[:MAX_SOURCES_PER_TOPIC]:
        summary = " ".join(item.summary.split())[:600]
        lines.append(
            f"- SOURCE: {item.source}\n"
            f"  TITLE: {item.title}\n"
            f"  URL: {item.canonical_url}\n"
            f"  SUMMARY: {summary or '(no summary provided by the feed)'}"
        )
    return "\n".join(lines)


def _to_draft(payload: dict[str, Any], topic: ScoredTopic) -> DraftPost:
    slug = slugify(str(payload.get("slug") or payload.get("title", "")), max_length=70)
    return DraftPost(
        title=str(payload["title"]).strip(),
        description=str(payload["description"]).strip(),
        slug=slug,
        tags=[str(t).strip().lower() for t in payload.get("tags", []) if str(t).strip()],
        body=str(payload["body"]).strip(),
        source_urls=topic.source_urls[:MAX_SOURCES_PER_TOPIC],
    )


async def write_draft(
    topic: ScoredTopic,
    *,
    client: AnthropicClient,
    settings: Settings,
    voice: str,
    internal_links: str,
) -> DraftPost:
    user = (
        f"Sources for this story:\n{_sources_brief(topic)}\n\n"
        f"Existing posts you may link to internally:\n{internal_links}\n\n"
        f"Target length: {settings.target_words_min} to {settings.target_words_max} words.\n"
        "Write the post."
    )
    payload = await client.complete_json(
        system_shared=voice,
        system_specific=WRITER_SYSTEM,
        user=user,
        max_tokens=settings.max_tokens_writer,
        label="writer-draft",
        json_schema=DRAFT_SCHEMA,
        effort="high",
    )
    draft = _to_draft(payload, topic)
    log.info("draft_written", slug=draft.slug, words=draft.word_count)
    return draft


async def revise_draft(
    draft: DraftPost,
    reports: list[CritiqueReport],
    topic: ScoredTopic,
    *,
    client: AnthropicClient,
    settings: Settings,
    voice: str,
    internal_links: str,
    round_index: int,
) -> DraftPost:
    issues: list[str] = []
    for report in reports:
        for issue in report.issues:
            quote = f'  Quote: "{issue.quote}"\n' if issue.quote else ""
            issues.append(
                f"- [{report.critic} / {issue.severity}] {issue.requirement}\n{quote}"
            )

    snapshot = json.dumps(
        {
            "title": draft.title,
            "description": draft.description,
            "slug": draft.slug,
            "tags": draft.tags,
            "body": draft.body,
        },
        ensure_ascii=False,
        indent=2,
    )
    user = (
        f"Sources for this story:\n{_sources_brief(topic)}\n\n"
        f"Existing posts you may link to internally:\n{internal_links}\n\n"
        f"Current post:\n{snapshot}\n\n"
        f"Reviewer issues to resolve:\n{''.join(issues)}"
    )
    payload = await client.complete_json(
        system_shared=voice,
        system_specific=REVISION_SYSTEM,
        user=user,
        max_tokens=settings.max_tokens_writer,
        label=f"writer-revision-{round_index}",
        json_schema=DRAFT_SCHEMA,
        effort="high",
    )
    revised = _to_draft(payload, topic)
    log.info("draft_revised", round=round_index, slug=revised.slug, words=revised.word_count)
    return revised
