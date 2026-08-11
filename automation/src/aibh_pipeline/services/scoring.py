"""Cluster candidates into topics and rank them by expected virality.

Everything here is deterministic arithmetic — no LLM call. Topic selection
runs on every candidate, so putting a model in this loop would blow the
per-run budget for no gain.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

from ..logging_setup import get_logger
from ..models import ScoredTopic, SourceItem, SourceKind
from ..settings import Settings
from ..textutil import (
    canonical_topic,
    content_words,
    normalise_text,
    token_overlap,
    trigram_overlap,
)

log = get_logger(__name__)

# Two headlines are the same story when they share most of their content
# words, or most of their character trigrams (which survives rewording).
SAME_STORY_TOKEN_OVERLAP = 0.62
SAME_STORY_TRIGRAM_OVERLAP = 0.72

# Engagement counts differ by orders of magnitude between platforms, so each
# is normalised against a reference value that reads as "this did well here".
REFERENCE_ENGAGEMENT: dict[SourceKind, float] = {
    SourceKind.HACKERNEWS: 300.0,
    SourceKind.REDDIT: 400.0,
    SourceKind.RSS: 0.0,
}

WEIGHTS = {
    "engagement": 3.0,
    "freshness": 2.0,
    "corroboration": 2.5,
    "niche": 4.0,
    "source": 1.0,
}


def cluster(items: list[SourceItem]) -> list[list[SourceItem]]:
    """Group items that cover the same story.

    Greedy single-pass clustering against cluster heads. With at most a few
    hundred candidates this is fast enough and easy to reason about.
    """
    clusters: list[list[SourceItem]] = []
    for item in items:
        for group in clusters:
            if _same_story(item.title, group[0].title):
                group.append(item)
                break
        else:
            clusters.append([item])
    return clusters


def _shares_a_subject(left: str, right: str) -> bool:
    """Guard against merging two stories that only share a predicate.

    "Lovable ships a no-code database builder" and "Replit ships a no-code
    database builder" overlap on four of five content words but are different
    stories. Requiring one headline's leading subject to appear in the other
    keeps them apart, while still merging "Muse Glimmer: 30B-parameter model"
    with "Introducing Muse Glimmer".
    """
    left_words = content_words(left)
    right_words = content_words(right)
    if not left_words or not right_words:
        return False
    return left_words[0] in set(right_words) or right_words[0] in set(left_words)


def _same_story(left: str, right: str) -> bool:
    similar = (
        token_overlap(left, right) >= SAME_STORY_TOKEN_OVERLAP
        or trigram_overlap(left, right) >= SAME_STORY_TRIGRAM_OVERLAP
    )
    return similar and _shares_a_subject(left, right)


def _engagement_score(items: list[SourceItem]) -> float:
    """Log-compressed best engagement signal in the cluster, in [0, 1]."""
    best = 0.0
    for item in items:
        reference = REFERENCE_ENGAGEMENT.get(item.kind, 0.0)
        if reference <= 0 or item.score_raw <= 0:
            continue
        # log1p keeps a 5000-point story from swamping a 400-point one.
        best = max(best, math.log1p(item.score_raw) / math.log1p(reference))
    return min(1.0, best)


def _freshness_score(items: list[SourceItem], *, lookback_hours: int, now: datetime) -> float:
    youngest = min(item.age_hours(now=now) for item in items)
    return max(0.0, 1.0 - youngest / max(1, lookback_hours))


def _corroboration_score(items: list[SourceItem]) -> float:
    """Reward stories that more than one outlet picked up."""
    distinct = len({item.source for item in items})
    if distinct <= 1:
        return 0.0
    return min(1.0, math.log2(distinct) / 2.0)


def _niche_score(items: list[SourceItem], niche: dict[str, list[str]]) -> float:
    """Relevance to AI tools / vibe coding / no-code / solo founders.

    Returns a value in [-1, 1]; off-niche stories go negative so they cannot
    win on engagement alone.
    """
    haystack = normalise_text(
        " ".join(f"{item.title} {item.summary}" for item in items)
    )

    def hits(bucket: str) -> int:
        return sum(1 for phrase in niche.get(bucket, []) if normalise_text(phrase) in haystack)

    positive = (
        min(hits("core"), 3) * 0.30
        + min(hits("tools"), 3) * 0.22
        + min(hits("adjacent"), 3) * 0.10
    )
    negative = min(hits("penalty"), 3) * 0.45
    return max(-1.0, min(1.0, positive - negative))


def _source_score(items: list[SourceItem]) -> float:
    return min(1.0, max(item.weight for item in items) / 1.5)


def score_topics(
    items: list[SourceItem],
    config: dict[str, Any],
    settings: Settings,
    *,
    now: datetime | None = None,
) -> list[ScoredTopic]:
    """Cluster then rank. Returns topics sorted best-first."""
    reference = now or datetime.now(UTC)
    niche = config.get("niche") or {}

    topics: list[ScoredTopic] = []
    off_niche = 0
    for group in cluster(items):
        ordered = sorted(
            group, key=lambda i: (i.score_raw, -i.age_hours(now=reference)), reverse=True
        )

        # Relevance is a gate, not a bonus. A 600-point Hacker News story about
        # telemarketing law will out-score an on-topic one on engagement alone,
        # and publishing it would be worse than publishing nothing.
        niche_score = _niche_score(ordered, niche)
        if niche_score < settings.min_niche_score:
            off_niche += 1
            continue

        components = {
            "engagement": _engagement_score(ordered),
            "freshness": _freshness_score(
                ordered, lookback_hours=settings.lookback_hours, now=reference
            ),
            "corroboration": _corroboration_score(ordered),
            "niche": niche_score,
            "source": _source_score(ordered),
        }
        total = sum(WEIGHTS[key] * value for key, value in components.items())

        topics.append(
            ScoredTopic(
                key=canonical_topic(ordered[0].title),
                title=ordered[0].title,
                score=round(total, 4),
                items=ordered,
            )
        )

    topics.sort(key=lambda t: t.score, reverse=True)
    log.info(
        "scoring_complete",
        candidates=len(items),
        topics=len(topics),
        dropped_off_niche=off_niche,
        top=[{"title": t.title[:80], "score": t.score} for t in topics[:5]],
    )
    return topics
