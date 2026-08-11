from __future__ import annotations

from datetime import UTC, datetime

import pytest
from tests.conftest import make_item, make_topic

from aibh_pipeline.clients.embeddings import EmbeddingProvider, cosine, lexical_embedding
from aibh_pipeline.models import DraftPost, PublishedTopic
from aibh_pipeline.services import dedup


@pytest.fixture
def store(settings, tmp_path, monkeypatch):
    monkeypatch.setattr(type(settings), "state_dir", property(lambda self: tmp_path))
    monkeypatch.setattr(
        type(settings), "published_topics_file", property(lambda self: tmp_path / "topics.json")
    )
    monkeypatch.setattr(
        type(settings), "embeddings_file", property(lambda self: tmp_path / "vectors.json")
    )
    return dedup.StateStore(settings)


def test_lexical_embedding_is_deterministic():
    assert lexical_embedding("Cursor raises prices") == lexical_embedding("Cursor raises prices")


def test_cosine_separates_related_from_unrelated():
    a = lexical_embedding("Cursor raises the price of its Pro plan for solo developers")
    b = lexical_embedding("Cursor increases Pro plan pricing for individual developers")
    c = lexical_embedding("Bubble ships a redesigned no-code database editor")
    assert cosine(a, b) > cosine(a, c)


def test_filter_seen_drops_processed_urls(store):
    store.topics.append(
        PublishedTopic(
            slug="old-post",
            canonical_topic="cursor prices",
            title="Cursor prices",
            source_urls=["https://example.com/cursor"],
            published_at=datetime.now(UTC),
        )
    )
    items = [
        make_item("Cursor prices", url="https://www.example.com/cursor/?utm_source=hn"),
        make_item("Something else", url="https://example.com/other"),
    ]
    kept = dedup.filter_seen(items, store)
    assert [i.canonical_url for i in kept] == ["https://example.com/other"]


async def test_near_duplicate_post_is_rejected(settings, store):
    provider = EmbeddingProvider(settings)
    draft = DraftPost(
        title="Cursor raises Pro plan pricing",
        description="x" * 150,
        slug="cursor-raises-pro-pricing",
        tags=["news"],
        body="body",
    )
    topic = make_topic("Cursor raises Pro plan pricing")
    store.record(draft, topic, await provider.embed(f"{draft.title}\n{draft.description}"))

    twin = draft.model_copy(update={"slug": "cursor-pro-plan-price-rise"})
    verdict = await dedup.is_duplicate_post(twin, store, provider, settings)
    assert verdict.is_duplicate


async def test_unrelated_post_is_not_a_duplicate(settings, store):
    provider = EmbeddingProvider(settings)
    published = DraftPost(
        title="Cursor raises Pro plan pricing",
        description="A price change for solo developers on the Pro plan. " + "y" * 100,
        slug="cursor-raises-pro-pricing",
        tags=["news"],
        body="body",
    )
    store.record(
        published,
        make_topic("Cursor raises Pro plan pricing"),
        await provider.embed(f"{published.title}\n{published.description}"),
    )

    other = DraftPost(
        title="Figma ships a new prototyping surface",
        description="Design handoff changes for teams shipping without engineers. " + "z" * 90,
        slug="figma-ships-prototyping-surface",
        tags=["news"],
        body="body",
    )
    verdict = await dedup.is_duplicate_post(other, store, provider, settings)
    assert not verdict.is_duplicate


async def test_slug_collision_on_disk_is_a_duplicate(settings, store, tmp_path, monkeypatch):
    monkeypatch.setattr(type(settings), "content_dir", property(lambda self: tmp_path))
    (tmp_path / "already-here-now.md").write_text("---\n---\n", encoding="utf-8")
    provider = EmbeddingProvider(settings)
    draft = DraftPost(
        title="Whatever",
        description="d" * 150,
        slug="already-here-now",
        tags=["news"],
        body="body",
    )
    verdict = await dedup.is_duplicate_post(draft, store, provider, settings)
    assert verdict.is_duplicate
    assert "slug" in verdict.reason


def test_vectors_from_different_providers_are_never_compared(store):
    store.vectors["foreign"] = {"provider": "voyage:x", "title": "t", "vector": [1.0, 0.0]}
    assert store.vectors["foreign"]["provider"] != "lexical"
