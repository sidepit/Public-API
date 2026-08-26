<p align="center">
  <img src="https://raw.githubusercontent.com/sidepit/Public-API/main/images/agents-are-trading.png" alt="Sidepit — agents are trading" width="720">
</p>

<h1 align="center">Sidepit — fair electronic pits for agents and humans</h1>

<p align="center">
  <a href="https://docs.sidepit.com"><img src="https://img.shields.io/badge/docs-docs.sidepit.com-f5a623" alt="Docs"></a>
  <a href="https://app.sidepit.com"><img src="https://img.shields.io/badge/ProofNet-LIVE-2ea44f" alt="ProofNet live"></a>
  <a href="https://docs.sidepit.com/llms.txt"><img src="https://img.shields.io/badge/agents-llms.txt-0f80c1" alt="llms.txt"></a>
</p>

<p align="center"><b>Point your agent at this repo and say: “read AGENTS.md and show me the live quote.”<br>Two minutes. No credentials. Live production data.</b></p>


**You keep the money key. Your agent gets a trading-only key you can revoke.**
That separation is enforced by the protocol: the agent can trade and cancel;
it cannot withdraw Bitcoin or authorize another agent.

<p align="center">
  <img src="https://raw.githubusercontent.com/sidepit/Public-API/main/images/cockpit.png" alt="sidepit // cockpit — the TUI: transparent book, risk envelope, plain-english prompt" width="860">
</p>
<p align="center"><i>The cockpit: transparent DLOB book, live position and risk envelope, and a prompt that takes plain english.</i></p>

<p align="center">
  <img src="https://raw.githubusercontent.com/sidepit/Public-API/main/images/doggie-wallet.png" alt="doggie // wallet — one number, two buttons" width="720">
</p>
<p align="center"><i>doggie // wallet (ctrl+d): your wealth as one number, the market as two buttons.</i></p>

[Sidepit](https://sidepit.com) is a Bitcoin-margined **forwards** exchange. DLOB
runs one-second deterministic auctions that make speed irrelevant: best price
wins, not the fastest machine. Your Bitcoin address is your account—no email,
password, or API-key signup—and unlocked Bitcoin returns only to that address.

The pair of public skills is the product journey:

1. [`sidepit-onboarding`](skills/sidepit-onboarding/SKILL.md) helps the human enter beta
   code `sidepit2025`, connect a Native SegWit UniSat wallet, fund deliberately,
   authorize a locally created agent key, and verify it ACTIVE.
2. [`sidepit-trade`](skills/sidepit-trade/SKILL.md) loads only that restricted
   key, previews exposure, published margin allowance, user-verified fee, and
   either an exact limit or a market order, previews the exposure,
   trades, reconciles, and flattens.

Together: send Bitcoin to your Sidepit ID → LOCK it to the exchange → trade →
unlock it back to that same address. Your agent earns its edge from its risk
model on a market designed for fair price discovery—not from faster fiber.

> **Funding rule:** never send BTC from an external wallet or exchange directly
> to Sidepit's deposit/lock address. Send it to your own connected `bc1q`
> Sidepit ID first; after it arrives, LOCK — sweep that balance to the
> deposit address.

The LOCK transaction tells Sidepit which account to credit: its input must spend
from the Sidepit ID controlled by the customer. An external wallet or exchange
sending straight to the lock address does not identify the intended account.

## Claude + Sidepit: two terminals

Install the cockpit and SDK from anywhere, then clone the skills:

```sh
pip install sidepit
git clone --recurse-submodules https://github.com/sidepit/Public-API
```

Prefer an isolated app install? Use `pipx install sidepit`. If your system
requires a virtual environment:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install sidepit
```

Terminal one — the cockpit:

```sh
sidepit
```

Terminal two — Claude with the Sidepit playbook:

```sh
cd Public-API
claude
```

Tell Claude:

> Read `skills/sidepit-onboarding/SKILL.md` and onboard me.

**Claude | Sidepit | make money!** Your key, your sizing, your risk, your call.

Using Sidepit as a Python SDK? The same installation gives your code:

```python
from sidepit_trader import RequestClient, Signer, Submitter
```

The installed commands:

```sh
sidepit                  # cockpit: book, positions, plain-English prompt
sidepit doggie           # wallet view: your wealth as one number, two buttons
sidepit list             # your wallets
sidepit use <name>       # switch wallet
sidepit import           # add a key (12 words or WIF, hidden input)
```

## Look before you trust (no keys, about 2 minutes)

```sh
git clone --recurse-submodules https://github.com/sidepit/Public-API && cd Public-API
./install_sidepit
python-client/.venv/bin/python examples/quickstart.py
```

`install_sidepit` builds the environment and gives you one command, `sidepit`.
Re-run it any time; it only adds what is missing and never touches your keys.

Expected: named exchange state, live dated forward and expiry, bid/ask, familiar
USD/BTC translation, one contract's USD exposure, and current margins. Live
production data, zero credentials. Native prices are **satoshis per USD**
(inverse): `USD/BTC = 100,000,000 / price`.

## The `sidepit` command

One command drives the whole client. Everything reads live production data;
nothing signs until a key is loaded.

Inside the app: `ctrl+d` toggles the wallet view, `ctrl+a` opens the wallet
list, `ctrl+q` quits. Logs go to `~/.sidepit/tui.log`.

## Point your agent at the right door

New account or agent authorization:

> Clone https://github.com/sidepit/Public-API with submodules, read
> `skills/sidepit-onboarding/SKILL.md`, and onboard me without ever asking for my
> wallet key or seed words.

Already have an ACTIVE trading-only key:

> Read `skills/sidepit-trade/SKILL.md`. Show my current account and an order
> preview, but preview it for me, then send it.

The first skill keeps the human's wallet inside UniSat. The second reads the
agent's protected 0600 file without sourcing it or displaying the secret.
Every live order gets a durable public preview and matching preview;
attempt and result records make reconnects and ambiguous sends recoverable.

Execution fees are 125 sats per contract per side of each fill. The engine
deducts them from available balance and reports them in `realized_fees`.

## Repo map

| path | what |
|------|------|
| `python-client/sidepit_trader/` | the SDK — signing, feeds, orders, wallet, `Trader` base class |
| `python-client/proto/` | generated protobuf stub (from the pinned proto) |
| `examples/` | start here — keyless quickstart |
| `skills/sidepit-onboarding/` | human onboarding: UniSat, TUI, or manual → funded account → ACTIVE agent key |
| `skills/sidepit-trade/` | agent trading: preview → send → reconcile → flatten |
| `AGENTS.md` | agent orientation: wire surface, message shapes, conventions |
| `users-cli/` | advanced terminal trading app |
| `Public-API-Data/` | **the contract**: `sidepit_api.proto` (submodule) — every message the exchange speaks |
| `python-client/facade/` | optional local REST/WS gateway over the wire |
| `integrations/ccxt/` | CCXT adapter (runs over the facade) |
| `DISTRIBUTION.md` | what ships today and the skills/update/Windows roadmap |

Development install from a clone: `pip install -e .` (dist name `sidepit`,
imports as `sidepit_trader`, and installs the `sidepit` cockpit command). The
examples run straight from the clone either way.

## The wire

Transport is [NNG](https://nng.nanomsg.org) over TCP at `api.sidepit.com`,
protobuf payloads — the ports are public by design; this SDK is one client of
a public protocol. The proto in `Public-API-Data/` is the full reference.
Full docs: [docs.sidepit.com](https://docs.sidepit.com) · app:
[app.sidepit.com](https://app.sidepit.com)

MIT license.
