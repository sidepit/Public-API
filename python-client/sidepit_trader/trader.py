"""Synchronous feed-reactor base — subclass and run.

The price feed (12122, ~1 msg/s) is the pulse; on each wake we drain the bar
feed (closed EpochBars) and the order feed (our fills), fire `on_bar` for new
bars, and call `decide` while the exchange is OPEN. Exchange state (open/close)
comes from the active-product reqrep on a light interval.

Forever-running: NNG auto-reconnects, so a server restart is transparent.
Subclass and override on_open / on_bar / decide / on_close / on_shutdown.
"""
import logging
import time
from dataclasses import dataclass

from . import wire
from ._proto import pb
from .config import HOST as _DEFAULT_HOST   # SIDEPIT_HOST env + testnet guard live in config
from .feeds import BarFeed, OrderFeed, PriceFeed, RejectionFeed
from .reqrep import RequestClient
from .signer import Signer
from .submit import Submitter

log = logging.getLogger("trader")

_STATE_POLL_SECS = 2.0   # how often to refresh exchange state via reqrep
_FEED_SILENCE_SECS = 30.0   # price feed ticks ~1/s when OPEN; silence beyond this while
                            # OPEN means the SUB pipes are silently dead (LB idle-drop,
                            # no RST) — reopen them. Overnight closes kill them otherwise.


def _state_name(state: int) -> str:
    try:
        return pb.ExchangeState.Name(state)
    except Exception:
        return str(state)


@dataclass
class TraderContext:
    """Passed to decide() each pulse while OPEN. Submit via `submitter`."""
    epoch: int
    ticker: str
    session_id: str
    quote: object          # MarketQuote (bid/ask/last) or None
    bar: object            # latest in-progress EpochBar or None
    position: int          # net contracts (signed), from our fills
    submitter: Submitter
    close_ms: int          # session trading_close_time (ms), 0 if unknown
    now_ms: int            # wall-clock now (ms)


