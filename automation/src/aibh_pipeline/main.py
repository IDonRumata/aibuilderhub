"""Pipeline entry point.

Exit codes:
  0  at least one post was published, or the day was deliberately skipped
     (nothing due, or no candidate worth writing about)
  1  an unexpected error
  2  the LLM call budget was exhausted
  3  every topic tried was rejected on quality grounds - alert
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .clients.anthropic_client import (
    AnthropicClient,
    BudgetExceededError,
    PostBudgetExceededError,
    RefusalError,
)
from .clients.embeddings import EmbeddingProvider
from .logging_setup import configure_logging, get_logger
from .models import CritiqueReport, DraftPost, PublishResult, ScoredTopic, Verdict
from .services import budget, cadence, critics, dedup, humanizer, publisher, writer
from .services.ingest import ingest, load_sources
from .services.scoring import score_topics
from .services.site import existing_posts, link_menu
from .settings import Settings, get_settings

log = get_logger(__name__)

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_BUDGET = 2
EXIT_REJECTED = 3


async def _publishable_topics(
    topics: list[ScoredTopic],
    store: dedup.StateStore,
    provider: EmbeddingProvider,
    settings: Settings,
) -> AsyncIterator[ScoredTopic]:
    """Yield every ranked topic that survives the cooloff and dedup checks.

    A generator, not a single pick. The run used to select one story and end
    the day if it failed review, throwing away the fourteen candidates ranked
    behind it. Now the caller takes the next one instead.
    """
    considered = settings.topics_per_batch * settings.max_topic_batches
    for index, topic in enumerate(topics[:considered]):
        failure = store.recently_failed(
            topic, cooloff_days=settings.failed_topic_cooloff_days
        )
        if failure:
            log.info(
                "topic_recently_failed",
                rank=index,
                title=topic.title[:90],
                reason=failure[:160],
            )
            continue

        verdict = await dedup.is_duplicate_topic(topic, store, provider, settings)
        if verdict.is_duplicate:
            log.info(
                "topic_is_duplicate",
                rank=index,
                title=topic.title[:90],
                against=verdict.against,
                reason=verdict.reason,
            )
            continue
        log.info("topic_selected", rank=index, title=topic.title[:90], score=topic.score)
        yield topic


async def _critique_loop(
    draft: DraftPost,
    topic: ScoredTopic,
    *,
    client: AnthropicClient,
    settings: Settings,
    voice: str,
    style_rules: str,
    internal_links: str,
    known_slugs: set[str],
) -> tuple[DraftPost, int, Verdict]:
    current = draft

    # Deterministic checks first. Sending a draft that stops mid-sentence to
    # four reviewers spends four calls establishing what a regex already
    # knows, and their verdicts then drown out the actual defect.
    dead = await critics.check_links(critics.MD_LINK_RE.findall(current.body), settings)
    upfront = critics.mechanical_issues(
        current,
        known_slugs=known_slugs,
        dead_links=dead,
        allowed_urls=set(topic.source_urls),
        settings=settings,
    )
    if any(issue.severity == "blocking" for issue in upfront):
        log.info(
            "repairing_draft_before_review",
            issues=[i.requirement[:120] for i in upfront if i.severity == "blocking"],
        )
        current = await writer.revise_draft(
            current,
            [CritiqueReport(critic="mechanical", verdict=Verdict.REVISE, issues=upfront)],
            topic,
            client=client,
            settings=settings,
            voice=voice,
            internal_links=internal_links,
            round_index=-1,
        )

    for round_index in range(settings.max_critic_rounds):
        reports = await critics.review(
            current,
            topic,
            client=client,
            settings=settings,
            voice=voice,
            style_rules=style_rules,
            internal_links=internal_links,
            known_slugs=known_slugs,
        )
        verdict = critics.verdict_of(reports)
        # The style reviewer's findings never block. Everything it objects to
        # - em dashes, banned words, typography - is fixed deterministically by
        # the humaniser in the very next step, and the regex rescan after that
        # is the real gate. Letting it veto here means the pipeline dies on
        # something it was about to repair anyway.
        blocking = [
            issue
            for report in reports
            if report.critic != "ai-pattern"
            for issue in report.issues
            if issue.severity == "blocking"
        ]
        log.info(
            "critique_round",
            round=round_index,
            verdict=verdict.value,
            blocking=len(blocking),
            issues=[
                f"{report.critic}/{issue.severity}: {issue.requirement[:110]}"
                for report in reports
                for issue in report.issues
            ][:12],
        )

        if verdict is Verdict.PASS:
            return current, round_index + 1, verdict
        if verdict is Verdict.REJECT:
            for report in reports:
                if report.verdict is Verdict.REJECT:
                    log.error("critic_rejected", critic=report.critic, notes=report.notes[:400])
            return current, round_index + 1, verdict

        if round_index == settings.max_critic_rounds - 1:
            # Last round. A reviewer can always find one more thing to
            # improve, so holding out for a unanimous PASS means never
            # publishing. What must not survive is a *blocking* issue: an
            # unsupported fact, a dead link, a broken frontmatter rule.
            # Anything softer is logged and shipped.
            if blocking:
                log.error(
                    "blocking_issues_survived",
                    count=len(blocking),
                    issues=[i.requirement[:140] for i in blocking[:5]],
                )
                return current, round_index + 1, Verdict.REJECT
            log.warning(
                "published_with_open_notes",
                count=sum(len(r.issues) for r in reports),
            )
            return current, round_index + 1, Verdict.PASS

        current = await writer.revise_draft(
            current,
            reports,
            topic,
            client=client,
            settings=settings,
            voice=voice,
            internal_links=internal_links,
            round_index=round_index,
        )
    return current, settings.max_critic_rounds, Verdict.REVISE


@dataclass(slots=True)
class PostOutcome:
    """What one topic attempt produced: a post, or the reason there is none."""

    result: PublishResult | None = None
    reason: str = ""
    dry: bool = False

    @property
    def ok(self) -> bool:
        return self.result is not None or self.dry


async def _produce_post(
    topic: ScoredTopic,
    *,
    client: AnthropicClient,
    settings: Settings,
    store: dedup.StateStore,
    provider: EmbeddingProvider,
    voice: str,
    style_rules: str,
    internal_links: str,
    known_slugs: set[str],
    as_draft: bool,
    dry_run: bool,
) -> PostOutcome:
    """Write, review, humanise and publish one topic.

    Every failure path returns a reason instead of raising, because a story
    that cannot be written is a fact about that story, not about the run. The
    caller records the reason and moves on to the next candidate.
    """
    client.begin_post()

    draft = await writer.write_draft(
        topic,
        client=client,
        settings=settings,
        voice=voice,
        internal_links=internal_links,
    )
    draft, rounds, verdict = await _critique_loop(
        draft,
        topic,
        client=client,
        settings=settings,
        voice=voice,
        style_rules=style_rules,
        internal_links=internal_links,
        known_slugs=known_slugs,
    )
    if verdict is not Verdict.PASS:
        return PostOutcome(reason=f"critics returned {verdict.value} after {rounds} rounds")

    body, remaining = await humanizer.humanize(
        draft.body, client=client, settings=settings, voice=voice
    )
    draft = draft.model_copy(update={"body": body})
    if remaining:
        return PostOutcome(
            reason="banned patterns survived the rewrite: "
            + ", ".join(sorted({v.rule for v in remaining}))
        )

    # The rewrite touched the prose, so re-run the deterministic checks.
    dead = await critics.check_links(critics.MD_LINK_RE.findall(draft.body), settings)
    mechanical = critics.mechanical_issues(
        draft,
        known_slugs=known_slugs,
        dead_links=dead,
        allowed_urls=set(topic.source_urls),
        settings=settings,
    )
    blocking = [i for i in mechanical if i.severity == "blocking"]
    if blocking:
        return PostOutcome(
            reason="post broke a hard requirement after humanising: "
            + "; ".join(i.requirement for i in blocking[:3])
        )

    duplicate = await dedup.is_duplicate_post(draft, store, provider, settings)
    if duplicate.is_duplicate:
        return PostOutcome(
            reason=f"final dedup check: {duplicate.reason} (vs {duplicate.against})"
        )

    if dry_run:
        log.info(
            "dry_run_complete",
            slug=draft.slug,
            title=draft.title,
            words=draft.word_count,
            llm_calls=client.calls_this_post,
        )
        print("\n" + "=" * 72)
        print(publisher.build_frontmatter(draft, publish_date=datetime.now(UTC), is_draft=True))
        print(draft.body)
        print("=" * 72)
        return PostOutcome(dry=True)

    result = publisher.publish(
        draft,
        topic,
        settings,
        as_draft=as_draft,
        critic_rounds=rounds,
        llm_calls=client.calls_this_post,
    )
    # Recorded immediately rather than at the end of the run: the next topic in
    # this same run has to see the post that was just written, or a run that
    # publishes twice loses half of its duplicate protection.
    store.record(draft, topic, await provider.embed(f"{draft.title}\n{draft.description}"))
    known_slugs.add(draft.slug)
    return PostOutcome(result=result)


def _skip_day(
    settings: Settings,
    *,
    reason: str,
    extra: dict[str, Any] | None = None,
    summary_lines: list[str] | None = None,
) -> int:
    """A run that deliberately wrote nothing. Not a failure."""
    publisher.write_run_summary(
        settings, {"published": False, "count": 0, "reason": reason, **(extra or {})}
    )
    publisher.append_step_summary(
        summary_lines or ["### Content pipeline", "", f"Nothing published: {reason}."]
    )
    publisher.set_output("published", "false")
    publisher.set_output("published_count", "0")
    return EXIT_OK


async def run(*, as_draft: bool, dry_run: bool, force: bool = False) -> int:
    settings = get_settings()

    # Before the secret is configured, a scheduled run should say so once and
    # stop, not fail every morning and mail the owner about it.
    if settings.anthropic_api_key is None:
        log.warning("anthropic_api_key_not_configured")
        publisher.write_run_summary(
            settings, {"published": False, "reason": "ANTHROPIC_API_KEY is not configured"}
        )
        publisher.append_step_summary(
            [
                "### Content pipeline",
                "",
                "`ANTHROPIC_API_KEY` is not set for this repository, so nothing ran.",
                "Add it under Settings, Secrets and variables, Actions.",
            ]
        )
        publisher.set_output("published", "false")
        publisher.set_output("published_count", "0")
        return EXIT_OK

    spend = budget.MonthlyBudget(settings)
    if spend.exceeded():
        log.error(
            "monthly_budget_exhausted",
            spent_usd=round(spend.spent_this_month, 4),
            budget_usd=settings.monthly_budget_usd,
        )
        publisher.write_run_summary(
            settings,
            {
                "published": False,
                "reason": (
                    f"monthly budget of ${settings.monthly_budget_usd} reached "
                    f"(${spend.spent_this_month:.2f} estimated so far)"
                ),
            },
        )
        publisher.append_step_summary(
            [
                "### Content pipeline",
                "",
                f"Stopped: the estimated spend for this month has reached "
                f"${spend.spent_this_month:.2f} against a ceiling of "
                f"${settings.monthly_budget_usd:.2f}.",
                "",
                "Raise `monthly_budget_usd` in automation settings to continue.",
            ]
        )
        publisher.set_output("published", "false")
        publisher.set_output("published_count", "0")
        return EXIT_BUDGET

    store = dedup.StateStore(settings)

    # The cron fires every day; the quota decides whether today writes. The
    # check sits before ingest deliberately, so a day that is already on target
    # costs nothing at all: no feeds fetched, no embeddings, no model calls.
    schedule = cadence.plan(store.topics, settings)
    log.info("cadence", **schedule.as_log_fields(), forced=force or dry_run)
    wanted = max(1, schedule.wanted) if (force or dry_run) else schedule.wanted
    if dry_run:
        wanted = 1
    if wanted == 0:
        return _skip_day(
            settings,
            reason=f"on schedule: {schedule.reason}",
            extra={"published_last_week": schedule.published_last_week},
            summary_lines=[
                "### Content pipeline",
                "",
                f"Nothing due today: {schedule.reason}.",
                "",
                "No feeds were fetched and no model was called.",
            ],
        )

    config = load_sources(settings.sources_file)
    voice = settings.voice_file.read_text(encoding="utf-8")
    style_rules = settings.banned_patterns_file.read_text(encoding="utf-8")

    provider = EmbeddingProvider(settings)
    site_posts = existing_posts(settings.content_dir)
    await dedup.index_existing_posts(site_posts, store, provider)

    known_slugs = {post.slug for post in site_posts if not post.draft}
    internal_links = link_menu(site_posts)

    candidates = dedup.filter_seen(await ingest(settings, config), store)
    if len(candidates) < settings.min_candidates:
        log.warning("too_few_candidates", count=len(candidates), needed=settings.min_candidates)

    topics = score_topics(candidates, config, settings)

    published: list[PublishResult] = []
    failures: list[dict[str, str]] = []
    attempts = 0
    stopped_by_budget = False
    prices = budget.Prices.from_settings(settings)
    client = AnthropicClient(settings)

    # An explicit iterator rather than `async for`: the loop must not pull a
    # topic it has no intention of writing. Pulling one runs a dedup check and,
    # worse, logs `topic_selected` for a story nobody touched, which is exactly
    # the kind of thing that misleads whoever reads these logs at 2am.
    stream = _publishable_topics(topics, store, provider, settings)
    try:
        while len(published) < wanted:
            if attempts >= settings.max_topic_attempts_per_run:
                log.warning("attempt_limit_reached", attempts=attempts)
                break
            in_flight = budget.estimate_cost(client.usage.as_dict(), prices)
            if not spend.allows_another_post(in_flight):
                log.error(
                    "monthly_budget_too_low_for_another_post",
                    remaining_usd=round(spend.remaining - in_flight, 4),
                )
                stopped_by_budget = True
                break
            if client.calls_remaining_in_run < settings.max_llm_calls:
                log.warning("run_call_budget_too_low", used=client.usage.calls)
                stopped_by_budget = True
                break

            topic = await anext(stream, None)
            if topic is None:
                break

            attempts += 1
            try:
                outcome = await _produce_post(
                    topic,
                    client=client,
                    settings=settings,
                    store=store,
                    provider=provider,
                    voice=voice,
                    style_rules=style_rules,
                    internal_links=internal_links,
                    known_slugs=known_slugs,
                    as_draft=as_draft,
                    dry_run=dry_run,
                )
            except PostBudgetExceededError as exc:
                # This topic ate its own ceiling. The run keeps what is left of
                # the budget for the next candidate instead of dying here.
                outcome = PostOutcome(reason=str(exc))
            except BudgetExceededError:
                # The run-wide ceiling. Nothing else can be attempted.
                raise
            except RefusalError as exc:
                outcome = PostOutcome(reason=f"model refused: {exc}")
            except Exception as exc:
                # Deliberately broad. Every earlier outage was one story taking
                # the whole day down with it, and an unexpected error in the
                # middle of post two must not throw away post one, which is
                # already on disk. The traceback is logged in full, three
                # failures in a row still exit 3, and the alert still fires.
                log.exception("post_attempt_failed", topic=topic.title[:120])
                outcome = PostOutcome(reason=f"{type(exc).__name__}: {exc}")

            if outcome.dry:
                break
            if outcome.result is not None:
                published.append(outcome.result)
                continue

            log.error("topic_failed", reason=outcome.reason, topic=topic.title[:120])
            failures.append({"topic": topic.title, "reason": outcome.reason})
            # Remember it, or the next run picks the same top-scoring story and
            # burns its budget failing on it again.
            store.record_failure(topic, outcome.reason)

    except BudgetExceededError as exc:
        log.error("run_budget_exceeded", error=str(exc), calls=client.usage.calls)
        stopped_by_budget = True
    finally:
        store.save()
        usage = client.usage.as_dict()
        cost = spend.record(usage, prices)
        spend.save()
        log.info(
            "usage",
            **usage,
            estimated_usd=round(cost, 5),
            month_to_date_usd=round(spend.spent_this_month, 4),
            budget_remaining_usd=round(spend.remaining, 4),
        )
        await client.aclose()

    if dry_run:
        return EXIT_OK

    if published:
        publisher.write_run_summary(
            settings,
            {
                "published": True,
                "count": len(published),
                "draft": as_draft,
                "posts": [_result_dict(result) for result in published],
                "failed_attempts": failures,
                "published_last_week": schedule.published_last_week + len(published),
                "weekly_target": settings.weekly_target_posts,
                "usage": client.usage.as_dict(),
                # The first post's fields also stay at the top level, so
                # anything that read last_run.json before posts became a list
                # keeps working.
                **_result_dict(published[0]),
            },
        )
        lines = [
            "### Content pipeline",
            "",
            f"Published {len(published)} post(s). "
            f"{schedule.published_last_week + len(published)} of "
            f"{settings.weekly_target_posts} for the week.",
            "",
        ]
        for result in published:
            lines.append(
                f"- **{result.title}** (`{result.slug}`, {result.word_count} words, "
                f"{result.critic_rounds} critic rounds, {result.llm_calls} calls)"
            )
        for failure in failures:
            lines.append(f"- skipped *{failure['topic'][:80]}*: {failure['reason'][:160]}")
        publisher.append_step_summary(lines)
        publisher.set_output("published", "true")
        publisher.set_output("published_count", str(len(published)))
        publisher.set_output("slug", published[0].slug)
        publisher.set_output("slugs", ", ".join(result.slug for result in published))
        publisher.set_output("path", published[0].path)
        return EXIT_OK

    if failures:
        log.error("day_skipped", attempts=attempts, failures=failures)
        publisher.write_run_summary(
            settings,
            {
                "published": False,
                "count": 0,
                "reason": f"all {attempts} topic(s) failed review",
                "failed_attempts": failures,
                "usage": client.usage.as_dict(),
            },
        )
        publisher.append_step_summary(
            [
                "### Content pipeline",
                "",
                f"Nothing published. {attempts} topic(s) tried and rejected:",
                "",
                *[f"- *{f['topic'][:90]}* - {f['reason'][:200]}" for f in failures],
            ]
        )
        publisher.set_output("published", "false")
        publisher.set_output("published_count", "0")
        return EXIT_BUDGET if stopped_by_budget else EXIT_REJECTED

    if stopped_by_budget:
        publisher.set_output("published", "false")
        publisher.set_output("published_count", "0")
        return EXIT_BUDGET

    log.warning("no_publishable_topic", topics=len(topics))
    return _skip_day(
        settings,
        reason="no_publishable_topic",
        summary_lines=[
            "### Content pipeline",
            "",
            "No publishable topic today. Skipping rather than publishing",
            "a duplicate or an off-topic post.",
        ],
    )


def _result_dict(result: Any) -> dict[str, Any]:
    return json.loads(result.model_dump_json())


async def show_topics(limit: int) -> int:
    """Dry run of ingest plus scoring. No LLM calls, no writes."""
    settings = get_settings()
    config = load_sources(settings.sources_file)
    store = dedup.StateStore(settings)
    candidates = dedup.filter_seen(await ingest(settings, config), store)
    topics = score_topics(candidates, config, settings)

    print(f"\n{len(candidates)} candidates -> {len(topics)} on-niche topics\n")
    for index, topic in enumerate(topics[:limit], start=1):
        print(f"{index:2}. {topic.score:6.2f}  [{topic.distinct_sources} source(s)]  {topic.title}")
        for item in topic.items[:3]:
            print(f"      {item.source:<18} {item.score_raw:>6.0f}  {item.canonical_url}")
    return EXIT_OK


def cli() -> int:
    parser = argparse.ArgumentParser(prog="aibh-pipeline", description=__doc__)
    parser.add_argument("--log-level", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    run_cmd = sub.add_parser("run", help="the full daily pipeline")
    run_cmd.add_argument(
        "--draft", action="store_true", help="publish with draft: true for human review"
    )
    run_cmd.add_argument(
        "--dry-run", action="store_true", help="generate and print, but write nothing"
    )
    run_cmd.add_argument(
        "--force",
        action="store_true",
        help="publish even if the week is already on target (manual runs)",
    )

    topics_cmd = sub.add_parser("topics", help="ingest and score only, no LLM calls")
    topics_cmd.add_argument("--limit", type=int, default=10)

    args = parser.parse_args()
    configure_logging(args.log_level)

    try:
        if args.command == "topics":
            return asyncio.run(show_topics(args.limit))
        return asyncio.run(
            run(as_draft=args.draft, dry_run=args.dry_run, force=args.force)
        )
    except KeyboardInterrupt:
        return EXIT_ERROR
    except Exception:
        log.exception("pipeline_failed")
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(cli())
