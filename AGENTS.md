# AGENTS.md — Sidepit, for AI agents

The first file an agent should read. The customer journey is deliberately split:
`skills/sidepit-locals/SKILL.md` helps the human create/fund the account and
authorize a restricted agent; `skills/sidepit-trade/SKILL.md` trades only after
that agent is ACTIVE. The full wire reference is
`Public-API-Data/sidepit_api.proto`.

**Customer safety boundary:** never ask for, display, source, or accept the
human's account key or seed words. The human signs account actions inside
UniSat. An agent uses only its own 0600 trading-only key file, which the
protocol prevents from withdrawing, authorizing, or revoking.

**Funding boundary:** never tell a customer to send BTC from an external wallet
or exchange directly to the exchange deposit/lock address. BTC goes to the
customer’s connected `bc1q` Sidepit ID first; only then does the human use LOCK
to forward that balance. Any instruction that skips the Sidepit-ID step is
stale and unsafe.

This is an identity requirement, not only a wallet-UI preference. The exchange
identifies and credits the account from the LOCK transaction input: it must
spend from the customer's Sidepit ID, whose public key is recovered from the
witness. A direct external-wallet-to-lock-address payment does not identify the
intended Sidepit account.

## What is Sidepit?

A Bitcoin-margined **forwards** exchange (dated contracts, e.g. `USDBTCU26` —
not perpetuals) running a deterministic limit order book. The exchange runs in
1-second **epochs**: each epoch's transactions are batched, ordered by a
sequencing auction, then matched by a standard CLOB at limit prices. Within an
epoch there is no time priority — best price wins, not the fastest machine.
Settlement is daily mark-to-market in satoshis; margin is shared across the
account.

**Prices are inverse: sats-per-USD.** `USD/BTC = 1e8 / price`. A rising
Sidepit price means a falling USD price of Bitcoin; a Sidepit bar `high` is
the USD `low`. P&L is in sats.

## The protocol

**NNG sockets + protobuf messages + secp256k1 ECDSA signing**, at
`api.sidepit.com`. The ports are public by design — you talk to the exchange
directly. Python deps: `pynng`, `protobuf==3.20.1`, `secp256k1`, `base58`
(`pip install -r python-client/requirements.txt`).

- Canonical proto: `Public-API-Data/sidepit_api.proto`
- Generated stub: `python-client/proto/sidepit_api_pb2.py` (the SDK re-exports it as `pb`)
- Port constants: `python-client/sidepit_trader/wire.py` (`Ports`)

You can drive the wire raw (pynng + the stub), or use the in-repo SDK
(`python-client/sidepit_trader/`) which wraps it. Both are shown below.

## Port map

| Port  | Socket | What flows |
|-------|--------|------------|
| 12121 | Push (you push) | order intake: signed `SignedTransaction` |
| 12122 | Sub | price feed: `MarketData` (quote + in-progress bar + depth), 1 msg **per product** per epoch |
| 12124 | Sub | order feed: `OrderData` — post-match book, fills, margin states; **multiple msgs per epoch**, read until `more_in_epoch == 0` |
| 12125 | Req/Rep | the read/metadata door: `RequestReply` → `ReplyRequest` — active product, quote, positions, bars, schedules, snapshot trigger, account verbs |
| 12127 | Sub | bar feed: closed 1-minute `EpochBar` per product |
| 12128 | Sub | rejection stream: `RejectedTransaction` |
| 12129 | Sub | snapshot stream: full open-order state, triggered by `SNAPSHOT` on 12125 |
| 12123 | Sub | epoch echo clock (`TxBlockStream`) — advanced |
| 12126 | Sub | auction stream (`EpochOrders`) — advanced |

Feeds publish while the exchange is OPEN; they are quiet while it is closed —
that is the schedule, not an error.

## The first call

Every client starts with `ACTIVE_PRODUCT` on 12125. One round-trip answers:
is the exchange up, which trading session, which contract is trading.

```python
# from python-client/ (or sys.path.insert the directory)
from sidepit_trader import RequestClient, pb
req = RequestClient()                      # api.sidepit.com
ap = req.active_product()
print(pb.ExchangeState.Name(ap.exchange_status.status.estate))   # names, not ints
print(ap.active_contract_product.product.ticker)                 # don't hardcode tickers
```

Runnable: `python examples/quickstart.py` from the repo root — no keys needed.

## Identity and signing

- An identity is a secp256k1 private key. `sidepit_id` = the P2WPKH bech32
  address (`bc1q…`) derived from the compressed pubkey. That address is the
  account. In the customer path, the account key stays inside UniSat.
- An agent mints only a distinct restricted identity with
  `python -m sidepit_trader.agent_key new --account bc1q…`. It writes one new
  0600 file, prints only public facts, and never overwrites an existing key.
- **Signing, exactly** (`sidepit_trader/signer.py`):
  1. stamp `tx.sidepit_id` (and `tx.agent_id` in delegate mode),
  2. `digest = SHA256(tx.SerializeToString())`,
  3. ECDSA-sign, serialize **compact** (64 bytes), **hex-encode**,
  4. wrap: `SignedTransaction{signature_version=0, transaction, signature}`.
- `Transaction.timestamp` is nanoseconds and doubles as a per-account nonce:
  mint strictly-increasing values and never reuse one (the SDK's
  `submit.next_ns()` does this). Run one writer per account.
- **The orderid**: `f"{sidepit_id}:{timestamp_ns}"` — client-minted, known
  before the exchange sees the order, and the correlation key on every feed
  (`BookOrder.orderid`, `FillData.agressiveid/passiveid`, rejects). The SDK's
  order verbs return this full string.

