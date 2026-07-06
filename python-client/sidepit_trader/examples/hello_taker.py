#!/usr/bin/env python3
"""hello_taker — the smallest real taker: subclass Trader, place ONE order, exit.

Needs a FUNDED identity (mint one: `python -m sidepit_trader.wallet`, deposit to it):
    SIDEPIT_ID=bc1q...  and  SIDEPIT_WIF=...  (or SIDEPIT_PRIV_HEX=...)

What it shows:
  - the Trader base: connect, seed state, react on the price-feed pulse
  - decide(ctx): runs only while EXCHANGE_OPEN, with the latest quote cached
  - submitting a marketable limit (Sidepit has no native market order type)
  - order verbs return the full orderid string "{sidepit_id}:{timestamp_ns}" —
    the handle that identifies the order on every feed
  - fills arrive on the order feed (ctx.position); rejects on 12128

Run from python-client/:   python sidepit_trader/examples/hello_taker.py
Env: SIDEPIT_HOST (default api.sidepit.com), SIDEPIT_TICKER (default = active).
"""
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from sidepit_trader import Signer, Trader, signer_from_env  # noqa: E402
from sidepit_trader import wire  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")


class HelloTaker(Trader):
    """Buys 1 contract at the first quote it sees, reports the fill, then idles."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.sent = False

    def on_open(self):
        print(f"exchange OPEN (session {self.session_id}); waiting for a quote...")

    def decide(self, ctx):
        if self.sent:
            return
        q = ctx.quote
        if not (q and (q.ask or q.last or q.bid)):
            return                                    # zero = empty side; don't price off it
        # Marketable limit: cross 2 ticks THROUGH the ask. Price is sats-per-USD.
        # Submitter signs (SHA256 -> ECDSA compact -> hex, signature_version=0)
        # and returns the full orderid string.
        oid, px = ctx.submitter.market_order(side=1, size=1, ticker=ctx.ticker,
                                             bid=q.bid, ask=q.ask, last=q.last,
                                             cross_ticks=2)
        if oid is None:
            return
        print(f"sent BUY 1 {ctx.ticker} @ {px} (orderid {oid})")
        print("outcomes arrive on the feeds: position updates on fill; "
              "12128 carries any rejection (RC_MARGIN = fund the account).")
        self.sent = True

    def on_bar(self, bar):
        print(f"closed 1-min bar: O{bar.open} H{bar.high} L{bar.low} C{bar.close} "
              f"v{bar.volume}  (sats-per-USD — Sidepit high is the USD low)")

    def on_shutdown(self):
        if self.sent and self.orders is not None:
            print(f"net position from own fills: {self.orders.position}")


def identity_from_env() -> Signer:
    """Delegate-aware env handoff: SIDEPIT_WIF=<agent key> + SIDEPIT_ID=<custody>
    yields an as_delegate signer (agent_id stamped); same/absent SIDEPIT_ID = direct."""
    try:
        return signer_from_env()
    except ValueError as e:
        sys.exit(f"{e}; to mint a key: python -m sidepit_trader.wallet")


if __name__ == "__main__":
    HelloTaker(
        host=os.environ.get("SIDEPIT_HOST", wire.DEFAULT_HOST),
        signer=identity_from_env(),
        ticker=os.environ.get("SIDEPIT_TICKER", ""),   # "" -> follow the active product
    ).run()
