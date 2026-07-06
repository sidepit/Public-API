# sidepit gateway — public JSON REST + WS boundary

The HTTP face of the exchange for external integrations (CCXT first). Hostable
server-side: **reads are non-custodial** (account state is public; endpoints take the
address), and the **write path is a relay** — clients sign their own `Transaction`
protobuf and POST the serialized `SignedTransaction`; the gateway holds no keys
(custody model **B**). An interim server-signed mode (**A**, trade-only delegate key
from env) exists for the classic CEX api-key UX and is off unless a key is configured.

```sh
cd python-client
python -m facade.server                      # dev: binds 127.0.0.1:8642
GATEWAY_HOST=0.0.0.0 python -m facade.server # hosted (put TLS in front)
```

Env: `SIDEPIT_HOST` (exchange, default `api.sidepit.com`), `GATEWAY_HOST`,
`GATEWAY_PORT`; optional A-mode key: `SIDEPIT_WIF`/`SIDEPIT_PRIV_HEX` (+ `SIDEPIT_ID`
for delegate mode).

## REST

| Endpoint | Maps to | Notes |
|----------|---------|-------|
| `GET /status` | reqrep `ACTIVE_PRODUCT` | exchange state (enum name), session, close time |
| `GET /markets` | `ACTIVE_PRODUCT` per ticker | base/quote/settle explicit: USD/BTC:BTC inverse **dated future**; prices sats-per-USD |
| `GET /ticker/{symbol}` | 12122 feed (cached) | 404 while exchange closed (feeds silent) |
| `GET /orderbook/{symbol}` | 12122 depth (cached) | bids/asks best-first `[price, size]` |
| `GET /trades/{symbol}` | 12124 fills (ring) | whole-venue prints |
| `GET /ohlcv/{symbol}?limit=&since_ms=` | `HISTORICAL_BARS` + live 12127 | 1m only; oldest-first `[ms,o,h,l,c,v]` |
| `GET /balance/{address}` | `POSITIONS` | `free`=server `available_margin`; `available_balance` is yesterday's settled figure — info only |
| `GET /positions/{address}` | `POSITIONS` | `entry_price` carries the resets-daily caveat |
| `GET /open_orders/{address}?sync=1` | snapshot sync 12125→12129 | authoritative; falls back to live view if the sync times out |
| `GET /orders/{orderid}` | 12124/12128 observational | status: open/closed/canceled/rejected |
| `GET /my_trades/{address}` | 12124 fills + reqrep seed | |
| `GET /rejections/{address}` | 12128 (ring) | codes by NAME with `expected` flag |
| `GET /nonce` | — | strictly increasing `timestamp_ns` for clients that want one |
| `POST /relay` `{signed_tx: hex}` | Push 12121 | **model B write path**; gateway validates shape, pushes bytes verbatim |
| `POST /orders`, `DELETE /orders/{id}` | sign + push | **model A (interim)**; 400 unless a key is configured |

## WS — `ws://…/ws`

Send `{"op":"subscribe","channels":[...],"address":"bc1q… (optional)"}` (empty
channels = everything). Events: `{"channel","symbol","address","ts","data"}` on
channels `ticker`, `orderbook`, `trades`, `ohlcv`, `orders`, `my_trades`,
`rejections`. Account-scoped events are filtered to the subscribed address.

## Semantics the gateway preserves (not flattened)

- **No instant acks.** The venue is a sequenced-batch CLOB with 1-second epochs;
  order/cancel outcomes are observational (order feed + reject feed), surfaced via
  `/orders/{id}`, `/rejections/{address}`, and the WS channels.
- **Limit orders only.** "Market" has no defined price under per-epoch sequencing.
- **Prices are sats-per-USD** end to end; conversion is the client's single boundary.
- **Reject codes by name** with an `expected` flag (`RC_CDUP`/`RC_CREJ` are normal in
  cancel-heavy flows; `RC_MARGIN`/`RC_REDUCE` are expected business outcomes).
- Feed discipline inside: drain-until-empty (`more_in_epoch`), big RECVBUF,
  silence-resubscribe, idle-reopen on the push pipe.
