"""Doggy/cockpit market intents stay native IOC and price-less."""
import sys
from pathlib import Path


USERS_CLI = Path(__file__).resolve().parents[2] / "users-cli"
sys.path.insert(0, str(USERS_CLI))

from sidepit_tui.intents import parse  # noqa: E402


def test_market_intent_is_native_ioc_without_a_price():
    intent = parse("buy 2 at market", last_sats=1548, contract_usd=500)
    assert intent.kind == "MKT"
    assert intent.side == 1
    assert intent.size == 2
    assert intent.price == 0
    assert "native IOC" in intent.summary
    assert "cancel every remainder" in intent.summary


def test_flatten_intent_uses_ioc_market_closes():
    intent = parse("go flat")
    assert intent.kind == "FLATTEN_ALL"
    assert "IOC market closes" in intent.summary
