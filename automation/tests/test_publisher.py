from __future__ import annotations

from datetime import UTC, datetime

import pytest
import yaml
from tests.conftest import make_topic

from aibh_pipeline.models import DraftPost
from aibh_pipeline.services import critics, publisher

NOW = datetime(2026, 8, 11, tzinfo=UTC)


def make_draft(**overrides) -> DraftPost:
    base = {
        "title": "Cursor adds an agent mode for solo builders",
        "description": (
            "Cursor's agent mode batches a refactor into one review instead of "
            "file-by-file approval. What it changes for a solo builder, and what it does not."
        ),
        "slug": "cursor-adds-agent-mode",
        "tags": ["news", "cursor", "ai-coding"],
        "body": "## TL;DR\n\nIt's worth 20 minutes.\n",
        "source_urls": ["https://example.com/cursor"],
    }
    return DraftPost(**{**base, **overrides})


def test_frontmatter_matches_the_content_collection_schema():
    text = publisher.build_frontmatter(make_draft(), publish_date=NOW, is_draft=False)
    publisher.validate_frontmatter(text + "\nbody\n")

    data = yaml.safe_load(text.split("---")[1])
    assert data["pubDate"] == "2026-08-11"
    assert data["author"] == publisher.POST_AUTHOR
    assert data["draft"] is False
    assert data["tags"][0] == "news"


def test_frontmatter_quotes_titles_containing_colons():
    draft = make_draft(title="Cursor: what changed")
    text = publisher.build_frontmatter(draft, publish_date=NOW, is_draft=True)
    assert yaml.safe_load(text.split("---")[1])["title"] == "Cursor: what changed"


def test_validate_rejects_a_missing_news_tag():
    draft = make_draft(tags=["cursor", "news"])
    # The model validator forces "news" first, so build the bad document by hand.
    bad = (
        "---\ntitle: t\ndescription: d\npubDate: 2026-08-11\n"
        "tags:\n  - cursor\nauthor: A\ndraft: false\n---\nbody\n"
    )
    with pytest.raises(ValueError, match="news"):
        publisher.validate_frontmatter(bad)
    assert draft.tags[0] == "news"


def test_validate_rejects_missing_fields():
    with pytest.raises(ValueError, match="missing"):
        publisher.validate_frontmatter("---\ntitle: t\n---\nbody\n")


def test_publish_writes_the_file_and_refuses_to_overwrite(settings, tmp_path, monkeypatch):
    monkeypatch.setattr(type(settings), "content_dir", property(lambda self: tmp_path))
    monkeypatch.setattr(settings, "repo_root", tmp_path)

    draft = make_draft()
    result = publisher.publish(draft, make_topic("Cursor agent mode"), settings)
    written = (tmp_path / "cursor-adds-agent-mode.md").read_text(encoding="utf-8")

    assert result.slug == "cursor-adds-agent-mode"
    assert written.startswith("---\n")
    assert "## TL;DR" in written

    with pytest.raises(FileExistsError):
        publisher.publish(draft, make_topic("Cursor agent mode"), settings)


def test_mechanical_issues_flags_every_hard_requirement():
    draft = make_draft(
        title="A title that is far too long to fit inside the sixty character limit",
        description="too short",
        slug="cursor-2026",
        tags=["cursor"],
        body="No links at all here.",
    )
    issues = critics.mechanical_issues(
        draft, known_slugs={"lovable-review-2026"}, dead_links=[], allowed_urls=set()
    )
    requirements = " ".join(i.requirement for i in issues)
    assert "Title is" in requirements
    assert "Description is" in requirements
    assert "year from the slug" in requirements
    assert "tags" in requirements
    assert "primary sources" in requirements


def test_mechanical_issues_accepts_a_well_formed_post():
    draft = make_draft(
        body=(
            "It's a small change, per [the announcement](https://example.com/cursor). "
            "We covered the editor in our [Cursor review](/blog/cursor-review-2026). "
            + "word " * 600
            + "and that is the end of it."
        ),
    )
    issues = critics.mechanical_issues(
        draft,
        known_slugs={"cursor-review-2026"},
        dead_links=[],
        allowed_urls={"https://example.com/cursor"},
    )
    assert [i.requirement for i in issues if i.severity == "blocking"] == []


def test_external_link_outside_the_supplied_sources_is_blocking():
    draft = make_draft(
        body=(
            "Per [some blog](https://random.example/post) it changed. "
            "See our [review](/blog/cursor-review-2026). "
            + "word " * 600
            + "and that is the end of it."
        )
    )
    issues = critics.mechanical_issues(
        draft,
        known_slugs={"cursor-review-2026"},
        dead_links=[],
        allowed_urls={"https://example.com/cursor"},
    )
    assert any("not among the supplied sources" in i.requirement for i in issues)


def test_a_truncated_body_is_blocking():
    draft = make_draft(
        body=(
            "It's a small change, per [the announcement](https://example.com/cursor). "
            "See our [review](/blog/cursor-review-2026). " + "word " * 600
            + "and the part that really matters is"
        )
    )
    issues = critics.mechanical_issues(
        draft,
        known_slugs={"cursor-review-2026"},
        dead_links=[],
        allowed_urls={"https://example.com/cursor"},
    )
    assert any(
        i.severity == "blocking" and "mid-sentence" in i.requirement for i in issues
    )


def test_a_very_short_body_is_blocking():
    draft = make_draft(
        body=(
            "Short. Per [the announcement](https://example.com/cursor) it shipped. "
            "See our [review](/blog/cursor-review-2026)."
        )
    )
    issues = critics.mechanical_issues(
        draft,
        known_slugs={"cursor-review-2026"},
        dead_links=[],
        allowed_urls={"https://example.com/cursor"},
    )
    assert any(i.severity == "blocking" and "too short" in i.requirement for i in issues)


def test_a_title_one_character_over_target_does_not_block():
    """60 is an SEO display guideline. Losing a day to 61 characters is not."""
    draft = make_draft(title="x" * 61)
    issues = critics.mechanical_issues(
        draft, known_slugs=set(), dead_links=[], allowed_urls=set()
    )
    title_issues = [i for i in issues if "Title is" in i.requirement]
    assert title_issues and title_issues[0].severity == "major"


def test_a_wildly_long_title_still_blocks():
    draft = make_draft(title="x" * 90)
    issues = critics.mechanical_issues(
        draft, known_slugs=set(), dead_links=[], allowed_urls=set()
    )
    assert any(
        "Title is" in i.requirement and i.severity == "blocking" for i in issues
    )


def test_an_em_dash_in_the_description_is_blocking(settings):
    """The humaniser only rewrites the body; metadata bypassed the gate."""
    draft = make_draft(
        description=(
            "Meta released a 30B open-weights model tuned for agentic tasks "
            "under Apache 2.0 \u2014 what it means for solo builders running local AI."
        )
    )
    issues = critics.mechanical_issues(
        draft,
        known_slugs=set(),
        dead_links=[],
        allowed_urls=set(),
        settings=settings,
    )
    assert any(i.severity == "blocking" and "Em dash" in i.requirement for i in issues)


def test_a_clean_description_passes_the_metadata_gate(settings):
    issues = critics.mechanical_issues(
        make_draft(),
        known_slugs=set(),
        dead_links=[],
        allowed_urls=set(),
        settings=settings,
    )
    assert not any("Em dash" in i.requirement for i in issues)
