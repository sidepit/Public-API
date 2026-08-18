---
name: sidepit-trade
description: "Trade a funded Sidepit account through an ACTIVE, trading-only delegate: read the live dated forward, preview limit or native IOC market exposure and published margin allowance, require explicit confirmation, place or cancel, reconcile, resume, and flatten safely. Use after sidepit-locals onboarding."
---

# Sidepit Trade — the agent enters the pit

You need an ACTIVE delegate key. If you do not have one, run the
`sidepit-locals` skill first.

You are now in the trading room. Use this mental model: **same kind of key,
different job**. The account key is the human's money key; this delegate key is
the agent's replaceable trading pass. The public handoff is complete—agent
public key out, ACTIVE result back—and the server now limits this key to
trading and canceling.

This is real mainnet Bitcoin and a real exchange. The agent loads only a
protected, trading-only key. It refuses an account key. No live order is sent
until the human sees a specific preview and replies `CONFIRM <preview-id>`.
Order, preview, attempt, and result records survive a fresh shell.

Losing or destroying this trading pass does not lose the human's Bitcoin; the
human can revoke its public ID and authorize a replacement. Existing orders and
positions remain. If another copy survives, it can trade until revoked.

In the first 30 seconds, know the product:

- Sidepit trades dated Bitcoin-margined **forwards**, not perpetuals.
- DLOB runs one-second deterministic auctions: best price wins, not the fastest
  machine.
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

The command also states the execution-fee schedule. There is one kind of fee:
an execution fee on fills — `execution_fee_sats_per_contract_per_side = 125`.
Open 1 contract: 125 sats; close it: another 125; round turn per trader:
250 sats (about $0.25 at $100,000/BTC — the exchange collects 250 per matched
contract because both counterparties pay 125). The engine deducts it from
available balance at each fill and reports it in `realized_fees`.

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

### Give the customer their price and risk view

The wire publishes the facts; the agent presents them in the customer's chosen
units. Read `ACTIVE_PRODUCT`, `QUOTE`, and `POSITIONS` together. For every open
ticker, keep the dated position separate and show its signed quantity, average
price, last liquid price, marked P&L, margin, and expiry.

Translate a Sidepit price `P` as follows:

- native forward: `P` satoshis per future USD;
- familiar forward: `forward USD/BTC = 100,000,000 / P`;
- today's dollars: `present-value USD/BTC = forward USD/BTC * discount_factor(now, expiry)`;
- another currency: multiply the requested dollar view by the current FX rate.

For today's dollars, retrieve a current maturity-matched U.S. dollar risk-free
zero rate. State the source, observation time, tenor, day-count convention, and
any interpolation. With a continuously compounded annual rate `r` and year
fraction `T`, `discount_factor = exp(-r * T)`. If the customer asks for spot,
retrieve spot separately and label it spot; a discounted forward is a
present-value view, not the spot market.

Current equity is calculated from the account response and the last liquid
price for each open ticker:

`mark_pnl = sum(qty * ((last - avg_price) / tic_min) * tic_value)`

- while `EXCHANGE_OPEN`: `equity = available_balance + realized_pnl + mark_pnl`;
- while closed: `equity = available_balance` because settlement has already
  folded P&L into the balance. Do not add `realized_pnl` again.

The customer view keeps the components visible:

- **Market open:** show the opening/settled balance, session realized P&L,
  unrealized P&L at the latest liquid mark, and marked equity. Unrealized P&L
  is the amount that would join the session result if that mark became the
  close.
- **Market closed:** show the closing balance and the full session P&L beside
  it. The close has moved the position average to the settlement mark, so
  unrealized P&L is zero. The wire's `available_balance` already contains the
  closing P&L; the still-visible realized figure explains the move and must not
  be added to that balance a second time.

Here `realized_pnl` is the sum of `ContractMargin.margin.realized_pnl` across
the account. If a position has no nonzero last liquid price, label its current
mark and account equity unavailable instead of substituting a remembered price.

Alongside equity, report the server's `available_margin`, `is_restricted`,
`trader_margin_state.risk_position` (signed net contracts), and
`trader_margin_state.net_oi` (gross open contracts). Do not collapse the
per-ticker positions into the aggregate when expiries differ.

