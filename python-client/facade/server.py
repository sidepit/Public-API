"""Sidepit gateway — public JSON REST + WS over the NNG/protobuf core.

The HTTP boundary for external integrations (CCXT first). Server-side, hostable:
all READS are non-custodial (parameterized by address — account state is public on this
venue), and the WRITE path is a RELAY: clients sign their own Transaction protobuf
(SHA256 → secp256k1 compact → hex, signature_version=0) and POST the serialized
SignedTransaction; the gateway holds NO keys and pushes the bytes to port 12121 with the
idle-reopen discipline. (Custody model "B": reads served publicly, signing client-side.)

Interim model "A" (optional, off by default): start with SIDEPIT_WIF/SIDEPIT_PRIV_HEX
(+ SIDEPIT_ID for delegate mode) and POST /orders signs server-side with that trade-only
delegate key — the familiar CEX api-key UX. Never logged, never echoed.

Env: SIDEPIT_HOST (default api.sidepit.com), GATEWAY_HOST (default 127.0.0.1 for dev;
set 0.0.0.0 behind TLS when hosting), GATEWAY_PORT (default 8642).

Run from python-client/:   python -m facade.server
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import threading
import time
from collections import deque

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_here, "..")))

import pynng  # noqa: E402
import uvicorn  # noqa: E402
# uvicorn serves WS only if a websocket library is importable — otherwise it
# silently 404s every upgrade (cost us an hour on the test box). Fail LOUDLY.
try:
    import websockets  # noqa: E402,F401
except ImportError as _e:
    raise SystemExit("FATAL: the 'websockets' package is required for the WS "
                     "endpoints (pip install websockets) — uvicorn would 404 "
                     "all upgrades without it") from _e
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from google.protobuf.json_format import MessageToJson, ParseDict  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from sidepit_trader import wire  # noqa: E402
from sidepit_trader._proto import pb  # noqa: E402
from sidepit_trader.reqrep import RequestClient  # noqa: E402
from sidepit_trader.signer import Signer, wif_to_priv_hex  # noqa: E402
from sidepit_trader.submit import RECONNECT_IDLE_SECS, Submitter, order_id  # noqa: E402
from sidepit_trader.sync import snapshot_sync  # noqa: E402
from sidepit_trader.wallet import sidepit_id_from_priv  # noqa: E402

log = logging.getLogger("gateway")

HOST = os.environ.get("SIDEPIT_HOST", wire.DEFAULT_HOST)
BIND = os.environ.get("GATEWAY_HOST", "127.0.0.1")
PORT = int(os.environ.get("GATEWAY_PORT", "8642"))

MARKETS_TTL_SECS = 60.0
FEED_SILENCE_RESUB_SECS = 60.0
TRADES_RING = 1000
BARS_RING = 1500
MAX_TRACKED_ORDERS = 50_000
MAX_TRACKED_ADDRS = 500

# RejectCode name -> expected-in-normal-operation? (CCXT maps to error classes BY NAME)
REJECT_EXPECTED = {"RC_CDUP": True, "RC_CREJ": True, "RC_MARGIN": True, "RC_REDUCE": True}


# ---------------------------------------------------------------------------
# optional interim model "A": server-held trade-only delegate key
# ---------------------------------------------------------------------------
class AKey:
    def __init__(self):
        wif = os.environ.get("SIDEPIT_WIF")
        priv = os.environ.get("SIDEPIT_PRIV_HEX") or (wif_to_priv_hex(wif) if wif else None)
        custody = os.environ.get("SIDEPIT_ID", "")
        self.signer = None
        self.sidepit_id = ""
        if priv:
            own = sidepit_id_from_priv(priv)
            self.signer = (Signer(priv, custody, trader_id=own) if custody and custody != own
                           else Signer(priv, custody or own))
            self.sidepit_id = self.signer.sidepit_id
            log.info("interim A-mode signing enabled for %s", self.sidepit_id)


AKEY = AKey()
_a_submitter = Submitter(AKEY.signer, HOST) if AKEY.signer else None

_req = RequestClient(HOST)
_req_lock = threading.Lock()      # one REQ socket; reqrep is strictly serial

_ns_lock = threading.Lock()
_last_ns = 0


def next_ns() -> int:
    """Strictly increasing nanosecond nonce (Transaction.timestamp / orderid suffix)."""
    global _last_ns
    with _ns_lock:
        _last_ns = max(int(time.time() * 1e9), _last_ns + 1)
        return _last_ns


class RawPusher:
    """Push pre-serialized SignedTransaction bytes to 12121 (relay write path).
    Same idle-reopen discipline as Submitter: the LB silently drops idle pipes and
    NNG still reports send() success, so reopen proactively before a risky send."""

    def __init__(self, host: str):
        self._host = host
        self._sock = wire.open_push(host)
        self._last = 0.0
        self._lock = threading.Lock()

    def push(self, data: bytes) -> None:
        with self._lock:
            now = time.monotonic()
            if self._last and now - self._last > RECONNECT_IDLE_SECS:
                try:
                    self._sock.close()
                except Exception:
                    pass
                self._sock = wire.open_push(self._host)
            try:
                self._sock.send(data)
            except pynng.Timeout:
                try:
                    self._sock.close()
                except Exception:
                    pass
                self._sock = wire.open_push(self._host)
                self._sock.send(data)
            self._last = time.monotonic()


_pusher = RawPusher(HOST)


# ---------------------------------------------------------------------------
# shared state (written by the feed thread, read by HTTP handlers)
# ---------------------------------------------------------------------------
STATE = {
    "tickers": {},        # ticker -> latest quote dict
    "orderbooks": {},     # ticker -> {bids, asks, epoch_ms}
    "bars": {},           # ticker -> deque [[ms,o,h,l,c,v]...]
    "trades": {},         # ticker -> deque of market trades (whole venue)
    "orders": {},         # orderid -> order dict (every bookorder seen; bounded)
    "order_lru": deque(), # insertion order for eviction
    "my_trades": {},      # address -> deque of that address's fills (lazy, bounded)
    "rejections": {},     # address -> deque of rejection dicts (lazy, bounded)
    "margin_states": {},  # address -> latest TraderMarginState dict
    "feed_alive_at": 0.0,
}
_seeded_addrs: set[str] = set()
_markets_cache = {"at": 0.0, "markets": [], "status": {}}
_state_cache = {"at": 0.0, "state": None}   # refreshed by every _status_dict() call


def _addr_ring(table: str, addr: str) -> deque:
    rings = STATE[table]
    ring = rings.get(addr)
    if ring is None:
        if len(rings) >= MAX_TRACKED_ADDRS:
            rings.pop(next(iter(rings)))
        ring = rings[addr] = deque(maxlen=TRADES_RING)
    return ring


def _track_order(oid: str, o: dict) -> None:
    if oid not in STATE["orders"] and len(STATE["orders"]) >= MAX_TRACKED_ORDERS:
        while STATE["order_lru"]:
            old = STATE["order_lru"].popleft()
            od = STATE["orders"].get(old)
            if od is not None and od["status"] != "open":
                del STATE["orders"][old]
                break
    if oid not in STATE["orders"]:
        STATE["order_lru"].append(oid)
    STATE["orders"][oid] = o


def _order_dict(oid: str, ticker: str, side: int, amount: int, price: int, ts_ns: int):
    return {
        "orderid": oid, "ticker": ticker, "side": "buy" if side > 0 else "sell",
        "price": price, "amount": amount, "filled": 0, "remaining": amount,
        "status": "open",            # open|closed|canceled|rejected
        "timestamp_ns": ts_ns, "timestamp_ms": ts_ns // 1_000_000,
        "average_fill_price": None, "reject_code": None, "reject_expected": None,
        "cancel_requested_ns": None,
        "note": "sequenced-batch venue: status is observational (order feed/reject feed); "
                "orders resolve at the next 1s epoch, never instantly",
    }


# ---------------------------------------------------------------------------
# WS fan-out
# ---------------------------------------------------------------------------
_ws_clients: dict[WebSocket, dict] = {}   # conn -> {"channels": set, "address": str}
_event_q: asyncio.Queue | None = None
_loop: asyncio.AbstractEventLoop | None = None


def emit(channel: str, symbol: str, data, address: str = "") -> None:
    """Queue a WS event from any thread. `address` tags account-scoped events."""
    if _loop is None or _event_q is None:
        return
    msg = {"channel": channel, "symbol": symbol, "address": address,
           "ts": int(time.time() * 1000), "data": data}
    _loop.call_soon_threadsafe(_event_q.put_nowait, msg)


async def _broadcaster():
    while True:
        msg = await _event_q.get()
        dead = []
        for ws, sub in list(_ws_clients.items()):
            chans = sub["channels"]
            if chans and msg["channel"] not in chans:
                continue
            if msg["address"] and sub["address"] and msg["address"] != sub["address"]:
                continue
            try:
                await ws.send_json(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            _ws_clients.pop(ws, None)


# ---------------------------------------------------------------------------
# feed thread — drain 12122/12127/12124/12128, fold state, emit WS events
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# LEGACY website compat (frontend.test.sidepit.com/trade) — delete this whole
# section once the site moves to the modern /ws protocol. Reproduces the old
# cex-ws/cex-tx/cex-reqrep surface exactly: WS /feed /order /echo broadcast
# bare MessageToJson (camelCase, defaults included) of MarketData / OrderData /
# TxBlockStream; POST /tx takes proto-JSON SignedTransaction; POST
# /position/request_position returns the {'message','response'} envelope with
# snake_case names. The current proto is a superset of the old one, so the
# old page parses these unchanged.
# ---------------------------------------------------------------------------
_legacy_clients: dict[str, set] = {'feed': set(), 'order': set(), 'echo': set()}


def emit_legacy(kind: str, m) -> None:
    # old-protocol firehose; serialization only happens when someone listens
    if _loop is None or not _legacy_clients[kind]:
        return
    try:
        text = MessageToJson(m, including_default_value_fields=True)
    except Exception:
        return
    _loop.call_soon_threadsafe(_legacy_send_nowait, kind, text)


def _legacy_send_nowait(kind: str, text: str) -> None:
    for ws in list(_legacy_clients[kind]):
        asyncio.ensure_future(_legacy_send_one(kind, ws, text))


async def _legacy_send_one(kind: str, ws, text: str) -> None:
    try:
        await ws.send_text(text)
    except Exception:
        _legacy_clients[kind].discard(ws)


def _on_echo(m) -> None:
    emit_legacy('echo', m)


ECHO_PORT = 12123


def _open_subs():
    subs = {}
    for name, port in (("price", wire.Ports.PRICE_FEED), ("bar", wire.Ports.BAR),
                       ("order", wire.Ports.ORDER), ("reject", wire.Ports.REJECTIONS),
                       ("echo", ECHO_PORT)):
        s = wire.open_sub(HOST, port)
        s.recv_buffer_size = 1024          # NNG RECVBUF: survive bursts (lossy Sub0)
        subs[name] = s
    return subs


def _on_market_data(md) -> None:
    t = md.ticker
    q = md.quote
    tick = {"ticker": t, "bid": q.bid, "bidsize": q.bidsize, "ask": q.ask,
            "asksize": q.asksize, "last": q.last, "lastsize": q.lastsize,
            "epoch_ms": int(md.epoch)}
    STATE["tickers"][t] = tick
    ob = {"ticker": t,
          "bids": [[d.b, d.bs] for d in md.depth if d.b > 0],
          "asks": [[d.a, getattr(d, "as")] for d in md.depth if d.a > 0],
          "epoch_ms": int(md.epoch)}
    STATE["orderbooks"][t] = ob
    emit("ticker", t, tick)
    emit("orderbook", t, ob)
    emit_legacy("feed", md)


def _on_bar(b) -> None:
    row = [int(b.epoch), b.open, b.high, b.low, b.close, b.volume]
    ring = STATE["bars"].setdefault(b.ticker, deque(maxlen=BARS_RING))
    if not ring or ring[-1][0] != row[0]:
        ring.append(row)
        emit("ohlcv", b.ticker, row)


def _fold_fill(f, ticker: str) -> None:
    for oid, is_aggr in ((f.agressiveid, True), (f.passiveid, False)):
        addr = oid.rsplit(":", 1)[0]
        if not addr:
            continue
        side = f.agressive_side if is_aggr else -f.agressive_side
        trade = {"orderid": oid, "ticker": ticker, "price": f.price, "amount": f.qty,
                 "side": "buy" if side > 0 else "sell", "taker": is_aggr,
                 "microtime_us": int(f.microtime),
                 "timestamp_ms": int(f.microtime) // 1000,
                 "id": f"{f.microtime}-{oid[-12:]}"}
        _addr_ring("my_trades", addr).append(trade)
        emit("my_trades", ticker, trade, address=addr)
        if f.passiveid == f.agressiveid:   # self-cross: one leg only
            break


def _on_order_data(od) -> None:
    emit_legacy("order", od)
    t = od.ticker
    ring = STATE["trades"].setdefault(t, deque(maxlen=TRADES_RING))
    for f in od.fills:
        trade = {"ticker": t, "price": f.price, "amount": f.qty,
                 "side": "buy" if f.agressive_side > 0 else "sell",
                 "microtime_us": int(f.microtime), "timestamp_ms": int(f.microtime) // 1000,
                 "id": f"{f.microtime}-{f.agressiveid[-8:]}"}
        ring.append(trade)
        emit("trades", t, trade)
        _fold_fill(f, t)
    for bo in od.bookorders:
        o = STATE["orders"].get(bo.orderid)
        if o is None:
            o = _order_dict(bo.orderid, bo.ticker, bo.side, bo.open_qty, bo.price,
                            int(bo.orderid.rsplit(":", 1)[-1] or 0))
            _track_order(bo.orderid, o)
        o["filled"] = bo.filled_qty
        o["remaining"] = bo.remaining_qty
        if bo.filled_qty and bo.avg_price:
            o["average_fill_price"] = bo.avg_price
        if bo.remaining_qty > 0:
            o["status"] = "open"
        elif bo.canceled_qty > 0:
            o["status"] = "canceled"
        else:
            o["status"] = "closed"
        emit("orders", bo.ticker, o, address=bo.traderid)
    for ms in od.margin_states:
        if len(STATE["margin_states"]) >= MAX_TRACKED_ADDRS:
            STATE["margin_states"].pop(next(iter(STATE["margin_states"])))
        STATE["margin_states"][ms.sidepit_id] = {
            "available_margin": int(ms.available_margin),
            "risk_position": ms.risk_position, "open_pnl": int(ms.open_pnl),
            "net_oi": ms.net_oi, "epoch_ms": int(od.epoch)}


def _on_reject(rj) -> None:
    tx = rj.transaction
    addr = tx.sidepit_id
    code = pb.RejectCode.Name(rj.reject_code)
    expected = REJECT_EXPECTED.get(code, False)
    which = tx.WhichOneof("tx")
    oid = order_id(addr, tx.timestamp)
    info = {"code": code, "expected": expected, "tx_type": which, "orderid": oid,
            "timestamp_ms": int(time.time() * 1000)}
    if which == "cancel_orderid":
        info["target_orderid"] = tx.cancel_orderid
    if which == "new_order":
        o = STATE["orders"].get(oid)
        if o is not None:
            o["status"] = "rejected"
            o["reject_code"] = code
            o["reject_expected"] = expected
            emit("orders", o["ticker"], o, address=addr)
    if addr:
        _addr_ring("rejections", addr).append(info)
        emit("rejections", "", info, address=addr)


def _feed_loop():
    subs = None
    last_rx = time.monotonic()
    parsers = {"price": (pb.MarketData, _on_market_data),
               "bar": (pb.EpochBar, _on_bar),
               "order": (pb.OrderData, _on_order_data),
               "reject": (pb.RejectedTransaction, _on_reject),
               "echo": (pb.TxBlockStream, _on_echo)}
    while True:
        try:
            if subs is None:
                subs = _open_subs()
                log.info("feeds subscribed (%s)", HOST)
            got = 0
            for name, (cls, fn) in parsers.items():
                while True:                  # drain-until-empty == more_in_epoch==0
                    try:
                        raw = subs[name].recv(block=False)
                    except pynng.TryAgain:
                        break
                    m = cls()
                    m.ParseFromString(raw)
                    fn(m)
                    got += 1
            now = time.monotonic()
            if got:
                last_rx = now
                STATE["feed_alive_at"] = time.time()
            elif now - last_rx > FEED_SILENCE_RESUB_SECS:
                # Idle pipes get silently dropped (no RST; NNG can't tell). Re-dial.
                for s in subs.values():
                    try:
                        s.close()
                    except Exception:
                        pass
                subs = None
                last_rx = now
                continue
            time.sleep(0.05)
        except Exception as e:
            log.warning("feed loop error (%s) — resubscribing", e)
            if subs:
                for s in subs.values():
                    try:
                        s.close()
                    except Exception:
                        pass
            subs = None
            time.sleep(2.0)


# ---------------------------------------------------------------------------
# reqrep helpers (serialized on one socket)
# ---------------------------------------------------------------------------
def _rq(fn):
    """Serialized reqrep with reopen-on-timeout: the REQ pipe suffers the same silent
    LB idle-drop as everything else (the gateway may not touch reqrep for minutes).
    One timeout = assume dead pipe, re-dial, retry once."""
    global _req
    with _req_lock:
        try:
            return fn(_req)
        except pynng.Timeout:
            log.warning("reqrep timeout — reopening REQ socket and retrying")
            try:
                _req.close()
            except Exception:
                pass
            _req = RequestClient(HOST)
            return fn(_req)


def rq_active_product(ticker: str | None = None):
    return _rq(lambda r: r.active_product(ticker))


def rq_positions(address: str):
    return _rq(lambda r: r.positions(address))


def rq_bars(ticker: str, session_id: str = ""):
    return _rq(lambda r: r.historical_bars(ticker, session_id))


def _seed_addr(address: str) -> None:
    """One-time history seed per address from the (100-capped) reqrep snapshot."""
    if address in _seeded_addrs:
        return
    _seeded_addrs.add(address)
    try:
        tp = rq_positions(address)
    except Exception as e:
        log.warning("seed %s skipped: %s", address[:14], e)
        return
    for oid, of in tp.orderfills.items():
        bo = of.order
        if oid in STATE["orders"]:
            continue
        o = _order_dict(oid, bo.ticker, bo.side, bo.open_qty, bo.price,
                        int(oid.rsplit(":", 1)[-1] or 0))
        o["filled"] = bo.filled_qty
        o["remaining"] = bo.remaining_qty
        o["average_fill_price"] = bo.avg_price or None
        o["status"] = ("open" if bo.remaining_qty > 0
                       else "canceled" if bo.canceled_qty > 0 else "closed")
        _track_order(oid, o)
        for f in of.fills:
            _fold_fill(f, bo.ticker)


def _status_dict():
    ap = rq_active_product()
    es = ap.exchange_status
    _state_cache["state"] = pb.ExchangeState.Name(es.status.estate)
    _state_cache["at"] = time.monotonic()
    return {"state": _state_cache["state"],
            "session_id": es.session.session_id or es.status.session_id,
            "active_ticker": ap.active_contract_product.product.ticker,
            "trading_open_ms": int(es.session.schedule.trading_open_time),
            "trading_close_ms": int(es.session.schedule.trading_close_time),
            "feed_alive_at": STATE["feed_alive_at"],
            "write_paths": {"relay": True, "server_signed": _a_submitter is not None}}


def _build_markets():
    now = time.monotonic()
    if now - _markets_cache["at"] < MARKETS_TTL_SECS and _markets_cache["markets"]:
        return _markets_cache
    ap0 = rq_active_product()
    tickers = list(ap0.exchange_status.session.schedule.product) or \
        [ap0.active_contract_product.product.ticker]
    markets = []
    for t in tickers:
        ap = rq_active_product(t)
        c = ap.active_contract_product.contract
        p = ap.active_contract_product.product
        cb = ap.contractbar
        markets.append({
            "id": p.ticker,
            # explicit, not inferred: USD priced in satoshis, margined/settled in BTC —
            # an inverse DATED future (not a perp)
            "base": "USD", "quote": "BTC", "settle": "BTC",
            "type": "future", "inverse": True, "linear": False,
            "contract_symbol": c.symbol, "active": p.is_active,
            "expiry_ms": int(p.expiration_date), "start_ms": int(p.start_trading_date),
            "contract_size_usd": c.unit_size,
            "price_unit": "sats-per-USD",   # USD/BTC = 1e8/price; high<->low flips vs USD
            "tick_size_sats": c.tic_min, "tick_value_sats": c.tic_value,
            "amount_step": 1, "min_amount": 1, "max_position": c.position_limits,
            "price_limit_percent": c.price_limit_percent,
            "initial_margin_sats": int(c.initial_margin),
            "maint_margin_sats": int(c.maint_margin),
            "day": {"open": cb.day_open, "high": cb.day_high, "low": cb.day_low,
                    "close": cb.day_close, "volume": cb.day_volume,
                    "previous_close": cb.previous_close,
                    "open_interest": cb.open_interest},
        })
    _markets_cache.update(at=now, markets=markets, status=_status_dict())
    return _markets_cache


# ---------------------------------------------------------------------------
# HTTP app
# ---------------------------------------------------------------------------
app = FastAPI(title="sidepit-gateway", docs_url=None, redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])   # browser frontends call cross-origin


@app.on_event("startup")
async def _startup():
    global _event_q, _loop
    _loop = asyncio.get_running_loop()
    _event_q = asyncio.Queue(maxsize=10000)
    asyncio.create_task(_broadcaster())
    threading.Thread(target=_feed_loop, daemon=True, name="feeds").start()


@app.get("/time")
def get_time():
    return {"ms": int(time.time() * 1000)}


@app.get("/status")
def get_status():
    return _status_dict()


@app.get("/markets")
def get_markets():
    m = _build_markets()
    return {"markets": m["markets"], "status": m["status"]}


def _need(symbol: str, table: str):
    d = STATE[table].get(symbol)
    if d is None:
        raise HTTPException(404, f"no live {table} for {symbol} yet "
                                 f"(feeds publish only while EXCHANGE_OPEN)")
    return d


@app.get("/ticker/{symbol}")
def get_ticker(symbol: str):
    return _need(symbol, "tickers")


@app.get("/orderbook/{symbol}")
def get_orderbook(symbol: str):
    return _need(symbol, "orderbooks")


@app.get("/trades/{symbol}")
def get_trades(symbol: str, limit: int = 100):
    return {"trades": list(STATE["trades"].get(symbol) or [])[-limit:]}


@app.get("/ohlcv/{symbol}")
def get_ohlcv(symbol: str, limit: int = 500, since_ms: int = 0):
    """Closed 1-minute bars, oldest-first: [ms,o,h,l,c,v] (sats-per-USD!). Backfills via
    HISTORICAL_BARS walking prev_session_id, then merges live closed bars."""
    rows: dict[int, list] = {}
    session = ""
    for _ in range(8):
        h = rq_bars(symbol, session)
        for b in h.bars:
            rows[int(b.epoch)] = [int(b.epoch), b.open, b.high, b.low, b.close, b.volume]
        if len(rows) >= limit or not h.prev_session_id or h.prev_session_id == session:
            break
        session = h.prev_session_id
    for r in STATE["bars"].get(symbol, []):
        rows[r[0]] = r
    out = sorted(rows.values())
    if since_ms:
        out = [r for r in out if r[0] >= since_ms]
    return {"ohlcv": out[-limit:], "timeframe": "1m"}


@app.get("/balance/{address}")
def get_balance(address: str):
    """`free` = server available_margin (withdrawable now); `used` = derived
    margin_required; `total` = free+used+open_pnl. available_balance is YESTERDAY'S
    settled figure (static intraday) — info only, never the basis for free/total."""
    tp = rq_positions(address)
    a = tp.accountstate
    realized = sum(cm.margin.realized_pnl for cm in a.contract_margins.values())
    fees = sum(cm.margin.realized_fees for cm in a.contract_margins.values())
    unreal = 0
    mkts = {m["id"]: m for m in _build_markets()["markets"]}
    for cm in a.contract_margins.values():
        for t, tposn in cm.positions.items():
            qty = tposn.position.position
            last = (STATE["tickers"].get(t) or {}).get("last", 0)
            mk = mkts.get(t)
            if qty and last and mk:
                unreal += int(qty * (last - tposn.position.avg_price)
                              * mk["tick_value_sats"] / max(mk["tick_size_sats"], 1))
    free = int(a.available_margin)
    used = max(0, int(a.available_balance) + realized - free)
    return {"currency": "BTC", "unit": "sats", "address": address,
            "free_sats": free, "used_sats": used, "total_sats": free + used + unreal,
            "open_pnl_sats": unreal, "realized_pnl_sats": realized,
            "realized_fees_sats": fees,
            "info": {"available_balance_sats": int(a.available_balance),
                     "basis": "free=available_margin; available_balance is yesterday's "
                              "settled figure, static intraday",
                     "net_locked_sats": int(a.net_locked),
                     "pending_unlock_sats": int(a.pending_unlock),
                     "total_balance_sats": int(a.total_balance),
                     "is_restricted": a.is_restricted,
                     "margin_state": STATE["margin_states"].get(address)}}


@app.get("/positions/{address}")
def get_positions(address: str):
    tp = rq_positions(address)
    out = []
    for cm in tp.accountstate.contract_margins.values():
        for t, tposn in cm.positions.items():
            p = tposn.position
            if not p.position and not tposn.open_bids and not tposn.open_asks:
                continue
            out.append({
                "ticker": t, "contracts": p.position,
                "side": "long" if p.position > 0 else "short" if p.position < 0 else "flat",
                "entry_price": p.avg_price,
                "entry_price_basis": "resets daily to settlement at EOD mark-to-market — "
                                     "NOT lifetime cost basis",
                "realized_pnl_sats": int(tposn.margin.realized_pnl),
                "margin_required_sats": int(tposn.margin.margin_required),
                "reduce_only": tposn.margin.reduce_only,
                "carried": tposn.margin.carried_position,
                "opened_today": tposn.margin.new_position,
                "open_bids": tposn.open_bids, "open_asks": tposn.open_asks})
    return {"positions": out, "address": address}


@app.get("/open_orders/{address}")
def get_open_orders(address: str, sync: int = 1):
    """Open orders for an address. sync=1 (default): authoritative snapshot sync
    (12125→12129) merged into the live view; sync=0: live view only."""
    _seed_addr(address)
    if sync:
        try:
            orders, _ = snapshot_sync(HOST, sidepit_id=address, timeout_ms=8000)
            for oid, bo in orders.items():
                o = STATE["orders"].get(oid)
                if o is None:
                    o = _order_dict(oid, bo.ticker, bo.side, bo.open_qty, bo.price,
                                    int(oid.rsplit(":", 1)[-1] or 0))
                    _track_order(oid, o)
                o.update(filled=bo.filled_qty, remaining=bo.remaining_qty, status="open")
            live = set(orders)
            for oid, o in STATE["orders"].items():       # snapshot is authoritative
                if (oid.startswith(address + ":") and o["status"] == "open"
                        and oid not in live):
                    o["status"] = "closed" if o["filled"] else "canceled"
        except pynng.Timeout:
            log.warning("snapshot sync timed out (exchange closed?) — live view only")
    out = [o for oid, o in STATE["orders"].items()
           if oid.startswith(address + ":") and o["status"] == "open"]
    return {"orders": out, "address": address}


@app.get("/orders/{orderid}")
def get_order(orderid: str):
    o = STATE["orders"].get(orderid)
    if o is None:
        raise HTTPException(404, "unknown orderid (not yet seen on the feeds; orders "
                                 "resolve at the next 1s epoch — poll again, or check "
                                 "/rejections/{address})")
    return o


@app.get("/my_trades/{address}")
def get_my_trades(address: str, symbol: str = "", limit: int = 200):
    _seed_addr(address)
    ring = STATE["my_trades"].get(address) or []
    out = [t for t in ring if not symbol or t["ticker"] == symbol]
    return {"trades": out[-limit:], "address": address}


@app.get("/rejections/{address}")
def get_rejections(address: str, limit: int = 100):
    return {"rejections": list(STATE["rejections"].get(address) or [])[-limit:],
            "address": address}


# ---------------------------------------------------------------------------
# write paths
# ---------------------------------------------------------------------------
class RelayReq(BaseModel):
    signed_tx: str        # hex of SignedTransaction.SerializeToString()


@app.post("/relay")
def post_relay(r: RelayReq):
    """Custody model B: the client signed its own Transaction (SHA256 of the serialized
    Transaction → secp256k1 ECDSA compact → hex, signature_version=0). The gateway
    validates shape only — signature verification is the exchange's job (RC_VERIFY on
    the reject feed) — and pushes the exact bytes to 12121. No keys here."""
    try:
        raw = bytes.fromhex(r.signed_tx)
        stx = pb.SignedTransaction()
        stx.ParseFromString(raw)
    except Exception:
        raise HTTPException(400, "signed_tx must be hex of a serialized SignedTransaction")
    tx = stx.transaction
    if not tx.sidepit_id or not tx.timestamp or not stx.signature:
        raise HTTPException(400, "transaction must carry sidepit_id, timestamp, signature")
    which = tx.WhichOneof("tx")
    if which is None:
        raise HTTPException(400, "transaction has no payload (new_order / cancel_orderid "
                                 "/ replace_order / auction_bid / unlock_req)")
    # Fast-fail on a FRESH closed-state cache (<=10s) — zero added latency while OPEN,
    # millisecond rejects while CLOSED. A stale cache falls through to the push.
    if (time.monotonic() - _state_cache["at"] <= 10.0
            and _state_cache["state"] not in (None, "EXCHANGE_OPEN")):
        raise HTTPException(503, f"exchange not accepting transactions "
                                 f"(state={_state_cache['state']}); orders are processed "
                                 f"only while EXCHANGE_OPEN")
    try:
        _pusher.push(raw)
    except pynng.Timeout:
        # While EXCHANGE_CLOSED the 12121 listener accepts the dial but nothing
        # consumes — sends block. Fail with the real semantic (and refresh the
        # state cache so the next call fast-fails).
        state = "?"
        try:
            state = _status_dict()["state"]
        except Exception:
            pass
        raise HTTPException(503, f"exchange not accepting transactions (state={state}); "
                                 f"orders are processed only while EXCHANGE_OPEN")
    oid = order_id(tx.sidepit_id, tx.timestamp)
    resp = {"orderid": oid, "tx_type": which, "timestamp_ns": int(tx.timestamp),
            "status": "relayed",
            "confirm": {"order": f"/orders/{oid}",
                        "rejections": f"/rejections/{tx.sidepit_id}",
                        "ws": "channel 'orders' / 'rejections'"}}
    if which == "new_order":
        o = _order_dict(oid, tx.new_order.ticker, tx.new_order.side,
                        tx.new_order.size, tx.new_order.price, int(tx.timestamp))
        _track_order(oid, o)
    elif which == "cancel_orderid":
        resp["target_orderid"] = tx.cancel_orderid
        t = STATE["orders"].get(tx.cancel_orderid)
        if t is not None:
            t["cancel_requested_ns"] = int(tx.timestamp)
    log.info("RELAY %s %s", which, oid)
    return resp


@app.get("/nonce")
def get_nonce():
    """Strictly increasing nanosecond timestamp for clients that want a server-issued
    Transaction.timestamp (avoids client clock skew producing RC_DUP)."""
    return {"timestamp_ns": next_ns()}


class NewOrderReq(BaseModel):
    symbol: str
    side: str            # "buy" | "sell"
    amount: int          # contracts, positive
    price: int           # sats-per-USD (limit only — no market orders in v1)
    type: str = "limit"


@app.post("/orders")
def post_order(o: NewOrderReq):
    """Interim custody model A: server-side signing with the gateway's trade-only
    delegate key. Enabled only when the gateway was started with a key."""
    if _a_submitter is None:
        raise HTTPException(400, "server-signed orders disabled (no key configured); "
                                 "use POST /relay with a client-signed transaction")
    if o.type != "limit":
        raise HTTPException(400, "limit orders only: fills on this venue are decided by "
                                 "the per-epoch sequencing auction, so 'market' has no "
                                 "defined price — cross with a priced limit instead")
    if o.side not in ("buy", "sell"):
        raise HTTPException(400, "side must be 'buy' or 'sell'")
    if o.amount <= 0 or o.price <= 0:
        raise HTTPException(400, "amount and price must be positive integers "
                                 "(price is sats-per-USD)")
    ts = next_ns()
    side = 1 if o.side == "buy" else -1
    _a_submitter.new_order(side, o.amount, o.price, o.symbol, timestamp_ns=ts)
    oid = order_id(AKEY.sidepit_id, ts)
    od = _order_dict(oid, o.symbol, side, o.amount, o.price, ts)
    _track_order(oid, od)
    return od


@app.delete("/orders/{orderid}")
def delete_order(orderid: str):
    """Interim custody model A cancel (server-signed)."""
    if _a_submitter is None:
        raise HTTPException(400, "server-signed cancel disabled (no key configured); "
                                 "use POST /relay with a client-signed cancel")
    ts = next_ns()
    _a_submitter.cancel(orderid, timestamp_ns=ts)
    o = STATE["orders"].get(orderid)
    if o is not None:
        o["cancel_requested_ns"] = ts
    return {"orderid": orderid, "cancel_timestamp_ns": ts,
            "note": "residual-only; resolves next epoch; RC_CREJ/RC_CDUP = already gone "
                    "(expected, not an error)"}


# --- LEGACY website endpoints (see the legacy compat section above) ----------
async def _legacy_ws(kind: str, ws: WebSocket) -> None:
    await ws.accept()
    _legacy_clients[kind].add(ws)
    try:
        while True:
            await ws.receive_text()      # old protocol has no inbound messages
    except WebSocketDisconnect:
        pass
    finally:
        _legacy_clients[kind].discard(ws)


@app.websocket("/feed")
async def legacy_feed(ws: WebSocket):
    await _legacy_ws("feed", ws)


@app.websocket("/order")
async def legacy_order(ws: WebSocket):
    await _legacy_ws("order", ws)


@app.websocket("/echo")
async def legacy_echo(ws: WebSocket):
    await _legacy_ws("echo", ws)


@app.post("/tx")
async def legacy_tx(request: Request):
    """Old shape: proto-JSON of SignedTransaction (the browser wallet signs).
    ParseDict -> verbatim bytes -> 12121, same as cex-tx did."""
    body = await request.json()
    stx = pb.SignedTransaction()
    try:
        ParseDict(body, stx, ignore_unknown_fields=True)
    except Exception as e:
        raise HTTPException(400, f"not a SignedTransaction JSON: {e}")
    if (time.monotonic() - _state_cache["at"] <= 10.0
            and _state_cache["state"] not in (None, "EXCHANGE_OPEN")):
        raise HTTPException(503, f"exchange not accepting transactions "
                                 f"(state={_state_cache['state']})")
    try:
        _pusher.push(stx.SerializeToString())
    except pynng.Timeout:
        raise HTTPException(503, "venue not accepting transactions")
    return {"message": "Transaction processed successfully."}


@app.post("/position/request_position")
async def legacy_position(request: Request):
    """Old envelope: {"message", "response"} with snake_case proto names."""
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    tid = (body.get("traderid") or (body.get("position") or {}).get("traderid")
           or "")
    rep = _rq(lambda rc: rc._request(pb.POSITIONS, traderid=tid))
    text = MessageToJson(rep, preserving_proto_field_name=True,
                         including_default_value_fields=True)
    return {"message": "Request processed successfully.",
            "response": json.loads(text)}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    _ws_clients[ws] = {"channels": set(), "address": ""}
    try:
        while True:
            msg = await ws.receive_json()
            op = msg.get("op")
            sub = _ws_clients[ws]
            if op == "subscribe":
                # ADDITIVE: each subscribe unions channels (CCXT issues one per watch*).
                # "replace": true resets the set; empty set = everything.
                if msg.get("replace"):
                    sub["channels"] = set()
                sub["channels"] |= set(msg.get("channels") or [])
                if msg.get("address"):
                    sub["address"] = msg["address"]
                await ws.send_json({"op": "subscribed",
                                    "channels": sorted(sub["channels"]) or "all",
                                    "address": sub["address"]})
            elif op == "unsubscribe":
                sub["channels"] -= set(msg.get("channels") or [])
                await ws.send_json({"op": "subscribed",
                                    "channels": sorted(sub["channels"]) or "all",
                                    "address": sub["address"]})
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.pop(ws, None)


def main():
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    log.info("sidepit gateway binding http://%s:%d (exchange %s)", BIND, PORT, HOST)
    uvicorn.run(app, host=BIND, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
