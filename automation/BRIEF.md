# AIBuilderHub content pipeline

Autonomous daily news pipeline for aibuilderhub.app. Collects candidate
stories from public feeds and APIs, picks the most promising one, writes a
post in the site's voice, puts it through four independent reviewers, strips
machine-writing tells, and writes the result into the Astro content
collection. GitHub Actions builds the site and pushes.

## The daily flow

```
ingest        50-150 candidates from RSS + Hacker News + Reddit
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
  |           REJECT -> stop, publish nothing, alert
humanizer     regex scan, targeted LLM rewrite, rescan (up to 2 rounds)
recheck       mechanical checks and dedup re-run on the rewritten body
publish       write src/content/blog/<slug>.md + update state/
```

The workflow then runs `npm run build` as a smoke test, re-runs the style
gate, and only then commits and pushes. If the build rejects the post,
nothing has been committed.

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

# what the cron does
uv run aibh-pipeline run
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

- Hard ceiling of 25 LLM calls per run (`max_llm_calls`), enforced in the
  client wrapper, not in a prompt. A worst-case run uses about 17: 1 draft,
  3 x (4 critics + 1 revision), 1-2 humaniser passes.
- Scoring, clustering and all mechanical checks are plain Python. No model is
  asked to count characters or rank 100 headlines.
- The shared voice document is cached across every call in a run.
- One post per day, maximum. The workflow's concurrency group prevents two
  runs racing.

## State

`state/published_topics.json` records slug, canonical topic, source URLs and a
content hash for everything published. `state/embeddings.json` holds one vector
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
- **Google and scaled content**: one post a day is a defensible rate. If organic
  traffic has not moved in two to three months, stop and reconsider rather than
  increasing volume. News decays in 48 hours; the evergreen reviews are what
  earn affiliate revenue.
