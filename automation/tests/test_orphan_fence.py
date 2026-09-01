"""An unclosed code fence must never reach the reviewers.

The body arrives as markdown inside a JSON string and the model sometimes
opens a fence it never closes, which makes markdown render the rest of the
article as a code block. On 1 September all three critics flagged the same
stray fence and the writer could not remove it across three revision rounds,
because "remove the stray backtick" does not say which one.
"""

from __future__ import annotations

from aibh_pipeline.textutil import drop_orphan_code_fence

WITH_ORPHAN = "## What shipped\n\nVercel added an adapter.\n\n```\n\nIt talks over the wire.\n"

BALANCED = (
    "## What shipped\n\n"
    "Wire it up like this:\n\n"
    "```bash\n"
    "npm i @ai-sdk/fx\n"
    "```\n\n"
    "That is the whole setup.\n"
)


def test_an_unclosed_fence_is_removed():
    cleaned = drop_orphan_code_fence(WITH_ORPHAN)
    assert "```" not in cleaned
    assert "It talks over the wire." in cleaned
    assert "Vercel added an adapter." in cleaned


def test_a_real_code_block_is_left_alone():
    assert drop_orphan_code_fence(BALANCED) == BALANCED


def test_a_body_with_no_fences_is_untouched():
    plain = "## Heading\n\nJust prose here.\n"
    assert drop_orphan_code_fence(plain) == plain


def test_the_writer_cleans_the_draft_before_anyone_reviews_it():
    from tests.conftest import make_topic

    from aibh_pipeline.services.writer import _to_draft

    draft = _to_draft(
        {
            "title": "Vercel ships an adapter",
            "description": "A short description of what shipped and who should care about it.",
            "slug": "vercel-ships-an-adapter",
            "tags": ["news"],
            "body": WITH_ORPHAN,
        },
        make_topic("Vercel ships an adapter"),
    )
    assert "```" not in draft.body