**Delegation is mandatory for customer-facing agents.** The human pastes the
agent's 33-byte public key into **Authorize trading agent** in the web app and
signs in UniSat. The agent waits until `accountstate.active_delegates` contains
its derived address. On the wire, delegate signing stamps `sidepit_id` = whose
margin and `agent_id` = who signed. A delegate can trade but cannot withdraw,
authorize, or revoke; the SDK raises `CourierRuleError` before such a send and
the server enforces the same boundary.

## Submit an order

Do not place a customer order from a literal code sample. Use the bundled
delegate-only gate in `skills/sidepit-trade/scripts/sidepit_agent.py`:

1. `preview-order` derives the active ticker and shows exact side/exposure,
   limit in both price conventions, projected position, margin, numeric fee,
   and whether the order currently rests or crosses.
2. The human replies `CONFIRM <preview-id>`.
3. `send-order` revalidates the preview, writes the public handle durably, then
   signs and submits with the ACTIVE delegate file.

Low-level SDK verbs remain `Submitter.new_order`, `cancel`, `cancel_replace`,
and `market_order`. There is no native market type: `market_order` places a
marketable limit crossed through the touch. Client builders must add the same
preview and explicit-confirmation boundary before exposing them to users.

A successful send means **queued**: the order resolves at the next 1-second
auction. Outcomes arrive on the feeds — fills and book updates on 12124,
rejections on 12128. The `Submitter` keeps its push connection fresh across
idle periods automatically; if you push raw NNG yourself, reopen an idle push
socket before sending.

## Read your account

- **Point-in-time (the quick check, e.g. right after an order):** `POSITIONS`
  on 12125 → `TraderPositionOrders`: `accountstate` (an `AccountMarginState`
  — balances, margin, positions per contract), `orderfills` (your recent
  orders with fills), `trader_margin_state` (available_margin,
  risk_position), and `accountops` (delegate + unlock records).
  SDK: `RequestClient.positions(sidepit_id)`.
- **Continuous (bots on the feeds):** position and margin levels stream in
  `OrderData.margin_states` on 12124; your fills are events on the same feed.
  Take position levels from the server's own numbers rather than recomputing
  them.
- **Complete resting-order list** (cancel-all, reconnect): the snapshot
  protocol — subscribe 12129, request `SNAPSHOT` on 12125, drain to the end
  sentinel. SDK: `sidepit_trader.sync.snapshot_sync(host, sidepit_id)`.
  Sentinels ride `OrderData.version` (−1 start, −2 end) and can carry orders —
  process them.

Balances: `available_balance` is yesterday's settled figure (static intraday);
`available_margin` is what is spendable/withdrawable now. Open P&L is computed
client-side from positions + `avg_price` + the current mark; at daily
settlement it folds into the balance and `avg_price` resets.

## Withdraw (human web action)

An agent never performs this action. The human chooses **Sidepit Account →
Unlock funds** in the web app, enters integer sats or MAX, confirms the same
account ID, and signs inside UniSat. Funds return **only** to `sidepit_id`;
there is no destination field. The UI tracks received, reserved, processing,
completed, or rejected and shows the Bitcoin transaction ID when available.
On the public wire, the corresponding records are
`accountstate.pending_unlock` and `RequestClient.unlock_records(sidepit_id)`.

## Rejects (12128)

Surface the code **name**, never the bare int:
`pb.RejectCode.Name(rej.reject_code)`. `RC_CDUP`/`RC_CREJ` on cancels are
normal traffic (the order was already filled or gone). The ones that mean
something: `RC_VERIFY` (bad signature bytes), `RC_DUP` (reused timestamp),
`RC_ID` (unknown account / delegate not registered), `RC_BAD` (malformed),
`RC_MARGIN` (insufficient margin — the server is the final margin check;
re-preview with less risk or fund deliberately), `RC_DK` (unknown ticker —
query `ACTIVE_PRODUCT`).
SDK: `RejectionFeed.code_name(rej)` / `is_error(rej)`.

## Exchange states

`pb.ExchangeState.Name(...)`: daily cycle `EXCHANGE_CLOSED → PENDING_OPEN →
OPEN → CLOSING → SETTLED → CLOSED`. Submit while `EXCHANGE_OPEN`. Session
schedule comes from `ACTIVE_PRODUCT` / `SCHEDULES`.

## Facts that shape correct clients

1. **Filter every feed by `ticker`** — the exchange is multi-product; feeds
   interleave one message per product.
2. **Drain 12124 until `more_in_epoch == 0`** (or `recv(block=False)` until
   empty) before acting on the book — one epoch can carry several messages.
3. **Prices are sats-per-USD.** Convert once at the edge; a Sidepit `high` is
   the USD `low`.
4. **reqrep is point-in-time; streams are continuous.** Check your account on
   12125 whenever you want; a running bot listens to the feeds and uses the
   streamed margin state.
5. **One writer per account** — the ns timestamp is the account's nonce.
6. **Quiet feeds while closed are the schedule**, and `session_id` keys by
   `schedule.date`.

## The lifecycle in commands

```sh
python-client/.venv/bin/python examples/quickstart.py
# Need an account or ACTIVE delegate? Follow skills/sidepit-locals/SKILL.md.
python-client/.venv/bin/python skills/sidepit-trade/scripts/sidepit_agent.py market
python-client/.venv/bin/python skills/sidepit-trade/scripts/sidepit_agent.py \
  status --key-file /absolute/path/to/agent.env
# Preview/confirm/send and preview/confirm/flatten: follow sidepit-trade/SKILL.md.
# Unlock/revoke stay in the human web app.
```

Tests (no network): `python-client/.venv/bin/python -m pytest python-client/tests -q`.

## Do not touch

- `Public-API-Data/` — the contract submodule. Read, never edit.
- Never print, log, or transmit a private key, WIF, or mnemonic. Key files
  are write-once; there is no delete.
