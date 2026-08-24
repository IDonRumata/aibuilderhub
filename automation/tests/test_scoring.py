from __future__ import annotations

import pytest
from tests.conftest import make_item

from aibh_pipeline.models import SourceKind
from aibh_pipeline.services.scoring import (
    cluster,
    has_citable_source,
    is_self_promo,
    score_topics,
)


def test_cluster_groups_the_same_story():
    items = [
        make_item("Cursor raises prices for its Pro plan"),
        make_item(
            "Cursor raises Pro plan prices",
            url="https://other.com/a",
            source="the-verge-ai",
        ),
        make_item("Bubble ships a new no-code editor", url="https://third.com/a"),
    ]
    groups = cluster(items)
    assert len(groups) == 2
    assert max(len(g) for g in groups) == 2


def test_off_niche_topics_are_dropped(sources_config, settings):
    items = [
        make_item("France to ban unsolicited telemarketing calls", score=600),
        make_item(
            "Cursor adds an agent mode for vibe coding",
            url="https://example.com/cursor",
            score=120,
        ),
    ]
    topics = score_topics(items, sources_config, settings)
    titles = [t.title for t in topics]
    assert "France to ban unsolicited telemarketing calls" not in titles
    assert any("Cursor" in t for t in titles)


def test_penalty_keywords_push_a_topic_below_the_gate(sources_config, settings):
    items = [
        make_item(
            "Crypto exchange launches an AI agent for bitcoin trading",
            summary="blockchain nft token price",
            score=900,
        )
    ]
    assert score_topics(items, sources_config, settings) == []


def test_corroboration_beats_raw_engagement(sources_config, settings):
    two_sources = [
        make_item("Lovable ships a no-code database builder", score=90),
        make_item(
            "Lovable ships no-code database builder",
            url="https://verge.example/x",
            source="the-verge-ai",
            kind=SourceKind.RSS,
            score=0,
        ),
    ]
    # Same niche vocabulary on both sides, so corroboration is the only
    # variable that differs.
    one_source = [
        make_item(
            "Replit ships a no-code database builder",
            url="https://example.com/replit",
            score=140,
        )
    ]
    topics = score_topics(two_sources + one_source, sources_config, settings)
    assert topics[0].title.startswith("Lovable")
    assert topics[0].distinct_sources == 2


def test_freshness_decays(sources_config, settings):
    fresh = make_item("Cursor ships an ai agent for no-code builders", hours_old=1, score=100)
    stale = make_item(
        "Windsurf ships an ai agent for no-code builders",
        url="https://example.com/w",
        hours_old=30,
        score=100,
    )
    topics = score_topics([stale, fresh], sources_config, settings)
    assert topics[0].title.startswith("Cursor")


def test_same_predicate_different_subject_is_not_one_story():
    items = [
        make_item("Lovable ships a no-code database builder"),
        make_item("Replit ships a no-code database builder", url="https://example.com/r"),
    ]
    assert len(cluster(items)) == 2


def test_blank_env_values_fall_back_to_defaults(monkeypatch):
    """GitHub Actions passes "" for an unset variable or secret."""
    from aibh_pipeline.settings import Settings

    monkeypatch.setenv("AIBH_MODEL", "")
    monkeypatch.setenv("VOYAGE_API_KEY", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    blank = Settings()
    assert blank.model == "claude-sonnet-5"
    assert blank.voyage_api_key is None
    assert blank.anthropic_api_key is None


def test_topics_with_readable_sources_outrank_bare_headlines(sources_config, settings):
    """A headline-only story gives the writer nothing but filler to invent."""
    bare = make_item(
        "Someone ships an ai agent for no-code builders",
        url="https://example.com/bare",
        score=300,
    )
    readable = make_item(
        "Cursor ships an ai agent for no-code builders",
        url="https://example.com/readable",
        score=300,
        summary="x" * 1200,
    )
    topics = score_topics([bare, readable], sources_config, settings)
    assert topics[0].title.startswith("Cursor")


# --- topic quality gates -------------------------------------------------
# Every scheduled run between 12 and 20 August 2026 was rejected by the
# critics. The cause was upstream: Reddit's JSON endpoint is blocked from the
# runner, the RSS fallback carries no vote counts, so min_upvotes never
# applied and "I built X" posts won on keywords and self-text length alone.



@pytest.mark.parametrize(
    "title",
    [
        "I built a memory + coordination graph my agents can actually use",
        "So I built a tool that turns Figma into React",
        "My first side project just hit 1000 users",
        "I've been working on an AI code reviewer",
        "Roast my landing page please",
        "We launched our SaaS after 6 months",
        "I made deploy a single message",
    ],
)
def test_first_person_project_posts_are_dropped(title):
    assert is_self_promo(title)


@pytest.mark.parametrize(
    "title",
    [
        "Anthropic launched Claude Code for the web",
        "Cursor raises $900M at a $29B valuation",
        "Meta's Muse Glimmer: a local model built for agents",
        "Grok 4.6",
        "Vercel made v0 free for students",
        "Are we teaching coding agents to be productive?",
    ],
)
def test_real_news_survives_the_self_promo_filter(title):
    assert not is_self_promo(title)


def test_a_reddit_post_with_unknown_engagement_is_not_citable():
    item = make_item(
        title="Some discussion thread",
        source="r/SideProject",
        kind=SourceKind.REDDIT,
        score=0.0,
    )
    assert not has_citable_source([item.model_copy(update={"engagement_measured": False})])


def test_a_publication_is_always_citable():
    assert has_citable_source(
        [make_item(title="Anthropic ships a thing", source="techcrunch", kind=SourceKind.RSS)]
    )


def test_a_reddit_post_with_real_upvotes_is_citable():
    item = make_item(
        title="Claude Code goes GA",
        source="r/ChatGPTCoding",
        kind=SourceKind.REDDIT,
        score=850.0,
    )
    assert has_citable_source([item])
