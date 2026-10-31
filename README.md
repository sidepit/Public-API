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

## Get started

Choose the [website](#use-the-website) or the [command-line cockpit](#use-the-command-line-cockpit).

You can also start by asking your agent to onboard you. Give it the
[onboarding playbook](skills/sidepit-onboarding/SKILL.md) and say:

> Read https://github.com/sidepit/Public-API/blob/main/skills/sidepit-onboarding/SKILL.md
> and onboard me. Ask whether I prefer the website or the command line.

The agent should guide your chosen path. A terminal agent can guide you through
the website just as a browser assistant can.

### Use the website

Start with the [Sidepit user docs](https://docs.sidepit.com) and open
[the trading app](https://app.sidepit.com). Follow the docs for wallet setup,
funding and authorizing an agent. This path needs no cockpit installation or
repository clone.

For help in your browser, open [Claude](https://claude.ai) or
[ChatGPT](https://chatgpt.com) and paste the onboarding prompt above, adding
"Use the website." Keep the assistant beside the trading app as you follow the
guide. Agents can read the docs through [llms.txt](https://docs.sidepit.com/llms.txt)
and its linked Markdown pages.

### Use the command-line cockpit

**Step 1 — install the cockpit.** Pick your machine, follow the steps.

**Windows — recommended: WSL2 (Ubuntu inside Windows)**

1. Start menu → type `PowerShell` → *Run as administrator*. In it:
   ```powershell
   wsl --install
   ```
   (Windows 10 2004+ or Windows 11.)
2. Reboot when asked. Ubuntu opens by itself and asks for a username and a
   password — pick any; this is your Linux user, not your Windows login.
3. In that Ubuntu window:
   ```sh
   sudo apt update && sudo apt install -y pipx
   pipx install sidepit
   pipx ensurepath
   ```
4. Close the Ubuntu window, open it again (Start menu → *Ubuntu*), run:
   ```sh
   sidepit
   ```
   You get the Linux cockpit, and Claude Code runs beside it in the same terminal.

**Windows — native, no WSL2**

1. Download and install Python 3.13:
   <https://www.python.org/ftp/python/3.13.17/python-3.13.17-amd64.exe>
   — tick *Add python.exe to PATH* on the first screen.
2. Start menu → `PowerShell`.
3. ```powershell
   pip install sidepit
   sidepit
   ```

**macOS (Apple Silicon or Intel)**

1. Download and install Python 3.13:
   <https://www.python.org/ftp/python/3.13.17/python-3.13.17-macos11.pkg>
2. When the installer finishes it opens the *Python 3.13* folder. Double-click
   `Install Certificates.command` in it.
3. Open Terminal (Applications → Utilities → Terminal).
4. ```sh
   pip3 install sidepit
   sidepit
   ```

**Linux (Ubuntu / Debian)**

```sh
sudo apt update && sudo apt install -y pipx
pipx install sidepit
pipx ensurepath
```
Reopen the terminal, run `sidepit`. Other distros: `pip install sidepit` inside a venv.

First run opens on the live market with no identity. Create, import or watch
one from the doors, or press Escape to just look and add a key later with ctrl+a.

**Step 2 — bring your terminal agent.** Claude Code and Codex are the ones we
test with. If you already use a terminal agent, continue to Step 3. Otherwise,
follow its official installation guide for your operating system:

- [Install Claude Code](https://code.claude.com/docs/en/setup), then run `claude`.
- [Install Codex](https://learn.chatgpt.com/docs/codex/cli), then run `codex`.
- For another terminal agent, follow its installation guide and point it at
  this repo's `AGENTS.md`.

**Step 3 — two terminals** (terminal agents only). Clone the repo (your agent
reads the playbooks in it; the cockpit does not need them):

```sh
git clone --recurse-submodules https://github.com/sidepit/Public-API
```

Terminal one — the cockpit:

```sh
sidepit
```

Terminal two — your agent, inside the repo:

```sh
cd Public-API
claude        # or: codex
```

Tell it:

> Read `skills/sidepit-onboarding/SKILL.md` and onboard me using the cockpit.

**Then, in the cockpit:**

1. **Fund** — send BTC to your address on the fund tab, then press LOCK. That
   opens your account.
2. **Delegate** — ask your agent to generate its own agent key and hand you the
   delegate pubkey. Delegates tab → paste it → register. Your agent can now
   trade for you; it can never withdraw.
3. **Doggie** — press ctrl+d for the wallet view: more USD or more BTC, two
   buttons, you decide.

Your key, your sizing, your risk, your call.

Using Sidepit as a Python SDK? `pip install sidepit` in your project's venv gives your code:

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
