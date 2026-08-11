"""Anthropic Messages API wrapper: retries, a hard call budget, structured JSON.

Every LLM call in the pipeline goes through :class:`AnthropicClient` so the
per-run call ceiling from settings cannot be bypassed by a looping critic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import anthropic
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..logging_setup import get_logger
from ..settings import Settings

log = get_logger(__name__)

RETRYABLE = (
    anthropic.RateLimitError,
    anthropic.InternalServerError,
    anthropic.APIConnectionError,
)


class BudgetExceededError(RuntimeError):
    """Raised when a run tries to exceed its LLM call ceiling."""


class RefusalError(RuntimeError):
    """The model declined the request (stop_reason == 'refusal')."""


@dataclass(slots=True)
class Usage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
        }


class AnthropicClient:
    """Thin async wrapper around the Messages API."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = anthropic.AsyncAnthropic(
            api_key=settings.require_anthropic_key().get_secret_value(),
            max_retries=0,  # tenacity owns the retry policy
        )
        self.usage = Usage()

    @property
    def calls_remaining(self) -> int:
        return max(0, self._settings.max_llm_calls - self.usage.calls)

    async def aclose(self) -> None:
        await self._client.close()

    async def complete(
        self,
        *,
        system_shared: str,
        system_specific: str,
        user: str,
        max_tokens: int,
        label: str,
        json_schema: dict[str, Any] | None = None,
        thinking: bool = False,
        effort: str | None = None,
    ) -> str:
        """One completion.

        ``system_shared`` is the style guide every agent sees; it carries the
        cache breakpoint so the writer and all four critics reuse one cached
        prefix instead of re-billing it on every call.
        """
        self._charge(label)

        system: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": system_shared,
                "cache_control": {"type": "ephemeral"},
            }
        ]
        if system_specific:
            system.append({"type": "text", "text": system_specific})

        params: dict[str, Any] = {
            "model": self._settings.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }

        output_config: dict[str, Any] = {}
        if effort:
            output_config["effort"] = effort
        if json_schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": json_schema}
        if output_config:
            params["output_config"] = output_config

        # Sonnet 5 runs adaptive thinking unless told otherwise. Critics do
        # deterministic checking, so thinking is off there to keep the run cheap.
        params["thinking"] = {"type": "adaptive"} if thinking else {"type": "disabled"}

        message = await self._send(params, label=label)
        return self._text_of(message, label=label)

    async def complete_json(
        self,
        *,
        system_shared: str,
        system_specific: str,
        user: str,
        max_tokens: int,
        label: str,
        json_schema: dict[str, Any],
        effort: str | None = None,
    ) -> dict[str, Any]:
        """A completion constrained to ``json_schema``, returned as a dict."""
        raw = await self.complete(
            system_shared=system_shared,
            system_specific=system_specific,
            user=user,
            max_tokens=max_tokens,
            label=label,
            json_schema=json_schema,
            thinking=False,
            effort=effort,
        )
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            # Structured outputs make this near-impossible, but a truncated
            # response would land here and must not read as a silent PASS.
            log.error("json_parse_failed", label=label, error=str(exc), raw=raw[:400])
            raise

    # ------------------------------------------------------------------ #

    def _charge(self, label: str) -> None:
        settings = self._settings
        if self.usage.calls >= settings.max_llm_calls:
            raise BudgetExceededError(
                f"LLM call budget of {settings.max_llm_calls} exhausted at {label!r}"
            )
        if self.usage.input_tokens >= settings.max_input_tokens_per_run:
            raise BudgetExceededError(
                f"input token budget of {settings.max_input_tokens_per_run} "
                f"exhausted at {label!r} ({self.usage.input_tokens} used)"
            )
        if self.usage.output_tokens >= settings.max_output_tokens_per_run:
            raise BudgetExceededError(
                f"output token budget of {settings.max_output_tokens_per_run} "
                f"exhausted at {label!r} ({self.usage.output_tokens} used)"
            )
        self.usage.calls += 1

    @retry(
        retry=retry_if_exception_type(RETRYABLE),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        reraise=True,
    )
    async def _send(self, params: dict[str, Any], *, label: str) -> anthropic.types.Message:
        message = await self._client.messages.create(**params)
        usage = message.usage
        self.usage.input_tokens += usage.input_tokens or 0
        self.usage.output_tokens += usage.output_tokens or 0
        self.usage.cache_read_tokens += getattr(usage, "cache_read_input_tokens", 0) or 0
        self.usage.cache_write_tokens += getattr(usage, "cache_creation_input_tokens", 0) or 0
        log.info(
            "llm_call",
            label=label,
            stop_reason=message.stop_reason,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read=getattr(usage, "cache_read_input_tokens", 0),
            calls_used=self.usage.calls,
        )
        return message

    @staticmethod
    def _text_of(message: anthropic.types.Message, *, label: str) -> str:
        if message.stop_reason == "refusal":
            raise RefusalError(f"model refused the request at {label!r}")
        parts = [block.text for block in message.content if block.type == "text"]
        text = "".join(parts).strip()
        if not text:
            raise RuntimeError(f"empty completion at {label!r} (stop={message.stop_reason})")
        if message.stop_reason == "max_tokens":
            log.warning("completion_truncated", label=label)
        return text
