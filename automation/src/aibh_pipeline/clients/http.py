"""Shared HTTP plumbing: one client, one timeout policy, one retry policy."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..logging_setup import get_logger
from ..settings import Settings

log = get_logger(__name__)

RETRYABLE = (httpx.TransportError, httpx.HTTPStatusError)


@asynccontextmanager
async def http_client(settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    """An httpx client with the project's User-Agent and timeout.

    Reddit rejects requests without a descriptive User-Agent, and every
    external call in this pipeline must have a timeout.
    """
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(settings.http_timeout_seconds),
        headers={"User-Agent": settings.user_agent, "Accept-Encoding": "gzip"},
        follow_redirects=True,
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
    ) as client:
        yield client


@retry(
    retry=retry_if_exception_type(RETRYABLE),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
async def get_with_retry(client: httpx.AsyncClient, url: str, **kwargs: object) -> httpx.Response:
    """GET with three attempts and exponential backoff.

    4xx responses other than 429 are not worth retrying, so they are raised
    immediately instead of burning the retry budget.
    """
    response = await client.get(url, **kwargs)  # type: ignore[arg-type]
    if 400 <= response.status_code < 500 and response.status_code != 429:
        response.raise_for_status()
    response.raise_for_status()
    return response


async def url_is_alive(client: httpx.AsyncClient, url: str) -> bool:
    """HEAD (falling back to a ranged GET) to check an external link resolves."""
    try:
        response = await client.head(url)
        if response.status_code == 405 or response.status_code >= 400:
            response = await client.get(url, headers={"Range": "bytes=0-2048"})
        return response.status_code < 400
    except httpx.HTTPError as exc:
        log.warning("link_check_failed", url=url, error=str(exc))
        return False
