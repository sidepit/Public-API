# Sidepit Python SDK

The official Python SDK for [Sidepit](https://sidepit.com) — **Bitcoin-margined
forwards**, cleared in one-second batch auctions. Best price wins; fastest
machine does not. Deposit Bitcoin → trade → get your Bitcoin back.

Your Bitcoin address IS your account. Your keys never leave your machine.

## Point your agent at it

This repo is built to be driven by an AI agent. Give your agent the repo and say:

> Clone https://github.com/sidepit/Public-API, read `AGENTS.md`, and show me
> the live quote.

`AGENTS.md` is the agent's entry door; `skills/sidepit-trade/` is a
step-by-step trading skill with exact commands and expected output.

## Quickstart (no keys, 2 minutes)

```sh
git clone --recurse-submodules https://github.com/sidepit/Public-API && cd Public-API
python3 -m venv python-client/.venv
python-client/.venv/bin/pip install -r python-client/requirements.txt
python-client/.venv/bin/python examples/quickstart.py
```

```
exchange EXCHANGE_OPEN · session 1783296000000 · active contract USDBTCU26
bid 3x1555 · ask 1556x3 · last 1572 (~$63,613/BTC)
```

Live production data, zero credentials. Prices are **sats-per-USD** (inverse):
`USD/BTC = 1e8 / price`.

## Where keys come from

There is one venue — production, real Bitcoin. Three rules:

1. **Generate your key locally** — `python -m sidepit_trader.wallet new`
   (run from `python-client/`). The private key never leaves your machine;
   the bc1q address it prints is your `sidepit_id` — your account.
2. **Deposit to your own address first** — move BTC to it yourself, and never
   fund from an address whose keys you don't control.
3. **Fund the exchange from it, then keep trading with those same keys** —
   the key that owns the address is the key that signs. The TUI's LOCK button
   (or `wallet.build_lock_tx()`) forwards your balance; you're credited once
   it confirms. Withdrawals return to the same address — there is no
   destination field to mistype, by design.

## Trade

```sh
cd python-client
SIDEPIT_ID=bc1q... SIDEPIT_WIF=... .venv/bin/python sidepit_trader/examples/hello_taker.py
```

```python
from sidepit_trader import signer_from_env, Submitter, RequestClient

sub = Submitter(signer_from_env(), "api.sidepit.com")
orderid = sub.new_order(side=1, size=1, price=1555, ticker="USDBTCU26")
# orderid = "bc1q...:1783296012345678901" — the handle on every feed

req = RequestClient()          # point-in-time account check after an order
tp = req.positions("bc1q...")  # positions, balances, margin, your fills
```

Orders return the full orderid string; outcomes (fills, rejects) arrive on the
feeds. The reqrep door (12125) gives point-in-time account state; the streams
give continuous updates. Rejects arrive on 12128 with named codes
(`RC_MARGIN` = fund the account).

**Humans:** `users-cli/` is *sidepit // cockpit* — a full terminal app:
create account, fund, trade, delegate, withdraw.

**Agents (recommended):** delegate. Your key appoints an agent key that can
trade but can never withdraw, appoint, or revoke — protocol-enforced. Hand the
agent key to your bot freely; revoke any time.
`Submitter.register_delegate(delegate_pubkey=...)`, then the agent signs with
`Signer.as_delegate(...)` — the env handoff is just
`SIDEPIT_WIF=<agent key> SIDEPIT_ID=<your account>`.

## Repo map

| path | what |
|------|------|
| `python-client/sidepit_trader/` | the SDK — signing, feeds, orders, wallet, `Trader` base class |
| `python-client/proto/` | generated protobuf stub (from the pinned proto) |
| `examples/` | start here — keyless quickstart |
| `skills/sidepit-trade/` | agent skill: onboard → read market → order → position → exit |
| `AGENTS.md` | agent orientation: wire surface, message shapes, conventions |
| `users-cli/` | the trading TUI for humans |
| `Public-API-Data/` | **the contract**: `sidepit_api.proto` (submodule) — every message the exchange speaks |
| `python-client/facade/` | optional local REST/WS gateway over the wire |
| `integrations/ccxt/` | CCXT adapter (runs over the facade) |

Optional install as a package: `pip install -e python-client` (dist name
`sidepit`, imports as `sidepit_trader`). The examples run straight from the
clone either way.

## The wire

Transport is [NNG](https://nng.nanomsg.org) over TCP at `api.sidepit.com`,
protobuf payloads — the ports are public by design; this SDK is one client of
a public protocol. The proto in `Public-API-Data/` is the full reference.
Full docs: [docs.sidepit.com](https://docs.sidepit.com) · app:
[app.sidepit.com](https://app.sidepit.com)

MIT license.
