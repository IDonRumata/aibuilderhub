"""How many posts a run should try to publish.

The pipeline used to be a calendar: two fixed slots a week, one post per slot,
one topic per post. A slot that produced nothing - because the critics rejected
the story, because GitHub dropped the cron, because the day's feeds were thin -
was simply lost until the next slot came round three or four days later. Two
consecutive misses meant a silent week, and that is exactly what happened
between 24 August and 7 September: four scheduled slots, one published post.

This module replaces the calendar with a quota. The cron now runs every day and
asks one question: how many posts went out in the last seven days? If the site
is behind the weekly target it writes; if it is on target it stops before
spending a cent. A failed day is no longer a lost week, because tomorrow's run
picks the work back up on its own.

Two guards keep the quota from turning into a burst:

* ``min_hours_between_posts`` spreads the week out. Three posts published on
  Monday would satisfy any weekly count while leaving the site silent until the
  following Monday, which is the failure this module exists to prevent.
* ``catchup_after_hours`` is the opposite valve: after a long silence a single
  run may publish more than one post, so an outage is repaid rather than
  written off.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from ..logging_setup import get_logger
from ..models import PublishedTopic
from ..settings import Settings

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Cadence:
    """The publication decision for one run."""

    wanted: int
    published_last_week: int
    hours_since_last: float | None
    reason: str

    @property
    def should_write(self) -> bool:
        return self.wanted > 0

    def as_log_fields(self) -> dict[str, object]:
        return {
            "wanted": self.wanted,
            "published_last_week": self.published_last_week,
            "hours_since_last": (
                None if self.hours_since_last is None else round(self.hours_since_last, 1)
            ),
            "reason": self.reason,
        }


def plan(
    published: list[PublishedTopic],
    settings: Settings,
    *,
    now: datetime | None = None,
) -> Cadence:
    """Decide how many posts this run should publish.

    ``published`` is the pipeline's own registry, not the whole site: the
    hand-written reviews are on a different clock and are not part of the news
    quota.
    """
    moment = now or datetime.now(UTC)
    week_ago = moment - timedelta(days=7)
    recent = [topic for topic in published if topic.published_at >= week_ago]
    last = max((topic.published_at for topic in published), default=None)
    hours_since = None if last is None else max(0.0, (moment - last).total_seconds() / 3600.0)

    deficit = settings.weekly_target_posts - len(recent)
    if deficit <= 0:
        return Cadence(
            wanted=0,
            published_last_week=len(recent),
            hours_since_last=hours_since,
            reason=(
                f"{len(recent)} posts in the last 7 days meets the target of "
                f"{settings.weekly_target_posts}"
            ),
        )

    if hours_since is not None and hours_since < settings.min_hours_between_posts:
        return Cadence(
            wanted=0,
            published_last_week=len(recent),
            hours_since_last=hours_since,
            reason=(
                f"last post was {hours_since:.0f}h ago, below the "
                f"{settings.min_hours_between_posts:.0f}h spacing"
            ),
        )

    silent_long_enough = hours_since is None or hours_since >= settings.catchup_after_hours
    wanted = 2 if (silent_long_enough and deficit >= 2) else 1
    wanted = max(0, min(wanted, deficit, settings.max_posts_per_run))
    return Cadence(
        wanted=wanted,
        published_last_week=len(recent),
        hours_since_last=hours_since,
        reason=(
            f"{len(recent)} of {settings.weekly_target_posts} posts in the last 7 days"
            + (" after a long silence" if silent_long_enough and wanted > 1 else "")
        ),
    )
