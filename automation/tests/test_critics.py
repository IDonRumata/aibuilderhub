"""What each critic is allowed to see.

The 24 August run burned all three review rounds on a deadlock between two
critics: the SEO critic requires one or two internal links, while the
fact-checker was only ever shown the external sources and struck those links
as unsupported claims. The writer could satisfy one or the other, never both,
so the day was skipped with a post that was otherwise finished.
"""

from __future__ import annotations

from tests.conftest import make_topic

from aibh_pipeline.models import DraftPost
from aibh_pipeline.services import critics

CATALOGUE = "/blog/cursor-review-2026 - Honest Cursor review after 3 months"


def make_draft() -> DraftPost:
    return DraftPost(
        title="Anthropic's priciest tier struggles to hold users",
        description=(
            "Cheaper coding models are pulling users away from the top tier. "
            "What that shift means for a solo builder picking a tool this month."
        ),
        slug="anthropic-priciest-tier-struggles",
        tags=["news", "ai-coding"],
        body="## TL;DR\n\nSee our [Cursor review](/blog/cursor-review-2026).\n",
        source_urls=["https://example.com/story"],
    )


class Recorder:
    """Stands in for AnthropicClient and records each critic's user message."""

    def __init__(self) -> None:
        self.seen: dict[str, str] = {}

    async def complete_json(self, *, label: str, user: str, **_: object) -> dict:
        self.seen[label] = user
        return {"verdict": "PASS", "notes": "", "issues": []}


async def test_fact_checker_is_shown_the_internal_link_catalogue(settings, monkeypatch):
    async def no_network(urls, settings):
        return []

    monkeypatch.setattr(critics, "check_links", no_network)
    client = Recorder()

    await critics.review(
        make_draft(),
        make_topic("Anthropic's priciest tier struggles to hold users"),
        client=client,
        settings=settings,
        voice="voice",
        style_rules="rules",
        internal_links=CATALOGUE,
        known_slugs={"cursor-review-2026"},
    )

    fact_checker = client.seen["critic-fact-checker"]
    assert "/blog/cursor-review-2026" in fact_checker, (
        "the fact-checker must see the catalogue, or it strikes required "
        "internal links as unverifiable claims"
    )