For a roll, read `SCHEDULES`, then query each published ticker. Show the current
and next dated contracts, expiries, prices, basis, quantities, and execution
fees as separate legs. A roll is never an invisible ticker substitution or an
automatic order.

Use a compact default view: native Sidepit price, forward USD/BTC, today's
USD/BTC, equity, available margin, and positions by expiry. Add spot, JPY, or
another user-defined lens on request.

STOP before adding risk if the account is restricted, available margin is not
enough for the intended order, funding is still pending, an existing order is
unexplained, or the delegate is not ACTIVE.

### Keep the margin conversation interactive

Before opening or increasing a position, ask whether the human intends it to be
**INTRADAY** or **OVERNIGHT**. Never choose that horizon silently. If intraday,
agree on the exit instruction rather than assuming the agent may flatten. If
overnight, tell the human to size from the current overnight terms, not merely
from the intraday allowance.

State the known Sidepit behavior plainly:

- Sidepit does not force an exit while the exchange is open.
- A margin rejection blocks that add-risk order; it does not liquidate an
  existing position. A restricted account may reduce risk only, so the trader
  can reduce or exit the position.
- To add margin, the human sends BTC to their own Sidepit ID first and then
  uses LOCK. Pending Bitcoin is not available margin.
- The public API does not define the cure deadline, what happens after it, or
  whether losses are capped at locked collateral. Obtain those current beta
  terms before choosing overnight exposure; do not fill the gap with behavior
  from another venue.

This is a conversation, not an argument. If the human supplies first-hand beta
behavior that is not in the public API, restate it as beta experience, keep any
remaining unknown explicit, and ask only the focused question needed for the
next decision. Never infer Sidepit liquidation, credit, or clearing behavior
from a generic exchange analogy.

## 5. Ask for the order—never choose it silently

Before constructing a preview, get these choices from the human:

1. BUY or SELL, using the exposure meanings at the top of this skill.
2. Positive integer contract count. The live market command states the USD
   amount per contract.
3. LIMIT or MARKET:
   - LIMIT requires a positive integer price in sats per USD. It never executes
     worse than that price and may rest.
   - MARKET has no price and no price protection. It is native IOC: in the next
     DLOB deterministic auction it fills available opposite liquidity and
     cancels every unfilled remainder. It never rests.
4. For LIMIT only, the exact limit price.
5. INTRADAY or OVERNIGHT intent; this does not authorize an automatic exit.
6. Nothing for the fee — the preview fills it from the published schedule
   (125 sats per contract per side) automatically. Only pass `--fee-sats` plus
   `--fee-source` if the human explicitly supplies a different, sourced figure.

Do not hardcode an order type, side, size, price, or ticker. Do not
interpret “do something” as permission to choose financial exposure. The
execution fee is the one value the schedule supplies for you.

## 6. Write the exact preview—nothing is sent

For a limit order, replace every placeholder with the human's choices and the
protected file path:

```sh
python-client/.venv/bin/python skills/sidepit-trade/scripts/sidepit_agent.py \
  preview-order \
  --key-file /absolute/path/to/agent.env \
  --side HUMAN_CHOICE_LOWERCASE \
  --contracts INTEGER \
  --limit-price SATS_PER_USD
```

For a native IOC market order, use `--market` and omit `--limit-price`:

```sh
python-client/.venv/bin/python skills/sidepit-trade/scripts/sidepit_agent.py \
  preview-order \
  --key-file /absolute/path/to/agent.env \
  --side HUMAN_CHOICE_LOWERCASE \
  --contracts INTEGER \
  --market
```

`HUMAN_CHOICE_LOWERCASE` must be exactly `buy` or `sell`; it is never chosen by
the agent. All other capitalized words are placeholders, not literal values.

The preview contains:

- active dated forward and either the exact limit plus USD/BTC or an explicit
  `IOC MARKET — no limit price` warning with the current reference quote;
- contract count, USD notional, and BTC-equivalent notional at the limit or
  clearly labeled current reference price;
