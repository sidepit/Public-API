---
name: sidepit-charts
description: "Chart any Sidepit session from the exchange's own records: walk HISTORICAL_BARS per (ticker, session_id) over the public 12125 door, cache immutable closed sessions locally, convert sat-quoted ticks to $/BTC (inverting high/low), and render candles plus a volume histogram — with an optional reference venue in a separate, time-synced pane. Use when a user wants session history, daily OHLC, or price/volume visualized. Requires no account or key — read-only public surfaces."
---


# sidepit-charts

Chart Sidepit from the exchange's own records. No account, no key — the
public 12125 door serves every bar the venue has. Paths assume the
Public-API repository root; setup as in the trade skill (venv + tests).

## 1. Resolve the ticker — then pass it explicitly, always

```python
from sidepit_trader import RequestClient
req = RequestClient()                       # api.sidepit.com
ticker = req.active_product().active_contract_product.product.ticker
```

**Every later call passes `ticker=` explicitly.** An empty ticker resolves
to TODAY'S active contract even for historical sessions — a June query
without it silently returns the wrong contract's bars (observed: a month
painted flat). STOP and fix the call rather than charting a suspicious
flat stretch.

The schedule can list **multiple products at once** (e.g. the front month
and the next contract, each with its own bar chain once it trades).
`active_contract_product` is the front month; to chart any other listed
product, name its ticker explicitly — the same explicit-ticker rule, for a
wider reason.

## 2. Walk the sessions, cache the closed ones forever

```python
hist = req.historical_bars(ticker=ticker)            # today's LIVE session
upsert(hist.bars)                                    # fold today in EVERY run
prev = hist.prev_session_id
while prev:                                          # stop ONLY on empty prev
    h = req.historical_bars(ticker=ticker, session_id=prev)
    if h.bars:                                       # a closed session can be
        upsert(h.bars)                               # legitimately EMPTY —
    mark_complete(ticker, prev)                      # skip it, keep walking
    prev = h.prev_session_id
```

Two rules the loop encodes — get them right:

- **Terminate only on an empty `prev_session_id`.** A real closed session
  can serve ZERO bars (every minute's close was 0 — early or parked
  sessions) while still linking further back; breaking on empty bars
  orphans everything older. The empty-reply-with-empty-prev case exists
  for UNKNOWN session ids, not for empty-but-real ones.
- **Today's bars are part of the chart.** Fold the live session's bars into
  the working set on every run — and never mark today complete; only
  closed sessions are immutable. Cache those forever (sqlite keyed
  `(ticker, epoch)`; the SDK's `TakerStore` ships exactly this schema) and
  never re-fetch a session marked complete.

## 3. Convert for humans — and swap high/low

Prices are integer **sats-per-USD** ticks. For a $/BTC chart invert every
price — and **high and low SWAP under inversion**:

```python
usd_open  = 1e8 / bar.open
usd_close = 1e8 / bar.close
usd_high  = 1e8 / bar.low      # the sat LOW is the dollar HIGH
usd_low   = 1e8 / bar.high
```

An un-swapped chart shows candles whose wicks point the wrong way — if the
chart looks inside-out, this is why. Volume needs no conversion: it is
contracts filled.

## 4. Render — candles + volume, reference venue in its own pane

- Candles pane + volume histogram pane from the same bars.
- A reference venue (e.g. an external perp's 1-minute bars) goes in a
  **separate pane, synced by TIME, never by bar index** — venues have
  different bar counts, and index-syncing shears the panes apart.
- **Never overlay the two venues on one axis.** A dated forward sits at a
  basis to a perp: compare moves, not levels.
- Web: lightweight-charts. Terminal: plotext/rich. The semantics above are
  renderer-independent.

## 5. Bar semantics — read before trusting any chart

- **`volume == 0` bars still move.** The close is carried and dragged by
  the touched side of the book (the clamp) — by design, not noise.
- **The minute grid is NOT contiguous.** Bars with `close == 0` are skipped
  server-side; do not interpolate the gaps away silently.
- **A bar labeled T covers epochs T+1s … T+60s**, and the first and last
  minute of a session are partial.
- **Flat-bar percentage is a liquidity metric**, not a rendering bug — one
  tick is $44–53 at current prices, so calm minutes round to flat.
- Filter `volume > 0` before any bar-based COMPARISON (stale quote prints
  masquerade as dislocations); keep zero-volume bars when charting the
  session as lived.

## Facts to keep straight

- The instrument is a dated **forward**; the venue runs a **DLOB —
  one-second deterministic auctions**. Bars aggregate those auctions.
- Everything here is read-only and keyless. Charting needs no credentials,
  ever — if a charting step asks for a key, something is wrong; STOP.
