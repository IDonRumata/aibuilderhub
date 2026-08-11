from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-used")

from aibh_pipeline.models import ScoredTopic, SourceItem, SourceKind
from aibh_pipeline.services.humanizer import load_rules
from aibh_pipeline.settings import get_settings


@pytest.fixture(scope="session")
def settings():
    return get_settings()


@pytest.fixture(scope="session")
def rules(settings):
    return load_rules(settings.banned_patterns_file)


@pytest.fixture(scope="session")
def sources_config(settings):
    from aibh_pipeline.services.ingest import load_sources

    return load_sources(settings.sources_file)


def make_item(
    title: str,
    *,
    url: str = "https://example.com/a",
    source: str = "hackernews",
    kind: SourceKind = SourceKind.HACKERNEWS,
    score: float = 100.0,
    summary: str = "",
    hours_old: float = 1.0,
    weight: float = 1.0,
) -> SourceItem:
    published = datetime.now(UTC).timestamp() - hours_old * 3600
    return SourceItem(
        title=title,
        url=url,
        source=source,
        kind=kind,
        published_at=datetime.fromtimestamp(published, tz=UTC),
        score_raw=score,
        summary=summary,
        weight=weight,
    )


def make_topic(title: str, **kwargs) -> ScoredTopic:
    item = make_item(title, **kwargs)
    return ScoredTopic(key=title.lower(), title=title, score=1.0, items=[item])
