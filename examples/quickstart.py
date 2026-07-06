#!/usr/bin/env python3
"""Keyless quickstart — read live market data. No account, no keys, no config.

    pip install -r python-client/requirements.txt   # once
    python examples/quickstart.py

The first call any client makes is ACTIVE_PRODUCT: is the exchange up, which
session, which contract is trading. Everything starts there.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "python-client"))

from sidepit_trader import RequestClient, pb  # noqa: E402

req = RequestClient()                        # api.sidepit.com (SIDEPIT_HOST to override)

ap = req.active_product()                    # the canonical first call
state = pb.ExchangeState.Name(ap.exchange_status.status.estate)
session = ap.exchange_status.session.session_id or ap.exchange_status.status.session_id
ticker = ap.active_contract_product.product.ticker
print(f"exchange {state} · session {session or '—'} · active contract {ticker}")

q = req.quote(ticker).quote                  # point-in-time quote
usd = f" (~${1e8 / q.last:,.0f}/BTC)" if q.last else ""
print(f"bid {q.bidsize}x{q.bid} · ask {q.ask}x{q.asksize} · last {q.last}{usd}")
print("prices are sats-per-USD: USD/BTC = 1e8 / price")

bars = req.historical_bars(ticker).bars      # 1-minute bars, oldest-first
for b in bars[-5:]:
    print(f"bar O{b.open} H{b.high} L{b.low} C{b.close} v{b.volume}")

req.close()