class Trader:
    def __init__(self, *, host: str = _DEFAULT_HOST, signer: Signer, ticker: str):
        self.host = host
        self.signer = signer
        self.ticker = ticker
        self.state = pb.EXCHANGE_UNKNOWN
        self.session_id = ""
        self.epoch = 0
        self.close_ms = 0
        self._prev_state = pb.EXCHANGE_UNKNOWN
        self.price = self.bars = self.orders = self.rejects = None
        self.submitter = None
        self.req = None

    # --- overridable hooks -------------------------------------------------
    def on_open(self):
        """Entering EXCHANGE_OPEN (session_id set). Backfill/seed per-session state."""

    def on_close(self):
        """Leaving EXCHANGE_OPEN."""

    def on_bar(self, bar):
        """A new CLOSED 1-minute bar arrived (already persisted)."""

    def on_fill(self, fill):
        """One of OUR fills arrived on the order feed (a pb.Fill; the fold into
        `orders.position` has already happened). Default: no-op."""

    def on_reject(self, rej):
        """One of OUR transactions was rejected on 12128 (a pb.RejectedTransaction).
        RC_CDUP/RC_CREJ are expected residual-cancel noise — use
        RejectionFeed.is_error(rej)/code_name(rej) to classify (the feed has
        already logged real errors at WARNING). Default: no-op."""

    def on_shutdown(self):
        """Called on ANY exit (normal, error, SIGINT) — cancel residuals / flush."""

    def decide(self, ctx: TraderContext):
        """React to the latest price/bars; submit via ctx.submitter. Called only OPEN."""

    # --- lifecycle ---------------------------------------------------------
    def run(self):
        log.info("connecting host=%s ticker=%s", self.host, self.ticker)
        self.req = RequestClient(self.host)
        self.price = PriceFeed(self.host, self.ticker)
        self.bars = BarFeed(self.host, self.ticker)
        self.orders = OrderFeed(self.host, self.signer.sidepit_id,
                                on_fill=self.on_fill)
        self.rejects = RejectionFeed(self.host, self.signer.sidepit_id)
        self.submitter = Submitter(self.signer, self.host)
        self._seed()
        log.info("seeded state=%s session=%s ticker=%s; reacting to feeds",
                 _state_name(self.state), self.session_id or "?", self.ticker)
        last_state = 0.0
        try:
            while True:
                md = self.price.poll()       # pulse (blocks up to ~250ms; None on timeout)
                now = time.monotonic()
                if now - last_state >= _STATE_POLL_SECS:
                    self._refresh_state()    # estate/session/close via reqrep
                    last_state = now
                # Feed-silence watchdog: while OPEN the price feed ticks ~1/s. Prolonged
                # silence = the SUB pipes were silently dropped (overnight idle / LB) and
                # NNG can't tell — reopen all feeds with fresh connections.
                if (self.state == pb.EXCHANGE_OPEN
                        and now - self.price.last_rx > _FEED_SILENCE_SECS):
                    log.warning("feeds silent %.0fs while OPEN — reopening subscriptions",
                                now - self.price.last_rx)
                    self._reopen_feeds()
                if md is not None:
                    self.epoch = md.epoch
                # Drain bars/fills and run the strategy every loop iteration (not only
                # on a fresh price msg) so flat-at-close and level checks still fire in a
                # quiet market. decide() reads the cached quote; the fired-set makes a
                # re-check with an unchanged quote idempotent.
                for b in self.bars.drain():
                    self.store_bar(b)
                    self.on_bar(b)
                self.orders.drain()
                for rj in self.rejects.drain():   # the feed logs errors at WARNING
                    self.on_reject(rj)
                if self.state == pb.EXCHANGE_OPEN and self.price.quote is not None:
                    self.decide(self._ctx())
        except KeyboardInterrupt:
            log.info("SIGINT — shutting down")
        finally:
            self.on_shutdown()

    def store_bar(self, bar):
        """Override to persist a live closed bar (base does nothing)."""

    def _ctx(self) -> TraderContext:
        return TraderContext(
            epoch=self.epoch, ticker=self.ticker, session_id=self.session_id,
            quote=self.price.quote, bar=self.price.bar,
            position=self.orders.position, submitter=self.submitter,
            close_ms=self.close_ms, now_ms=int(time.time() * 1000))

    def _seed(self):
        self._refresh_state(force_transition=True)

    def _refresh_state(self, force_transition: bool = False):
        """Read estate + session + active contract + close time via reqrep. Drives the
        open/close hooks (the taker has no clock feed, so state is polled)."""
        try:
            ap = self.req.active_product(self.ticker or None)
            es = ap.exchange_status
            self.state = es.status.estate
            self.session_id = es.session.session_id or es.status.session_id or self.session_id
            sym = ap.active_contract_product.product.ticker
            if sym and sym != self.ticker:
                log.info("active contract roll: %s -> %s", self.ticker, sym)
                self.ticker = sym
                # repoint the multi-product feeds at the new active contract
                if self.price is not None:
                    self.price.ticker = sym
                if self.bars is not None:
                    self.bars.ticker = sym
            sch = es.session.schedule
            if sch.trading_close_time:
                self.close_ms = sch.trading_close_time
        except Exception as e:
            if force_transition:
                log.warning("could not seed state: %s", e)
            return
        if self.state != self._prev_state or force_transition:
            self._transition(self._prev_state, self.state)
            self._prev_state = self.state

    def _reopen_feeds(self):
        """Fresh SUB connections for all feeds. The overnight close leaves the old pipes
        silently dead (idle-drop, no RST), so reconnect explicitly rather than trusting
        NNG's transparent reconnect (it never learns the pipe died)."""
        self.price.reopen()
        self.bars.reopen()
        self.orders.reopen()
        self.rejects.reopen()

    def _transition(self, old: int, new: int):
        log.info("STATE %s -> %s", _state_name(old), _state_name(new))
        if new == pb.EXCHANGE_OPEN:
            # New session: reconnect every feed BEFORE on_open so the session
            # starts on fresh SUB connections.
            self._reopen_feeds()
            self.on_open()
        elif old == pb.EXCHANGE_OPEN:
            self.on_close()
