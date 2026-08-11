from __future__ import annotations

from tests.conftest import make_item

from aibh_pipeline.models import SourceKind
from aibh_pipeline.services.scoring import cluster, score_topics


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
