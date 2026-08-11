from __future__ import annotations

import pytest

from aibh_pipeline.textutil import (
    canonical_topic,
    canonicalise_url,
    strip_markdown,
    token_overlap,
    trigram_overlap,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://www.example.com/post/", "https://example.com/post"),
        ("http://Example.com/post?utm_source=hn", "https://example.com/post"),
        ("https://example.com/post#section", "https://example.com/post"),
        ("https://example.com/post?id=7&fbclid=abc", "https://example.com/post?id=7"),
        ("https://m.example.com/post", "https://example.com/post"),
    ],
)
def test_canonicalise_url_strips_noise(raw, expected):
    assert canonicalise_url(raw) == expected


def test_canonical_topic_is_order_independent():
    left = canonical_topic("OpenAI ships GPT-5 to every user")
    right = canonical_topic("GPT-5 ships to every OpenAI user")
    assert left == right


def test_trigram_overlap_detects_rewording():
    assert trigram_overlap("Cursor raises its prices", "Cursor raises prices") > 0.8
    assert trigram_overlap("Cursor raises its prices", "Bubble adds a new editor") < 0.4


def test_token_overlap_ignores_stopwords():
    assert token_overlap("The Lovable editor is broken", "Lovable editor broken") == 1.0


def test_strip_markdown_removes_links_and_code():
    text = "See [the docs](https://x.dev) and `run()`.\n\n```py\nprint(1)\n```"
    plain = strip_markdown(text)
    assert "https://x.dev" not in plain
    assert "print(1)" not in plain
    assert "the docs" in plain
