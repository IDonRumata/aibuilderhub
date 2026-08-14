"""Pipeline entry point.

Exit codes:
  0  a post was published, or the day was deliberately skipped (no candidate)
  1  an unexpected error
  2  the LLM call budget was exhausted
  3  the post was rejected on quality grounds - the day is skipped, alert
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from typing import Any

from .clients.anthropic_client import AnthropicClient, BudgetExceededError, RefusalError
from .clients.embeddings import EmbeddingProvider
from .logging_setup import configure_logging, get_logger
from .models import CritiqueReport, DraftPost, PublishResult, ScoredTopic, Verdict
from .services import budget, critics, dedup, humanizer, publisher, writer
from .services.ingest import ingest, load_sources
from .services.scoring import score_topics
from .services.site import existing_posts, link_menu
from .settings import Settings, get_settings

log = get_logger(__name__)

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_BUDGET = 2
EXIT_REJECTED = 3


async def _select_topic(
    topics: list[ScoredTopic],
    store: dedup.StateStore,
    provider: EmbeddingProvider,
    settings: Settings,
) -> ScoredTopic | None:
    """Walk the ranked topics in batches until one survives dedup."""
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
        return topic
    return None


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


async def run(*, as_draft: bool, dry_run: bool) -> int:
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
        return EXIT_BUDGET

    config = load_sources(settings.sources_file)
    voice = settings.voice_file.read_text(encoding="utf-8")
    style_rules = settings.banned_patterns_file.read_text(encoding="utf-8")

    store = dedup.StateStore(settings)
    provider = EmbeddingProvider(settings)
    site_posts = existing_posts(settings.content_dir)
    await dedup.index_existing_posts(site_posts, store, provider)

    known_slugs = {post.slug for post in site_posts if not post.draft}
    internal_links = link_menu(site_posts)

    candidates = dedup.filter_seen(await ingest(settings, config), store)
    if len(candidates) < settings.min_candidates:
        log.warning("too_few_candidates", count=len(candidates), needed=settings.min_candidates)

    topics = score_topics(candidates, config, settings)
    topic = await _select_topic(topics, store, provider, settings)
    if topic is None:
        log.warning("no_publishable_topic", topics=len(topics))
        publisher.write_run_summary(
            settings, {"published": False, "reason": "no_publishable_topic"}
        )
        publisher.append_step_summary(
            [
                "### Content pipeline",
                "",
                "No publishable topic today. Skipping rather than publishing",
                "a duplicate or an off-topic post.",
            ]
        )
        publisher.set_output("published", "false")
        # A skipped day is a normal outcome, not a failure.
        store.save()
        return EXIT_OK

    client = AnthropicClient(settings)
    try:
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
            return _abort(
                settings,
                store,
                reason=f"critics returned {verdict.value} after {rounds} rounds",
                topic=topic,
            )

        body, remaining = await humanizer.humanize(
            draft.body, client=client, settings=settings, voice=voice
        )
        draft = draft.model_copy(update={"body": body})
        if remaining:
            return _abort(
                settings,
                store,
                reason="banned patterns survived the rewrite: "
                + ", ".join(sorted({v.rule for v in remaining})),
                topic=topic,
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
            return _abort(
                settings,
                store,
                reason="post broke a hard requirement after humanising: "
                + "; ".join(i.requirement for i in blocking[:3]),
                topic=topic,
            )

        duplicate = await dedup.is_duplicate_post(draft, store, provider, settings)
        if duplicate.is_duplicate:
            return _abort(
                settings,
                store,
                reason=f"final dedup check: {duplicate.reason} (vs {duplicate.against})",
                topic=topic,
            )

        if dry_run:
            log.info(
                "dry_run_complete",
                slug=draft.slug,
                title=draft.title,
                words=draft.word_count,
                llm_calls=client.usage.calls,
            )
            print("\n" + "=" * 72)
            print(publisher.build_frontmatter(draft, publish_date=datetime.now(UTC), is_draft=True))
            print(draft.body)
            print("=" * 72)
            return EXIT_OK

        result = publisher.publish(
            draft,
            topic,
            settings,
            as_draft=as_draft,
            critic_rounds=rounds,
            llm_calls=client.usage.calls,
        )
        store.record(draft, topic, await provider.embed(f"{draft.title}\n{draft.description}"))
        store.save()

        publisher.write_run_summary(
            settings,
            {
                "published": True,
                "draft": as_draft,
                **_result_dict(result),
                "usage": client.usage.as_dict(),
            },
        )
        publisher.append_step_summary(
            [
                "### Content pipeline",
                "",
                f"Published **{result.title}**",
                "",
                f"- slug: `{result.slug}`",
                f"- words: {result.word_count}",
                f"- critic rounds: {result.critic_rounds}",
                f"- LLM calls: {result.llm_calls}",
                f"- unicode scrub: {_scrub_summary(result)}",
                f"- sources: {', '.join(result.source_urls)}",
            ]
        )
        publisher.set_output("published", "true")
        publisher.set_output("slug", result.slug)
        publisher.set_output("path", result.path)
        return EXIT_OK

    except BudgetExceededError as exc:
        log.error("budget_exceeded", error=str(exc), calls=client.usage.calls)
        publisher.write_run_summary(settings, {"published": False, "reason": str(exc)})
        publisher.set_output("published", "false")
        return EXIT_BUDGET
    except RefusalError as exc:
        log.error("model_refused", error=str(exc))
        publisher.write_run_summary(settings, {"published": False, "reason": str(exc)})
        publisher.set_output("published", "false")
        return EXIT_REJECTED
    finally:
        usage = client.usage.as_dict()
        cost = spend.record(usage, budget.Prices.from_settings(settings))
        spend.save()
        log.info(
            "usage",
            **usage,
            estimated_usd=round(cost, 5),
            month_to_date_usd=round(spend.spent_this_month, 4),
            budget_remaining_usd=round(spend.remaining, 4),
        )
        await client.aclose()


def _result_dict(result: Any) -> dict[str, Any]:
    return json.loads(result.model_dump_json())


def _scrub_summary(result: PublishResult) -> str:
    """One line about Layer A for the job summary."""
    if not result.unicode_checked:
        return "**not checked** (cleaner unavailable)"
    if not (result.unicode_removed or result.unicode_replaced):
        return "clean"
    return f"removed {result.unicode_removed}, replaced {result.unicode_replaced}"


def _abort(settings: Settings, store: dedup.StateStore, *, reason: str, topic: ScoredTopic) -> int:
    """Skip the day loudly. Nothing is written to the content collection."""
    log.error("day_skipped", reason=reason, topic=topic.title[:120])
    # Remember the failure, or tomorrow's run picks the same top-scoring
    # story and burns its whole budget failing on it again.
    store.record_failure(topic, reason)
    publisher.write_run_summary(
        settings, {"published": False, "reason": reason, "topic": topic.title}
    )
    publisher.append_step_summary(
        [
            "### Content pipeline",
            "",
            "No post published today.",
            "",
            f"- topic: {topic.title}",
            f"- reason: {reason}",
        ]
    )
    publisher.set_output("published", "false")
    store.save()
    return EXIT_REJECTED


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

    topics_cmd = sub.add_parser("topics", help="ingest and score only, no LLM calls")
    topics_cmd.add_argument("--limit", type=int, default=10)

    args = parser.parse_args()
    configure_logging(args.log_level)

    try:
        if args.command == "topics":
            return asyncio.run(show_topics(args.limit))
        return asyncio.run(run(as_draft=args.draft, dry_run=args.dry_run))
    except KeyboardInterrupt:
        return EXIT_ERROR
    except Exception:
        log.exception("pipeline_failed")
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(cli())
