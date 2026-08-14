"""Layer A scrub on the publication path.

Carriers are written as escapes on purpose: a literal zero-width space in a
test file is invisible to review and to grep, which is the whole problem this
module exists to solve.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from tests.conftest import make_topic
from tests.test_publisher import make_draft

from aibh_pipeline.services import hygiene, publisher

ZWSP = "\u200b"  # ZERO WIDTH SPACE - removed
NBSP = "\u00a0"  # NO-BREAK SPACE - replaced with a plain space
RLO = "\u202e"  # RIGHT-TO-LEFT OVERRIDE - removed

REAL_SKILL_SCRIPTS = Path(__file__).resolve().parents[2] / hygiene.SCRIPT_RELPATH.parent


@pytest.fixture
def publish_root(settings, tmp_path, monkeypatch):
    """A throwaway repo root that still carries the vendored cleaner.

    publish() resolves the written path relative to repo_root, so the content
    directory has to live inside it - which means the skill has to as well.
    """
    scripts = tmp_path / hygiene.SCRIPT_RELPATH.parent
    shutil.copytree(REAL_SKILL_SCRIPTS, scripts)
    content = tmp_path / "src" / "content" / "blog"
    content.mkdir(parents=True)

    monkeypatch.setattr(settings, "repo_root", tmp_path)
    monkeypatch.setattr(type(settings), "content_dir", property(lambda self: content))
    return content


def test_scrub_removes_zero_width_and_normalises_exotic_spaces(settings):
    result = hygiene.scrub(f"Bo{ZWSP}lt ships{NBSP}today.", settings)

    assert result.ran
    assert result.text == "Bolt ships today."
    assert result.removed_count == 1
    assert result.replaced_count == 1
    assert result.touched


def test_scrub_leaves_clean_text_byte_identical(settings):
    text = "## TL;DR\n\nIt's worth 20 minutes - no more.\n"
    result = hygiene.scrub(text, settings)

    assert result.text == text
    assert not result.touched
    assert result.summary() == "clean"


def test_scrub_does_not_invent_a_trailing_newline(settings):
    """The cleaner's stdout path adds one; scrub() only touches codepoints."""
    assert hygiene.scrub("no newline here", settings).text == "no newline here"
    assert hygiene.scrub("one\n", settings).text == "one\n"
    assert hygiene.scrub("two\n\n", settings).text == "two\n\n"


def test_scrub_preserves_emoji_glue_and_code_blocks(settings):
    """ZWJ inside an emoji sequence is presentation glue, not a carrier."""
    text = "Ship it \U0001f468\u200d\U0001f4bb\n\n```python\nx = 1\n```\n"
    assert hygiene.scrub(text, settings).text == text


def test_a_missing_cleaner_passes_text_through_instead_of_raising(settings, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "repo_root", tmp_path)
    text = f"still{ZWSP}dirty"

    result = hygiene.scrub(text, settings)

    assert result.text == text
    assert result.ran is False
    assert result.summary() == "not checked"


def test_a_broken_cleaner_passes_text_through(settings, monkeypatch, tmp_path):
    """A cleaner that exits non-zero must not cost the day's post."""
    scripts = tmp_path / hygiene.SCRIPT_RELPATH.parent
    scripts.mkdir(parents=True)
    (scripts / "clean_text.py").write_text("import sys\nsys.exit(3)\n", encoding="utf-8")
    monkeypatch.setattr(settings, "repo_root", tmp_path)

    result = hygiene.scrub("text", settings)

    assert result.text == "text"
    assert result.ran is False


def test_publish_scrubs_the_document_it_writes(settings, publish_root):
    draft = make_draft(
        title=f"Cursor{NBSP}adds an agent mode",
        body=f"## TL;DR\n\nIt{ZWSP}'s worth 20 minutes.{RLO}\n",
    )
    result = publisher.publish(draft, make_topic("Cursor agent mode"), settings)
    written = (publish_root / f"{draft.slug}.md").read_text(encoding="utf-8")

    assert ZWSP not in written
    assert NBSP not in written
    assert RLO not in written
    # The scrub normalises the title in place rather than dropping the space.
    assert "Cursor adds an agent mode" in written
    assert result.unicode_checked
    assert result.unicode_removed == 2
    assert result.unicode_replaced == 1


def test_publish_reports_a_clean_document_as_checked_and_untouched(settings, publish_root):
    result = publisher.publish(make_draft(), make_topic("Cursor agent mode"), settings)

    assert (publish_root / "cursor-adds-agent-mode.md").is_file()
    assert result.unicode_checked
    assert result.unicode_removed == 0
    assert result.unicode_replaced == 0
