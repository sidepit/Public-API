# CLAUDE.md — Public-API

The Python client stack for [Sidepit](https://sidepit.com): Bitcoin-margined
forwards, one-second batch auctions.

**Start at `AGENTS.md`** — the agent orientation (wire surface, signing,
message shapes). A guided trading walkthrough lives in
`skills/sidepit-trade/SKILL.md`.

## Layout

- `python-client/sidepit_trader/` — the SDK (signing, feeds, orders, wallet)
- `python-client/proto/` — generated protobuf stub
- `Public-API-Data/` — the contract: `sidepit_api.proto` (submodule; read, never edit)
- `examples/` — keyless quickstart
- `users-cli/` — the trading TUI
- `python-client/facade/` — optional local REST/WS gateway
- `integrations/ccxt/` — CCXT adapter (over the facade)

## Hard rules

- **Keys: never deleted, never printed.** No WIF, mnemonic, or priv_hex in
  output, logs, or commits — ever. Key files are write-once.
- This is production with real Bitcoin. Treat every signed send as real money.
  Fund-safety values are pinned in `sidepit_trader/config.py`.
- Wire truth is the pinned proto in `Public-API-Data/`. Position and margin
  levels come from the server; the orderid handle is
  `"{sidepit_id}:{timestamp_ns}"`.

Tests: `python-client/.venv/bin/python -m pytest python-client/tests -q`
(no network needed).
