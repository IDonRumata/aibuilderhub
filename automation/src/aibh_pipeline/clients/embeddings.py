"""Embeddings for semantic deduplication.

Two providers behind one interface:

* ``voyage``  - the hosted API, used when VOYAGE_API_KEY is present.
* ``lexical`` - a deterministic hashed bag-of-features vector computed locally.

The lexical provider needs no key, no model download and no network, which is
what makes the dedup check runnable in CI and in tests. It catches near-
duplicate wording well; it does not catch a full paraphrase, which is why
dedup also compares canonical URLs and title trigrams.

Vectors from different providers are never compared: each stored vector
records which provider produced it.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter

import httpx

from ..logging_setup import get_logger
from ..settings import Settings
from ..textutil import char_trigrams, content_words
from .http import get_with_retry  # noqa: F401  (kept for symmetry of imports)

log = get_logger(__name__)

LEXICAL_DIMENSIONS = 512
VOYAGE_URL = "https://api.voyageai.com/v1/embeddings"


def cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    norm_l = math.sqrt(sum(a * a for a in left))
    norm_r = math.sqrt(sum(b * b for b in right))
    if norm_l == 0 or norm_r == 0:
        return 0.0
    return dot / (norm_l * norm_r)


def _bucket(token: str) -> int:
    digest = hashlib.sha512(token.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % LEXICAL_DIMENSIONS


def lexical_embedding(text: str) -> list[float]:
    """A hashed, L2-normalised bag of words and character trigrams."""
    counts: Counter[int] = Counter()
    for word in content_words(text):
        counts[_bucket(f"w:{word}")] += 3
    for trigram in char_trigrams(text):
        counts[_bucket(f"t:{trigram}")] += 1

    vector = [0.0] * LEXICAL_DIMENSIONS
    for index, count in counts.items():
        # Sub-linear weighting keeps a repeated word from dominating.
        vector[index] = 1.0 + math.log(count)

    norm = math.sqrt(sum(v * v for v in vector))
    return [v / norm for v in vector] if norm else vector


class EmbeddingProvider:
    """Chooses the hosted provider when a key is configured, else lexical."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._voyage_available = settings.voyage_api_key is not None

    @property
    def name(self) -> str:
        return f"voyage:{self._settings.voyage_model}" if self._voyage_available else "lexical"

    @property
    def threshold(self) -> float:
        return (
            self._settings.semantic_dupe_threshold
            if self._voyage_available
            else self._settings.lexical_dupe_threshold
        )

    async def embed(self, text: str) -> tuple[str, list[float]]:
        """Return ``(provider_name, vector)``.

        A hosted-provider failure degrades to the lexical vector rather than
        failing the run; the provider name recorded alongside the vector keeps
        the two from ever being compared.
        """
        if self._voyage_available:
            try:
                return f"voyage:{self._settings.voyage_model}", await self._embed_voyage(text)
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                log.warning("voyage_embedding_failed", error=str(exc))
                self._voyage_available = False
        return "lexical", lexical_embedding(text)

    async def _embed_voyage(self, text: str) -> list[float]:
        settings = self._settings
        key = settings.voyage_api_key
        assert key is not None
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(settings.http_timeout_seconds),
            headers={
                "Authorization": f"Bearer {key.get_secret_value()}",
                "Content-Type": "application/json",
                "User-Agent": settings.user_agent,
            },
        ) as client:
            response = await client.post(
                VOYAGE_URL,
                json={
                    "input": [text],
                    "model": settings.voyage_model,
                    "input_type": "document",
                },
            )
            response.raise_for_status()
            payload = response.json()
        return [float(v) for v in payload["data"][0]["embedding"]]
