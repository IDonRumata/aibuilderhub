"""Reddit ingestion via the public JSON endpoints (no OAuth).

Reddit tolerates a handful of unauthenticated requests a day as long as the
User-Agent identifies the client, but it can tighten the rules at any time.
Every failure mode here degrades to an empty list so the pipeline survives
losing this source entirely.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from ..logging_setup import get_logger
from ..models import SourceItem, SourceKind
from ..settings import Settings
from .http import get_with_retry

log = get_logger(__name__)

LISTING = "https://www.reddit.com/r/{subreddit}/{sort}.json"
RSS_LISTING = "https://www.reddit.com/r/{subreddit}/{sort}.rss"
PERMALINK = "https://www.reddit.com{path}"


async def fetch_subreddit(
    client: httpx.AsyncClient,
    settings: Settings,
    *,
    subreddit: str,
    sort: str = "top",
    period: str = "day",
    limit: int = 25,
    min_upvotes: int = 25,
    weight: float = 1.0,
) -> list[SourceItem]:
    """Pull one subreddit listing. Never raises."""
    params = {"limit": str(limit), "raw_json": "1"}
    if sort == "top":
        params["t"] = period

    try:
        response = await get_with_retry(
            client, LISTING.format(subreddit=subreddit, sort=sort), params=params
        )
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        # Reddit blocks the unauthenticated JSON endpoint from many networks
        # (403) while still serving the RSS view of the same listing. The RSS
        # version carries no vote counts, so those items score on relevance
        # and freshness alone — still better than losing the source.
        log.warning("reddit_json_blocked", subreddit=subreddit, error=str(exc))
        return await _fetch_via_rss(
            client, settings, subreddit=subreddit, sort=sort, period=period, weight=weight
        )

    children = payload.get("data", {}).get("children", []) if isinstance(payload, dict) else []

    items: list[SourceItem] = []
    for child in children:
        post = child.get("data", {}) if isinstance(child, dict) else {}
        if post.get("stickied") or post.get("over_18") or post.get("removed_by_category"):
            continue
        upvotes = float(post.get("ups", 0) or 0)
        if upvotes < min_upvotes:
            continue
        title = post.get("title") or ""
        if not title:
            continue

        # Link posts point outward; self posts only have their permalink.
        url = post.get("url_overridden_by_dest") or ""
        if not url or post.get("is_self"):
            url = PERMALINK.format(path=post.get("permalink", ""))
        if not url.startswith("http"):
            continue

        try:
            items.append(
                SourceItem(
                    title=title,
                    url=url,
                    source=f"r/{subreddit}",
                    kind=SourceKind.REDDIT,
                    published_at=datetime.fromtimestamp(
                        int(post.get("created_utc", 0)), tz=UTC
                    ),
                    score_raw=upvotes,
                    comments=int(post.get("num_comments", 0) or 0),
                    summary=(post.get("selftext") or "")[:1200],
                    weight=weight,
                )
            )
        except (ValueError, OSError) as exc:
            log.debug("reddit_post_rejected", subreddit=subreddit, error=str(exc))

    log.info("reddit_fetched", subreddit=subreddit, items=len(items), via="json")
    return items


async def _fetch_via_rss(
    client: httpx.AsyncClient,
    settings: Settings,
    *,
    subreddit: str,
    sort: str,
    period: str,
    weight: float,
) -> list[SourceItem]:
    """Fallback path: the same listing as an Atom feed."""
    from .rss import fetch_feed

    url = RSS_LISTING.format(subreddit=subreddit, sort=sort)
    if sort == "top":
        url = f"{url}?t={period}"

    items = await fetch_feed(
        client, settings, name=f"r/{subreddit}", url=url, weight=weight
    )
    # fetch_feed tags everything as RSS; correct the kind so scoring applies
    # the right engagement reference for this platform.
    return [item.model_copy(update={"kind": SourceKind.REDDIT}) for item in items]
