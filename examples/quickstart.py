#!/usr/bin/env python3
"""Keyless quickstart — read live market data. No account, no keys, no config.

    pip install -r python-client/requirements.txt   # once
    python examples/quickstart.py

The first call any client makes is ACTIVE_PRODUCT: is the exchange up, which
session, which contract is trading. Everything starts there.
"""
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "python-client"))

from sidepit_trader import RequestClient, pb  # noqa: E402


def local_time(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).astimezone().isoformat()


def next_open(req, ticker):
    now = int(time.time() * 1000)
    future = [s for s in req.schedules().products
              if s.trading_open_time > now and ticker in s.product]
    if not future:
        return "not published"
    return local_time(min(future, key=lambda s: s.trading_open_time).trading_open_time)


def network_help(exc):
    detail = str(exc).lower()
    if "permission" in detail or "operation not permitted" in detail:
        cause = "network permission denied"
    elif "name or service" in detail or "getaddrinfo" in detail or "dns" in detail:
        cause = "DNS lookup failed"
    elif "refused" in detail:
        cause = "connection refused"
    elif "timed out" in detail or type(exc).__name__ in ("TryAgain", "Timeout"):
        cause = "connection timed out"
    else:
        cause = type(exc).__name__
    return (f"{cause}. Your agent may need permission to reach "
            "api.sidepit.com:12125; check network access and run this command again.")


def main():
    req = RequestClient()                    # api.sidepit.com (SIDEPIT_HOST to override)
    try:
        ap = req.active_product()            # the canonical first call
        state = pb.ExchangeState.Name(ap.exchange_status.status.estate)
        ticker = ap.active_contract_product.product.ticker
        contract = ap.active_contract_product.contract
        product = ap.active_contract_product.product
        print(f"exchange {state} · active forward {ticker}")

        q = req.quote(ticker).quote          # point-in-time quote
        usd = f" (~${1e8 / q.last:,.0f}/BTC)" if q.last else ""
        print(f"bid {q.bidsize}x{q.bid} · ask {q.ask}x{q.asksize} · last {q.last}{usd}")
        print("prices are sats-per-USD: USD/BTC = 1e8 / price")
        print(f"one contract = ${contract.unit_size:,} of USD exposure · "
              f"initial margin {contract.initial_margin:,} sats · "
              f"maintenance {contract.maint_margin:,} sats")
        print(f"expires {local_time(product.expiration_date)}")
        if state != "EXCHANGE_OPEN":
            print(f"market closed · next published open {next_open(req, ticker)}")

        bars = req.historical_bars(ticker).bars
        useful = []
        last_shape = None
        for b in bars:
            shape = (b.open, b.high, b.low, b.close, b.volume)
            if not any(shape) or shape == last_shape:
                continue
            useful.append(b)
            last_shape = shape
        for b in useful[-2:]:
            print(f"recent bar O{b.open} H{b.high} L{b.low} C{b.close} v{b.volume}")
    finally:
        req.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        sys.exit("quickstart: " + network_help(exc))
