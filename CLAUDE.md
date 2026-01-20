# CLAUDE.md

Context for Claude Code sessions working on this repository.

---

## What Is This Repo?

**Public-API** is the public-facing Python API for Sidepit – a Bitcoin-denominated derivatives exchange with a Deterministic Limit Order Book (DLOB).

This repo is for:
- Traders building bots (taker and maker)
- AI agents interacting with the exchange
- Anyone integrating with Sidepit

---

## Current State: Early Alpha

This is **raw and evolving**. We're in the middle of the **Proof Run** – a 6-week live trading program to prove:
1. Better fills for takers (eliminate flash crashes)
2. Spread-alpha capture for makers

**What's missing:**
- Historical market data API
- Polish (error handling, docs, edge cases)

**What's actively changing:**
- APIs being fixed based on user feedback
- Backend features being added
- Market maker alpha being written (C++ side)

---

## Key Files

| File | Purpose |
|------|---------|
| `PROOF_RUN_GUIDE.md` | Developer guide for Proof Run participants |
| `MIGRATION_GUIDE.md` | BetaV2 changes (multi-product, nested positions) |
| `python-client/feed_demo.py` | Feed pattern: NNG → CLI, REST, or WebSocket |
| `users-cli/cli/main.py` | Full trading CLI reference implementation |
| `Public-API-Data/sidepit_api.proto` | Protobuf definitions |

---

## Architecture

```
Protocol: NNG (Nanomsg) + Protobuf
Signing: ECDSA/secp256k1 (Bitcoin keys)
```

**NNG Ports (api.sidepit.com):**
- 12121: Transaction submission (Push)
- 12122: Market data feed (Sub)
- 12123: Auction echo (Sub)
- 12124: Order book updates (Sub)
- 12125: Positions request/reply (Req)
- 12126: Auction clearing (Sub)

**REST Endpoints (already live):**
- `https://api.sidepit.com/quote`
- `https://api.sidepit.com/active_product/`
- `https://api.sidepit.com/request_position/{address}`

REST = same pattern as `feed_demo.py` (NNG wrapped in FastAPI).

---

## Repo Structure

```
Public-API/
├── python-client/     # Low-level clients (feeds, requests, transactions)
├── users-cli/         # Full trading CLI application
├── Public-API-Data/   # Protobuf definitions (submodule)
├── education/         # NNG, Protobuf, crypto primers
└── PROOF_RUN_GUIDE.md # Start here for Proof Run
```

---

## For External Contributors

PRs welcome. This API isn't polished – that's the point. Find problems, report them, fix them.

Read `PROOF_RUN_GUIDE.md` first. Feed it to your LLM for full context.

---

## Links

- **Repo:** https://github.com/sidepit/Public-API
- **Docs:** https://docs.sidepit.com/
- **Web UI:** https://app.sidepit.com/trading-view (code: `sidepit2025`)
- **Proof Run Memo:** https://spiky-elephant-06d.notion.site/Sidepit-2e8fd3f03fea8050b8f2cc7959b42f76
