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
    # Enough material by default that scoring's "too thin to write from" gate
    # does not silently drop every fixture; tests about that gate pass their
    # own short summary explicitly.
    summary: str = (
        "A reported story with enough detail to write from: what shipped, who "
        "it is for, what it costs, and how it compares with the alternatives "
        "that solo builders already pay for. Includes the vendor's own framing, "
        "the pricing page as it stood on the day, and the first round of "
        "independent reaction from people who actually tried it in anger, "
        "including the two complaints that came up more than once and the "
        "one thing every reviewer agreed the vendor got right this time."
    ),
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
