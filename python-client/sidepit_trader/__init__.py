"""sidepit_trader — the public taker SDK over the low-level python-client.

A taker reacts to the ordinary exchange feeds (price, 1-minute bars, fills) and
positions — no epoch clock, no auction. `Trader` is the synchronous feed-reactor
base you subclass (override `on_bar` / `decide`); the rest are protocol
primitives — signing, submit, request/reply — plus a local SQLite store that
ships with the SDK (bars + identity, "the beginning of statedb") and a
`SwingTracker` for breakout levels.

Quick start:
    from sidepit_trader import Trader, Signer, TakerStore
    class MyTaker(Trader):
        def on_bar(self, bar): ...      # update your levels
        def decide(self, ctx): ...      # cross via ctx.submitter
    MyTaker(host="api.sidepit.com",
            signer=Signer.from_wif(MY_WIF, MY_SIDEPIT_ID),
            ticker="USDBTCM26").run()

Runnable starters live in `sidepit_trader/examples/`; `python -m sidepit_trader.wallet
new` mints an identity and `python -m sidepit_trader.flatten` is the emergency exit.
"""
from ._proto import pb
from .errors import SidepitError, CourierRuleError
from .signer import Signer, signer_from_env, wif_to_priv_hex
from .submit import Submitter, order_id
from .reqrep import RequestClient
from .feeds import PriceFeed, BarFeed, OrderFeed, RejectionFeed
from .sync import snapshot_sync
from .flatten import flatten
from .store import TakerStore, DEFAULT_PATH
from .swings import SwingTracker, Swing
from .trader import Trader, TraderContext

__all__ = [
    "pb", "SidepitError", "CourierRuleError",
    "Signer", "signer_from_env", "wif_to_priv_hex", "Submitter", "order_id",
    "RequestClient",
    "PriceFeed", "BarFeed", "OrderFeed", "RejectionFeed",
    "snapshot_sync", "flatten",
    "TakerStore", "DEFAULT_PATH", "SwingTracker", "Swing", "Trader", "TraderContext",
]
