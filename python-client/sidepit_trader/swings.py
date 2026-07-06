"""Swing detection — a faithful Python port of FAS/Fractals/Spring.h (Jay's fractal).

This is a direct translation of the C++ `Spring` class; the algorithm is Jay's,
ported line-for-line. `mTops` = swing highs (buy-stop levels), `mBots` = swing lows
(sell-stop levels). A swing is added when price retraces `retrace` of the prior leg
(`PercentRetrace = small / large`); `CheckLows`/`CheckHighs` invalidate a swing on
their own when price trades through it — so the signal layer self-negates and
execution doesn't have to.

What it's fed (a "trade" in Spring terms) is the caller's choice — see the Trader.
`feed`/`feed_bar` map a price (+ epoch as the timestamp) onto Spring's `NewTrade`.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Swing:
    price: float
    epoch: int          # Spring's JBBO.timestamp()


class SwingTracker:
    def __init__(self, retrace: float = 0.50, min_ticks: int = 0):
        self._ret = retrace
        self._min_ticks = min_ticks   # absolute minimum swing amplitude (0 = off)
        self._tops: list[Swing] = []   # swing highs
        self._bots: list[Swing] = []   # swing lows
        self._prev: Swing | None = None
        self._first = True
        self._last_low = False
        self._length = 0
        self._hi_base = False

    # --- public API (maps onto Spring::NewTrade) ---------------------------
    def feed_bar(self, bar) -> None:
        self._new_trade(Swing(bar.close, bar.epoch))

    def feed(self, price, epoch: int) -> None:
        self._new_trade(Swing(price, epoch))

    def highs(self) -> list[Swing]:
        return list(self._tops)

    def lows(self) -> list[Swing]:
        return list(self._bots)

    def reset(self) -> None:
        self.__init__(self._ret, self._min_ticks)

    def consume_high(self, s: Swing) -> None:
        """Remove a swing high that's been acted on (fired). Keeps `_length` consistent."""
        try:
            self._tops.remove(s)
            self._length = len(self._tops) + len(self._bots)
        except ValueError:
            pass

    def consume_low(self, s: Swing) -> None:
        """Remove a swing low that's been acted on (fired). Keeps `_length` consistent."""
        try:
            self._bots.remove(s)
            self._length = len(self._tops) + len(self._bots)
        except ValueError:
            pass

    # --- Spring.h, line-for-line -------------------------------------------
    def _new_trade(self, t: Swing) -> None:
        if self._first:
            self._prev = t
            self._first = False
            return
        if self._length == 0:
            self._base_trade(t)
            return
        if t.price < self._prev.price:          # IsLow
            self._check_lows(t.price)
            self._add_low(t)
        elif t.price > self._prev.price:        # IsHigh
            self._check_highs(t.price)
            self._add_high(t)
        self._prev = t

    def _base_trade(self, t: Swing) -> None:
        if t.price < self._prev.price:
            self._hi_base = False
            self._last_low = True
            self._bots.append(t)
            self._length = 1
            self._prev = t
        elif t.price > self._prev.price:
            self._hi_base = True
            self._last_low = False
            self._tops.append(t)
            self._length = 1
            self._prev = t

    @staticmethod
    def _pct(large: float, small: float) -> float:
        return small / large if large else 0.0

    def _add_low(self, t: Swing) -> bool:
        if self._last_low:
            return False
        # Minimum swing amplitude: the drop from the last top must be >= min_ticks,
        # else it's noise (a retrace fraction alone can't filter a 1-tick-chop market).
        if self._min_ticks and self._tops and (self._tops[-1].price - t.price) < self._min_ticks:
            return False
        doadd = False
        if self._length <= 1 or not self._tops or not self._bots:
            doadd = True
        else:
            large = self._tops[-1].price - self._bots[-1].price
            small = self._tops[-1].price - t.price
            if self._pct(large, small) >= self._ret:
                doadd = True
        if doadd:
            self._bots.append(t)
            self._length += 1
            self._last_low = True
            return True
        return False

    def _add_high(self, t: Swing) -> bool:
        if not self._last_low:
            return False
        if self._min_ticks and self._bots and (t.price - self._bots[-1].price) < self._min_ticks:
            return False
        doadd = False
        if self._length <= 1 or not self._tops or not self._bots:
            doadd = True
        else:
            large = self._tops[-1].price - self._bots[-1].price
            small = t.price - self._bots[-1].price
            if self._pct(large, small) >= self._ret:
                doadd = True
        if doadd:
            self._tops.append(t)
            self._length += 1
            self._last_low = False
            return True
        return False

    def _clear_lows(self, i: int) -> None:
        self._length -= (len(self._bots) - i)
        del self._bots[i:]

    def _clear_highs(self, i: int) -> None:
        self._length -= (len(self._tops) - i)
        del self._tops[i:]

    def _check_lows(self, low: float) -> None:
        i = 0
        while i < len(self._bots) and low > self._bots[i].price:
            i += 1
        if i < len(self._bots):
            mdt = self._bots[i].epoch
            self._clear_lows(i)
            j = 1
            while j < len(self._tops) and self._tops[j].epoch < mdt:
                j += 1
            if j < len(self._tops):
                self._clear_highs(j)
            self._last_low = False

    def _check_highs(self, high: float) -> None:
        i = 0
        while i < len(self._tops) and high < self._tops[i].price:
            i += 1
        if i < len(self._tops):
            mdt = self._tops[i].epoch
            self._clear_highs(i)
            j = 1
            while j < len(self._bots) and self._bots[j].epoch < mdt:
                j += 1
            if j < len(self._bots):
                self._clear_lows(j)
            self._last_low = True