- plain-language BUY/SELL exposure and projected position;
- for MARKET, projected position is the maximum if the IOC fills completely;
- current margin used, additional initial-margin allowance, and available margin;
- the execution fee in sats with its USD equivalent at the reference price —
  filled from the published schedule (125 sats per contract per side) unless
  the human supplied a sourced override;
- RESTING/MARKETABLE LIMIT or IOC MARKET expectation and the DLOB auction caveat;
- a public preview file and unique preview ID.

Return the entire preview to the human. Wait. Only the exact reply
`CONFIRM <preview-id>` authorizes that preview. “Yes,” an old confirmation, or a
changed order type/side/size/price/fee does not. To change anything, create a
new preview.

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
available margin, preview expiry, order type, and execution expectation. It
writes the public order handle to an attempt record **before** the network send,
subscribes to rejections before sending, then reports one of:

- `RESTING LIMIT` — visible with remaining quantity;
- `FILLED` — filled quantity and average price;
- `PARTIAL FILL` — market quantity filled and IOC remainder canceled;
- `CANCELED` — an IOC market order found no available opposite liquidity;
- `REJECTED — RC_NAME` — use the recovery map below;
- `UNKNOWN` — do not retry; run status using the persisted order handle.

`QUEUED` means the bytes were sent to the next DLOB deterministic auction. It
is not a fill.

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
native IOC market orders. The preview computes the execution fee from the
published schedule (125 sats per contract per side on the closes):

```sh
python-client/.venv/bin/python skills/sidepit-trade/scripts/sidepit_agent.py \
  preview-flatten \
  --key-file /absolute/path/to/agent.env
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

If orders or positions changed, it stops rather than improvising. Cancels may
already be queued; run status and make a fresh preview. `INCOMPLETE` means an IOC
close could not fill the whole position: run status and preview the residual—
never blindly retry.

## Recovery map

- **Closed:** run `sidepit_agent.py market`; use its next-open time.
- **Funding pending or zero:** run `sidepit_agent.py public-account --account
  bc1qACCOUNT`; wait for credited funds or inspect the public Bitcoin TXID.
- **Delegate pending:** rerun `delegate-status`; submitted is not ACTIVE.
- **`RC_MARGIN`:** the add-risk order was rejected; no existing position was
  forcibly exited. Run status, reduce the order size, reduce risk, or have the
  human add BTC to their Sidepit ID and LOCK it. Pending funding is not margin.
- **`RC_ID`:** the account or delegate is unknown; rerun `delegate-status`.
- **`RC_DK`:** the forward is no longer active; rerun market and re-preview.
- **`RC_VERIFY`, `RC_BAD`, `RC_DUP`:** STOP; preserve the attempt record and
  report the named code plus public order ID.
- **Order absent/UNKNOWN:** run status. Never create a second order for the same
  intent until the first public handle is resolved.
- **Network failure after send:** treat the outcome as unknown. The attempt
  record is the recovery anchor; never infer failure and resend.

## Operating reference

- **Fees:** one kind only — an execution fee on fills.
  `execution_fee_sats_per_contract_per_side = 125`. Per trader: open 1
  contract = 125 sats, close = 125 sats, round turn = 250 sats (~$0.25 at
  $100,000/BTC). The exchange collects 250 sats per matched contract because
  both counterparties pay 125. Previews fill this automatically. The engine
  deducts it at each fill and reports it in `realized_fees`.
- **Market orders:** native IOC orders carry wire `price=0`. They have no price
  protection, fill available opposite liquidity in one DLOB auction, and cancel
  every unfilled remainder atomically. They never rest.
- **Margin:** the active contract publishes initial and maintenance margin per
  contract. The server publishes current used/available margin and is the final
  order check. Sidepit does not force an exit while the exchange is open.
  Restricted accounts reduce risk only. Open P&L and margin move with the
  market; start small. Before overnight exposure, obtain the current overnight
  requirement, cure deadline, post-deadline handling, and loss boundary from
  the web experience or beta operator; the public API does not define them.
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
- DLOB means one-second deterministic auctions; use that exact term in customer
  copy.
- A Sidepit price high is a familiar USD/BTC low because the quote is inverse.
- Keep one writer per account and never reuse a timestamp nonce.
