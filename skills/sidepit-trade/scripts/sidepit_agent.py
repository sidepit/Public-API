#!/usr/bin/env python3
"""Sidepit trading lifecycle for an AI agent — delegate key or owner key.

This command never accepts an owner key.  It reads one protected delegate env
file, keeps the secret out of argv/stdout, verifies that the delegate is ACTIVE,
and puts a durable preview/attempt record in ~/.sidepit/agent-trade/.

Run from the Public-API repository root.  Use --help for the exact commands.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "python-client"))

from sidepit_trader import (  # noqa: E402
    RejectionFeed,
    RequestClient,
    Signer,
    Submitter,
    pb,
)
from sidepit_trader.config import EXECUTION_FEE_SATS_PER_CONTRACT_PER_SIDE  # noqa: E402
from sidepit_trader.signer import wif_to_priv_hex  # noqa: E402
from sidepit_trader.submit import next_ns  # noqa: E402
from sidepit_trader.sync import snapshot_sync  # noqa: E402
from sidepit_trader.wallet import decode_segwit, from_wif  # noqa: E402


HOST = os.environ.get("SIDEPIT_HOST", "api.sidepit.com")
STATE_DIR = Path(os.environ.get(
    "SIDEPIT_AGENT_STATE_DIR", "~/.sidepit/agent-trade"
)).expanduser()


class Stop(RuntimeError):
    """A safety stop with a human-readable recovery action."""


@dataclass(frozen=True)
class Delegate:
    path: Path
    account: str
    agent_id: str
    signer: Signer


def _parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if line.startswith("export ") and "=" in line:
            key, value = line[7:].split("=", 1)
            out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def load_delegate(raw_path: str) -> Delegate:
    """Read a 0600 delegate file without printing any secret."""
    path = Path(raw_path).expanduser()
    if path.is_symlink():
        raise Stop(f"delegate file is a symlink: {path}; use the real 0600 file")
    try:
        info = path.stat()
    except FileNotFoundError:
        raise Stop(f"delegate file not found: {path}") from None
    if not stat.S_ISREG(info.st_mode):
        raise Stop(f"delegate path is not a regular file: {path}")
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise Stop(f"delegate file is not owned by this user: {path}")
    mode = stat.S_IMODE(info.st_mode)
    if mode != 0o600:
        raise Stop(f"delegate file mode is {mode:04o}, expected 0600: chmod 600 {path}")

    values = _parse_env_file(path)
    account = values.get("SIDEPIT_ID", "")
    wif = values.get("SIDEPIT_WIF", "")
    if not account or not wif:
        raise Stop(f"delegate file must contain SIDEPIT_ID and SIDEPIT_WIF: {path}")
    try:
        identity = from_wif(wif)
    except Exception as exc:
        raise Stop(f"delegate file failed its key self-check: {type(exc).__name__}") from None
    if identity.sidepit_id == account:
        # The key IS the account: direct owner-key trading, same commands.
        signer = Signer(wif_to_priv_hex(wif), account)
        return Delegate(path.resolve(), account, identity.sidepit_id, signer)
    signer = Signer.as_delegate(wif_to_priv_hex(wif), account)
    if signer.trader_id != identity.sidepit_id:
        raise Stop("delegate derivation self-check failed")
    return Delegate(path.resolve(), account, identity.sidepit_id, signer)


def _new_req() -> RequestClient:
    return RequestClient(HOST)


def _state_name(ap) -> str:
    return pb.ExchangeState.Name(ap.exchange_status.status.estate)


def _fmt_ms(value: int) -> str:
    if not value:
        return "unknown"
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).astimezone().isoformat()


def _next_open(req: RequestClient, ticker: str) -> str:
    now_ms = int(time.time() * 1000)
    try:
        schedules = req.schedules().products
    except Exception:
        return "unavailable"
    future = [s for s in schedules
              if int(s.trading_open_time) > now_ms
              and (not ticker or ticker in s.product)]
    if not future:
        future = [s for s in schedules if int(s.trading_open_time) > now_ms]
    if not future:
        return "not published"
    return _fmt_ms(min(future, key=lambda s: int(s.trading_open_time)).trading_open_time)


def market_snapshot(req: RequestClient) -> dict:
    ap = req.active_product()
    cp = ap.active_contract_product
    ticker = cp.product.ticker
    q = req.quote(ticker).quote
    return {
        "state": _state_name(ap),
        "ticker": ticker,
        "bid": int(q.bid),
        "bid_size": int(q.bidsize),
        "ask": int(q.ask),
        "ask_size": int(q.asksize),
        "last": int(q.last),
        "unit_usd": int(cp.contract.unit_size),
        "initial_margin_sats": int(cp.contract.initial_margin),
        "maintenance_margin_sats": int(cp.contract.maint_margin),
        "position_limit": int(cp.contract.position_limits),
        "expiration_ms": int(cp.product.expiration_date),
        "next_open": _next_open(req, ticker),
    }


def _print_market(m: dict) -> None:
    usd = 1e8 / m["last"] if m["last"] else 0
    print(f"exchange         {m['state']}")
    print(f"active forward   {m['ticker']}  expires {_fmt_ms(m['expiration_ms'])}")
    print(f"quote            {m['bid_size']}x{m['bid']} / {m['ask']}x{m['ask_size']} "
          f"sats per USD")
    print(f"familiar price   ${usd:,.2f} per BTC" if usd else "familiar price   unavailable")
    print(f"one contract     ${m['unit_usd']:,} of USD exposure")
    print(f"initial margin   {m['initial_margin_sats']:,} sats per contract")
    print(f"maintenance      {m['maintenance_margin_sats']:,} sats per contract")
    if m["state"] != "EXCHANGE_OPEN":
        print(f"next open        {m['next_open']}")


def _requests_for(tp, agent_id: str) -> list[dict]:
    out = []
    for r in tp.accountops.account_requests:
        tx = r.account_tx
        which = tx.WhichOneof("tx")
        rid = (tx.new_delegate.agent_id if which == "new_delegate"
               else tx.revoke_delegate if which == "revoke_delegate" else "")
        if rid != agent_id:
            continue
        out.append({
            "verb": which,
            "oid": r.oid,
            "pending": bool(r.is_pending),
            "reject": pb.RejectCode.Name(r.reject_code),
        })
    return out


def _is_active(tp, agent_id: str) -> bool:
    return any(d.agent_id == agent_id for d in tp.accountstate.active_delegates)


def require_active(req: RequestClient, delegate: Delegate):
    tp = req.positions(delegate.account)
    if _is_active(tp, delegate.agent_id):
        return tp
    requests = _requests_for(tp, delegate.agent_id)
    if requests:
        last = requests[-1]
        state = "PENDING" if last["pending"] else last["reject"]
        recovery = ("wait, then rerun delegate-status" if last["pending"]
                    else "open the web app, correct the authorization, and sign again")
        raise Stop(f"delegate is not ACTIVE ({state}); {recovery}")
    raise Stop(
        "delegate is not ACTIVE and no authorization receipt was found; in the web app "
        "choose Authorize trading agent, paste this key's public key, and sign"
    )


def _position(tp, ticker: str) -> int:
    for cm in tp.accountstate.contract_margins.values():
        if ticker in cm.positions:
            return int(cm.positions[ticker].position.position)
    return 0


def _margin_used(tp) -> int:
    return sum(int(p.margin.margin_required)
               for cm in tp.accountstate.contract_margins.values()
               for p in cm.positions.values())


def _open_orders(account: str) -> tuple[dict, str]:
    try:
        orders, epoch = snapshot_sync(HOST, sidepit_id=account)
        return orders, str(epoch)
    except Exception as exc:
        return {}, f"unavailable ({type(exc).__name__}; snapshots may be quiet while closed)"


def _ensure_state_dir() -> Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(STATE_DIR, 0o700)
    return STATE_DIR


def _write_once(path: Path, payload: dict) -> None:
    data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(data)


def _read_record(raw_path: str, action: str) -> tuple[Path, dict]:
    path = Path(raw_path).expanduser().resolve()
    try:
        payload = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise Stop(f"cannot read preview {path}: {type(exc).__name__}") from None
    if payload.get("schema") != 1 or payload.get("action") != action:
        raise Stop(f"{path} is not a Sidepit {action} preview")
    claimed = payload.get("preview_id", "")
    unsigned = dict(payload)
    unsigned.pop("preview_id", None)
    if not claimed or _preview_id(unsigned) != claimed:
        raise Stop(f"preview integrity check failed: {path}; create a fresh preview")
    return path, payload


def _preview_id(payload: dict) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(body).hexdigest()[:16]


def _expectation(side: int, limit_price: int | None, bid: int, ask: int,
                 *, is_market: bool = False) -> str:
    if is_market:
        return ("IOC MARKET — takes available opposite liquidity in the next DLOB "
                "auction and cancels every unfilled remainder; no price protection")
    assert limit_price is not None
    if side > 0 and ask and limit_price >= ask:
        return "MARKETABLE LIMIT — can fill in the next DLOB auction, not guaranteed"
    if side < 0 and bid and limit_price <= bid:
        return "MARKETABLE LIMIT — can fill in the next DLOB auction, not guaranteed"
    return "RESTING — waits unless the market reaches the limit"


def _direction(side: int, unit_usd: int, contracts: int) -> str:
    amount = unit_usd * contracts
    if side > 0:
        return (f"BUY adds a ${amount:,} USD hedge and reduces BTC-price exposure; "
                "too much can make the account net short BTC")
    return (f"SELL removes ${amount:,} of USD hedge and increases BTC-price exposure; "
            "a negative position is leveraged long BTC")


def cmd_market(_args) -> int:
    req = _new_req()
    try:
        _print_market(market_snapshot(req))
    finally:
        req.close()
    print(f"execution fee    {EXECUTION_FEE_SATS_PER_CONTRACT_PER_SIDE} sats per "
          "contract per side (open + close = "
          f"{2 * EXECUTION_FEE_SATS_PER_CONTRACT_PER_SIDE} sats round turn per "
          "trader); the engine deducts it at each fill")
    return 0


def cmd_public_account(args) -> int:
    try:
        version, program = decode_segwit(args.account)
    except Exception:
        version, program = None, None
    if version != 0 or program is None or len(program) != 20:
        raise Stop("account must be a mainnet Native SegWit address beginning bc1q")
    req = _new_req()
    try:
        tp = req.positions(args.account)
    finally:
        req.close()
    a = tp.accountstate
    pending = sum(int(x.lock_sats) for x in tp.locks if x.is_pending)
    credited = sum(int(x.lock_sats) - int(x.unlock_sats) for x in tp.locks if not x.is_pending)
    print(f"account          {args.account}")
    print(f"deposits         {credited:,} sats credited; {pending:,} sats pending")
    print(f"available margin {int(a.available_margin):,} sats")
    for sym, cm in sorted(a.contract_margins.items()):
        for tick, pos in sorted(cm.positions.items()):
            rp = int(pos.position.position)
            if rp:
                print(f"position         {tick} {rp:+d} @ avg {pos.position.avg_price:g}")
    open_orders = [of.order for of in tp.orderfills.values()
                   if int(of.order.open_qty) > int(of.order.filled_qty)]
    print(f"resting orders   {len(open_orders)}")
    active = [d.agent_id for d in a.active_delegates]
    print(f"active agents    {len(active)}")
    for agent_id in active:
        print(f"                 {agent_id}")
    if args.agent_id:
        print(f"requested agent  {args.agent_id} "
              f"{'ACTIVE' if args.agent_id in active else 'NOT ACTIVE'}")
        for item in _requests_for(tp, args.agent_id)[-3:]:
            result = "PENDING" if item["pending"] else item["reject"]
            print(f"receipt          {item['verb']} {item['oid']} {result}")
    if int(a.pending_unlock):
        print(f"unlocking        {int(a.pending_unlock):,} sats")
    return 0


def cmd_delegate_status(args) -> int:
    delegate = load_delegate(args.key_file)
    req = _new_req()
    try:
        tp = req.positions(delegate.account)
    finally:
        req.close()
    active = _is_active(tp, delegate.agent_id)
    print(f"account          {delegate.account}")
    print(f"agent id         {delegate.agent_id}")
    print(f"delegate         {'ACTIVE' if active else 'NOT ACTIVE'}")
    for item in _requests_for(tp, delegate.agent_id)[-3:]:
        result = "PENDING" if item["pending"] else item["reject"]
        print(f"receipt          {item['verb']} {item['oid']} {result}")
    if not active:
        print("next             authorize/review this agent in the web app, then rerun this command")
        return 3
    print(f"key file         {delegate.path} (secret not displayed)")
    return 0


def cmd_status(args) -> int:
    delegate = load_delegate(args.key_file)
    req = _new_req()
    try:
        market = market_snapshot(req)
        tp = req.positions(delegate.account)
    finally:
        req.close()
    _print_market(market)
    print(f"account          {delegate.account}")
    print(f"agent id         {delegate.agent_id}")
    print(f"delegate         {'ACTIVE' if _is_active(tp, delegate.agent_id) else 'NOT ACTIVE'}")
    a = tp.accountstate
    print(f"balance          {int(a.total_balance):,} sats total")
    print(f"available margin {int(a.available_margin):,} sats")
    for sym, cm in sorted(a.contract_margins.items()):
        for tick, pos in sorted(cm.positions.items()):
            rp = int(pos.position.position)
            if rp:
                print(f"position         {tick} {rp:+d} @ avg {pos.position.avg_price:g}")
    open_orders = [of.order for of in tp.orderfills.values()
                   if int(of.order.open_qty) > int(of.order.filled_qty)]
    print(f"resting orders   {len(open_orders)}")
    print(f"margin in use    {_margin_used(tp):,} sats")
    print(f"restricted       {'YES — reduce only' if a.is_restricted else 'no'}")
    pending = sum(int(x.lock_sats) for x in tp.locks if x.is_pending)
    credited = sum(int(x.lock_sats) - int(x.unlock_sats) for x in tp.locks if not x.is_pending)
    print(f"deposits         {credited:,} sats credited; {pending:,} sats pending")
    positions = []
    for cm in a.contract_margins.values():
        for ticker, p in cm.positions.items():
            qty = int(p.position.position)
            if qty:
                positions.append((ticker, qty, float(p.position.avg_price),
                                  int(p.margin.margin_required)))
    if positions:
        for ticker, qty, avg, margin in positions:
            print(f"position         {ticker} {qty:+d} @ {avg:.2f}; margin {margin:,} sats")
    else:
        print("position         flat")
    orders, epoch = _open_orders(delegate.account)
    if epoch.startswith("unavailable"):
        print(f"open orders      UNKNOWN — snapshot {epoch}")
    else:
        print(f"open orders      {len(orders)} (snapshot {epoch})")
    for oid, order in sorted(orders.items()):
        print(f"                 {oid} side={int(order.side):+d} "
              f"{int(order.remaining_qty)} @ {int(order.price)}")
    for oid, item in list(tp.orderfills.items())[-5:]:
        order = item.order
        print(f"recent order     {oid} filled={int(order.filled_qty)} "
              f"remaining={int(order.remaining_qty)} canceled={int(order.canceled_qty)}")
    return 0


def _order_payload(args, delegate: Delegate, market: dict, tp) -> dict:
    side = 1 if args.side == "buy" else -1
    is_market = bool(getattr(args, "market", False))
    limit_price = None if is_market else args.limit_price
    reference_price = (limit_price if not is_market else
                       ((market["ask"] if side > 0 else market["bid"])
                        or market["last"] or market["bid"] or market["ask"]))
    if reference_price <= 0:
        raise Stop("no live price is available for an honest exposure estimate")
    current = _position(tp, market["ticker"])
    projected = current + side * args.contracts
    initial = int(market["initial_margin_sats"])
    risk_increase = max(0, abs(projected) - abs(current))
    margin_allowance = risk_increase * initial
    available = int(tp.accountstate.available_margin)
    if margin_allowance > available:
        raise Stop(
            f"preview needs up to {margin_allowance:,} sats of additional initial margin "
            f"but only {available:,} sats is available; reduce size or fund the account"
        )
    now = time.time_ns()
    payload = {
        "schema": 1,
        "action": "order",
        "created_ns": now,
        "expires_ns": now + args.expires_seconds * 1_000_000_000,
        "host": HOST,
        "account": delegate.account,
        "agent_id": delegate.agent_id,
        "ticker": market["ticker"],
        "side": side,
        "side_name": args.side.upper(),
        "contracts": args.contracts,
        "order_type": "market" if is_market else "limit",
        "limit_price": limit_price,
        "reference_price": reference_price,
        "quote": {"bid": market["bid"], "ask": market["ask"], "last": market["last"]},
        "expectation": _expectation(side, limit_price, market["bid"], market["ask"],
                                     is_market=is_market),
        "unit_usd": market["unit_usd"],
        "usd_notional": market["unit_usd"] * args.contracts,
        "btc_equivalent_sats_at_reference": (
            market["unit_usd"] * args.contracts * reference_price
        ),
        "current_position": current,
        "projected_position": projected,
        "initial_margin_rate_sats": initial,
        "additional_margin_allowance_sats": margin_allowance,
        "available_margin_sats": available,
        "current_margin_used_sats": _margin_used(tp),
        "fee_sats": args.fee_sats,
        "fee_source": args.fee_source,
        "direction": _direction(side, market["unit_usd"], args.contracts),
    }
    payload["preview_id"] = _preview_id(payload)
    return payload


def _print_order_preview(p: dict) -> None:
    reference_usd_btc = 1e8 / p["reference_price"]
    print("ORDER PREVIEW — NOTHING SENT")
    print(f"preview id       {p['preview_id']}")
    print(f"account          {p['account']}")
    print(f"active forward   {p['ticker']}")
    if p["order_type"] == "market":
        print(f"order            IOC MARKET {p['side_name']} {p['contracts']} contract(s) · "
              "no limit price (wire price 0)")
        print(f"reference        {p['reference_price']} sats per USD "
              f"(${reference_usd_btc:,.2f}/BTC); actual fills can differ")
    else:
        print(f"order            LIMIT {p['side_name']} {p['contracts']} contract(s) @ "
              f"{p['limit_price']} sats per USD (${reference_usd_btc:,.2f}/BTC)")
    exposure_label = "exposure max" if p["order_type"] == "market" else "exposure"
    print(f"{exposure_label:<17}${p['usd_notional']:,}; approximately "
          f"{p['btc_equivalent_sats_at_reference']:,} sats BTC-equivalent at the "
          f"{p['reference_price']} reference")
    print(f"meaning          {p['direction']}")
    position_label = "position max" if p["order_type"] == "market" else "position"
    print(f"{position_label:<17}{p['current_position']:+d} -> "
          f"{p['projected_position']:+d}" +
          (" if fully filled" if p["order_type"] == "market" else ""))
    print(f"execution        {p['expectation']}")
    print(f"margin           {p['additional_margin_allowance_sats']:,} sats additional "
          f"allowance; {p['available_margin_sats']:,} sats available")
    fee_usd = p["fee_sats"] / p["reference_price"] if p["reference_price"] else 0
    print(f"fee              {p['fee_sats']:,} sats (~${fee_usd:,.2f} at reference) — "
          f"{p['fee_source']}; deducted by the engine at each fill")
    print("auction          queued for the next DLOB one-second deterministic auction; "
          "sending is not a fill")


def _fee_defaults(args, contracts: int) -> None:
    """Fill fee fields from the published execution-fee schedule when the
    human did not override: 125 sats per contract per side."""
    if args.fee_sats is None:
        args.fee_sats = EXECUTION_FEE_SATS_PER_CONTRACT_PER_SIDE * contracts
        args.fee_source = ("published execution-fee schedule: "
                           f"{EXECUTION_FEE_SATS_PER_CONTRACT_PER_SIDE} sats/"
                           "contract/side (2026-08-17)")
    elif not args.fee_source:
        raise Stop("an overridden --fee-sats requires --fee-source")


def cmd_preview_order(args) -> int:
    is_market = bool(getattr(args, "market", False))
    if args.contracts <= 0 or (args.fee_sats is not None and args.fee_sats < 0):
        raise Stop("contracts must be positive; fee-sats cannot be negative")
    _fee_defaults(args, args.contracts)
    if not is_market and (args.limit_price is None or args.limit_price <= 0):
        raise Stop("a limit order requires a positive limit-price")
    delegate = load_delegate(args.key_file)
    req = _new_req()
    try:
        market = market_snapshot(req)
        if market["state"] != "EXCHANGE_OPEN":
            raise Stop(f"exchange is {market['state']}; next open {market['next_open']}; "
                       "rerun market, then create a fresh preview")
        tp = require_active(req, delegate)
        payload = _order_payload(args, delegate, market, tp)
    finally:
        req.close()
    path = _ensure_state_dir() / f"order-preview-{payload['preview_id']}.json"
    _write_once(path, payload)
    _print_order_preview(payload)
    print(f"preview file     {path}")
    return 0


def _matching_rejects(feed: RejectionFeed, timestamp_ns: int) -> list:
    return [r for r in feed.drain() if int(r.transaction.timestamp) == timestamp_ns]


def _result_for_order(tp, orderid: str) -> str:
    if orderid not in tp.orderfills:
        return "UNKNOWN — not in point-in-time order history; do not retry"
    order = tp.orderfills[orderid].order
    remaining = int(order.remaining_qty)
    filled = int(order.filled_qty)
    canceled = int(order.canceled_qty)
    if remaining > 0:
        return f"RESTING LIMIT — {remaining} remaining"
    if filled > 0 and canceled > 0:
        return (f"PARTIAL FILL — {filled} filled @ {float(order.avg_price):.2f}; "
                f"{canceled} remainder canceled")
    if filled > 0:
        return f"FILLED — {filled} filled @ {float(order.avg_price):.2f}"
    if canceled > 0:
        return f"CANCELED — {canceled} unfilled contract(s) canceled"
    return "SEEN — terminal quantities not yet published"


def _submit_preview(submitter: Submitter, p: dict, timestamp_ns: int) -> str:
    if p["order_type"] == "market":
        return submitter.market_order(
            int(p["side"]), int(p["contracts"]), p["ticker"],
            timestamp_ns=timestamp_ns,
        )
    return submitter.new_order(
        int(p["side"]), int(p["contracts"]), int(p["limit_price"]),
        p["ticker"], timestamp_ns=timestamp_ns,
    )


def cmd_send_order(args) -> int:
    preview_path, p = _read_record(args.preview_file, "order")
    if time.time_ns() > int(p["expires_ns"]):
        raise Stop("preview expired; create a fresh preview")
    delegate = load_delegate(args.key_file)
    if (delegate.account, delegate.agent_id) != (p["account"], p["agent_id"]):
        raise Stop("delegate file does not match this preview")

    req = _new_req()
    try:
        market = market_snapshot(req)
        if market["state"] != "EXCHANGE_OPEN" or market["ticker"] != p["ticker"]:
            raise Stop("market state or active forward changed; create a fresh preview")
        tp = require_active(req, delegate)
        if _position(tp, p["ticker"]) != int(p["current_position"]):
            raise Stop("position changed after preview; create a fresh preview")
        is_market = p["order_type"] == "market"
        now_expectation = _expectation(
            int(p["side"]),
            None if is_market else int(p["limit_price"]),
            market["bid"], market["ask"], is_market=is_market,
        )
        if now_expectation != p["expectation"]:
            raise Stop("the order's execution expectation changed; create a fresh preview")
        if int(tp.accountstate.available_margin) < int(p["additional_margin_allowance_sats"]):
            raise Stop("available margin fell below the preview allowance; create a fresh preview")

        timestamp_ns = next_ns()
        orderid = f"{delegate.account}:{timestamp_ns}"
        attempt = {
            "schema": 1, "action": "order-attempt", "preview_id": p["preview_id"],
            "preview_file": str(preview_path), "orderid": orderid,
            "timestamp_ns": timestamp_ns, "created_ns": time.time_ns(),
        }
        attempt_path = _ensure_state_dir() / f"order-attempt-{p['preview_id']}.json"
        try:
            _write_once(attempt_path, attempt)
        except FileExistsError:
            old = json.loads(attempt_path.read_text())
            raise Stop(f"this preview already has an attempt: {old.get('orderid')}; "
                       "run status and never retry it") from None

        rejects = RejectionFeed(HOST, delegate.account)
        time.sleep(0.10)
        submitter = Submitter(delegate.signer, HOST)
        sent_id = _submit_preview(submitter, p, timestamp_ns)
        if sent_id != orderid:
            raise Stop(f"order handle self-check failed; inspect {attempt_path}")
        print(f"QUEUED           {orderid}")
        print(f"attempt record   {attempt_path}")
        time.sleep(args.wait_seconds)
        rejected = _matching_rejects(rejects, timestamp_ns)
        tp_after = req.positions(delegate.account)
    finally:
        req.close()

    if rejected:
        outcome = "REJECTED — " + ", ".join(RejectionFeed.code_name(r) for r in rejected)
    else:
        outcome = _result_for_order(tp_after, orderid)
    if p["order_type"] == "market" and outcome.startswith("RESTING"):
        outcome = ("CONTRACT ERROR — IOC market order is resting; preserve records, "
                   "stop trading, and report the public order ID")
    result = {"schema": 1, "action": "order-result", "preview_id": p["preview_id"],
              "orderid": orderid, "outcome": outcome, "checked_ns": time.time_ns()}
    result_path = _ensure_state_dir() / f"order-result-{p['preview_id']}.json"
    _write_once(result_path, result)
    print(f"outcome          {outcome}")
    print(f"result record    {result_path}")
    return 0 if not outcome.startswith(("REJECTED", "UNKNOWN", "CONTRACT ERROR")) else 4


def cmd_cancel(args) -> int:
    delegate = load_delegate(args.key_file)
    if not args.order_id.startswith(delegate.account + ":"):
        raise Stop("order-id does not belong to the delegate's account")
    req = _new_req()
    try:
        market = market_snapshot(req)
        if market["state"] != "EXCHANGE_OPEN":
            raise Stop(f"exchange is {market['state']}; next open {market['next_open']}")
        require_active(req, delegate)
        cancel_preview = {"schema": 1, "action": "cancel-attempt",
                          "account": delegate.account, "agent_id": delegate.agent_id,
                          "orderid": args.order_id, "created_ns": time.time_ns()}
        cancel_tag = hashlib.sha256(
            json.dumps(cancel_preview, sort_keys=True).encode()).hexdigest()[:16]
        cancel_path = _ensure_state_dir() / f"cancel-attempt-{cancel_tag}.json"
        _write_once(cancel_path, cancel_preview)
        rejects = RejectionFeed(HOST, delegate.account)
        time.sleep(0.10)
        cancel_id = Submitter(delegate.signer, HOST).cancel(args.order_id)
        print(f"CANCEL QUEUED    {args.order_id}")
        print(f"cancel handle    {cancel_id}")
        print(f"attempt record   {cancel_path}")
        time.sleep(args.wait_seconds)
        rejected = _matching_rejects(rejects, int(cancel_id.rsplit(":", 1)[1]))
        tp = req.positions(delegate.account)
    finally:
        req.close()
    if rejected:
        names = ", ".join(RejectionFeed.code_name(r) for r in rejected)
        print(f"outcome          {names} (RC_CDUP/RC_CREJ means it was already filled or gone)")
    else:
        print(f"outcome          {_result_for_order(tp, args.order_id)}")
    return 0


def _flatten_payload(args, delegate: Delegate, market: dict, tp, orders: dict) -> dict:
    positions: dict[str, int] = {}
    closes = []
    for cm in tp.accountstate.contract_margins.values():
        for ticker, item in cm.positions.items():
            qty = int(item.position.position)
            if not qty:
                continue
            positions[ticker] = qty
            side = -1 if qty > 0 else 1
            closes.append({"ticker": ticker, "position": qty, "side": side,
                           "contracts": abs(qty), "order_type": "market"})
    _fee_defaults(args, sum(c["contracts"] for c in closes))
    now = time.time_ns()
    payload = {
        "schema": 1, "action": "flatten", "created_ns": now,
        "expires_ns": now + args.expires_seconds * 1_000_000_000,
        "host": HOST, "account": delegate.account, "agent_id": delegate.agent_id,
        "open_order_ids": sorted(orders), "positions": positions, "closes": closes,
        "fee_sats": args.fee_sats, "fee_source": args.fee_source,
        "warning": "cancels land first; if the position changes, close orders stop",
    }
    payload["preview_id"] = _preview_id(payload)
    return payload


def cmd_preview_flatten(args) -> int:
    if args.fee_sats is not None and args.fee_sats < 0:
        raise Stop("fee-sats cannot be negative")
    delegate = load_delegate(args.key_file)
    req = _new_req()
    try:
        market = market_snapshot(req)
        if market["state"] != "EXCHANGE_OPEN":
            raise Stop(f"exchange is {market['state']}; next open {market['next_open']}")
        tp = require_active(req, delegate)
    finally:
        req.close()
    orders, epoch = snapshot_sync(HOST, sidepit_id=delegate.account)
    p = _flatten_payload(args, delegate, market, tp, orders)
    path = _ensure_state_dir() / f"flatten-preview-{p['preview_id']}.json"
    _write_once(path, p)
    print("FLATTEN PREVIEW — NOTHING SENT")
    print(f"preview id       {p['preview_id']}")
    print(f"cancel first     {len(p['open_order_ids'])} open order(s), snapshot epoch {epoch}")
    for item in p["closes"]:
        side = "BUY" if item["side"] > 0 else "SELL"
        print(f"close            {item['ticker']} IOC MARKET {side} "
              f"{item['contracts']} (unfilled remainder cancels)")
    if not p["open_order_ids"] and not p["closes"]:
        print("result           already flat")
    print(f"fee              {p['fee_sats']:,} sats ({p['fee_source']}; "
          "deducted by the engine at each fill)")
    print(f"preview file     {path}")
    return 0


def cmd_send_flatten(args) -> int:
    preview_path, p = _read_record(args.preview_file, "flatten")
    if time.time_ns() > int(p["expires_ns"]):
        raise Stop("preview expired; create a fresh flatten preview")
    delegate = load_delegate(args.key_file)
    if (delegate.account, delegate.agent_id) != (p["account"], p["agent_id"]):
        raise Stop("delegate file does not match this preview")
    req = _new_req()
    try:
        market = market_snapshot(req)
        if market["state"] != "EXCHANGE_OPEN":
            raise Stop("exchange is not open; create a fresh flatten preview at the open")
        tp = require_active(req, delegate)
        positions = {ticker: _position(tp, ticker) for ticker in p["positions"]}
        if positions != {k: int(v) for k, v in p["positions"].items()}:
            raise Stop("position changed after preview; create a fresh flatten preview")
        orders, _ = snapshot_sync(HOST, sidepit_id=delegate.account)
        if sorted(orders) != p["open_order_ids"]:
            raise Stop("open orders changed after preview; create a fresh flatten preview")

        attempt_path = _ensure_state_dir() / f"flatten-attempt-{p['preview_id']}.json"
        try:
            _write_once(attempt_path, {
                "schema": 1, "action": "flatten-attempt", "preview_id": p["preview_id"],
                "preview_file": str(preview_path), "created_ns": time.time_ns(),
            })
        except FileExistsError:
            raise Stop("this flatten preview was already attempted; run status and never retry it")
        sub = Submitter(delegate.signer, HOST)
        for orderid in p["open_order_ids"]:
            sub.cancel(orderid)
        if p["open_order_ids"]:
            print(f"CANCELS QUEUED   {len(p['open_order_ids'])}")
            time.sleep(args.wait_seconds)
        tp_after_cancel = req.positions(delegate.account)
        positions_after = {ticker: _position(tp_after_cancel, ticker)
                           for ticker in p["positions"]}
        if positions_after != {k: int(v) for k, v in p["positions"].items()}:
            raise Stop("orders were canceled, but position changed; create a fresh flatten preview")

        close_ids = []
        for item in p["closes"]:
            close_ids.append(sub.market_order(item["side"], item["contracts"],
                                              item["ticker"]))
        if close_ids:
            print("CLOSES QUEUED    " + ", ".join(close_ids))
            time.sleep(args.wait_seconds)
        final_tp = req.positions(delegate.account)
    finally:
        req.close()
    remaining = {ticker: _position(final_tp, ticker) for ticker in p["positions"]
                 if _position(final_tp, ticker)}
    print(f"outcome          {'FLAT' if not remaining else 'INCOMPLETE ' + str(remaining)}")
    print(f"attempt record   {attempt_path}")
    return 0 if not remaining else 5


def _network_message(exc: Exception) -> str:
    detail = str(exc).lower()
    if "permission" in detail or "operation not permitted" in detail:
        cause = "network permission denied"
    elif "name or service" in detail or "getaddrinfo" in detail or "dns" in detail:
        cause = "DNS lookup failed"
    elif "refused" in detail:
        cause = "connection refused"
    elif "timed out" in detail or "tryagain" in type(exc).__name__.lower():
        cause = "connection timed out"
    elif not isinstance(exc, (OSError, ConnectionError, TimeoutError)) \
            and "pynng" not in type(exc).__module__:
        raise exc  # a code error, not a network fault — surface it honestly
    else:
        return (f"unexpected {type(exc).__name__}; preserve every public attempt "
                "record, run status, and report without retrying")
    return (f"{cause}. Your agent may need permission to reach {HOST}:12125; "
            "check network access, then rerun the same read-only command")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Sidepit trading with preview and recovery gates — delegate key or your own account key")
    sub = p.add_subparsers(dest="command", required=True)

    q = sub.add_parser("market", help="keyless market, contract, margin, and next-open read")
    q.set_defaults(func=cmd_market)

    q = sub.add_parser("public-account", help="keyless deposit and delegate status")
    q.add_argument("--account", required=True)
    q.add_argument("--agent-id")
    q.set_defaults(func=cmd_public_account)

    for name, func, help_text in (
        ("delegate-status", cmd_delegate_status, "prove this saved delegate is ACTIVE"),
        ("status", cmd_status, "resume from a fresh shell: account, positions, orders"),
    ):
        q = sub.add_parser(name, help=help_text)
        q.add_argument("--key-file", required=True)
        q.set_defaults(func=func)

    q = sub.add_parser("preview-order", help="write a public, expiring order preview")
    q.add_argument("--key-file", required=True)
    q.add_argument("--side", required=True, choices=("buy", "sell"))
    q.add_argument("--contracts", required=True, type=int)
    order_kind = q.add_mutually_exclusive_group(required=True)
    order_kind.add_argument("--limit-price", type=int)
    order_kind.add_argument("--market", action="store_true",
                            help="native IOC market order; omit limit price")
    q.add_argument("--fee-sats", type=int, default=None,
                   help="override the published execution-fee schedule "
                        "(default: 125 sats/contract/side); requires --fee-source")
    q.add_argument("--fee-source", default="")
    q.add_argument("--expires-seconds", type=int, default=300)
    q.set_defaults(func=cmd_preview_order)

    q = sub.add_parser("send-order", help="send the previewed order")
    q.add_argument("--key-file", required=True)
    q.add_argument("--preview-file", required=True)
    q.add_argument("--wait-seconds", type=float, default=3.0)
    q.set_defaults(func=cmd_send_order)

    q = sub.add_parser("cancel", help="cancel one public order handle from a fresh shell")
    q.add_argument("--key-file", required=True)
    q.add_argument("--order-id", required=True)
    q.add_argument("--wait-seconds", type=float, default=3.0)
    q.set_defaults(func=cmd_cancel)

    q = sub.add_parser("preview-flatten", help="preview cancel-all plus position closes")
    q.add_argument("--key-file", required=True)
    q.add_argument("--fee-sats", type=int, default=None,
                   help="override the published execution-fee schedule "
                        "(default: 125 sats/contract/side on the closes); "
                        "requires --fee-source")
    q.add_argument("--fee-source", default="")
    q.add_argument("--expires-seconds", type=int, default=300)
    q.set_defaults(func=cmd_preview_flatten)

    q = sub.add_parser("send-flatten", help="send the previewed flatten")
    q.add_argument("--key-file", required=True)
    q.add_argument("--preview-file", required=True)
    q.add_argument("--wait-seconds", type=float, default=3.0)
    q.set_defaults(func=cmd_send_flatten)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return int(args.func(args))
    except Stop as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("STOP: interrupted; check status before any retry", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"STOP: {_network_message(exc)}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
