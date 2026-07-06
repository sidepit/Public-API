"""The bridge: one background thread that owns every SDK/NNG object.

pynng sockets are not safely shared across threads, so the rule here is simple:
ALL exchange I/O happens on this one thread. The UI never touches the SDK; it
reads immutable `Snap` snapshots the bridge posts, and enqueues commands
(orders, cancels, account verbs, on-chain lock) the bridge executes in order.

Cadences (human terminal, not a bot):
  - exchange state + quote        every ~1.5s (12125 reqrep)
  - account (positions/margin)    every ~3s when an address is set
  - open-order snapshot sync      every ~10s while OPEN (12129, authoritative)
  - rejections feed               drained every loop (12128, ours only)
  - on-chain balance (esplora)    every ~60s and on demand

Connections stay healthy on their own: the REQ socket is reopened on Timeout
and retried once; the Submitter keeps its push connection fresh across idle
periods.
"""
from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field

import pynng

from sidepit_trader import wallet
from sidepit_trader._proto import pb
from sidepit_trader.feeds import RejectionFeed
from sidepit_trader.reqrep import RequestClient
from sidepit_trader.signer import Signer
from sidepit_trader.submit import Submitter
from sidepit_trader.sync import snapshot_sync

QUOTE_SECS = 1.5
ACCOUNT_SECS = 3.0
SYNC_SECS = 10.0
CHAIN_SECS = 60.0


@dataclass
class Snap:
    """One immutable view of everything the UI shows. Sats everywhere."""
    ts: float = 0.0
    # exchange
    state: str = "?"
    is_open: bool = False
    ticker: str = ""
    session_id: str = ""
    open_ms: int = 0
    close_ms: int = 0
    bid: int = 0
    bidsize: int = 0
    ask: int = 0
    asksize: int = 0
    last: int = 0
    lastsize: int = 0
    epoch_ms: int = 0
    contract_usd: int = 500            # Contract.unit_size ($ per contract)
    tick_size_sats: int = 1            # Contract.tic_min
    tick_value_sats: int = 0           # Contract.tic_value
    depth_bids: list = field(default_factory=list)   # [(price, size)] best-first
    depth_asks: list = field(default_factory=list)
    # identity
    address: str = ""
    watch_only: bool = True
    # account (sats; names match AccountMarginState)
    net_locked: int = 0
    available_balance: int = 0     # YESTERDAY'S settled figure — static intraday
    available_margin: int = 0      # live withdrawable basis
    pending_unlock: int = 0
    total_balance: int = 0
    is_restricted: bool = False
    realized_pnl: int = 0
    realized_fees: int = 0
    positions: list = field(default_factory=list)    # dicts, gateway-shaped
    orders: list = field(default_factory=list)       # today's orders (orderfills)
    open_orders: list = field(default_factory=list)  # authoritative (snapshot sync)
    delegates: list = field(default_factory=list)    # delegate_data
    # on-chain (sidepit_id address UTXOs)
    chain_confirmed: int = 0
    chain_mempool: int = 0
    chain_at: float = 0.0


