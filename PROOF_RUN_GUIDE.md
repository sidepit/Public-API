# Sidepit Proof Run – Developer Guide

> **For LLM Context**: This document describes the Sidepit Public API for the Alpha Proof Run. Feed this entire file to your LLM for full context on the codebase, architecture, and how to get started.

---

## Early Alpha – Let's Build It Together

This is an **early alpha version** of the Public-API repository. We're killing multiple birds here:

1. **Prove the exchange works** – Demonstrate that Sidepit is just a better way to trade
2. **Build a clean public API** – For AI agents and trading bots
3. **Onboard our first external developers** – You

By the end of this proof run, we'll have both: measurable proof of better execution quality AND a polished API that any developer can use.

**What's missing:**
- **Historical market data** – There's currently no way to get historical chart data. We need this to compare proof run results. This is actively being built.
- **Polish** – Error messages, documentation, edge cases. You'll find rough edges.

**The deal:** You find the problems, we fix them. PRs welcome. Let's build it together.

---

## What Is This?

Sidepit is a Bitcoin-denominated derivatives exchange with a **Deterministic Limit Order Book (DLOB)**. This repository contains the **public-facing Python API** for traders.

You're participating in the **Alpha Proof Run** – a 6-week live trading program to prove:
1. **Better fills for takers** – eliminate flash crashes and flash pops
2. **Spread-alpha capture for makers** – only possible with Sidepit's batch auction architecture

**Your role:** Build **taker bots** and **maker bots** in Python – take liquidity, provide liquidity, demonstrate better execution quality.

**Sidepit Alpha's role:** Build the **C++ market maker** and **hedge book** – institutional-grade infrastructure with coroutines, order book sync, and real-time replication.

**Sidepit's role:** Fix the backend, add features you need, and provide customized APIs and solutions to get you exactly what you need. You're the early adopters. We'll build what you need to succeed.

---

## Repository Structure

```
Public-API/
├── python-client/          # Low-level client libraries
│   ├── feed_demo.py        # ★ START HERE – Feed as CLI, REST API, or WebSocket
│   ├── req_client.py       # Request/reply client (quotes, positions)
│   ├── tx_client.py        # Transaction client (order submission)
│   └── feed_nng_client.py  # NNG feed subscriber
│
├── users-cli/              # ★ Full trading application reference
│   └── cli/
│       ├── main.py         # Entry point – interactive trading CLI
│       ├── sidepit_cli_handler.py  # Command handling
│       ├── sidepit_manager.py      # Position/ticker management
│       └── sidepit_api_client.py   # Order placement
│
├── Public-API-Data/        # Protocol buffer definitions (submodule)
├── MIGRATION_GUIDE.md      # BetaV2 changes (multi-product, nested positions)
└── education/              # NNG, Protobuf, cryptography primers
```

---

## Two Key Entry Points

### 1. `feed_demo.py` – Data Feeds Three Ways

This file demonstrates how the same NNG feed can be consumed as:
- **CLI** – Interactive command-line
- **REST API** – FastAPI server at `localhost:8000/quote/{ticker}`
- **WebSocket** – Real-time streaming

```bash
cd python-client
python feed_demo.py
# Select mode: 1=CLI, 2=WebSocket, 3=HTTP API
```

**Why this matters:** The core protocol is NNG + Protobuf for low latency. But you can wrap it in whatever interface you prefer. This is the pattern.

### 2. `users-cli/` – Complete Trading Application

A full end-to-end trading CLI that demonstrates:
- Wallet management (create/import private keys, bech32 addresses)
- Balance management (lock/unlock BTC into trading account)
- Order placement and cancellation
- Position monitoring
- Market data display

```bash
cd users-cli
python -m venv .env && source .env/bin/activate
pip install -r requirements.txt
python cli/main.py
```

**Use this as your reference** for how all the pieces fit together.

---

## Architecture

### Protocol Stack

```
┌─────────────────────────────────────────────────────────┐
│  Your Code                                              │
├─────────────────────────────────────────────────────────┤
│  Python Client (this repo)                              │
├─────────────────────────────────────────────────────────┤
│  NNG (Nanomsg Next Gen) – Push, Pull, Req, Rep, Pub, Sub│
├─────────────────────────────────────────────────────────┤
│  Protobuf – Binary serialization                        │
├─────────────────────────────────────────────────────────┤
│  ECDSA/secp256k1 – Transaction signing                  │
└─────────────────────────────────────────────────────────┘
```

### NNG Ports (api.sidepit.com)

| Port  | Socket | Purpose |
|-------|--------|---------|
| 12121 | Push   | Transaction submission |
| 12122 | Sub    | Market data feed (quotes, depth) |
| 12123 | Sub    | Auction echo (real-time order flow) |
| 12124 | Sub    | Order book updates |
| 12125 | Req    | Positions request/reply |
| 12126 | Sub    | Auction clearing results |
| 12127 | Sub    | Bar data feed |
| 12128 | Sub    | Rejection stream |
| 12129 | Req    | Snapshot service (full state) |

### Order Submission Flow

```
1. Build Transaction protobuf (NewOrder with ticker, side, price, qty)
2. Serialize to bytes
3. Sign with ECDSA (your Bitcoin private key)
4. Wrap in SignedTransaction
5. Push to port 12121
```

**Important:** Even if we add REST endpoints, order submission requires protobuf serialization + signing. This is by design – every order is cryptographically signed.

