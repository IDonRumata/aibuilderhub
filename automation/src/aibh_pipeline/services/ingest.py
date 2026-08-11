"""Collect candidate stories from every configured source, concurrently."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from ..clients.hackernews import fetch_hackernews
from ..clients.http import http_client
from ..clients.reddit import fetch_subreddit
from ..clients.rss import fetch_feed
from ..logging_setup import get_logger
from ..models import SourceItem
from ..settings import Settings

log = get_logger(__name__)


def load_sources(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


async def ingest(settings: Settings, config: dict[str, Any]) -> list[SourceItem]:
    """Fetch every source in parallel and return deduplicated candidates.

    A source that raises is logged and dropped; losing one feed must never
    take down the run.
    """
    async with http_client(settings) as client:
        tasks: list[asyncio.Task[list[SourceItem]]] = []

        for feed in config.get("rss") or []:
            tasks.append(
                asyncio.create_task(
                    fetch_feed(
                        client,
                        settings,
                        name=feed["name"],
                        url=feed["url"],
                        weight=float(feed.get("weight", 1.0)),
                    )
                )
            )

        for hn in config.get("hackernews") or []:
            tasks.append(
                asyncio.create_task(
                    fetch_hackernews(
                        client,
                        settings,
                        name=hn.get("name", "hackernews"),
                        listing=hn.get("listing", "topstories"),
                        limit=int(hn.get("limit", 60)),
                        min_points=int(hn.get("min_points", 40)),
                        weight=float(hn.get("weight", 1.0)),
                    )
                )
            )

        for sub in config.get("reddit") or []:
            tasks.append(
                asyncio.create_task(
                    fetch_subreddit(
                        client,
                        settings,
                        subreddit=sub["subreddit"],
                        sort=sub.get("sort", "top"),
                        period=sub.get("period", "day"),
                        limit=int(sub.get("limit", 25)),
                        min_upvotes=int(sub.get("min_upvotes", 25)),
                        weight=float(sub.get("weight", 1.0)),
                    )
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)

    items: list[SourceItem] = []
    failed = 0
    for result in results:
        if isinstance(result, BaseException):
            failed += 1
            log.warning("source_failed", error=str(result))
            continue
        items.extend(result)

    fresh = _within_window(items, settings.lookback_hours)
    deduped = _dedupe_by_url(fresh)

    log.info(
        "ingest_complete",
        sources=len(results),
        failed=failed,
        raw=len(items),
        fresh=len(fresh),
        deduped=len(deduped),
    )
    return deduped[: settings.max_candidates]


def _within_window(items: list[SourceItem], hours: int) -> list[SourceItem]:
    now = datetime.now(UTC)
    return [item for item in items if item.age_hours(now=now) <= hours]


def _dedupe_by_url(items: list[SourceItem]) -> list[SourceItem]:
    """Keep the highest-signal item per canonical URL.

    The same story often arrives from several aggregators; keeping the copy
    with the strongest engagement number preserves the scoring signal.
    """
    best: dict[str, SourceItem] = {}
    for item in items:
        key = item.canonical_url
        current = best.get(key)
        if current is None or item.score_raw > current.score_raw:
            best[key] = item
    return sorted(best.values(), key=lambda i: i.score_raw, reverse=True)
