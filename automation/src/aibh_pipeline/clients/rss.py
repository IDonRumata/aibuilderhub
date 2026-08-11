"""RSS/Atom ingestion: feedparser for parsing, httpx for transport."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from time import struct_time

import feedparser
import httpx

from ..logging_setup import get_logger
from ..models import SourceItem, SourceKind
from ..settings import Settings
from .http import get_with_retry

log = get_logger(__name__)

MAX_ITEMS_PER_FEED = 25


def _to_datetime(parsed: struct_time | None) -> datetime | None:
    if not parsed:
        return None
    try:
        return datetime(*parsed[:6], tzinfo=UTC)
    except (TypeError, ValueError):
        return None


def _summary_of(entry: object) -> str:
    for attr in ("summary", "description"):
        value = getattr(entry, attr, "")
        if value:
            # feedparser hands back HTML; strip it crudely, the writer only
            # ever sees a short factual gist anyway.
            import re

            return re.sub(r"<[^>]+>", " ", value)[:1200]
    return ""


async def fetch_feed(
    client: httpx.AsyncClient,
    settings: Settings,
    *,
    name: str,
    url: str,
    weight: float,
) -> list[SourceItem]:
    """Fetch and parse one feed. Never raises: a dead feed is a skipped feed."""
    try:
        response = await get_with_retry(client, url)
    except httpx.HTTPError as exc:
        log.warning("feed_fetch_failed", feed=name, url=url, error=str(exc))
        return []

    # feedparser is CPU-bound and synchronous; keep the event loop free.
    parsed = await asyncio.to_thread(feedparser.parse, response.content)
    if getattr(parsed, "bozo", 0) and not parsed.entries:
        log.warning("feed_unparseable", feed=name, url=url)
        return []

    now = datetime.now(UTC)
    items: list[SourceItem] = []
    for entry in parsed.entries[:MAX_ITEMS_PER_FEED]:
        link = getattr(entry, "link", "")
        title = getattr(entry, "title", "")
        if not link or not title:
            continue
        published = _to_datetime(
            getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
        )
        try:
            items.append(
                SourceItem(
                    title=title,
                    url=link,
                    source=name,
                    kind=SourceKind.RSS,
                    published_at=published or now,
                    summary=_summary_of(entry),
                    weight=weight,
                )
            )
        except ValueError as exc:  # malformed URL in the feed
            log.debug("feed_entry_rejected", feed=name, error=str(exc))

    log.info("feed_fetched", feed=name, items=len(items))
    return items
