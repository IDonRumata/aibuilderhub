"""Hard spending limits.

Three independent ceilings, in order of how quickly they bite:

1. calls per run          - already enforced in AnthropicClient
2. tokens per run         - stops a single runaway loop mid-flight
3. estimated spend per月  - stops repeated runs adding up

The third is the one that matters if something triggers the workflow over and
over: it persists across runs in state/usage.json and refuses to start a new
run once the month's estimate is spent.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime

from ..logging_setup import get_logger
from ..settings import Settings

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Prices:
    """US dollars per million tokens."""

    input_per_mtok: float
    output_per_mtok: float
    cache_read_per_mtok: float
    cache_write_per_mtok: float

    @classmethod
    def from_settings(cls, settings: Settings) -> Prices:
        return cls(
            input_per_mtok=settings.price_input_per_mtok,
            output_per_mtok=settings.price_output_per_mtok,
            # Cached reads bill at about a tenth of input, writes at 1.25x.
            cache_read_per_mtok=settings.price_input_per_mtok * 0.1,
            cache_write_per_mtok=settings.price_input_per_mtok * 1.25,
        )


def estimate_cost(usage: dict[str, int], prices: Prices) -> float:
    """Estimated US dollars for one run's token usage.

    An estimate, not an invoice: the authority on what you were charged is the
    Anthropic console. This exists to stop runaway spend, not to do accounting.
    """
    return (
        usage.get("input_tokens", 0) * prices.input_per_mtok
        + usage.get("output_tokens", 0) * prices.output_per_mtok
        + usage.get("cache_read_tokens", 0) * prices.cache_read_per_mtok
        + usage.get("cache_write_tokens", 0) * prices.cache_write_per_mtok
    ) / 1_000_000


class MonthlyBudget:
    """Running per-month spend estimate, persisted in state/usage.json."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._path = settings.usage_file
        self.months: dict[str, dict[str, float]] = {}
        if self._path.exists():
            try:
                loaded = json.loads(self._path.read_text(encoding="utf-8"))
                self.months = loaded if isinstance(loaded, dict) else {}
            except json.JSONDecodeError as exc:
                log.error("usage_state_unreadable", error=str(exc))

    @staticmethod
    def _key(when: datetime | None = None) -> str:
        return (when or datetime.now(UTC)).strftime("%Y-%m")

    @property
    def spent_this_month(self) -> float:
        return float(self.months.get(self._key(), {}).get("estimated_usd", 0.0))

    @property
    def remaining(self) -> float:
        return max(0.0, self._settings.monthly_budget_usd - self.spent_this_month)

    def exceeded(self) -> bool:
        return self.spent_this_month >= self._settings.monthly_budget_usd

    def record(self, usage: dict[str, int], prices: Prices) -> float:
        cost = estimate_cost(usage, prices)
        month = self.months.setdefault(
            self._key(), {"estimated_usd": 0.0, "runs": 0, "input_tokens": 0, "output_tokens": 0}
        )
        month["estimated_usd"] = round(float(month["estimated_usd"]) + cost, 6)
        month["runs"] = int(month["runs"]) + 1
        month["input_tokens"] = int(month["input_tokens"]) + usage.get("input_tokens", 0)
        month["output_tokens"] = int(month["output_tokens"]) + usage.get("output_tokens", 0)
        return cost

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Keep the last 24 months so the file cannot grow without bound.
        trimmed = dict(sorted(self.months.items())[-24:])
        self._path.write_text(
            json.dumps(trimmed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        log.info(
            "usage_recorded",
            month=self._key(),
            estimated_usd=round(self.spent_this_month, 4),
            budget_usd=self._settings.monthly_budget_usd,
        )
