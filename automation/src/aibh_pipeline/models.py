"""Pydantic models shared by every stage of the pipeline."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class SourceKind(StrEnum):
    RSS = "rss"
    HACKERNEWS = "hackernews"
    REDDIT = "reddit"


class SourceItem(BaseModel):
    """One candidate story as it came out of an external feed or API."""

    model_config = ConfigDict(frozen=True)

    title: str
    url: HttpUrl
    source: str
    kind: SourceKind
    published_at: datetime
    # Raw popularity signal in the source's own units (HN points, Reddit
    # upvotes, 0 for plain RSS which carries no engagement data).
    score_raw: float = 0.0
    comments: int = 0
    summary: str = ""
    # Per-source multiplier from sources.yaml.
    weight: float = 1.0
    # False when the feed carried no vote data at all, which is different from
    # "nobody voted". Reddit blocks the unauthenticated JSON endpoint from many
    # networks and the RSS fallback has no counts, so those items would
    # otherwise look identical to a post that genuinely flopped.
    engagement_measured: bool = True

    @field_validator("published_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    @field_validator("title", "summary")
    @classmethod
    def _clean(cls, value: str) -> str:
        return " ".join(value.split())

    def age_hours(self, *, now: datetime | None = None) -> float:
        reference = now or datetime.now(UTC)
        return max(0.0, (reference - self.published_at).total_seconds() / 3600.0)

    @property
    def canonical_url(self) -> str:
        """URL stripped of tracking parameters, used as the dedup key."""
        from .textutil import canonicalise_url

        return canonicalise_url(str(self.url))


class ScoredTopic(BaseModel):
    """A cluster of source items that all cover the same story."""

    key: str
    title: str
    score: float
    items: list[SourceItem] = Field(min_length=1)

    @property
    def primary(self) -> SourceItem:
        return self.items[0]

    @property
    def source_urls(self) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for item in self.items:
            url = item.canonical_url
            if url not in seen:
                seen.add(url)
                out.append(url)
        return out

    @property
    def distinct_sources(self) -> int:
        return len({item.source for item in self.items})


class DraftPost(BaseModel):
    """A generated post before it is written to disk."""

    title: str
    description: str
    slug: str
    tags: list[str]
    body: str
    source_urls: list[str] = Field(default_factory=list)

    @field_validator("tags")
    @classmethod
    def _news_first(cls, tags: list[str]) -> list[str]:
        rest = [t for t in tags if t != "news"]
        return ["news", *rest]

    @property
    def word_count(self) -> int:
        return len(self.body.split())

    @property
    def content_hash(self) -> str:
        payload = f"{self.title}\n{self.description}\n{self.body}".encode()
        return hashlib.sha512(payload).hexdigest()[:32]


class Verdict(StrEnum):
    PASS = "PASS"
    REVISE = "REVISE"
    REJECT = "REJECT"


class CritiqueIssue(BaseModel):
    """One concrete problem a critic found, with the exact text to change."""

    quote: str = ""
    requirement: str
    severity: Literal["minor", "major", "blocking"] = "major"


class CritiqueReport(BaseModel):
    critic: str = ""
    verdict: Verdict
    issues: list[CritiqueIssue] = Field(default_factory=list)
    notes: str = ""

    @property
    def blocking(self) -> bool:
        return self.verdict is Verdict.REJECT


class PublishedTopic(BaseModel):
    """A row in state/published_topics.json."""

    slug: str
    canonical_topic: str
    title: str
    source_urls: list[str] = Field(default_factory=list)
    content_hash: str = ""
    published_at: datetime

    @field_validator("published_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class PublishResult(BaseModel):
    path: str
    slug: str
    title: str
    word_count: int
    source_urls: list[str]
    critic_rounds: int
    llm_calls: int
