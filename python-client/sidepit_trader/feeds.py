"""Synchronous feed drains — price, bar, and order/fills.

The price feed (12122, `MarketData`, ~1 msg/second) is the natural pulse, so
the Trader BLOCKS on it and, on each wake, drains the bar feed (12127, closed
`EpochBar`) and the order feed (12124, post-match `OrderData`) which NNG has
already buffered (recv(block=False) until TryAgain).
"""
import logging
import time

import pynng

from . import wire
from ._proto import pb

log = logging.getLogger("feeds")


class PriceFeed:
    """MarketData on 12122. `poll()` is the Trader's pulse: it blocks (with a short
    timeout so SIGINT lands promptly) for the next message, then drains any backlog
    and returns the NEWEST MarketData FOR OUR TICKER. Caches the latest quote / bar.

    The exchange is multi-product: 12122 interleaves every contract (e.g. USDBTCM26 AND
    USDBTCU26), so messages are filtered to `self.ticker`.
    `ticker` is settable so the Trader can repoint it on a contract roll."""

    def __init__(self, host: str, ticker: str, timeout_ms: int = 250):
        self._host = host
        self._timeout_ms = timeout_ms
        self.sock = wire.open_sub(host, wire.Ports.PRICE_FEED)
        self.sock.recv_timeout = timeout_ms
        self.ticker = ticker
        self.quote = None      # latest MarketQuote (bid/ask/last) for our ticker
        self.bar = None        # latest in-progress EpochBar (MarketData.bar)
        self.epoch = 0
        self.last_rx = time.monotonic()   # last time ANY message arrived (liveness signal)

    def reopen(self):
        """Tear down and re-dial the subscription. The overnight close leaves SUB pipes
        silently dead (LB idle-drop, no RST — NNG never notices), so the Trader reopens
        feeds at each session open and on feed-silence while OPEN."""
        try:
            self.sock.close()
        except Exception:
            pass
        self.sock = wire.open_sub(self._host, wire.Ports.PRICE_FEED)
        self.sock.recv_timeout = self._timeout_ms
        self.last_rx = time.monotonic()

    def _apply(self, md) -> None:
        self.epoch = md.epoch
        if md.HasField("quote"):
            self.quote = md.quote
        if md.HasField("bar"):
            self.bar = md.bar

    def poll(self):
        """Block for the next MarketData (returns None on the timeout window so the
        caller can handle signals), then drain the backlog. Returns the newest md FOR
        OUR TICKER, or None if nothing for our ticker arrived this window."""
        try:
            raw = self.sock.recv()
        except pynng.Timeout:
            return None
        self.last_rx = time.monotonic()
        newest = None
        while True:
            md = pb.MarketData()
            md.ParseFromString(raw)
            if md.ticker == self.ticker:
                newest = md
            try:
                raw = self.sock.recv(block=False)
            except pynng.TryAgain:
                break
        if newest is not None:
            self._apply(newest)
        return newest


class BarFeed:
    """Closed 1-minute EpochBars on 12127. `drain()` returns every new bar for OUR
    ticker NNG has buffered since the last call (non-blocking), oldest-first. The feed
    is multi-product, so we filter to `self.ticker` (settable for contract rolls) —
    otherwise another contract's bars would corrupt the swing series."""

    def __init__(self, host: str, ticker: str):
        self._host = host
        self.sock = wire.open_sub(host, wire.Ports.BAR)
        self.ticker = ticker

    def reopen(self):
        try:
            self.sock.close()
        except Exception:
            pass
        self.sock = wire.open_sub(self._host, wire.Ports.BAR)

    def drain(self) -> list:
        out = []
        while True:
            try:
                raw = self.sock.recv(block=False)
            except pynng.TryAgain:
                return out
            b = pb.EpochBar()
            b.ParseFromString(raw)
            if b.ticker == self.ticker:
                out.append(b)


class RejectionFeed:
    """RejectedTransaction on 12128. `drain()` returns rejections buffered since the last
    call (non-blocking), optionally only OURS (sidepit_id given). RC_CDUP/RC_CREJ are
    EXPECTED (cancels are residual-only; canceling a filled/gone order is harmlessly
    rejected) — `is_error()` separates them from real problems (RC_MARGIN, RC_ID, ...)."""

    def __init__(self, host: str, sidepit_id: str | None = None):
        self._host = host
        self.sock = wire.open_sub(host, wire.Ports.REJECTIONS)
        self.sid = sidepit_id

    def reopen(self):
        try:
            self.sock.close()
        except Exception:
            pass
        self.sock = wire.open_sub(self._host, wire.Ports.REJECTIONS)

    @staticmethod
    def code_name(rj) -> str:
        """Readable RejectCode name ('RC_MARGIN'), never a bare integer."""
        try:
            return pb.RejectCode.Name(rj.reject_code)
        except Exception:
            return str(rj.reject_code)

    @classmethod
    def is_error(cls, rj) -> bool:
        """True if this rejection needs attention (not an expected residual-cancel miss)."""
        return cls.code_name(rj) not in ("RC_CDUP", "RC_CREJ")

    def drain(self) -> list:
        out = []
        while True:
            try:
                raw = self.sock.recv(block=False)
            except pynng.TryAgain:
                return out
            rj = pb.RejectedTransaction()
            rj.ParseFromString(raw)
            if self.sid and rj.transaction.sidepit_id != self.sid:
                continue
            (log.warning if self.is_error(rj) else log.debug)(
                "REJECT %s %s ts=%d", self.code_name(rj),
                rj.transaction.sidepit_id, rj.transaction.timestamp)
            out.append(rj)


