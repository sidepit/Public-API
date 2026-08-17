---
name: sidepit-trade
description: "Trade a funded Sidepit account through an ACTIVE, trading-only delegate: read the live dated forward, preview exposure and published margin allowance, require explicit confirmation, place or cancel an order, reconcile the outcome, resume later, and flatten safely. Use after sidepit-locals has completed onboarding."
---

# Sidepit Trade — the agent enters the pit

You need an ACTIVE delegate key. If you do not have one, run the
`sidepit-locals` skill first.

This is real mainnet Bitcoin and a real exchange. The agent loads only a
protected, trading-only key. It refuses an account key. No live order is sent
until the human sees a specific preview and replies `CONFIRM <preview-id>`.
Order, preview, attempt, and result records survive a fresh shell.

In the first 30 seconds, know the product:

- Sidepit trades dated Bitcoin-margined **forwards**, not perpetuals.
- One-second batch auctions remove speed priority inside the batch: best price
  wins, not the fastest machine.
- Prices are inverse, in satoshis per USD: `USD/BTC = 100,000,000 / price`.
  A satoshi, or sat, is one hundred-millionth of a Bitcoin.
- BUY adds a synthetic USD hedge and reduces BTC-price exposure. SELL removes
  that hedge and increases BTC exposure; a negative position is leveraged long
  BTC.
- The delegate can trade and cancel. It cannot withdraw, authorize, or revoke.

Read the paired [acceptance test](ACCEPTANCE.md) before a first live order.
Paths below assume the Public-API repository root and Python 3.10+.

## 1. Prove the toolchain

```sh
python3 -m venv python-client/.venv
python-client/.venv/bin/pip install -r python-client/requirements.txt
python-client/.venv/bin/python -m pytest python-client/tests -q
```

Expected: all tests pass with zero failures. Warnings are acceptable. If any
test fails, STOP and report the failing test; do not trade.

## 2. Read the live market without a key

```sh
python-client/.venv/bin/python skills/sidepit-trade/scripts/sidepit_agent.py market
```

Expected: named exchange state, active forward and expiry, quote in sats per
USD, familiar USD/BTC price, USD exposure per contract, initial and maintenance
margin, and next open when closed.

If the market is closed, STOP for live execution and rerun this command at the
printed next-open time. If connection fails, the command identifies permission,
DNS, refusal, or timeout. An agent sandbox may need permission for
`api.sidepit.com:12125`.

The command also states a current public-product limitation: the API does not
publish a pre-trade fee schedule. Before any live preview, the human must obtain
the exact expected fee from current Sidepit terms or the beta operator. Do not
guess it and do not turn a past fee into a current claim.

## 3. Prove the saved key is an ACTIVE delegate

Use the absolute file path produced by `sidepit-locals`. Do not source it, read
it, copy its contents, or place a secret in the command line:

```sh
python-client/.venv/bin/python skills/sidepit-trade/scripts/sidepit_agent.py \
  delegate-status --key-file /absolute/path/to/agent.env
```

Expected: account, agent ID, `delegate ACTIVE`, and the protected path with
`secret not displayed`. The command rejects a direct account key, a symlink,
wrong ownership, or any mode other than `0600`.

If the result is PENDING, wait and rerun the same command. If rejected or
missing, return to **Authorize trading agent** in the web app. Never submit an
order until ACTIVE appears in the server's live set.

Run one writer per account. A transaction's nanosecond timestamp is the account
nonce; two concurrent trading processes can collide.

## 4. Resume or inspect from a fresh shell

This is also the “come back tomorrow” command:

```sh
python-client/.venv/bin/python skills/sidepit-trade/scripts/sidepit_agent.py \
  status --key-file /absolute/path/to/agent.env
```

It prints the current forward, delegate state, deposits, available and used
margin, restriction state, positions, complete resting-order snapshot, and
recent public order handles. It never prints the secret.

STOP before adding risk if the account is restricted, available margin is not
enough for the intended order, funding is still pending, an existing order is
unexplained, or the delegate is not ACTIVE.

## 5. Ask for the order—never choose it silently

Before constructing a preview, get four choices from the human:

1. BUY or SELL, using the exposure meanings at the top of this skill.
2. Positive integer contract count. The live market command states the USD
   amount per contract.
3. Positive integer limit price in sats per USD. A buy at or above the ask, or
   sell at or below the bid, is marketable but still waits for the next auction.
4. Exact expected trading fee in sats and its current source. If unavailable,
   STOP; the public API cannot supply it yet.

Do not hardcode a side, size, price, ticker, or fee. Do not interpret “do
something” as permission to choose financial exposure.

## 6. Write the exact preview—nothing is sent

Replace every placeholder with the human's choices and the protected file path:

```sh
python-client/.venv/bin/python skills/sidepit-trade/scripts/sidepit_agent.py \
  preview-order \
  --key-file /absolute/path/to/agent.env \
  --side HUMAN_CHOICE_LOWERCASE \
  --contracts INTEGER \
  --limit-price SATS_PER_USD \
  --fee-sats INTEGER \
  --fee-source "CURRENT_SOURCE_AND_DATE"
```

`HUMAN_CHOICE_LOWERCASE` must be exactly `buy` or `sell`; it is never chosen by
the agent. All other capitalized words are placeholders, not literal values.

The preview contains:

- active dated forward and exact limit in sats per USD plus USD/BTC;
- contract count, USD notional, and BTC-equivalent notional at the limit;
- plain-language BUY/SELL exposure and projected position;
- current margin used, additional initial-margin allowance, and available margin;
- numeric fee with its human-supplied current source;
- RESTING or MARKETABLE expectation and the one-second auction caveat;
- a public preview file and unique preview ID.

