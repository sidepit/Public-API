# sidepit_trader

The Python SDK for Sidepit — a clean, simple package a trader or AI
agent can copy and run. It ships with a local SQLite store (`~/.sidepit/state.db`) that
fills itself with 1-minute bar history and holds your trading identity, so sample code is
ready to trade out of the box.

It consumes what the exchange provides — the price feed, the 1-minute bar feed,
fills, and positions. `Trader` is the synchronous feed-reactor base; you override
`on_bar` and `decide`.

## Layout

| file | role |
|------|------|
| `wire.py`    | NNG ports/sockets (price 12122, bar 12127, order 12124, positions 12125, rejections 12128, snapshot 12129) |
| `feeds.py`   | synchronous drains: `PriceFeed` (pulse), `BarFeed`, `OrderFeed`, `RejectionFeed` |
| `trader.py`  | `Trader` base — connect, seed state, react; `TraderContext` |
| `signer.py`  | `Signer` — ECDSA signing; `Signer.as_delegate()` for hot/cold key split |
| `submit.py`  | `Submitter` — new_order, market_order, cancel, cancel_replace, unlock, register/revoke_delegate — order verbs return the full orderid string |
| `reqrep.py`  | positions, active product, quote, `historical_bars`, `schedules`, delegate submit |
| `sync.py`    | `snapshot_sync` — authoritative open-order sync (12125 → 12129) |
| `flatten.py` | cancel-all + close position + verify; `python -m sidepit_trader.flatten` |
| `wallet.py`  | identity + on-chain: `python -m sidepit_trader.wallet new` mints a key |
| `swings.py`  | `SwingTracker` — Spring zigzag with a retrace filter; breakout levels |
| `store.py`   | `TakerStore` — bars + identity + session-backfill bookkeeping (SQLite) |
| `examples/`  | `hello_market_data`, `hello_positions`, `hello_crossover`, `hello_taker` |

## Run

```sh
# from python-client/ — read-only, no keys:
python sidepit_trader/examples/hello_market_data.py
python sidepit_trader/examples/hello_crossover.py

# trading (funded key):
python -m sidepit_trader.wallet new          # mint an identity, fund its address
SIDEPIT_ID=bc1q... SIDEPIT_WIF=... python sidepit_trader/examples/hello_taker.py
SIDEPIT_ID=bc1q... SIDEPIT_WIF=... python -m sidepit_trader.flatten
```

Identity precedence: env (`SIDEPIT_WIF` or `SIDEPIT_PRIV_HEX`, plus optional `SIDEPIT_ID`
— when it differs from the key's own address the key signs as a registered delegate for
that custody account), then the flat-file keystore (`~/.sidepit/keys/*.env`, 0600; the
`ACTIVE` file selects the active identity).

Env: `SIDEPIT_HOST` (default `api.sidepit.com`), `SIDEPIT_TICKER` (default = the active
product), `SIDEPIT_STATE_DB` (default `~/.sidepit/state.db`; honored only with
`SIDEPIT_TESTNET` — production values are pinned in `config.py`).
