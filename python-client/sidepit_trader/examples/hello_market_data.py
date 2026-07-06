#!/usr/bin/env python3
"""hello_market_data — subscribe to the price feed and print quotes. No keys needed.

Demonstrates the three habits every Sidepit feed consumer must have:
  1. TICKER FILTERING — feeds interleave one message per product per epoch.
  2. PRICE INVERSION — prices are sats-per-USD; USD/BTC = 1e8 / px.
  3. THE DRAIN PATTERN — the order feed (12124) emits MULTIPLE OrderData per epoch
     in multi-product deployments; read until more_in_epoch == 0 (equivalently:
     non-blocking recv until empty) before acting on the book.

Run from python-client/:   python sidepit_trader/examples/hello_market_data.py
Env: SIDEPIT_HOST (default api.sidepit.com), SIDEPIT_TICKER (default = active product).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

import pynng  # noqa: E402

from sidepit_trader import RequestClient, pb  # noqa: E402
from sidepit_trader import wire  # noqa: E402

HOST = os.environ.get("SIDEPIT_HOST", wire.DEFAULT_HOST)


def main():
    # Which contract is trading right now? (Don't hardcode tickers — they roll.)
    req = RequestClient(HOST)
    ap = req.active_product()
    ticker = os.environ.get("SIDEPIT_TICKER") or ap.active_contract_product.product.ticker
    state = pb.ExchangeState.Name(ap.exchange_status.status.estate)  # names, not ints
    print(f"host={HOST} ticker={ticker} state={state}")
    if state != "EXCHANGE_OPEN":
        print("note: feeds are silent while the exchange is closed — this is normal.")

    try:
        price_sub = wire.open_sub(HOST, wire.Ports.PRICE_FEED)  # MarketData, ~1/s when OPEN
        order_sub = wire.open_sub(HOST, wire.Ports.ORDER)       # OrderData (book + fills)
    except Exception as e:
        # During EXCHANGE_CLOSED hours the feed publishers may be down entirely —
        # the dial itself fails. Not a client bug.
        sys.exit(f"feed connect failed ({e}); exchange state is {state} — "
                 f"try again when the session is OPEN.")
    # The dial can also "succeed" asynchronously with nothing publishing behind it
    # (closed hours). Bound the wait so we report instead of blocking forever.
    price_sub.recv_timeout = 30_000  # ms

    print("waiting for MarketData... (Ctrl-C to stop)")
    while True:
        try:
            raw = price_sub.recv()                           # blocks for the next epoch
        except pynng.Timeout:
            state = pb.ExchangeState.Name(req.active_product().exchange_status.status.estate)
            print(f"no data for 30s (state={state}) — feeds publish only while "
                  f"EXCHANGE_OPEN; still waiting...")
            continue
        md = pb.MarketData()
        md.ParseFromString(raw)
        if md.ticker != ticker:                              # (1) FILTER — multi-product!
            continue
        q = md.quote
        usd = 1e8 / q.last if q.last else 0.0                # (2) INVERSION
        print(f"epoch={md.epoch} bid={q.bidsize}x{q.bid} ask={q.ask}x{q.asksize} "
              f"last={q.last} (~${usd:,.0f}/BTC)")

        # (3) DRAIN the order feed until empty before trusting the book view.
        # One epoch can carry several OrderData (one per active ticker); acting on
        # the first message only gives a partial, incorrect book.
        fills = 0
        while True:
            try:
                raw = order_sub.recv(block=False)
            except pynng.TryAgain:
                break                                        # drained: more_in_epoch == 0
            od = pb.OrderData()
            od.ParseFromString(raw)
            if od.ticker == ticker:
                fills += len(od.fills)
        if fills:
            print(f"  ... {fills} fill(s) this epoch on {ticker}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nbye")
