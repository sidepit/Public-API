"""Build, sign, and push transactions (orders, cancels, account verbs).

Order identity is the full orderid string `f"{sidepit_id}:{timestamp_ns}"` —
client-minted, known before the exchange sees the order, and the correlation
key across every feed (book orders, fills, rejects).
"""
import logging
import threading
import time

import pynng

from . import wire
from .errors import CourierRuleError
from .signer import Signer
from ._proto import pb

log = logging.getLogger("submit")

# Keep the push connection fresh: reopen it before sending if it has been idle
# longer than this. Long-lived connections stay healthy without any caller code.
RECONNECT_IDLE_SECS = 180


def order_id(sidepit_id: str, timestamp_ns: int) -> str:
    return f"{sidepit_id}:{timestamp_ns}"


_ns_lock = threading.Lock()
_ns_last = 0


def next_ns() -> int:
    """Strictly increasing nanosecond nonce, process-wide. The server's replay
    guard drops any duplicate (sidepit_id, timestamp) — and a fast UI (doggie
    taps, double-clicks) or a tight bot loop can land on the same clock tick.
    Never hand out the same value twice, even across threads/Submitters."""
    global _ns_last
    with _ns_lock:
        now = time.time_ns()
        if now <= _ns_last:
            now = _ns_last + 1
        _ns_last = now
        return now


