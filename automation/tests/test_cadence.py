"""The publication quota.

These are the rules that decide whether a given day writes anything at all,
and they are the difference between "the cron fired" and "the site published".
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from aibh_pipeline.models import PublishedTopic
from aibh_pipeline.services import cadence

NOW = datetime(2026, 9, 7, 6, 30, tzinfo=UTC)


def published(*ages_in_hours: float) -> list[PublishedTopic]:
    return [
        PublishedTopic(
            slug=f"post-{index}",
            canonical_topic=f"topic {index}",
            title=f"Post {index}",
            published_at=NOW - timedelta(hours=age),
        )
        for index, age in enumerate(ages_in_hours)
    ]


def test_an_empty_site_starts_writing_immediately(settings):
    plan = cadence.plan([], settings, now=NOW)
    assert plan.wanted >= 1
    assert plan.published_last_week == 0


def test_a_week_on_target_writes_nothing(settings):
    # Three posts spread over the last week: the target is met.
    plan = cadence.plan(published(10, 60, 120), settings, now=NOW)
    assert plan.wanted == 0
    assert "meets the target" in plan.reason


def test_a_post_this_morning_blocks_a_second_one_this_afternoon(settings):
    """The afternoon run exists to catch a dropped cron, not to double up."""
    plan = cadence.plan(published(4), settings, now=NOW)
    assert plan.wanted == 0
    assert "spacing" in plan.reason


def test_being_behind_after_a_proper_gap_writes(settings):
    plan = cadence.plan(published(50), settings, now=NOW)
    assert plan.wanted == 1


def test_a_long_silence_is_repaid_with_two_posts(settings):
    """The exact case that produced a silent fortnight: nothing for days."""
    plan = cadence.plan(published(24 * 9), settings, now=NOW)
    assert plan.wanted == 2
    assert plan.published_last_week == 0


def test_the_catch_up_never_exceeds_the_weekly_target(settings):
    # Two posts already this week, both old enough. Only one is still owed.
    plan = cadence.plan(published(24 * 5, 24 * 6), settings, now=NOW)
    assert plan.wanted == 1


def test_posts_older_than_a_week_do_not_count_towards_the_target(settings):
    plan = cadence.plan(published(24 * 8, 24 * 9, 24 * 10), settings, now=NOW)
    assert plan.published_last_week == 0
    assert plan.wanted > 0


@pytest.mark.parametrize("hours", [0.0, 1.0, 35.9])
def test_spacing_holds_for_any_recent_post(settings, hours):
    assert cadence.plan(published(hours), settings, now=NOW).wanted == 0
