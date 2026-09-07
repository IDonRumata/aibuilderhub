# AIBuilderHub content pipeline

Autonomous news pipeline for aibuilderhub.app. Collects candidate stories from
public feeds and APIs, picks the most promising ones, writes a post in the
site's voice, puts it through four independent reviewers, strips
machine-writing tells, and writes the result into the Astro content
collection. GitHub Actions builds the site and pushes.

## How often it publishes

The cron runs **daily**, twice, but the number of posts is set by a **weekly
quota of three**, not by the calendar. Every run asks how many posts went out
in the last seven days:

- already on target - stop immediately, before fetching a single feed
- behind target, last post less than 36 hours old - stop, to keep the week
  spread out rather than bunched into one day
- behind target - write one post
- behind target after 72 hours of silence - write up to two, to repay the gap

The logic lives in `services/cadence.py` and the knobs in `settings.py`
(`weekly_target_posts`, `min_hours_between_posts`, `catchup_after_hours`,
`max_posts_per_run`).

This replaced two fixed slots a week (Mondays and Thursdays, one post each).
Fixed slots have no memory: a slot that produced nothing, for any reason, cost
three or four days of silence, and two bad slots in a row cost a fortnight.
That is exactly what happened between 24 August and 7 September - four
scheduled slots, one published post. A quota recovers on its own, because
tomorrow's run can see that yesterday's did not deliver.

`--force` overrides the quota for manual runs.

## The flow of one post

```
cadence       how many posts are owed this week? none -> stop, cost zero
  |
ingest        150-400 candidates from RSS + Hacker News + Reddit
  |           a failing source is logged and skipped, never fatal
dedup L1      drop anything whose source URL was already covered
scoring       cluster into stories, rank by engagement / freshness /
  |           corroboration / niche fit. Niche fit is a GATE, not a bonus
dedup L2      per topic: cosine + title trigram check against everything
  |           already on the site. First survivor wins
writer        one draft from titles, URLs and feed summaries only
critics       fact-checker, ai-pattern, editor, seo-integrity - all four,
  |           independently, plus deterministic mechanical checks
  |           REVISE -> writer revises -> critics again, up to 3 rounds
  |           REJECT -> abandon this story, quarantine it, try the next
humanizer     regex scan, targeted LLM rewrite, rescan (up to 2 rounds)
recheck       mechanical checks and dedup re-run on the rewritten body
publish       write src/content/blog/<slug>.md + update state/
  |
  \___________ still owed a post? take the next topic and go round again
```

A topic that fails at any stage is recorded in `state/failed_topics.json` and
the run moves on to the next candidate. Losing one story no longer loses the
day: that single change is the difference between "the run failed" and "the
run published the second-best story instead".

The workflow then runs `npm run build` as a smoke test, re-runs the style
gate, and only then commits and pushes. If the build rejects the post,
nothing has been committed.

## The watchdog

`.github/workflows/content-watchdog.yml` runs every afternoon, reads the newest
timestamp in `state/published_topics.json`, and opens a GitHub issue if the
site has published nothing for four days. It closes the issue by itself once
posts resume. It calls no model and costs nothing.

It exists because a skipped day exits 0 and looks, from the outside, exactly
like a healthy one. The fortnight of silence in late August was only noticed by
the owner reading the site.

## Commands

```bash
cd automation
uv sync

# ingest + scoring only, no LLM calls, no writes
uv run aibh-pipeline topics --limit 15

# full run, prints the post and writes nothing
uv run aibh-pipeline run --dry-run

# full run, publishes with draft: true (invisible on the live site)
uv run aibh-pipeline run --draft

# what the cron does: publishes only if the week is behind target
uv run aibh-pipeline run

# publish now regardless of the weekly quota
uv run aibh-pipeline run --force
```

Exit codes: `0` published or day deliberately skipped, `1` unexpected error,
`2` LLM call budget exhausted, `3` quality rejection (day skipped, alert).

## Configuration

Everything tunable lives in `src/aibh_pipeline/settings.py` and is overridable
by environment variable. Secrets come only from the environment.

| Variable | Required | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | yes | the only mandatory secret |
| `VOYAGE_API_KEY` | no | enables hosted embeddings for dedup |
| `AIBH_MODEL` | no | defaults to `claude-sonnet-5` |
| `AIBH_LOG_LEVEL` | no | defaults to `INFO` |

Content configuration:

- `config/sources.yaml` - feeds, subreddits, weights, and the niche vocabulary
  that decides what is on-topic.
- `config/style/voice.md` - the house voice, extracted from the site's best
  existing posts. Every prompt is written against it and it carries the prompt
  cache breakpoint, so writer and all four critics share one cached prefix.
- `config/style/banned_patterns.yaml` - the anti-AI-tell block list.

## Cost control

- Hard ceiling of 25 LLM calls **per post** (`max_llm_calls`) and 80 per run
  (`max_llm_calls_per_run`), enforced in the client wrapper, not in a prompt. A
  post uses about 17: 1 draft, 3 x (4 critics + 1 revision), 1-2 humaniser
  passes. A post that exhausts its own ceiling is abandoned; the run keeps what
  is left of the budget for the next candidate.
- One post costs roughly $0.40. Three a week, with the odd failed attempt, is
  about $6 a month against a `monthly_budget_usd` ceiling of $10. The ceiling
  is a runaway guard, not the operating limit - but a debugging session of five
  manual runs really does cost $2, so check `state/usage.json` before one.
- Scoring, clustering and all mechanical checks are plain Python. No model is
  asked to count characters or rank 100 headlines.
- The shared voice document is cached across every call in a run.
- Two posts per run, maximum, and only to repay a silence. The workflow's
  concurrency group prevents two runs racing.

## State

`state/published_topics.json` records slug, canonical topic, source URLs, a
content hash and a timestamp for everything published. The timestamps are what
the weekly quota counts, so this file is the pipeline's schedule as well as its
dedup memory. `state/embeddings.json` holds one vector
per post, tagged with the provider that produced it - vectors from different
providers are never compared. Both are committed alongside the post so the
next run knows what exists. Neither contains anything sensitive.

The 23 hand-written posts already on the site are indexed into the same store
on first run, so the pipeline will not publish a duplicate of an existing
review.

## Known constraints

- **Reddit blocks the unauthenticated JSON API from many networks** (403). The
  client falls back to the same listing's RSS feed, which works, but carries no
  vote counts - those items score on relevance and freshness alone.
- **Dedup defaults to a local lexical embedder.** It catches near-duplicate
  wording reliably and full paraphrases less so. URL-level dedup and title
  trigram overlap cover most of the rest. Set `VOYAGE_API_KEY` for semantic
  vectors.
- **Copyright**: the writer only ever sees titles, URLs and short feed
  summaries. Source article text is never fetched, so it cannot be copied.
- **Google and scaled content**: three posts a week is a defensible rate; a
  daily machine-written news feed is the shape the scaled content abuse policy
  targets. If organic traffic has not moved in two to three months, stop and
  reconsider rather than raising `weekly_target_posts`. News decays in 48
  hours; the evergreen reviews are what earn affiliate revenue.