class Submitter:
    """Signs and pushes transactions on the 12121 order pipe. Owns its push
    connection and keeps it fresh automatically (reopen after idle, retry on
    send timeout) — callers just call the verbs."""

    def __init__(self, signer: Signer, host: str, port: int = wire.Ports.CLIENT_API):
        self._signer = signer
        self._host = host
        self._port = port
        self._sock = wire.open_push(host, port)
        self._last_send = 0.0   # monotonic time of the last successful send

    def _reconnect(self) -> None:
        try:
            self._sock.close()
        except Exception:
            pass
        self._sock = wire.open_push(self._host, self._port)

    def _push(self, stx) -> None:
        data = stx.SerializeToString()
        now = time.monotonic()
        if self._last_send and now - self._last_send > RECONNECT_IDLE_SECS:
            log.info("push idle %.0fs (> %ds) — reopening before send",
                     now - self._last_send, RECONNECT_IDLE_SECS)
            self._reconnect()
        try:
            self._sock.send(data)
        except pynng.Timeout:                 # backstop: dead pipe NNG did notice
            log.warning("send timed out — reconnecting and retrying")
            self._reconnect()
            self._sock.send(data)
        self._last_send = time.monotonic()

    @staticmethod
    def _now_ns() -> int:
        return next_ns()   # strictly increasing — duplicates are server-rejected

    def new_order(self, side: int, size: int, price: int, ticker: str,
                  timestamp_ns: int | None = None) -> str:
        """Submit a NewOrder. Returns the full orderid string
        `"{sidepit_id}:{timestamp_ns}"` — the handle that identifies this order
        on every feed (book orders, fills, rejects)."""
        ts = timestamp_ns or self._now_ns()
        tx = pb.Transaction(version=1, timestamp=ts)
        tx.new_order.side = side
        tx.new_order.size = size
        tx.new_order.price = price
        tx.new_order.ticker = ticker
        self._push(self._signer.sign(tx))
        return order_id(self._signer.sidepit_id, ts)

    def market_order(self, side: int, size: int, ticker: str, *,
                     bid: int = 0, ask: int = 0, last: int = 0,
                     cross_ticks: int = 2, timestamp_ns: int | None = None):
        """Submit a 'market' order — set-and-forget. Sidepit has no native market type,
        so 'market' = a marketable limit placed `cross_ticks` THROUGH the opposite touch
        (buy at ask+cross, sell at bid-cross). This call owns the cross so callers just
        pass the current quote. If the touch side is empty, fall back across last/other
        side so we still cross something. Returns (orderid, price) — orderid is the full
        `"{sidepit_id}:{timestamp_ns}"` string; on a bad price (<=0) returns
        (None, price) and sends nothing."""
        if side > 0:
            ref = ask or last or bid
            price = ref + cross_ticks
        else:
            ref = bid or last or ask
            price = ref - cross_ticks
        if price <= 0:
            return None, price
        oid = self.new_order(side, size, price, ticker, timestamp_ns=timestamp_ns)
        return oid, price

    def cancel(self, orderid: str, timestamp_ns: int | None = None) -> str:
        """Submit a cancel for `orderid`. Returns the cancel transaction's own
        orderid string `"{sidepit_id}:{timestamp_ns}"` (for reject correlation)."""
        ts = timestamp_ns or self._now_ns()
        tx = pb.Transaction(version=1, timestamp=ts)
        tx.cancel_orderid = orderid
        self._push(self._signer.sign(tx))
        return order_id(self._signer.sidepit_id, ts)

    def cancel_replace(self, ref_orderid: str, price: int,
                       timestamp_ns: int | None = None) -> str:
        """Submit a CancelReplace: retire `ref_orderid` and repost its remaining qty at
        `price` (price-only change). Returns the REPLACEMENT order's orderid — this
        tx's own `"{sidepit_id}:{timestamp_ns}"` string."""
        ts = timestamp_ns or self._now_ns()
        tx = pb.Transaction(version=1, timestamp=ts)
        tx.replace_order.ref_orderid = ref_orderid
        tx.replace_order.price = price
        self._push(self._signer.sign(tx))
        return order_id(self._signer.sidepit_id, ts)

    def auction_bid(self, ordering_salt: str, bid: int) -> int:
        ts = self._now_ns()
        tx = pb.Transaction(version=1, timestamp=ts)
        tx.auction_bid.ordering_salt = ordering_salt
        tx.auction_bid.bid = bid
        self._push(self._signer.sign(tx))
        return ts

    # --- account verbs -----------------------------------------------------
    # These do NOT ride the 12121 order pipe. They are custody-signed and posted
    # to the 12125 metadata door (TypeMask DELEGATE/UNLOCK). The ack means
    # received; the verb is verified and applied live in-session (the next
    # session boundary is the outer bound) — confirm by reading account state.
    # Courier rule: a delegate may trade, never appoint, revoke, or withdraw.

    def _account_sign(self, tx):
        if self._signer.trader_id:
            raise CourierRuleError(
                "account verbs are custody-signed — use the custody "
                "Signer, never a delegate (courier rule)")
        return self._signer.sign(tx)

    def _door(self):
        if getattr(self, "_req", None) is None:
            from .reqrep import RequestClient  # lazy: reqrep is independent of submit
            self._req = RequestClient(self._host)
        return self._req

    def unlock(self, amount_sats: int | None = None, *, minmax: int | None = None,
               timestamp_ns: int | None = None) -> int:
        """Withdraw: the EXCHANGE sends BTC on-chain back to sidepit_id (you never build
        a Bitcoin tx). Default = pb.MAX (everything withdrawable); pass amount_sats
        for an EXPLICIT amount; MAX resolves to min(available_balance,
        available_margin). Applies live in-session (the session boundary is the
        outer bound). Lifecycle: PENDING -> RESERVED -> COMPLETED on the chain
        outflow; track via accountstate.pending_unlock. The ack means received;
        the verdict is served on POSITIONS — a rejected unlock is stored as
        UNLOCK_REJECTED (read RequestClient.unlock_records). A second unlock
        while one is open is rejected and recorded the same way.
        Funds always return to sidepit_id; there is no destination field."""
        ts = timestamp_ns or self._now_ns()
        tx = pb.Transaction(version=1, timestamp=ts)
        if minmax is not None:
            tx.unlock_req.minmax = minmax
        elif amount_sats:
            tx.unlock_req.minmax = pb.EXPLICIT
        else:
            tx.unlock_req.minmax = pb.MAX
        if amount_sats:
            tx.unlock_req.explicit_amount = amount_sats
        stx = self._account_sign(tx)
        self._door().submit_unlock(stx)
        return ts

    def register_delegate(self, trader_id: str | None = None, delegate_pubkey: str = "",
                          signature: str = "", timestamp_ns: int | None = None) -> int:
        """Authorize a hot-wallet key to trade for this account. Sign with the CUSTODY
        key (a plain Signer). Pass ONLY delegate_pubkey (the hot key's 33-byte
        compressed pubkey, hex) — the hot key's bc1q address (trader_id) is
        DERIVED from it here (wallet.sidepit_id_from_pubkey); the server
        enforces P2WPKH(delegate_pubkey) == trader_id, so a typed address can
        only ever break the registration. If trader_id IS supplied (legacy
        callers) it must match the derivation or this raises ValueError before
        anything is signed or sent. Never asks for the delegate's private key.
        Applies live in-session (the session boundary is the outer bound);
        confirm via the DELEGATE records on POSITIONS. Once active, trade with
        Signer.as_delegate(hot_priv_hex, custody_sidepit_id)."""
        if not delegate_pubkey:
            raise ValueError("delegate_pubkey (33-byte compressed pubkey, hex) is required")
        from .wallet import sidepit_id_from_pubkey  # lazy: wallet imports signer
        derived = sidepit_id_from_pubkey(delegate_pubkey)
        if trader_id and trader_id != derived:
            raise ValueError(
                f"trader_id {trader_id!r} does not match P2WPKH(delegate_pubkey) "
                f"{derived!r} — omit trader_id; it is derived from the pubkey")
        ts = timestamp_ns or self._now_ns()
        tx = pb.Transaction(version=1, timestamp=ts)
        tx.new_delegate.agent_id = derived
        tx.new_delegate.agent_pubkey = delegate_pubkey
        if signature:
            tx.new_delegate.signature = signature
        stx = self._account_sign(tx)
        self._door().submit_delegate(stx)
        return ts

    def revoke_delegate(self, trader_id: str, timestamp_ns: int | None = None) -> int:
        """Revoke a delegate (by its bc1q address, or "ALL" for every delegate).
        Sign with the CUSTODY key; applies live in-session."""
        ts = timestamp_ns or self._now_ns()
        tx = pb.Transaction(version=1, timestamp=ts)
        tx.revoke_delegate = trader_id
        stx = self._account_sign(tx)
        self._door().submit_delegate(stx)
        return ts
