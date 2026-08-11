"""Small text helpers shared by ingest, scoring and dedup.

Deliberately dependency-free so the dedup rules stay easy to unit test.
"""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING_PREFIXES = ("utm_", "mc_", "pk_", "hsa_")
_TRACKING_KEYS = {
    "fbclid", "gclid", "igshid", "ref", "ref_src", "source", "cmpid", "smid",
    "at_medium", "at_campaign", "guccounter", "s", "share_id", "rss",
}

_STOPWORDS = frozenset(
    (
        "a an the and or but of for to in on at by with from as is are was were "
        "be been being this that these those it its it's you your we our they "
        "their he she his her them new now just how what why when who which "
        "more most very can will would could should"
    ).split()
)

_WORD_RE = re.compile(r"[a-z0-9']+")


def canonicalise_url(url: str) -> str:
    """Strip tracking parameters, fragments and trailing slashes from a URL.

    Two links to the same article from two aggregators must collapse to the
    same string, otherwise URL-level dedup silently lets duplicates through.
    """
    parts = urlsplit(url.strip())
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if host.startswith("m.") and host.count(".") >= 2:
        host = host[2:]

    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=False)
        if not k.lower().startswith(_TRACKING_PREFIXES) and k.lower() not in _TRACKING_KEYS
    ]

    path = parts.path.rstrip("/") or "/"
    scheme = "https" if parts.scheme in ("http", "https", "") else parts.scheme
    return urlunsplit((scheme, host, path, urlencode(query), ""))


def normalise_text(text: str) -> str:
    """Lowercase, strip accents and punctuation, collapse whitespace."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(_WORD_RE.findall(stripped.lower()))


def content_words(text: str) -> list[str]:
    """Normalised tokens with stopwords removed."""
    return [w for w in normalise_text(text).split() if w not in _STOPWORDS and len(w) > 2]


def canonical_topic(title: str) -> str:
    """A stable, order-independent fingerprint of what a headline is about.

    "OpenAI ships GPT-5 to everyone" and "GPT-5 ships to all OpenAI users"
    both reduce to the same sorted keyword set.
    """
    words = sorted(set(content_words(title)))
    return " ".join(words)


def char_trigrams(text: str) -> set[str]:
    normalised = normalise_text(text).replace(" ", "")
    if len(normalised) < 3:
        return {normalised} if normalised else set()
    return {normalised[i : i + 3] for i in range(len(normalised) - 2)}


def trigram_overlap(left: str, right: str) -> float:
    """Jaccard-style overlap of character trigrams, in [0, 1].

    Uses the smaller set as the denominator so a short headline contained in a
    longer one still scores high.
    """
    a, b = char_trigrams(left), char_trigrams(right)
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def token_overlap(left: str, right: str) -> float:
    a, b = set(content_words(left)), set(content_words(right))
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def strip_markdown(text: str) -> str:
    """Rough markdown-to-plain-text, good enough for word counts and matching."""
    without_code = re.sub(r"```.*?```", " ", text, flags=re.S)
    without_inline = re.sub(r"`[^`]*`", " ", without_code)
    without_links = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", without_inline)
    without_marks = re.sub(r"[*_>#]+", " ", without_links)
    return " ".join(without_marks.split())
