# Sidepit — agent guide

**The contract lives in [`Public-API-Data`](Public-API-Data/)** — its README has
the basic facts and every port; `sidepit_api.proto` is every message, exactly as
production speaks it. This file adds the working recipes and trading facts.

Sidepit is a Bitcoin-margined forwards exchange — you are using Bitcoin to
trade USD. Orders match in one-second deterministic auctions (DLOB): the best
price wins, every second. Live market data is open to everyone — no
credentials, no signup.

## The whole exchange in four reads and one write

- **ACTIVE_PRODUCT** — status of the exchange and the live contract.
- **SCHEDULES** — opening and closing times.
- **POSITIONS** (`TraderPositionOrders`) — everything about an account in one
  message: open orders, positions, margins, locks, unlocks, delegates.
- **Subscribe the feeds** — 12122 streams market data; 12124 streams your
  order events and fills.
- All that's left is **signing and sending orders to 12121**.

That's the full surface. Sidepit is best execution for taking Bitcoin risk —
an execution layer that connects easily to your own signals and systems.
End to end, ProofNet is live.

## Read the market in one line

Install two standard tools (`apt-get install nng-utils protobuf-compiler` or
`brew install nng protobuf`) and run from `Public-API-Data/`:

    echo 'TypeMask: 4 ticker: "USDBTCU26"' \
    | protoc sidepit_api.proto --proto_path . --encode=RequestReply \
    | nngcat --req --dial tcp://api.sidepit.com:12125 --file - --raw \
    | protoc sidepit_api.proto --proto_path . --decode=ReplyRequest

Add `--raw` so the reply flows to your decoder. One request type per call —
named by the proto's `ReplyRequestTypes`; the field takes the number:

| Request | TypeMask | Notes |
|---|---|---|
| ACTIVE_PRODUCT | 1 | product & contract spec — start here |
| POSITIONS | 2 | add `traderid: "bc1q..."` |
| QUOTE | 4 | live quote & ten levels of depth (add ticker) |
| HISTORICAL_BARS | 16 | add ticker; empty session_id = today; walk history via prev_session_id |
| SCHEDULES | 32 | the trading calendar |

Feeds carry every product — filter by ticker and you're set.

## Trading facts

- Contract terms (tick value, margin per contract, price limits, hours) come
  live from ACTIVE_PRODUCT — one read and you know the market you're in.
  Prices are sats per USD.
- Your orderid is `sidepit_id:timestamp` — you mint the timestamp, the
  exchange echoes it back, and it's your handle for cancel and status. Mint a
  fresh one for every order (unique per account).
- A limit order names its price. **A market order simply omits the price** —
  it executes against available liquidity right away.
- **Buying the contract is buying USD exposure — to go long Bitcoin, sell.**
- Opening a contract takes the initial margin free at that moment; holding
  intraday takes maintenance per contract; **positions opened today are checked
  against initial margin again at the close** — cover it, or go flat before the
  close (one `flatten`). The margin page on the docs has the full model.
- Positions and P&L: ask the API (POSITIONS). The exchange keeps your books
  for you, updated every second — and **Sidepit decides when your deposit is
  tradeable, not the Bitcoin chain**: it shows in `net_locked` when Sidepit
  sees it; trade when `available_margin` credits. No mempool-watching needed.
- SCHEDULES is the authority on sessions. Quiet feeds while the exchange is
  closed just means the market is resting — one 12125 read at the open seeds
  your state, then the feeds keep you current.

## Delegated keys — your agent's own trading key

An account owner can give an agent its own key that trades the account while
the owner's Bitcoin stays under the owner's control — enforced by the
protocol itself, and the owner can swap it any time. To get one: hand the
owner your public key, they authorize it in the web app or TUI, and you're
live — sign with `sidepit_id` = their account, `agent_id` = your address (the
SDK's env handoff does this automatically). Trading directly with a key you
own works just as well.

## The CLI

`skills/sidepit-trade/scripts/sidepit_agent.py` — one tool, every verb:
`market` (keyless), `public-account --account bc1q...` (keyless),
`delegate-status` / `status` (with a key), `preview-order` → `send-order`,
`cancel`, `preview-flatten` → `send-flatten`. Each subcommand has `--help`.
Key files are env-shaped: your key + the account you trade.

## Recipes

- **Get flat**: cancel resting orders, close the position at market — the
  trade skill's `flatten` does both in one command.
- **Contract roll**: dated forwards have an expiry — SCHEDULES shows it, and
  the next contract is always listed alongside.

The SDK (`python-client/`), the trade skill (`skills/sidepit-trade`), and the
charts skill (`skills/sidepit-charts`) cover the workflows. **Official docs:** <https://docs.sidepit.com> This file plus the contract is everything an agent
needs to start.
