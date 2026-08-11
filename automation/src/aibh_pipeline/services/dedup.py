"""Two-level deduplication.

Level 1, at ingest: any candidate whose canonical URL has already been
processed is dropped before it can reach scoring.

Level 2, before publication: the new post's title plus description is compared
against every published post by cosine similarity, by character-trigram
overlap of the titles, and by filesystem slug collision.

Reference posts (the tool reviews and comparisons already on the site) are
loaded into the same index, so "Cursor raised its prices" stays publishable
while "a review of Cursor" is correctly caught as a duplicate.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ..clients.embeddings import EmbeddingProvider, cosine
from ..logging_setup import get_logger
from ..models import DraftPost, PublishedTopic, ScoredTopic, SourceItem
from ..settings import Settings
from ..textutil import canonical_topic, canonicalise_url, trigram_overlap
from .site import ExistingPost

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class DuplicateVerdict:
    is_duplicate: bool
    reason: str = ""
    against: str = ""
    score: float = 0.0


class StateStore:
    """JSON-backed registry of what has already been published."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.topics: list[PublishedTopic] = []
        self.vectors: dict[str, dict[str, object]] = {}
        self._load()

    # ------------------------------------------------------------------ #

    def _load(self) -> None:
        topics_path = self._settings.published_topics_file
        if topics_path.exists():
            try:
                raw = json.loads(topics_path.read_text(encoding="utf-8"))
                self.topics = [PublishedTopic.model_validate(entry) for entry in raw]
            except (json.JSONDecodeError, ValueError) as exc:
                log.error("state_topics_unreadable", error=str(exc))
                self.topics = []

        vectors_path = self._settings.embeddings_file
        if vectors_path.exists():
            try:
                self.vectors = json.loads(vectors_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                log.error("state_vectors_unreadable", error=str(exc))
                self.vectors = {}

        log.info("state_loaded", topics=len(self.topics), vectors=len(self.vectors))

    def save(self) -> None:
        self._settings.state_dir.mkdir(parents=True, exist_ok=True)
        self._settings.published_topics_file.write_text(
            json.dumps(
                [json.loads(t.model_dump_json()) for t in self.topics],
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        self._settings.embeddings_file.write_text(
            json.dumps(self.vectors, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        log.info("state_saved", topics=len(self.topics), vectors=len(self.vectors))

    # ------------------------------------------------------------------ #

    @property
    def seen_urls(self) -> set[str]:
        return {url for topic in self.topics for url in topic.source_urls}

    @property
    def known_slugs(self) -> set[str]:
        return {topic.slug for topic in self.topics}

    def record(self, draft: DraftPost, topic: ScoredTopic, vector: tuple[str, list[float]]) -> None:
        provider, values = vector
        self.topics.append(
            PublishedTopic(
                slug=draft.slug,
                canonical_topic=canonical_topic(draft.title),
                title=draft.title,
                source_urls=topic.source_urls,
                content_hash=draft.content_hash,
                published_at=datetime.now(UTC),
            )
        )
        self.vectors[draft.slug] = {
            "provider": provider,
            "title": draft.title,
            "vector": values,
        }


def filter_seen(items: list[SourceItem], store: StateStore) -> list[SourceItem]:
    """Level 1: drop candidates whose source URL was already covered."""
    seen = {canonicalise_url(url) for url in store.seen_urls}
    kept = [item for item in items if item.canonical_url not in seen]
    dropped = len(items) - len(kept)
    if dropped:
        log.info("dedup_url_filter", dropped=dropped, kept=len(kept))
    return kept


async def index_existing_posts(
    posts: list[ExistingPost],
    store: StateStore,
    provider: EmbeddingProvider,
) -> None:
    """Make sure every post already on the site has a vector in the index.

    Without this, the first automated run would happily publish a duplicate of
    one of the twenty-odd hand-written reviews.
    """
    added = 0
    for post in posts:
        entry = store.vectors.get(post.slug)
        if entry and entry.get("provider") == provider.name:
            continue
        name, values = await provider.embed(f"{post.title}\n{post.description}")
        store.vectors[post.slug] = {
            "provider": name,
            "title": post.title,
            "vector": values,
        }
        added += 1
    if added:
        log.info("existing_posts_indexed", added=added, provider=provider.name)


async def is_duplicate_topic(
    topic: ScoredTopic,
    store: StateStore,
    provider: EmbeddingProvider,
    settings: Settings,
) -> DuplicateVerdict:
    """Check a candidate topic before spending any tokens writing it."""
    return await _compare(
        text=f"{topic.title}\n{topic.primary.summary[:400]}",
        title=topic.title,
        store=store,
        provider=provider,
        settings=settings,
    )


async def is_duplicate_post(
    draft: DraftPost,
    store: StateStore,
    provider: EmbeddingProvider,
    settings: Settings,
) -> DuplicateVerdict:
    """Final check on the finished post, including a slug collision test."""
    if (settings.content_dir / f"{draft.slug}.md").exists():
        return DuplicateVerdict(True, "slug already exists on disk", draft.slug, 1.0)
    if draft.slug in store.known_slugs:
        return DuplicateVerdict(True, "slug already in the published registry", draft.slug, 1.0)
    return await _compare(
        text=f"{draft.title}\n{draft.description}",
        title=draft.title,
        store=store,
        provider=provider,
        settings=settings,
    )


async def _compare(
    *,
    text: str,
    title: str,
    store: StateStore,
    provider: EmbeddingProvider,
    settings: Settings,
) -> DuplicateVerdict:
    name, vector = await provider.embed(text)

    best_score = 0.0
    best_slug = ""
    for slug, entry in store.vectors.items():
        if entry.get("provider") != name:
            continue
        score = cosine(vector, [float(v) for v in entry.get("vector", [])])  # type: ignore[arg-type]
        if score > best_score:
            best_score, best_slug = score, slug

    if best_score >= provider.threshold:
        return DuplicateVerdict(
            True,
            f"semantic similarity {best_score:.3f} >= {provider.threshold}",
            best_slug,
            best_score,
        )

    for slug, entry in store.vectors.items():
        overlap = trigram_overlap(title, str(entry.get("title", "")))
        if overlap > settings.trigram_dupe_threshold:
            return DuplicateVerdict(
                True,
                f"title trigram overlap {overlap:.2f} > {settings.trigram_dupe_threshold}",
                slug,
                overlap,
            )

    return DuplicateVerdict(False, "", best_slug, best_score)


def state_paths(settings: Settings) -> list[Path]:
    return [settings.published_topics_file, settings.embeddings_file]