class OrderFeed:
    """Post-match OrderData on 12124. `drain()` folds our own fills into a running
    net-position estimate (cheap; the Trader reconciles against reqrep occasionally).
    Returns the number of OrderData messages processed this call.

    `on_fill`: optional callback invoked with each of OUR Fill messages as it is
    parsed (the Trader base wires its `on_fill` hook here)."""

    def __init__(self, host: str, sidepit_id: str, on_fill=None):
        self._host = host
        self.sock = wire.open_sub(host, wire.Ports.ORDER)
        self.sid = sidepit_id
        self.on_fill = on_fill
        self.position = 0          # net contracts (signed), from our fills (ESTIMATE — drifts)
        # Engine-authoritative net, per ticker, from OrderData.margin_states broadcast each
        # epoch. risk_position is the real signed net with NO fold drift — prefer this over
        # `position` for any risk/hedge decision. Empty until the first OrderData arrives.
        self.margin_position: dict[str, int] = {}   # ticker -> risk_position
        # Every trader's last-broadcast available_margin (the echo-credibility map).
        self.margin_avail: dict[str, int] = {}      # sidepit_id -> available_margin
        self.open_orders: dict[str, int] = {}   # orderid -> remaining_qty (ours)

    def reopen(self):
        """Re-dial the order feed (position/open_orders state is kept — it's ours)."""
        try:
            self.sock.close()
        except Exception:
            pass
        self.sock = wire.open_sub(self._host, wire.Ports.ORDER)

    def drain(self) -> int:
        n = 0
        while True:
            try:
                raw = self.sock.recv(block=False)
            except pynng.TryAgain:
                return n
            od = pb.OrderData()
            od.ParseFromString(raw)
            n += 1
            # Engine-authoritative position: OrderData broadcasts each trader's live
            # TraderMarginState every epoch. risk_position is the real signed net — no fold
            # drift. Stored per-ticker (OrderData is ticker-scoped). Consumers that need the
            # truth read margin_position[ticker] instead of the fill-fold `position`.
            # We also keep every trader's LAST-EPOCH available_margin: the credibility map
            # for echo anticipation (Jay 2026-06-11) — an echoed order from a sender with no
            # margin will be rejected at match (RC_MARGIN), so anticipators must ignore it.
            for ms in od.margin_states:
                if ms.sidepit_id == self.sid:
                    self.margin_position[od.ticker] = ms.risk_position
                self.margin_avail[ms.sidepit_id] = int(ms.available_margin)
            # Log + count OUR fills as they happen. agressive_side is the taker's side
            # (+1 buy / -1 sell); count once, from whichever leg is ours.
            for f in od.fills:
                ours_agg = f.agressiveid.startswith(self.sid + ":")
                ours_pass = f.passiveid.startswith(self.sid + ":")
                if not (ours_agg or ours_pass):
                    continue
                oid = f.agressiveid if ours_agg else f.passiveid
                side = f.agressive_side if ours_agg else -f.agressive_side
                self.position += side * f.qty
                log.info("FILL %s %s %d @ %d (%s) filled-net=%d",
                         oid, "BUY" if side > 0 else "SELL", f.qty, f.price,
                         "aggressive" if ours_agg else "passive", self.position)
                if self.on_fill is not None:
                    self.on_fill(f)
            # Track OUR resting orders; log when one rests (partial/unfilled) or completes.
            for bo in od.bookorders:
                if bo.traderid != self.sid:
                    continue
                if bo.remaining_qty > 0:
                    if bo.orderid not in self.open_orders:
                        log.info("RESTING %s side=%d remaining=%d filled=%d @ %d "
                                 "(unfilled — book too thin to fully cross)",
                                 bo.orderid, bo.side, bo.remaining_qty, bo.filled_qty, bo.price)
                    self.open_orders[bo.orderid] = bo.remaining_qty
                else:
                    if bo.orderid in self.open_orders:
                        log.info("DONE %s filled=%d canceled=%d", bo.orderid,
                                 bo.filled_qty, bo.canceled_qty)
                    self.open_orders.pop(bo.orderid, None)
