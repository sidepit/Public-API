"""The cockpit's BTC/SATS toggle remains exact at the wire boundary."""
import sys
from pathlib import Path


USERS_CLI = Path(__file__).resolve().parents[2] / "users-cli"
sys.path.insert(0, str(USERS_CLI))

from sidepit_tui.app import SidepitApp  # noqa: E402


def test_unlock_amount_parses_btc_and_sats_to_the_same_wire_amount():
    assert SidepitApp._parse_money_input("0.005", "BTC") == 500_000
    assert SidepitApp._parse_money_input("500,000", "SATS") == 500_000


def test_max_and_blank_both_mean_full_unlock():
    assert SidepitApp._parse_money_input("MAX", "BTC") is None
    assert SidepitApp._parse_money_input("", "SATS") is None


def test_numeric_unlock_value_round_trips_across_toggle():
    sats = SidepitApp._parse_money_input("0.00500001", "BTC")
    assert sats == 500_001
    assert SidepitApp._money_input(sats, "SATS") == "500,001"
    assert SidepitApp._money_input(sats, "BTC") == "0.00500001"
