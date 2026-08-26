"""Prompt → typed intent. The cockpit's core loop (TUI-Design-Handoff §priorities):
the user types plain english, we SHOW the parsed intent as a `[sys]` line, then
execute. The parser is deliberately keyword-based and honest — it either produces
a typed intent it can explain, or says it didn't understand. No guessing with
money.

Real-system rules enforced here (mockup fiction loses):
  - "market" orders are native immediate-or-cancel orders (`NewOrder.price=0`);
    available opposite liquidity fills and every unfilled remainder cancels in
    the same DLOB deterministic auction.
  - sizes are integer CONTRACTS on the wire; `0.25 btc` is converted via the
    live price (1 contract = $contract_size, $1 = price_sats sats).
  - prices are sats-per-USD (the native book unit).
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Intent:
    kind: str          # LMT | MKT | CANCEL_ALL | CANCEL | FLATTEN_ALL | RISK | BOOK | HELP
    summary: str       # the `[sys] parsed →` line shown to the user
    side: int = 0
    size: int = 0
    price: int = 0
    orderid: str = ""


HELP = ("commands: buy/sell <n> @ <price> · buy/sell <n> at market · "
        "buy/sell <x> btc at market · cancel all · cancel <orderid-tail> · "
        "go flat / flatten · risk · book · help")

_LMT = re.compile(r"^(buy|sell|b|s)\s+([\d.,]+)\s*(btc)?\s*(?:@|at)\s*([\d,]+)$")
_MKT = re.compile(r"^(buy|sell|b|s)\s+([\d.,]+)\s*(btc)?\s+(?:at\s+)?(?:market|mkt)$")
_CXL = re.compile(r"^cancel\s+(.+)$")


def _contracts(qty_raw: str, is_btc: bool, last_sats: int, contract_usd: int) -> int:
    """Integer contracts from either a contract count or a BTC notional."""
    q = float(qty_raw.replace(",", ""))
    if not is_btc:
        return int(q)
    if last_sats <= 0 or contract_usd <= 0:
        raise ValueError("no live price to convert btc notional — use contracts")
    # q BTC = q*1e8 sats; one contract = contract_usd * last_sats sats of notional.
    # NEVER round a sub-contract request up: asking for 0.001 BTC (~$79) and
    # getting one $500 contract is a silent 6x. Say the real number instead.
    exact = q * 1e8 / (contract_usd * last_sats)
    usd = q * 1e8 / last_sats
    if exact < 1:
        raise ValueError(
            f"{q:g} BTC is about ${usd:,.0f} — less than one contract "
            f"(${contract_usd:,} each). Size in contracts: 'buy 1 at market'")
    return int(exact)          # truncate: never more exposure than asked for


def parse(text: str, *, last_sats: int = 0, contract_usd: int = 500) -> Intent:
    t = " ".join(text.strip().lower().split())
    if not t or t in ("help", "?"):
        return Intent("HELP", HELP)
    if t in ("go flat", "go flat and exit", "flatten", "flatten all", "exit all"):
        return Intent("FLATTEN_ALL",
                      "parsed → FLATTEN_ALL · cancel all working orders, then send "
                      "IOC market closes for every position")
    if t in ("cancel all", "cancel all working orders", "cancel everything"):
        return Intent("CANCEL_ALL", "parsed → CANCEL_ALL · cancel all working orders")
    if t in ("risk", "what's my risk", "whats my risk", "what's my risk in btc terms",
             "show me my risk"):
        return Intent("RISK", "parsed → RISK · BTC-denominated envelope")
    if t in ("book", "show book", "show me the book", "show me the book before i send"):
        return Intent("BOOK", "parsed → BOOK · 5-level transparent book (always on)")
    m = _LMT.match(t)
    if m:
        side = 1 if m.group(1)[0] == "b" else -1
        size = _contracts(m.group(2), bool(m.group(3)), last_sats, contract_usd)
        price = int(m.group(4).replace(",", ""))
        if size <= 0 or price <= 0:
            raise ValueError("size and price must be positive")
        return Intent("LMT",
                      f"parsed → LMT {'BUY' if side > 0 else 'SELL'} {size} @ {price} "
                      f"sats/USD · routing to the next DLOB deterministic auction",
                      side=side, size=size, price=price)
    m = _MKT.match(t)
    if m:
        side = 1 if m.group(1)[0] == "b" else -1
        size = _contracts(m.group(2), bool(m.group(3)), last_sats, contract_usd)
        if size <= 0:
            raise ValueError("size must be positive")
        return Intent("MKT",
                      f"parsed → MKT {'BUY' if side > 0 else 'SELL'} {size} · "
                      f"native IOC: fill available liquidity, cancel every remainder · "
                      f"routing to the next DLOB auction",
                      side=side, size=size)
    m = _CXL.match(t)
    if m:
        tail = m.group(1).strip()
        return Intent("CANCEL", f"parsed → CANCEL ·…{tail[-18:]}", orderid=tail)
    raise ValueError(f"didn't understand: '{text.strip()}' — try 'help'")