---

## BetaV2 Changes

See `MIGRATION_GUIDE.md` for full details. Key changes:

### Multi-Product Support
- Multiple tickers per session (e.g., `USDBTCH26`, `USDBTCM26`)
- Positions nested by contract: `contract_margins["USDBTC"].positions["USDBTCH26"]`

### API Changes
```python
# Now supports ticker parameter
quote = req_client.get_quote(ticker="USDBTCH26")
product = req_client.get_active_product(ticker="USDBTCM26")

# Positions in nested structure
for symbol, contract_margin in account.contract_margins.items():
    for ticker, pos in contract_margin.positions.items():
        print(f"{ticker}: {pos.position.position} @ {pos.position.avg_price}")
```

### Exchange Status
```python
from sidepit_api_pb2 import ExchangeState

status = product.exchange_status.status.estate  # Returns int (2 = OPEN)
status_name = ExchangeState.Name(status)        # Returns "EXCHANGE_OPEN"
```

---

## What's Happening on the Market Maker Side

While you're building taker bots with Python, we're building the market maker infrastructure in C++. This gives you context on the complexity:

### Gists (Technical Deep Dives)
- [OrderBook Sync](https://gist.github.com/jaybny/2ad5e8c250d0b1842fb3d61a1671106b) – Full-node market makers can sync order book state in seconds
- [Multi-Product Engine](https://gist.github.com/jaybny/715caaa9f1d915b0111846cd05e92cd5) – Unified margin across multiple contract months

### Why This Matters
The market maker side involves:
- **C++20 coroutines** for non-blocking I/O
- **Deterministic sequencing** – epoch-based batch processing
- **Real-time replication** – microsecond-level order flow intelligence
- **Snapshot + delta sync** – join any epoch, rebuild full state

This is institutional-grade infrastructure. The Python API you're using is simpler by design – it's for takers, not market makers. But understanding the full picture helps you see why certain design decisions were made.

---

## Quick Start

### 1. Clone and Setup
```bash
git clone https://github.com/sidepit/Public-API.git
cd Public-API
git checkout betaV2
git submodule update --init
```

### 2. Try the Feed Demo
```bash
cd python-client
python -m venv .venv && source .venv/bin/activate
pip install pynng protobuf fastapi uvicorn websockets
python feed_demo.py
```

### 3. Try the CLI
```bash
cd users-cli
python -m venv .env && source .env/bin/activate
pip install -r requirements.txt
python cli/main.py
```

### 4. Try the Web UI
- URL: https://app.sidepit.com/trading-view
- Code: `sidepit2025`

### 5. REST Endpoints (Already Live)

These are the same pattern as `feed_demo.py` – NNG wrapped in REST, just running server-side:

```bash
# Get current quote
curl https://api.sidepit.com/quote

# Get active product info (ticker, session, exchange status)
curl https://api.sidepit.com/active_product/

# Get positions for an address
curl https://api.sidepit.com/request_position/bc1qa29486m9azmwer9hdf0rdc6yx9c7mdpsl4hn6m
```

**Key insight:** Running `feed_demo.py` locally in HTTP mode gives you the exact same architecture as `api.sidepit.com`. The server-side REST API is just NNG clients wrapped in FastAPI – nothing magic.

---

## What We Need From You

### Build
- **Taker bot** – Take liquidity, demonstrate better fills
- **Maker bot** – Provide liquidity, capture spread
- Start simple: subscribe to quotes, place orders
- Bonus: Help us build the historical data solution

### Report
- What's broken?
- What's confusing?
- What's missing?
- What would make this easier for AI agents?

### Iterate
- This API isn't polished. That's the point.
- We'll fix things as you find them.
- PRs welcome.
- By the end of this run: a clean API for any developer or AI agent to use.

---

## Resources

| Resource | Link |
|----------|------|
| GitHub Repo | https://github.com/sidepit/Public-API |
| Docs | https://docs.sidepit.com/ |
| Web UI | https://app.sidepit.com/trading-view (code: `sidepit2025`) |
| REST: Quote | https://api.sidepit.com/quote |
| REST: Active Product | https://api.sidepit.com/active_product/ |
| REST: Positions | https://api.sidepit.com/request_position/{address} |
| OrderBook Sync Gist | https://gist.github.com/jaybny/2ad5e8c250d0b1842fb3d61a1671106b |
| Multi-Product Gist | https://gist.github.com/jaybny/715caaa9f1d915b0111846cd05e92cd5 |

---

## LLM Context Tips

If you're feeding this to an LLM, also include:
- `MIGRATION_GUIDE.md` – Full BetaV2 migration details
- `python-client/feed_demo.py` – Feed patterns
- `users-cli/cli/main.py` – Full application flow
- `users-cli/cli/sidepit_cli_handler.py` – Command implementation

The protobuf definitions are in `Public-API-Data/sidepit_api.proto`.

---

## Contact

Questions? Issues?

- Jay: jay@sidepit.com
- Telegram: t.me/sidepitceo
- GitHub Issues: https://github.com/sidepit/Public-API/issues

---

## You're the Early Adopters

You're not just using an API – you're shaping the future of trading.

Sidepit is a better way to trade. No flash crashes. No toxic flow. Deterministic execution. And you're the first ones building on it.

We'll fix what's broken. We'll build what you need. We'll get you exactly what it takes to succeed.

**LFG.**

---

*Co-authored with Claude (Opus 4.5)*