Return the entire preview to the human. Wait. Only the exact reply
`CONFIRM <preview-id>` authorizes that preview. “Yes,” an old confirmation, or a
changed side/size/price/fee does not. To change anything, create a new preview.

## 7. Send only the confirmed preview

After the exact confirmation, use the printed preview file and confirmation:

```sh
python-client/.venv/bin/python skills/sidepit-trade/scripts/sidepit_agent.py \
  send-order \
  --key-file /absolute/path/to/agent.env \
  --preview-file /absolute/path/to/order-preview-ID.json \
  --confirm "CONFIRM PREVIEW_ID"
```

The command rechecks ACTIVE state, market open, active forward, position,
available margin, preview expiry, and rest-or-cross expectation. It writes the
public order handle to an attempt record **before** the network send, subscribes
to rejections before sending, then reports one of:

- `RESTING` — visible with remaining quantity;
- `FILLED` — filled quantity and average price;
- `REJECTED — RC_NAME` — use the recovery map below;
- `UNKNOWN` — do not retry; run status using the persisted order handle.

`QUEUED` means the bytes were sent to the one-second auction. It is not a fill.

## 8. Cancel from a fresh shell

First show the human the full public order ID and ask for the exact phrase
`CANCEL <order-id>`. After that confirmation:

```sh
python-client/.venv/bin/python skills/sidepit-trade/scripts/sidepit_agent.py \
  cancel \
  --key-file /absolute/path/to/agent.env \
  --order-id 'bc1qACCOUNT:TIMESTAMP' \
  --confirm 'CANCEL bc1qACCOUNT:TIMESTAMP'
```

The cancel is also queued. `RC_CDUP` or `RC_CREJ` normally means the order was
already filled or gone. Run status to learn the resulting position before any
replacement order.

## 9. Preview and flatten all exposure

Flatten cancels every resting order first, then closes remaining positions with
marketable limits. Obtain the exact expected total trading fee, then preview:

```sh
python-client/.venv/bin/python skills/sidepit-trade/scripts/sidepit_agent.py \
  preview-flatten \
  --key-file /absolute/path/to/agent.env \
  --fee-sats INTEGER \
  --fee-source "CURRENT_SOURCE_AND_DATE"
```

Show the complete cancel/close preview and wait for `CONFIRM <preview-id>`.
Then:

```sh
python-client/.venv/bin/python skills/sidepit-trade/scripts/sidepit_agent.py \
  send-flatten \
  --key-file /absolute/path/to/agent.env \
  --preview-file /absolute/path/to/flatten-preview-ID.json \
  --confirm "CONFIRM PREVIEW_ID"
```

If orders, positions, or crossing conditions changed, it stops rather than
improvising. Cancels may already be queued; run status and make a fresh preview.
`INCOMPLETE` also means run status and preview the residual—never blindly retry.

## Recovery map

- **Closed:** run `sidepit_agent.py market`; use its next-open time.
- **Funding pending or zero:** run `sidepit_agent.py public-account --account
  bc1qACCOUNT`; wait for credited funds or inspect the public Bitcoin TXID.
- **Delegate pending:** rerun `delegate-status`; submitted is not ACTIVE.
- **`RC_MARGIN`:** run status; reduce size or add deliberate funding.
- **`RC_ID`:** the account or delegate is unknown; rerun `delegate-status`.
- **`RC_DK`:** the forward is no longer active; rerun market and re-preview.
- **`RC_VERIFY`, `RC_BAD`, `RC_DUP`:** STOP; preserve the attempt record and
  report the named code plus public order ID.
- **Order absent/UNKNOWN:** run status. Never create a second order for the same
  intent until the first public handle is resolved.
- **Network failure after send:** treat the outcome as unknown. The attempt
  record is the recovery anchor; never infer failure and resend.

## Operating reference

- **Fees:** realized fees are published after trading, but the current public
  API has no pre-trade schedule. The preview requires a numeric fee and current
  human-verified source. This is a product gap, not permission to estimate.
- **Margin:** the active contract publishes initial and maintenance margin per
  contract. The server publishes current used/available margin and is the final
  order check. Restricted accounts reduce risk only. Open P&L and margin move
  with the market; start small. The current public API does not publish the
  complete margin-stress or forced-reduction policy, so obtain current beta
  terms before adding risk.
- **Deposits:** LOCK forwards the connected address's whole confirmed balance,
  minus the Bitcoin network fee. Credit follows chain confirmation; `pending`
  is not available margin. No fixed confirmation count or time is promised.
- **Daily settlement:** open P&L settles into the BTC balance and average entry
  resets. `available_balance` is the last settled figure;
  `available_margin` is what can be used now.
- **Expiry/roll:** these are dated forwards. Always use the currently active
  ticker and printed expiry; never reuse yesterday's ticker. Flatten or obtain
  an explicit roll instruction before expiry.
- **Trade history:** status shows recent orders; the durable files in
  `~/.sidepit/agent-trade/` preserve previews, attempts, results, and handles.
- **Unlock/revoke:** the agent cannot perform either action. The human uses the
  web app. Unlock requests return only to the same account address and the UI
  tracks received, reserved, processing, completed, or rejected. No completion
  time is promised; never resubmit while pending.
- **Support:** provide only public account, agent, order, receipt, and Bitcoin
  transaction IDs to the Sidepit beta operator. Never provide a key, seed
  words, or key-file contents.

## Protocol facts for client builders

- Feeds mix products; filter every message by ticker.
- Drain order data through `more_in_epoch == 0` before acting on the book.
- Request/reply is point-in-time; feeds are continuous. Reconnect and snapshot
  before trusting remembered open orders.
- A Sidepit price high is a familiar USD/BTC low because the quote is inverse.
- Keep one writer per account and never reuse a timestamp nonce.
