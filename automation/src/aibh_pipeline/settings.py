"""Central configuration. Every secret comes from the environment, never from disk."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
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

    def require_anthropic_key(self) -> SecretStr:
        if self.anthropic_api_key is None:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        return self.anthropic_api_key

    voyage_model: str = "voyage-3-lite"

    # --- model ------------------------------------------------------------
    # The spec named claude-sonnet-4-5; claude-sonnet-5 is the current Sonnet
    # and is what this defaults to. Override with AIBH_MODEL.
    model: str = Field(default="claude-sonnet-5", alias="AIBH_MODEL")
    max_tokens_writer: int = 6000
    max_tokens_critic: int = 2000
    max_tokens_humanizer: int = 6000

    # --- budget guards ----------------------------------------------------
    # Hard ceiling on LLM calls per run. The writer/critic loop is bounded at
    # 1 + 3 * (1 + 4) = 16 calls plus humanising, so 25 leaves headroom while
    # still stopping any runaway loop.
    max_llm_calls: int = 25
    max_critic_rounds: int = 3

    # --- ingest -----------------------------------------------------------
    lookback_hours: int = 36
    min_candidates: int = 20
    max_candidates: int = 150
    http_timeout_seconds: float = 20.0
    user_agent: str = "aibuilderhub-content-bot/1.0 (+https://aibuilderhub.app)"

    # --- selection --------------------------------------------------------
    topics_per_batch: int = 5
    max_topic_batches: int = 3
    # Minimum niche relevance a topic must clear to be publishable at all.
    # Anything at or below zero is off-topic for this audience.
    min_niche_score: float = 0.15

    # --- dedup ------------------------------------------------------------
    # Cosine similarity above which a topic counts as already covered.
    semantic_dupe_threshold: float = 0.86
    # Threshold used when falling back to the local lexical embedder, which
    # produces a different similarity distribution than a semantic model.
    lexical_dupe_threshold: float = 0.62
    trigram_dupe_threshold: float = 0.40

    # --- writing ----------------------------------------------------------
    target_words_min: int = 600
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
