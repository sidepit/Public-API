"""The TUI bridge must never trigger 12129 whole-book snapshots.

Regression for the 2026-09-09 production finding: the bridge refreshed its
open-orders panel with snapshot_sync every 10s, making the engine broadcast
the ENTIRE order book on a timer. Open orders are the remaining>0 subset of
the POSITIONS reply's orderfills — the per-account door the bridge already
polls.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve()
                       .parents[2] / "users-cli"))

from sidepit_trader._proto import pb  # noqa: E402
from sidepit_tui import bridge as bridge_mod  # noqa: E402
from sidepit_tui.bridge import Bridge  # noqa: E402


def _tpo_with_orders():
    tp = pb.TraderPositionOrders()
    resting = tp.orderfills["bc1qme:100"].order
    resting.ticker = "USDBTCU26"
    resting.side = 1
    resting.price = 1500
    resting.open_qty = 3
    resting.filled_qty = 1
    resting.remaining_qty = 2
    done = tp.orderfills["bc1qme:50"].order
    done.ticker = "USDBTCU26"
    done.side = -1
    done.price = 1600
    done.open_qty = 1
    done.filled_qty = 1
    done.remaining_qty = 0
    return tp


def test_bridge_never_imports_snapshot_sync():
    source = pathlib.Path(bridge_mod.__file__).read_text()
    assert "snapshot_sync" not in source
    assert "12129" not in source.replace(
        "never touches the 12129 snapshot stream", "").replace(
        "a 12129 whole-book snapshot", "")


def test_open_orders_come_from_orderfills():
    b = Bridge("example.invalid", on_snap=lambda s: None,
               on_event=lambda k, t: None)
    b.snap.address = "bc1qme"
    b._rq = lambda fn: fn(_FakeReq())
    b._poll_account()
    assert b.snap.open_orders == [{
        "orderid": "bc1qme:100", "ticker": "USDBTCU26", "side": "buy",
        "price": 1500, "remaining": 2, "filled": 1}]
    # the closed order is still visible in history, just not "open"
    assert {o["orderid"]: o["status"] for o in b.snap.orders} == {
        "bc1qme:100": "open", "bc1qme:50": "closed"}


class _FakeReq:
    def positions(self, address):
        assert address == "bc1qme"
        return _tpo_with_orders()
