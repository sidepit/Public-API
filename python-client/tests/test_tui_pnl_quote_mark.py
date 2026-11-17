"""Open P&L is marked from the quote, as the web app does it: a long at the ask,
a short at the bid, and never at the last trade when the quote is missing."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "users-cli"))

from sidepit_tui.app import equity_sats, position_mark, position_pnl  # noqa: E402
from sidepit_tui.bridge import Snap  # noqa: E402

T = "USDBTCU26"


def pos(contracts: int, entry: float = 1300, ticker: str = T) -> dict:
    return {"ticker": ticker, "contracts": contracts, "entry_price": entry,
            "margin_required": 0, "side": "long" if contracts > 0 else "short",
            "realized_pnl": 0, "reduce_only": False, "open_bids": 0, "open_asks": 0}


def snap(positions, bid=1290, ask=1310, last=1300, is_open=True) -> Snap:
    s = Snap(ticker=T, bid=bid, ask=ask, last=last, is_open=is_open,
             available_balance=500_000, realized_pnl=1_000,
             tick_size_sats=1, tick_value_sats=500)
    s.positions = positions
    return s


def test_long_marks_at_the_ask_and_short_at_the_bid():
    s = snap([pos(+2)])
    assert position_mark(s, s.positions[0]) == 1310
    assert position_pnl(s, s.positions[0]) == 2 * (1310 - 1300) * 500
    s = snap([pos(-2)])
    assert position_mark(s, s.positions[0]) == 1290
    assert position_pnl(s, s.positions[0]) == -2 * (1290 - 1300) * 500


def test_equity_adds_realized_and_the_quote_marked_open_pnl():
    s = snap([pos(+1)])
    assert equity_sats(s) == (500_000 + 1_000 + 5_000, 5_000)


def test_missing_quote_side_is_unknown_not_the_last_trade():
    s = snap([pos(+1)], ask=0)                 # last is 1300 and must not be used
    assert position_pnl(s, s.positions[0]) is None
    assert equity_sats(s) == (501_000, None)   # open P&L left out, not guessed


def test_position_on_another_ticker_has_no_mark():
    s = snap([pos(+1, ticker="USDBTCZ26")])
    assert position_pnl(s, s.positions[0]) is None
    assert equity_sats(s)[1] is None


def test_flat_and_closed_need_no_mark():
    assert equity_sats(snap([pos(0)], bid=0, ask=0)) == (501_000, 0)
    assert equity_sats(snap([pos(+3)], is_open=False)) == (500_000, 0)