class Bridge(threading.Thread):
    """`on_snap(Snap)` and `on_event(kind, text)` are called FROM THIS THREAD —
    the app wraps them with call_from_thread. kind: info|success|warning|error."""

    def __init__(self, host: str, on_snap, on_event):
        super().__init__(daemon=True, name="sidepit-bridge")
        self.host = host
        # UI delivery must never kill (or be killed by) this thread: during app
        # shutdown the event loop closes while we may be mid-dial, and
        # call_from_thread starts raising — swallow, we're halting anyway.
        def _safe(fn):
            def inner(*a):
                try:
                    fn(*a)
                except Exception:
                    pass
            return inner
        self.on_snap = _safe(on_snap)
        self.on_event = _safe(on_event)
        self.cmds: queue.Queue = queue.Queue()
        self.snap = Snap()
        self._identity: wallet.Identity | None = None
        self._req: RequestClient | None = None
        self._sub: Submitter | None = None
        self._rejects: RejectionFeed | None = None
        self._halt = threading.Event()
        self._last = {"quote": 0.0, "account": 0.0, "sync": 0.0, "chain": 0.0}

    # --- identity (called from UI thread BEFORE start(), or via command) ----
    def set_identity(self, address: str, wif: str | None) -> None:
        """Watch-only when wif is None. Called before start()."""
        self.snap.address = address
        self.snap.watch_only = wif is None
        if wif:
            self._identity = wallet.from_wif(wif)

    # --- command surface (UI thread enqueues; run loop executes) ------------
    def cmd(self, *parts) -> None:
        self.cmds.put(parts)

    def stop(self) -> None:
        self._halt.set()

    # --- internals (bridge thread only) --------------------------------------
    def _rq(self, fn):
        """reqrep with reopen-on-timeout (LB idle-drop survival)."""
        if self._req is None:
            self._req = RequestClient(self.host)
        try:
            return fn(self._req)
        except pynng.Timeout:
            try:
                self._req.close()
            except Exception:
                pass
            self._req = RequestClient(self.host)
            return fn(self._req)

    def _submitter(self) -> Submitter:
        if self.snap.watch_only or self._identity is None:
            raise RuntimeError("watch-only: no signing key loaded")
        if self._sub is None:
            self._sub = Submitter(self._identity.signer(), self.host)
        return self._sub

    def run(self) -> None:
        while not self._halt.is_set():
            try:
                self._tick()
            except Exception as e:  # the loop must survive anything
                self.on_event("error", f"bridge: {type(e).__name__}: {e}")
                time.sleep(1.0)
            time.sleep(0.1)

    def _tick(self) -> None:
        now = time.monotonic()
        try:
            while True:
                self._exec(self.cmds.get_nowait())
        except queue.Empty:
            pass
        dirty = False
        if now - self._last["quote"] >= QUOTE_SECS:
            self._last["quote"] = now
            self._poll_exchange()
            dirty = True
        if self.snap.address and now - self._last["account"] >= ACCOUNT_SECS:
            self._last["account"] = now
            self._poll_account()
            dirty = True
        if (self.snap.address and self.snap.is_open
                and now - self._last["sync"] >= SYNC_SECS):
            self._last["sync"] = now
            self._poll_open_orders()
            dirty = True
        if self.snap.address and now - self._last["chain"] >= CHAIN_SECS:
            self._last["chain"] = now
            self._poll_chain()
            dirty = True
        self._drain_rejections()
        if dirty:
            self.snap.ts = time.time()
            self.on_snap(self.snap)

    # --- polls ---------------------------------------------------------------
    def _poll_exchange(self) -> None:
        ap = self._rq(lambda r: r.active_product())
        es = ap.exchange_status
        s = self.snap
        prev = s.state
        s.state = pb.ExchangeState.Name(es.status.estate)
        s.is_open = es.status.estate == pb.EXCHANGE_OPEN
        s.session_id = es.session.session_id or es.status.session_id
        s.ticker = ap.active_contract_product.product.ticker or s.ticker
        s.open_ms = int(es.session.schedule.trading_open_time)
        s.close_ms = int(es.session.schedule.trading_close_time)
        c = ap.active_contract_product.contract
        if c.unit_size:
            s.contract_usd = c.unit_size
            s.tick_size_sats = c.tic_min or 1
            s.tick_value_sats = c.tic_value
        if prev != "?" and prev != s.state:
            self.on_event("info", f"exchange {prev} → {s.state}")
        try:
            md = self._rq(lambda r: r.quote(s.ticker or None))
            q = md.quote
            s.bid, s.bidsize = q.bid, q.bidsize
            s.ask, s.asksize = q.ask, q.asksize
            s.last, s.lastsize = q.last, q.lastsize
            s.epoch_ms = int(md.epoch)
            # python protobuf keeps the reserved-word field name 'as' (live-found
            # gateway lesson): getattr, never d.as_
            s.depth_bids = [(d.b, d.bs) for d in md.depth if d.b > 0]
            s.depth_asks = [(d.a, getattr(d, "as")) for d in md.depth if d.a > 0]
        except Exception:
            pass   # quote is decorative while closed

    def _poll_account(self) -> None:
        tp = self._rq(lambda r: r.positions(self.snap.address))
        a = tp.accountstate
        s = self.snap
        s.net_locked = int(a.net_locked)
        s.available_balance = int(a.available_balance)
        s.available_margin = int(a.available_margin)
        s.pending_unlock = int(a.pending_unlock)
        s.total_balance = int(a.total_balance)
        s.is_restricted = a.is_restricted
        s.realized_pnl = sum(int(cm.margin.realized_pnl)
                             for cm in a.contract_margins.values())
        s.realized_fees = sum(int(cm.margin.realized_fees)
                              for cm in a.contract_margins.values())
        poss = []
        for cm in a.contract_margins.values():
            for t, tposn in cm.positions.items():
                p = tposn.position
                if not p.position and not tposn.open_bids and not tposn.open_asks:
                    continue
                poss.append({
                    "ticker": t, "contracts": p.position,
                    "side": ("long" if p.position > 0
                             else "short" if p.position < 0 else "flat"),
                    "entry_price": p.avg_price,   # resets daily at settlement
                    "realized_pnl": int(tposn.margin.realized_pnl),
                    "margin_required": int(tposn.margin.margin_required),
                    "reduce_only": tposn.margin.reduce_only,
                    "open_bids": tposn.open_bids, "open_asks": tposn.open_asks})
        s.positions = poss
        orders = []
        for oid, of in tp.orderfills.items():
            bo = of.order
            orders.append({
                "orderid": oid, "ticker": bo.ticker,
                "side": "buy" if bo.side > 0 else "sell",
                "price": bo.price, "qty": bo.open_qty,
                "filled": bo.filled_qty, "remaining": bo.remaining_qty,
                "avg_price": bo.avg_price or 0,
                "status": ("open" if bo.remaining_qty > 0
                           else "canceled" if bo.canceled_qty > 0 else "closed"),
                "ns": int(oid.rsplit(":", 1)[-1] or 0)})
        orders.sort(key=lambda o: -o["ns"])
        s.orders = orders
        delegs = []
        has_pending_req = any(r.is_pending for r in tp.accountops.account_requests)
        for ad in tp.accountops.delegate_data:
            delegs.append({
                "trader_id": ad.agent_id,
                "status": pb.AccountDelegate.DelegateStatus.Name(ad.status),
                "is_active": ad.is_active,
                "updatetime": int(ad.updatetime),
                "pending": not ad.is_active and has_pending_req})
        s.delegates = delegs

    def _poll_open_orders(self) -> None:
        try:
            orders, _epoch = snapshot_sync(self.host, self.snap.address,
                                           timeout_ms=5000)
        except pynng.Timeout:
            return   # closed / no worker — keep the last view
        self.snap.open_orders = [{
            "orderid": oid, "ticker": bo.ticker,
            "side": "buy" if bo.side > 0 else "sell",
            "price": bo.price, "remaining": bo.remaining_qty,
            "filled": bo.filled_qty}
            for oid, bo in sorted(orders.items())]

    def _poll_chain(self) -> None:
        try:
            c, m = wallet.balance(self.snap.address)
            self.snap.chain_confirmed, self.snap.chain_mempool = c, m
            self.snap.chain_at = time.time()
        except Exception as e:
            self.on_event("warning", f"on-chain lookup failed: {e}")

    def _drain_rejections(self) -> None:
        if self._rejects is None:
            if not self.snap.address:
                return
            self._rejects = RejectionFeed(self.host, self.snap.address)
        try:
            for rj in self._rejects.drain():
                if rj.transaction.sidepit_id != self.snap.address:
                    continue
                code = RejectionFeed.code_name(rj)
                kind = "error" if RejectionFeed.is_error(rj) else "info"
                self.on_event(kind, f"rejected {code}: "
                              f"{rj.transaction.sidepit_id}:{rj.transaction.timestamp}")
        except Exception:
            pass

    # --- commands -------------------------------------------------------------
    def _exec(self, parts) -> None:
        verb = parts[0]
        try:
            if verb == "order":
                _, side, price, size = parts
                oid = self._submitter().new_order(side, size, price, self.snap.ticker)
                self.on_event("success",
                              f"order submitted {('BUY' if side > 0 else 'SELL')} "
                              f"{size} @ {price} → {oid[-18:]} "
                              f"(resolves next epoch — watch Open Orders)")
                self._last["sync"] = 0.0   # re-sync soon
            elif verb == "cancel":
                _, oid = parts
                self._submitter().cancel(oid)
                self.on_event("success", f"cancel submitted for …{oid[-18:]}")
                self._last["sync"] = 0.0
            elif verb == "market":
                _, side, size = parts
                s = self.snap
                oid, px = self._submitter().market_order(
                    side, size, s.ticker, bid=s.bid, ask=s.ask, last=s.last)
                if oid is None:
                    self.on_event("error", f"market: no live quote to cross (px={px})")
                else:
                    self.on_event("success",
                                  f"MKT {('BUY' if side > 0 else 'SELL')} {size} → "
                                  f"marketable limit @ {px} · clears next epoch")
                self._last["sync"] = 0.0
            elif verb == "cancel_all":
                n = 0
                for o in list(self.snap.open_orders):
                    self._submitter().cancel(o["orderid"])
                    n += 1
                self.on_event("success", f"cancel submitted for {n} open order(s)")
                self._last["sync"] = 0.0
            elif verb == "flatten":
                sub = self._submitter()
                s = self.snap
                for o in list(s.open_orders):
                    sub.cancel(o["orderid"])
                closed = 0
                for p in s.positions:
                    qty = p["contracts"]
                    if not qty:
                        continue
                    oid, px = sub.market_order(-1 if qty > 0 else 1, abs(qty),
                                               p["ticker"], bid=s.bid, ask=s.ask,
                                               last=s.last)
                    if oid is not None:
                        closed += 1
                self.on_event("success",
                              f"FLATTEN_ALL submitted · {len(s.open_orders)} cancel(s), "
                              f"{closed} closing order(s) · verify next epoch")
                self._last["sync"] = 0.0
                self._last["account"] = 0.0
            elif verb == "unlock":
                _, amount = parts
                # One open unlock per account: a second request while one is
                # RESERVED is rejected on margin and recorded as UNLOCK_REJECTED.
                if self.snap.pending_unlock > 0:
                    self.on_event("warning",
                                  f"an unlock is already RESERVED "
                                  f"({self.snap.pending_unlock:,} sats pending) — "
                                  f"one open unlock per account; a second request "
                                  f"would be rejected. Wait for it to complete.")
                    return
                self._submitter().unlock(amount)
                what = f"{amount:,} sats" if amount else \
                    "MAX (resolves to min(available_balance, available_margin))"
                self.on_event("success",
                              f"unlock requested: {what}. It applies live "
                              f"in-session — watch 'pending unlock'; a rejected "
                              f"unlock shows up in the unlock records. BTC "
                              f"always returns to {self.snap.address}.")
                self._last["account"] = 0.0
            elif verb == "register_delegate":
                _, trader_id, pubkey = parts
                self._submitter().register_delegate(trader_id, pubkey)
                self.on_event("success",
                              f"delegate registration submitted for {trader_id} "
                              f"(applies live in-session — watch the delegates "
                              f"panel)")
                self._last["account"] = 0.0
            elif verb == "revoke_delegate":
                _, trader_id = parts
                self._submitter().revoke_delegate(trader_id)
                self.on_event("success", f"delegate revoke submitted for {trader_id}")
                self._last["account"] = 0.0
            elif verb == "lock_all":
                # one button, everything: the user does not manage sats. The
                # ENTIRE confirmed balance is forwarded; the fee comes out of
                # it; no change output — this is funding, not a wallet.
                total = self.snap.chain_confirmed + self.snap.chain_mempool
                if total <= 0:
                    self.on_event("warning", "nothing on-chain to lock yet")
                    return
                txid, p = wallet.build_lock_tx(self._need_identity(), total,
                                               broadcast=True,
                                               fee_from_amount=True)
                self.on_event("success",
                              f"ACCOUNT FUNDED: locked your whole balance — "
                              f"{p.amount_sats:,} sats to the exchange "
                              f"({p.fee_sats:,} network fee). txid {txid}. "
                              f"Credited once confirmed on-chain.")
                self._last["chain"] = 0.0
            elif verb == "exit_all":
                _, dest = parts
                txid, p = wallet.build_sweep_tx(self._need_identity(), dest,
                                                broadcast=True)
                self.on_event("success",
                              f"EXIT BROADCAST: your entire balance — "
                              f"{p.amount_sats:,} sats — is on its way to {dest} "
                              f"({p.fee_sats:,} network fee). txid {txid}. "
                              f"Goodbye (until next time).")
                self._last["chain"] = 0.0
            elif verb == "chain_refresh":
                self._last["chain"] = 0.0
            elif verb == "sync_now":
                self._last["sync"] = 0.0
                self._last["account"] = 0.0
        except Exception as e:
            self.on_event("error", f"{verb}: {e}")

    def _need_identity(self) -> wallet.Identity:
        if self._identity is None:
            raise RuntimeError("watch-only: no signing key loaded")
        return self._identity
