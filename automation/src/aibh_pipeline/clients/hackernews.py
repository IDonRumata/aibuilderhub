"""Hacker News ingestion via the public Firebase API."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import httpx

from ..logging_setup import get_logger
from ..models import SourceItem, SourceKind
from ..settings import Settings
from .http import get_with_retry

log = get_logger(__name__)

API = "https://hacker-news.firebaseio.com/v0"
ITEM_URL = "https://news.ycombinator.com/item?id={id}"
CONCURRENCY = 8


async def _fetch_item(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    item_id: int,
) -> dict | None:
    async with semaphore:
        try:
            response = await get_with_retry(client, f"{API}/item/{item_id}.json")
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            log.debug("hn_item_failed", item_id=item_id, error=str(exc))
            return None
    return data if isinstance(data, dict) else None


async def fetch_hackernews(
    client: httpx.AsyncClient,
    settings: Settings,
    *,
    name: str = "hackernews",
    listing: str = "topstories",
    limit: int = 60,
    min_points: int = 40,
    weight: float = 1.0,
) -> list[SourceItem]:
    """Pull the current top stories. Never raises."""
    try:
        response = await get_with_retry(client, f"{API}/{listing}.json")
        ids = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("hn_listing_failed", listing=listing, error=str(exc))
        return []

    if not isinstance(ids, list):
        return []

    semaphore = asyncio.Semaphore(CONCURRENCY)
    stories = await asyncio.gather(
        *(_fetch_item(client, semaphore, int(i)) for i in ids[:limit])
    )

    items: list[SourceItem] = []
    for story in stories:
        if not story or story.get("type") != "story" or story.get("dead") or story.get("deleted"):
            continue
        points = float(story.get("score", 0))
        if points < min_points:
            continue
        title = story.get("title") or ""
        # Ask HN and similar self-posts have no external URL; point at the
        # discussion so the writer still has something citable.
        url = story.get("url") or ITEM_URL.format(id=story.get("id"))
        if not title:
            continue
        try:
            items.append(
                SourceItem(
                    title=title,
                    url=url,
                    source=name,
                    kind=SourceKind.HACKERNEWS,
                    published_at=datetime.fromtimestamp(int(story.get("time", 0)), tz=UTC),
                    score_raw=points,
                    comments=int(story.get("descendants", 0) or 0),
                    summary=(story.get("text") or "")[:1200],
                    weight=weight,
                )
            )
        except (ValueError, OSError) as exc:
            log.debug("hn_story_rejected", error=str(exc))

    log.info("hn_fetched", listing=listing, items=len(items))
    return items
