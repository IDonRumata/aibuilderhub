"""Central configuration. Every secret comes from the environment, never from disk."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_core.core_schema import ValidationInfo
from pydantic_settings import BaseSettings, SettingsConfigDict

# automation/src/aibh_pipeline/settings.py -> automation/
AUTOMATION_DIR = Path(__file__).resolve().parents[2]
# automation/ -> repository root
REPO_ROOT = AUTOMATION_DIR.parent


class Settings(BaseSettings):
    """Pipeline configuration.

    Values are read from the process environment (GitHub Actions secrets in
    production) and, for local runs only, from ``automation/.env``.
    """

    model_config = SettingsConfigDict(
        env_file=AUTOMATION_DIR / ".env",
        env_file_encoding="utf-8",
        env_prefix="AIBH_",
        extra="ignore",
    )

    # --- credentials -----------------------------------------------------
    # Optional at load time so ingest/scoring can be exercised without a key;
    # AnthropicClient fails loudly if a run actually needs one.
    anthropic_api_key: SecretStr | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    voyage_api_key: SecretStr | None = Field(default=None, alias="VOYAGE_API_KEY")

    @field_validator("anthropic_api_key", "voyage_api_key", mode="before")
    @classmethod
    def _blank_secret_is_unset(cls, value: object) -> object:
        # GitHub Actions substitutes an empty string for a secret that was
        # never created, which otherwise looks like a configured credential
        # and produces `Illegal header value b'Bearer '`.
        if isinstance(value, str) and not value.strip():
            return None
        return value

    def require_anthropic_key(self) -> SecretStr:
        if self.anthropic_api_key is None:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        return self.anthropic_api_key

    voyage_model: str = "voyage-3-lite"

    # --- model ------------------------------------------------------------
    # The spec named claude-sonnet-4-5; claude-sonnet-5 is the current Sonnet
    # and is what this defaults to. Override with AIBH_MODEL.
    model: str = Field(default="claude-sonnet-5", alias="AIBH_MODEL")

    @field_validator("model", "voyage_model", mode="before")
    @classmethod
    def _blank_falls_back_to_default(cls, value: object, info: ValidationInfo) -> object:
        # Same trap as above: an unset repository variable arrives as "",
        # which the API rejects with "model: String should have at least 1
        # character" rather than falling back to the default here.
        if isinstance(value, str) and not value.strip():
            field = cls.model_fields[str(info.field_name)]
            return field.default
        return value

    max_tokens_writer: int = 6000
    max_tokens_critic: int = 2000
    max_tokens_humanizer: int = 6000

    # --- cadence ----------------------------------------------------------
    # The cron fires daily; these decide whether a given day writes anything.
    # See services/cadence.py for why this is a quota and not a calendar.
    #
    # Three posts a week is the deliberate ceiling. The site's bottleneck is
    # domain authority, not volume (LINK-BUILDING-PLAN.md), and a daily
    # machine-written news feed is precisely the shape Google's scaled content
    # abuse policy targets. Raise this only with a reason.
    weekly_target_posts: int = 3
    # A single run may publish more than one post only to repay a silence.
    max_posts_per_run: int = 2
    # Ceiling on topics tried in one run, including the ones that fail review.
    #
    # Three was too tight. The funnel offers about sixteen usable topics a day
    # and roughly a third of attempts are rejected, so three attempts leave a
    # real chance that a day ends silent while a dozen perfectly good stories
    # are still queued behind the ones that failed. Five makes an empty day
    # need five consecutive rejections, which has never happened.
    #
    # This is not the real limit and is not meant to be. Before every attempt
    # the run checks the month's remaining budget and its own call ceiling and
    # stops on either, so a pathological day cannot spend the month - it simply
    # stops earlier than five. Raising this number buys attempts on the days
    # that have budget for them; it cannot create budget.
    max_topic_attempts_per_run: int = 5
    # Minimum spacing between posts. Without it the weekly quota could be
    # satisfied by three posts on Monday and silence until the next Monday,
    # which is the outage this whole mechanism exists to prevent.
    min_hours_between_posts: float = 36.0
    # After this much silence a run is allowed to publish two posts to catch up.
    catchup_after_hours: float = 72.0

    # --- budget guards ----------------------------------------------------
    # Hard ceiling on LLM calls for ONE post. The writer/critic loop is bounded
    # at 1 + 3 * (1 + 4) = 16 calls plus humanising, so 25 leaves headroom while
    # still stopping any runaway loop.
    max_llm_calls: int = 25
    # Ceiling for the whole run, across every post and every failed attempt.
    # The loop stops as soon as fewer than max_llm_calls remain, so this has to
    # be at least max_topic_attempts_per_run * max_llm_calls or the attempt
    # ceiling above is decorative: at 80 the run ran out of calls after three
    # attempts no matter what the setting said.
    max_llm_calls_per_run: int = 130
    max_critic_rounds: int = 3

    # Token ceilings for a single run. One post uses roughly 60k input and 12k
    # output; a run may attempt five, so these leave headroom while still
    # stopping a loop.
    max_input_tokens_per_run: int = 900_000
    max_output_tokens_per_run: int = 180_000

    # Hard monthly ceiling on estimated spend. Once the month's estimate
    # reaches this, the pipeline refuses to start until the month rolls over -
    # which reads as weeks of silence, so the ceiling has to sit above the real
    # cost of the target rate rather than at it.
    #
    # Measured: one attempt costs about 0.40 dollars whether it publishes or
    # not, and roughly a third of attempts are rejected by the critics. Three
    # posts a week is therefore about 22 attempts and 9 dollars a month. Twelve
    # leaves a month's worth of margin for a debugging session.
    #
    # Two posts a week instead of three costs about 6. That is the one number
    # to change if the bill matters more than the cadence.
    monthly_budget_usd: float = 12.0

    # What one attempt is assumed to cost when deciding whether to start
    # another. Measured: 0.46 dollars for the run of 7 September.
    typical_post_cost_usd: float = 0.45

    # US dollars per million tokens, for the spend estimate only. Defaults are
    # the standard claude-sonnet-5 rates; update if you change model.
    price_input_per_mtok: float = 3.0
    price_output_per_mtok: float = 15.0

    # --- ingest -----------------------------------------------------------
    # The cron runs Mondays and Thursdays, so the longest gap between runs
    # is 96 hours. A 36-hour window meant every Friday, Saturday and Sunday
    # story was invisible to the pipeline - more than half the week's news
    # was discarded before scoring ever saw it. Freshness is still scored,
    # so newer items keep winning; older ones are no longer thrown away.
    lookback_hours: int = 96
    min_candidates: int = 20
    # Candidates are truncated after being sorted by raw engagement, and
    # RSS items carry no vote count, so a tight cap silently throws away
    # the publication feeds first - exactly the material worth writing
    # from. Scoring is cheap arithmetic, so the cap only needs to stop a
    # runaway feed, not to bound normal work.
    max_candidates: int = 400
    http_timeout_seconds: float = 20.0
    # Reddit rate limits per client; hitting five subreddits at once 429s.
    reddit_delay_seconds: float = 3.0
    user_agent: str = "aibuilderhub-content-bot/1.0 (+https://aibuilderhub.app)"

    # --- selection --------------------------------------------------------
    topics_per_batch: int = 5
    max_topic_batches: int = 3
    # Minimum niche relevance a topic must clear to be publishable at all.
    # Anything at or below zero is off-topic for this audience.
    min_niche_score: float = 0.15
    # Minimum characters of source summary across a topic's cluster. Below
    # this the writer has to invent, and the fact-checker rejects the result.
    min_summary_chars: int = 400
    # Days a topic that failed review is left alone before being retried.
    failed_topic_cooloff_days: int = 7

    # --- dedup ------------------------------------------------------------
    # Cosine similarity above which a topic counts as already covered.
    semantic_dupe_threshold: float = 0.86
    # Threshold used when falling back to the local lexical embedder, which
    # produces a different similarity distribution than a semantic model.
    lexical_dupe_threshold: float = 0.62
    trigram_dupe_threshold: float = 0.40

    # --- writing ----------------------------------------------------------
    target_words_min: int = 500
    target_words_max: int = 1000

    # --- paths ------------------------------------------------------------
    repo_root: Path = REPO_ROOT
    automation_dir: Path = AUTOMATION_DIR

    @property
    def content_dir(self) -> Path:
        return self.repo_root / "src" / "content" / "blog"

    @property
    def config_dir(self) -> Path:
        return self.automation_dir / "config"

    @property
    def state_dir(self) -> Path:
        return self.automation_dir / "state"

    @property
    def sources_file(self) -> Path:
        return self.config_dir / "sources.yaml"

    @property
    def voice_file(self) -> Path:
        return self.config_dir / "style" / "voice.md"

    @property
    def banned_patterns_file(self) -> Path:
        return self.config_dir / "style" / "banned_patterns.yaml"

    @property
    def published_topics_file(self) -> Path:
        return self.state_dir / "published_topics.json"

    @property
    def embeddings_file(self) -> Path:
        return self.state_dir / "embeddings.json"

    @property
    def failed_topics_file(self) -> Path:
        return self.state_dir / "failed_topics.json"

    @property
    def usage_file(self) -> Path:
        return self.state_dir / "usage.json"

    @field_validator("semantic_dupe_threshold", "lexical_dupe_threshold", "trigram_dupe_threshold")
    @classmethod
    def _fraction(cls, value: float) -> float:
        if not 0.0 < value < 1.0:
            raise ValueError("threshold must be strictly between 0 and 1")
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()  # type: ignore[call-arg]  # values come from the environment
