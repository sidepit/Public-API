"""Doggie/cockpit market intents stay price-less market orders (fill what they can, rest cancels)."""
import sys
from pathlib import Path


USERS_CLI = Path(__file__).resolve().parents[2] / "users-cli"
sys.path.insert(0, str(USERS_CLI))

from sidepit_tui.intents import parse  # noqa: E402


def test_market_intent_is_a_market_order_without_a_price():
    intent = parse("buy 2 at market", last_sats=1548, contract_usd=500)
    assert intent.kind == "MKT"
    assert intent.side == 1
    assert intent.size == 2
    assert intent.price == 0
    assert "market order" in intent.summary
    assert "the rest cancels" in intent.summary
    assert "auction" not in intent.summary.lower()


def test_flatten_intent_uses_market_closes():
    intent = parse("go flat")
    assert intent.kind == "FLATTEN_ALL"
    assert "market orders to close" in intent.summary


def test_order_size_is_capped():
    import pytest
    from sidepit_tui.intents import MAX_CONTRACTS, parse
    assert parse(f"buy {MAX_CONTRACTS} at market", last_sats=1200, contract_usd=500).size == MAX_CONTRACTS
    with pytest.raises(ValueError, match="max 1000 contracts"):
        parse("buy 22112212222112 at market", last_sats=1200, contract_usd=500)
    with pytest.raises(ValueError, match="max 1000 contracts"):
        parse("sell 1001 @ 1259", last_sats=1200, contract_usd=500)
