# CCXT integration — sidepit

The CCXT exchange class for Sidepit. **Canonical copies live here**; the working ccxt
checkout (branch `sidepit-integration` in a `ccxt/ccxt` clone) carries the same files at:

| Here | In the ccxt repo |
|------|------------------|
| `sidepit.ts` | `ts/src/sidepit.ts` |
| `pro/sidepit.ts` | `ts/src/pro/sidepit.ts` (WebSocket / ccxt.pro) |
| `abstract/sidepit.ts` | `ts/src/abstract/sidepit.ts` (generated-style implicit API) |
| `smoke.mjs` | smoke test, one PASS/FAIL line per CCXT method |

Registration (4 lines) goes in `ts/ccxt.ts`: REST import + `exchanges` map entry +
pro import + `pro` map entry, alphabetical (`poloniex` … `sidepit` … `tokocrypto`).

## Architecture (custody model B — non-custodial)

- **Reads**: plain HTTP/WS against the public gateway (`python-client/facade/` in this
  repo). Account reads are address-parameterized; no credentials transit anywhere.
- **Writes**: the TS class itself serializes the `Transaction` protobuf (hand-rolled
  writer, ~60 lines) and signs — SHA256 over the exact bytes → secp256k1 ECDSA compact
  (low-s, via CCXT's bundled noble-curves) → hex, `signature_version=0` — then POSTs the
  serialized `SignedTransaction` to `POST /relay`. The gateway holds no keys.
- **Credentials**: `apiKey` = the account's `bc1q…` address (sidepit_id); `secret` = the
  64-hex secp256k1 private key of the signing key. Delegate (hot/cold) mode: secret =
  the hot key, `options.traderId` = the hot key's address, apiKey stays the custody
  address.
- **Byte-exactness is load-bearing**: the TS serializer is verified byte-for-byte
  against the Python SDK (`sidepit_trader/signer.py`) including ns timestamps beyond
  2^53 (string math via `Precise`, no BigInt — transpiler-safe), proto3 default-omission
  (`signature_version=0` emits nothing), and sint32 zigzag for `side`.

## Semantics preserved (not flattened)

- **Nothing resolves instantly.** 1-second sequenced-batch epochs; `createOrder` returns
  `status: 'open'` optimistically with the deterministic id
  `{sidepit_id}:{timestamp_ns}` (strictly increasing ns nonce); outcomes are
  observational via `fetchOrder` / `fetchOpenOrders` / `watchOrders` / `fetchRejections`.
- **Limit orders only** (`has.createMarketOrder = false`): market-order fills would be
  salt-dependent under per-epoch sequencing.
- **Prices**: native sats-per-USD → unified BTC-per-USD (`× 1e-8`), converted exactly
  once (`satsToPrice` / `priceToSats`). Markets are explicit `USD/BTC:BTC-<expiry>`,
  inverse dated forwards.
- **Balance basis**: `free` = server `available_margin`; `available_balance`
  (yesterday's settled figure, static intraday) is info-only. `entryPrice` carries the
  resets-daily-at-settlement caveat.
- **RejectCodes map by NAME** (`exceptions.exact`): `RC_MARGIN → InsufficientFunds`,
  `RC_DUP → InvalidNonce`, `RC_VERIFY`/`RC_ID → AuthenticationError`, `RC_CDUP`/`RC_CREJ
  → OrderNotFound` (expected outcomes in cancel-heavy flows — see
  `options.rejectCodes` for the expected flags).

## Build & test

```sh
# in the ccxt clone (branch sidepit-integration)
npm run tsBuild                          # TS -> JS
npx tsx build/transpile.ts sidepit       # -> python/ccxt/sidepit.py, php/sidepit.php
npx tsx build/transpileWS.ts sidepit     # -> python/ccxt/pro/sidepit.py, php/pro/

# gateway (this repo, python-client/):
python -m facade.server

# smoke: state-adaptive — closed-hours expectations vs full live cycle when OPEN
node integrations/ccxt/smoke.mjs
```

Transpiler constraints honored (regex-based): no `for…of`, no floating comments between
methods, no blank lines inside methods, no `return new X()` (use
`throwExactlyMatchedException`), no BigInt.

Status: **20/20 smoke checks pass against production during a live session** with a funded
account (set `SIDEPIT_ID` + `SIDEPIT_WIF` in the env for the funded write path; falls back
to a throwaway key otherwise) — including the full client-signed relay cycle: createOrder
→ epoch-confirmed `open` → cancelOrder → epoch-confirmed `canceled`, and watchTicker over
WS. The 16-check closed-hours branch runs automatically outside session hours. Not yet
submitted upstream — that is a later step.
