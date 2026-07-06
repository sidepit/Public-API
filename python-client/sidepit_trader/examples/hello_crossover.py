#!/usr/bin/env python3
"""hello_crossover — a 5/20 moving-average crossover on the 1-minute bar feed.

The complete signal leg of a trading agent, stopping one step short of order
placement (that step is hello_taker.py; the exit step is `python -m
sidepit_trader.flatten`). Demonstrates:

  - HISTORY: backfill 1-minute bars via HISTORICAL_BARS on 12125 (oldest-first;
    walk prev_session_id back until we have enough), so the MA(20) is live from
    the first tick instead of 20 minutes after start.
  - LIVE: fold closed bars from the bar feed (12127), ticker-filtered, deduped
    on epoch against the backfill seam.
  - SIGNAL: MA(5) crossing MA(20). Prices are SATS-PER-USD (inverse): MA5
    crossing ABOVE MA20 = sats-per-USD momentum up = USD strengthening = BTC/USD
    falling. Decide which direction you actually want before trading this.

Run from python-client/:   python sidepit_trader/examples/hello_crossover.py
Env: SIDEPIT_HOST (default api.sidepit.com), SIDEPIT_TICKER (default = active).
"""
import os
import sys
from collections import deque

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from sidepit_trader import BarFeed, RequestClient  # noqa: E402
from sidepit_trader import wire  # noqa: E402

FAST, SLOW = 5, 20
HOST = os.environ.get("SIDEPIT_HOST", wire.DEFAULT_HOST)


def backfill(req: RequestClient, ticker: str, need: int) -> list:
    """Most recent `need` closed bars, oldest-first, walking the session chain back."""
    bars, session = [], ""
    for _ in range(8):                       # at most 8 sessions back
        h = req.historical_bars(ticker, session)
        bars = list(h.bars) + bars           # h.bars is oldest-first within the session
        if len(bars) >= need or not h.prev_session_id or h.prev_session_id == session:
            break
        session = h.prev_session_id
    return bars[-need:]


def main():
    req = RequestClient(HOST)
    ap = req.active_product()
    ticker = os.environ.get("SIDEPIT_TICKER") or ap.active_contract_product.product.ticker

    closes: deque = deque(maxlen=SLOW)
    last_epoch = 0
    for b in backfill(req, ticker, SLOW):
        closes.append(b.close)
        last_epoch = max(last_epoch, b.epoch)
    print(f"ticker={ticker} backfilled {len(closes)} bars (through epoch {last_epoch})")

    def mas():
        if len(closes) < SLOW:
            return None, None
        c = list(closes)
        return sum(c[-FAST:]) / FAST, sum(c) / SLOW

    fast_prev, slow_prev = mas()
    feed = BarFeed(HOST, ticker)
    print(f"live: watching MA({FAST})/MA({SLOW}) on closed 1-min bars... (Ctrl-C to stop)")
    while True:
        for b in feed.drain():
            if b.epoch <= last_epoch:        # dedupe the backfill/live seam
                continue
            last_epoch = b.epoch
            closes.append(b.close)
            fast, slow = mas()
            if fast is None:
                print(f"bar close={b.close} ({len(closes)}/{SLOW} bars)")
                continue
            signal = ""
            if fast_prev is not None:
                if fast_prev <= slow_prev and fast > slow:
                    signal = "  >>> CROSS UP (sats/USD momentum up = USD up, BTC/USD down)"
                elif fast_prev >= slow_prev and fast < slow:
                    signal = "  >>> CROSS DOWN (sats/USD momentum down = BTC/USD up)"
            print(f"bar close={b.close}  MA{FAST}={fast:.1f}  MA{SLOW}={slow:.1f}{signal}")
            fast_prev, slow_prev = fast, slow
        import time
        time.sleep(1.0)                      # bars close once a minute; poll lightly


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nbye")
