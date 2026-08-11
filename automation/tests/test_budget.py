"""Spending limits. These are the guard against an unbounded bill."""

from __future__ import annotations

import pytest

from aibh_pipeline.clients.anthropic_client import AnthropicClient, BudgetExceededError
from aibh_pipeline.services.budget import MonthlyBudget, Prices, estimate_cost


@pytest.fixture
def budget(settings, tmp_path, monkeypatch):
    monkeypatch.setattr(type(settings), "state_dir", property(lambda self: tmp_path))
    monkeypatch.setattr(
        type(settings), "usage_file", property(lambda self: tmp_path / "usage.json")
    )
    return MonthlyBudget(settings)


def test_a_normal_run_costs_a_fraction_of_a_cent(settings):
    """The real numbers from the first successful live run."""
    cost = estimate_cost(
        {
            "input_tokens": 59926,
            "output_tokens": 12093,
            "cache_read_tokens": 29646,
            "cache_write_tokens": 1581,
        },
        Prices.from_settings(settings),
    )
    assert 0.0 < cost < 0.40


def test_spend_accumulates_and_the_ceiling_holds(settings, budget):
    prices = Prices.from_settings(settings)
    assert not budget.exceeded()

    # A million output tokens is far past a month of normal runs.
    for _ in range(30):
        budget.record({"output_tokens": 1_000_000}, prices)

    assert budget.exceeded()
    assert budget.remaining == 0.0


def test_spend_survives_a_reload(settings, budget):
    budget.record({"output_tokens": 100_000}, Prices.from_settings(settings))
    budget.save()

    reloaded = MonthlyBudget(settings)
    assert reloaded.spent_this_month == pytest.approx(budget.spent_this_month)


def test_the_call_ceiling_stops_a_runaway_loop(settings):
    client = AnthropicClient.__new__(AnthropicClient)
    client._settings = settings
    from aibh_pipeline.clients.anthropic_client import Usage

    client.usage = Usage(calls=settings.max_llm_calls)
    with pytest.raises(BudgetExceededError, match="call budget"):
        client._charge("writer-draft")


def test_the_output_token_ceiling_stops_a_runaway_loop(settings):
    from aibh_pipeline.clients.anthropic_client import Usage

    client = AnthropicClient.__new__(AnthropicClient)
    client._settings = settings
    client.usage = Usage(calls=1, output_tokens=settings.max_output_tokens_per_run)
    with pytest.raises(BudgetExceededError, match="output token budget"):
        client._charge("writer-draft")


def test_the_input_token_ceiling_stops_a_runaway_loop(settings):
    from aibh_pipeline.clients.anthropic_client import Usage

    client = AnthropicClient.__new__(AnthropicClient)
    client._settings = settings
    client.usage = Usage(calls=1, input_tokens=settings.max_input_tokens_per_run)
    with pytest.raises(BudgetExceededError, match="input token budget"):
        client._charge("writer-draft")
