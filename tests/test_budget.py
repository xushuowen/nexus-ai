"""Tests for the Token Budget Controller."""

import asyncio
import pytest
from unittest.mock import patch

# Ensure config is loadable
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def budget():
    from nexus.core.budget import BudgetController
    with patch("nexus.config.load_config", return_value={
        "budget": {
            "daily_limit_tokens": 1000,
            "per_request_max_tokens": 200,
            "curiosity_daily_ops": 5,
            "curiosity_per_op_tokens": 100,
            "warning_threshold": 0.8,
            "hard_stop": True,
            "reset_hour": 0,
        }
    }), patch("nexus.config.data_dir", return_value=Path(__file__).parent / "test_data"):
        bc = BudgetController()
        bc._tokens_used = 0
        bc._curiosity_ops_used = 0
        yield bc


@pytest.mark.asyncio
async def test_budget_request_allowed(budget):
    allowed = await budget.request_tokens(100, source="test")
    assert allowed is True


@pytest.mark.asyncio
async def test_budget_request_denied_when_exhausted(budget):
    budget._tokens_used = 950
    allowed = await budget.request_tokens(100, source="test")
    assert allowed is False


@pytest.mark.asyncio
async def test_budget_consume(budget):
    await budget.consume_tokens(50, source="test")
    assert budget.tokens_used == 50
    assert budget.tokens_remaining == 950


@pytest.mark.asyncio
async def test_budget_warning_threshold(budget):
    budget._tokens_used = 800
    assert budget.is_warning is True
    assert budget.is_exhausted is False


@pytest.mark.asyncio
async def test_budget_exhausted(budget):
    budget._tokens_used = 1000
    assert budget.is_exhausted is True


@pytest.mark.asyncio
async def test_curiosity_op_allowed(budget):
    allowed = await budget.request_curiosity_op(50)
    assert allowed is True
    assert budget.curiosity_ops_remaining == 4


@pytest.mark.asyncio
async def test_curiosity_op_denied_over_limit(budget):
    budget._curiosity_ops_used = 5
    allowed = await budget.request_curiosity_op(50)
    assert allowed is False


def test_budget_status(budget):
    status = budget.get_status()
    assert "tokens_used" in status
    assert "daily_limit" in status
    assert "usage_ratio" in status
    assert status["daily_limit"] == 1000
