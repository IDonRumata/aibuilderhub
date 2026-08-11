"""End-to-end orchestration test with a stubbed model.

Proves the wiring - ingest, scoring, dedup, writer, four critics, humanizer,
publisher - without a network call or an API key. The real model quality is
checked by running `aibh-pipeline run --dry-run` with a key.
"""

from __future__ import annotations

import json

import pytest
from tests.conftest import make_item

from aibh_pipeline import main
from aibh_pipeline.clients.anthropic_client import Usage
from aibh_pipeline.services import critics, humanizer, writer

GOOD_BODY = """\n## TL;DR

Cursor's agent mode is worth 20 minutes of your evening. It won't read the diff
for you. What it does is take the boring 80% of a refactor off your hands, and
on a 6-file change that's a real saving, [per the announcement](https://example.com/cursor).

Here's the part that matters if you're building alone. The old flow meant
approving each edit by hand, one file at a time, which got tedious on anything
past 3 files. You'd start skimming around file 4, and skimming is how a bad
rename ships. The new mode batches the whole change into a single review, so
you read it once, properly, with the shape of the change visible instead of
scattered across a dozen approval prompts.

That sounds like a small ergonomic tweak. In practice it changes what you're
willing to attempt on a Tuesday night.

I'm not sold on the pricing, though. At $20 a month it's fine if you open the
editor most days and you're shipping something real. Twice a week and it's a
subscription you'll forget you have until the charge lands. We made much the
same argument in our [Cursor review](/blog/cursor-review-2026), and nothing
about the agent mode changes that arithmetic. The tool is priced for people who
write code for a living, not for people who write code on weekends.

## What it actually changes

Three things, and only one of them is about speed.

The first is review shape. A single batched diff is easier to reason about than
twelve sequential prompts, because you can see whether the change is coherent
rather than whether each individual hunk looks plausible. Coherence is the
thing that breaks in agent-driven refactors, and it's the thing per-file
approval hides from you.

The second is abandonment cost. When a run goes wrong halfway through, you now
throw away one review instead of unpicking eight applied edits. That lowers the
stakes of trying, which matters more than raw throughput when you're the only
person who can fix what breaks.

The third is the one everybody will talk about: it's faster. It is. That's also
the least interesting part, because speed on a task you then have to verify by
hand is only worth as much as the verification is cheap.

## Where it falls short

The agent still can't run your test suite on its own. That's the limitation
that decides how much this is worth to you. If your project has a fast test
command, you get a tight loop: generate, batch, review, run, repeat. If your
tests take 4 minutes or your project has none, you're back to reading code
carefully, and a bigger diff is now working against you.

There's also a quieter risk. Batched review encourages approving as a unit, and
a unit is exactly the granularity at which a subtle mistake slips past. I'd
rather have the batch than not. I'd also rather nobody pretended this removes
the need to read what landed.

## What to do about it

If you already pay for the editor, turn it on and use it for the changes you'd
otherwise put off. Multi-file renames, moving a component, threading a new
argument through five call sites. That's where the batching earns its keep.

If you don't pay for it, this isn't the feature that should change your mind.
It's a better version of something you can already approximate with more clicks,
and the honest framing is that it saves clicks rather than solving a problem
you couldn't solve before.

Worth trying. Not worth switching editors for.
"""


class StubClient:
    """Returns a fixed draft and unanimous PASS verdicts."""

    def __init__(self, *_args, **_kwargs) -> None:
        self.usage = Usage()
        self.closed = False
        self.labels: list[str] = []

    async def complete_json(self, *, label: str, **kwargs) -> dict:
        self.usage.calls += 1
        self.labels.append(label)
        if label.startswith("writer"):
            return {
                "title": "Cursor adds an agent mode for solo builders",
                "description": (
                    "Cursor's agent mode batches a multi-file refactor into one review "
                    "instead of approving each edit by hand. Here's what that changes "
                    "for a solo builder."
                ),
                "slug": "cursor-adds-agent-mode",
                "tags": ["news", "cursor", "ai-coding"],
                "body": GOOD_BODY,
            }
        return {"verdict": "PASS", "notes": "fine", "issues": []}

    async def complete(self, *, label: str, **kwargs) -> str:
        self.usage.calls += 1
        self.labels.append(label)
        raise AssertionError("the humaniser should not be called on a clean body")

    async def aclose(self) -> None:
        self.closed = True


