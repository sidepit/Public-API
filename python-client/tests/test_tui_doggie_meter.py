"""Doggie meter = margin capacity, from the exchange's numbers.

Fixture = Jay's live screenshots (2026-09-10): wealth 0.00319 BTC = 319,000 sats,
USDBTCU26 maint_margin 100,000 / initial_margin 200,000 sats per contract,
$500 contracts. Intraday the engine charges maintenance margin on the net
position, so 319,000 // 100,000 = 3 contracts either way — he maxed at +3 and -3.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "users-cli"))

from sidepit_tui.bridge import Snap  # noqa: E402
from sidepit_tui.doggie import meter  # noqa: E402

MAINT, INITIAL, EQUITY = 100_000, 200_000, 319_000


def snap(pos: int, margin_reject_at: float = 0.0) -> Snap:
    held = abs(pos) * MAINT
    s = Snap(maint_margin_sats=MAINT, initial_margin_sats=INITIAL,
             available_margin=EQUITY - held, available_balance=EQUITY,
             contract_usd=500, last=1293, is_open=True, state="EXCHANGE_OPEN",
             margin_reject_at=margin_reject_at)
    if pos:
        s.positions = [{"ticker": "USDBTCU26", "contracts": pos, "margin_required": held,
                        "entry_price": 1293, "side": "long" if pos > 0 else "short",
                        "realized_pnl": 0, "reduce_only": False, "open_bids": 0, "open_asks": 0}]
    return s


def test_flat_account_sits_in_the_middle_with_three_taps_each_way():
    m = meter(snap(0), now=1000.0)
    assert (m["n_max"], m["points"], m["index"]) == (3, 7, 3)
    assert m["room"] == 3 and not m["at_max"]


def test_max_short_is_the_left_end_and_max_levered_the_right_end():
    short = meter(snap(+3), now=1000.0)
    assert (short["index"], short["at_max"], short["taps_left"]) == (0, True, 0)
    levered = meter(snap(-3), now=1000.0)
    assert (levered["index"], levered["at_max"], levered["taps_left"]) == (6, True, 0)


def test_jays_rule_long_one_with_room_two():
    # position -1 (levered one), available margin = 2 contracts of maintenance:
    # 2 more the same way, 2+1+1 = 4 steps the other way.
    m = meter(snap(-1), now=1000.0)
    assert m["room"] == 2 and m["n_max"] == 3 and m["points"] == 7
    assert m["index"] == 4                       # dot one right of centre
    assert m["n_max"] - abs(m["pos"]) == 2       # same direction
    assert abs(m["pos"]) + m["n_max"] == 4       # opposite direction
    assert not m["at_max"]


def test_exchange_margin_rejection_pins_max_briefly_then_clears():
    s = snap(-2, margin_reject_at=1000.0)
    assert meter(s, now=1003.0)["at_max"]
    assert not meter(s, now=1020.0)["at_max"]


def test_unknown_margin_spec_degrades_honestly():
    s = snap(0); s.maint_margin_sats = 0
    m = meter(s, now=1000.0)
    assert not m["known"] and m["n_max"] == 0
