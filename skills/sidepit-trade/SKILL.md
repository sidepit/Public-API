---
name: sidepit-trade
description: Trade on Sidepit (Bitcoin-margined forwards, one-second batch auctions) from this repo — read the market keylessly, place and cancel orders with a funded key, check positions, and exit. Use when asked to trade, quote, or manage a Sidepit account.
---

# sidepit-trade

Drive the Sidepit exchange from a clone of this repo. No pip package needed —
everything runs from the repo. Real venue, real Bitcoin: follow the steps in
order and STOP where a check fails.

Paths below assume the repo root. Python 3.10+.

## 1. Setup (once per machine)

```sh
python3 -m venv python-client/.venv
python-client/.venv/bin/pip install -r python-client/requirements.txt
```

Verify the toolchain — this needs no network beyond pip:

```sh
python-client/.venv/bin/python -m pytest python-client/tests -q
```

Expected output ends with: `20 passed` (warnings are fine).
**STOP if any test fails** — report the failure; do not trade.

## 2. Read the market (no keys)

```sh
python-client/.venv/bin/python examples/quickstart.py
```

Expected shape (live values vary):

```
exchange EXCHANGE_OPEN · session 1783296000000 · active contract USDBTCU26
bid 3x1555 · ask 1556x3 · last 1572 (~$63,613/BTC)
prices are sats-per-USD: USD/BTC = 1e8 / price
bar O1556 H1556 L1556 C1556 v0
...
```

- Note the **active contract ticker** (here `USDBTCU26`) — use it everywhere
  below; never hardcode a remembered ticker.
- If the state is not `EXCHANGE_OPEN`: the market is closed. Reads work;
  orders wait for the open (schedule via `RequestClient.schedules()`).
  **STOP here if the task needs a fill now.**
- If the script cannot connect at all, report it and STOP.

## 3. Credentials (env)

Trading needs a funded identity in env. Two modes — both use the same two
variables:

- **Direct** (the key is the account): `SIDEPIT_WIF=<wif>` and optionally
  `SIDEPIT_ID=<its own bc1q address>`.
- **Delegate** (recommended for agents — the key trades a customer's account
  but can never withdraw): `SIDEPIT_WIF=<agent key>` +
  `SIDEPIT_ID=<the account's bc1q address>`. When `SIDEPIT_ID` differs from
  the key's own address, the SDK signs in delegate mode automatically.

Check:

```sh
test -n "$SIDEPIT_WIF" && echo creds-present || echo creds-missing
```

If `creds-missing`: **STOP and ask the user** for `SIDEPIT_WIF` (+
`SIDEPIT_ID` for delegate mode). Never invent, print, or log key material.

No account yet? Mint one and show the user its address to fund:

```sh
cd python-client && .venv/bin/python -m sidepit_trader.wallet new
```

It prints the new address (`sidepit_id`) and the WIF **once**. The user
deposits BTC to that address (their own address — never from keys they don't
control), then forwards it to the exchange (the `users-cli/` TUI's LOCK
button does this in one tap). Trading works once the deposit is credited.

## 4. Place an order

Run from `python-client/` with the env set. side: `1` buy / `-1` sell;
price in sats-per-USD; size in contracts.

```sh
cd python-client
.venv/bin/python - <<'EOF'
from sidepit_trader import signer_from_env, Submitter, RequestClient, pb

req = RequestClient()
ap = req.active_product()
assert ap.exchange_status.status.estate == pb.EXCHANGE_OPEN, "market not open"
ticker = ap.active_contract_product.product.ticker
q = req.quote(ticker).quote
print(f"{ticker} bid={q.bid} ask={q.ask} last={q.last}")

sub = Submitter(signer_from_env(), "api.sidepit.com")
orderid = sub.new_order(side=1, size=1, price=q.bid, ticker=ticker)  # joins the bid
print("orderid:", orderid)
EOF
```

Expected: the quote line, then `orderid: bc1q...:<19-digit nanoseconds>`.
That full string is THE handle — keep it; it identifies the order on every
feed. A successful send means **queued**: the order resolves at the next
1-second auction; there is no synchronous ack.

For an immediate fill use a marketable limit instead:
`sub.market_order(side=1, size=1, ticker=ticker, bid=q.bid, ask=q.ask,
last=q.last)` — returns `(orderid, price)`.

## 5. Check the account (point-in-time)

Wait ~3 seconds (one auction plus margin), then:

```sh
cd python-client
.venv/bin/python - <<'EOF'
import os
from sidepit_trader import RequestClient, signer_from_env

sid = os.environ.get("SIDEPIT_ID") or signer_from_env().sidepit_id
tp = RequestClient().positions(sid)
a = tp.accountstate
print(f"available_margin={a.available_margin} available_balance={a.available_balance}")
for symbol, cm in a.contract_margins.items():
    for ticker, tpos in cm.positions.items():
        print(f"{ticker}: position={tpos.position.position:+d} avg={tpos.position.avg_price:.2f}")
for oid, of in tp.orderfills.items():
    bo = of.order
    print(f"{oid[-22:]} side={bo.side:+d} price={bo.price} "
          f"filled={bo.filled_qty} remaining={bo.remaining_qty}")
EOF
```

Expected: your orderid appears in the order list with `remaining` > 0
(resting) or `filled` > 0 (filled). This reqrep read is point-in-time — the
right tool right after an order. A continuously running bot listens to the
feeds instead (see `sidepit_trader/trader.py`).

If the order is absent AND all numbers are zero: the account is unfunded or
the wrong `SIDEPIT_ID` is set — **STOP and re-check step 3**. Rejections
stream on port 12128 with named codes; `RC_MARGIN` means insufficient margin
(fund the account or reduce size); `RC_ID` in delegate mode means the
delegate is not registered.

## 6. Cancel / go flat

Cancel one order (from step 4's handle):

```python
sub.cancel(orderid)          # queued like everything else; confirm in step 5
```

Cancel everything and close the position — the one-command exit:

```sh
cd python-client && SIDEPIT_ID=... SIDEPIT_WIF=... .venv/bin/python -m sidepit_trader.flatten
```

Expected final line: `flatten OK: positions={} open_orders=0`.
If it prints `INCOMPLETE`, run it once more; report if it persists.

## 7. Withdraw (advanced — account key only)

Withdrawal returns BTC to the account's own `sidepit_id` address; there is no
destination to choose. Requires the ACCOUNT key (a delegate signer raises
`CourierRuleError` — that is the permission model working):

```python
from sidepit_trader import signer_from_env, Submitter, RequestClient
signer = signer_from_env()
sub = Submitter(signer, "api.sidepit.com")
sub.unlock()                                   # everything withdrawable (MAX)
print(RequestClient().unlock_records(signer.sidepit_id))
```

Lifecycle: `UNLOCK_PENDING → UNLOCK_RESERVED → UNLOCK_PROCESSING →
UNLOCK_COMPLETED` (a rejected request shows as `UNLOCK_REJECTED` in the same
records). One open unlock per account at a time. Track
`accountstate.pending_unlock` in step 5's read.

## Facts to keep straight

- Prices are **sats-per-USD**; `USD/BTC = 1e8 / price`. A Sidepit high is the
  USD low.
- Feeds interleave every product — always filter by ticker.
- The ns timestamp is the account's nonce: one trading process per account.
- reqrep = point-in-time; feeds = continuous. Both are yours.
- Never print or log `SIDEPIT_WIF`, a mnemonic, or a private key. Anywhere.