@pytest.fixture
def wired(settings, tmp_path, monkeypatch):
    content = tmp_path / "content"
    state = tmp_path / "state"
    content.mkdir()
    state.mkdir()

    monkeypatch.setattr(type(settings), "content_dir", property(lambda self: content))
    monkeypatch.setattr(type(settings), "state_dir", property(lambda self: state))
    monkeypatch.setattr(
        type(settings), "published_topics_file", property(lambda self: state / "topics.json")
    )
    monkeypatch.setattr(
        type(settings), "embeddings_file", property(lambda self: state / "vectors.json")
    )
    monkeypatch.setattr(settings, "repo_root", tmp_path)

    (content / "cursor-review-2026.md").write_text(
        "---\ntitle: Cursor review\ndescription: A hands-on review of the editor.\n"
        "pubDate: 2026-06-16\ntags:\n  - review\n  - cursor\nauthor: AIBuilderHub\n"
        "draft: false\n---\n\nbody\n",
        encoding="utf-8",
    )

    async def fake_ingest(_settings, _config):
        return [
            make_item(
                "Cursor ships an agent mode for vibe coding",
                url="https://example.com/cursor",
                score=420,
                summary="Cursor says the new agent mode batches multi-file edits.",
            ),
            make_item(
                "Cursor ships agent mode for vibe coding",
                url="https://verge.example/cursor",
                source="the-verge-ai",
                score=0,
            ),
        ]

    monkeypatch.setattr(main, "ingest", fake_ingest)
    monkeypatch.setattr(main, "AnthropicClient", StubClient)

    async def no_dead_links(_urls, _settings):
        return []

    monkeypatch.setattr(critics, "check_links", no_dead_links)
    return settings, content, state


async def test_full_run_publishes_a_valid_post(wired):
    _settings, content, state = wired

    assert await main.run(as_draft=True, dry_run=False) == main.EXIT_OK

    published = content / "cursor-adds-agent-mode.md"
    assert published.exists()
    text = published.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "draft: true" in text
    assert "tags:\n- news" in text.replace("\n  - ", "\n- ")

    summary = json.loads((state / "last_run.json").read_text(encoding="utf-8"))
    assert summary["published"] is True
    assert summary["slug"] == "cursor-adds-agent-mode"

    topics = json.loads((state / "topics.json").read_text(encoding="utf-8"))
    assert topics[0]["slug"] == "cursor-adds-agent-mode"


async def test_second_run_refuses_to_publish_the_same_story(wired):
    _settings, content, _state = wired

    assert await main.run(as_draft=True, dry_run=False) == main.EXIT_OK
    # The URL-level filter removes every candidate, so there is no topic left.
    assert await main.run(as_draft=True, dry_run=False) == main.EXIT_OK
    assert len(list(content.glob("cursor-adds-agent-mode*.md"))) == 1


async def test_a_reject_verdict_publishes_nothing(wired, monkeypatch):
    _settings, content, _state = wired

    class Rejecting(StubClient):
        async def complete_json(self, *, label: str, **kwargs) -> dict:
            payload = await StubClient.complete_json(self, label=label, **kwargs)
            if label.startswith("critic-fact"):
                return {
                    "verdict": "REJECT",
                    "notes": "central claim unsupported",
                    "issues": [],
                }
            return payload

    monkeypatch.setattr(main, "AnthropicClient", Rejecting)
    assert await main.run(as_draft=True, dry_run=False) == main.EXIT_REJECTED
    # Only the pre-existing fixture post is on disk; nothing new was written.
    assert [p.name for p in content.glob("*.md")] == ["cursor-review-2026.md"]


async def test_dry_run_writes_nothing(wired):
    _settings, content, state = wired
    assert await main.run(as_draft=True, dry_run=True) == main.EXIT_OK
    assert not list(content.glob("cursor-adds-agent-mode.md"))
    assert not (state / "last_run.json").exists()


async def test_the_stub_draft_survives_the_style_scanner(settings):
    rules = humanizer.load_rules(settings.banned_patterns_file)
    assert humanizer.scan(GOOD_BODY, rules) == []


def test_writer_brief_never_contains_source_body_text():
    """Only titles, URLs and feed summaries reach the model."""
    from tests.conftest import make_topic

    topic = make_topic("Cursor ships agent mode", summary="short feed blurb")
    brief = writer._sources_brief(topic)
    assert "short feed blurb" in brief
    assert brief.count("SUMMARY:") == 1


async def test_missing_api_key_skips_the_day_quietly(settings, monkeypatch, tmp_path):
    monkeypatch.setattr(type(settings), "state_dir", property(lambda self: tmp_path))
    monkeypatch.setattr(settings, "anthropic_api_key", None)
    assert await main.run(as_draft=False, dry_run=False) == main.EXIT_OK
    summary = json.loads((tmp_path / "last_run.json").read_text(encoding="utf-8"))
    assert summary["published"] is False
    assert "ANTHROPIC_API_KEY" in summary["reason"]
