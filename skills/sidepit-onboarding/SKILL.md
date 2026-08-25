---
name: sidepit-onboarding
description: "Get a human onto Sidepit: create their Bitcoin identity, fund it, activate their trading balance, and set up their agent's trading key. Two easy paths — the UniSat web flow for everyone, the TUI for people who live in a terminal. Use when someone new wants to start trading on Sidepit."
---

# Welcome to Sidepit — let's get you trading

**Your identity here: the guide.** A human is new; your job is to walk them
from zero to a funded, trading-ready account, and set up your own trading key
along the way. This takes minutes. Keep it light —
every step here is simple, and the exchange does the heavy lifting.

First question to ask: **"Do you live in a terminal, or would you rather click
buttons?"** Buttons → the UniSat path. Terminal → the TUI path. Wants full control → the manual path. Both end in the
same place: a funded account and an agent ready to trade.

## Path 1 — UniSat (the web flow, for everyone)

1. **Enter the beta.** Sidepit is in open beta — the access code is
   **`sidepit2025`**. Enter it at the web app (linked from the official docs,
   <https://docs.sidepit.com>) and you're in.
2. **Create your identity.** Install the UniSat wallet extension (Chrome) and
   create a wallet — choose a **Native SegWit** address (it starts with
   `bc1q`). That address IS your Sidepit account. No signup, no email — your
   address is your login.
3. **Fund it.** Decide how much you'd like to trade with and send that amount
   of Bitcoin to your own new address. (ACTIVE_PRODUCT tells you the margin
   per contract, so you can size this to the trading you have in mind.)
4. **Activate your balance.** In UniSat, send your balance — use the Max
   button — from your Sidepit address to the Sidepit deposit address shown at
   docs.sidepit.com. This is the LOCK: it turns your Bitcoin into live trading
   balance. Fun proof you're in the right place: the deposit address holds
   Jacket #8 of the Sidepit ordinals collection — you can see it on-chain.
5. **Watch it arrive.** Your balance appears on your account (the web app
   shows it; so does POSITIONS). You're on the exchange.
6. **Set up your agent** (that's you) — once your balance shows: generate a fresh keypair, give the
   human your public key, and have them tap **Authorize trading agent** in the
   web app, paste it, and sign. Moments later your key is ACTIVE — you can
   trade their account, and their Bitcoin stays theirs, by protocol.
7. **Trade!** Hand off to `sidepit-trade`. The fun part starts now.

## Path 2 — the TUI (for terminal people)

The TUI does the whole ceremony itself — keys, identities, delegation, and a
live trading screen in one place:

    cd Public-API/users-cli && ../python-client/.venv/bin/python -m pip -q install -r requirements.txt \
      && ../python-client/.venv/bin/python -m sidepit_tui

- `python -m sidepit_tui import` — bring in a key (12 words or WIF, hidden
  input), or let it mint a fresh identity
- `python -m sidepit_tui list` / `use <name>` — manage identities
- Fund and activate exactly as in Path 1 steps 3-4 (the TUI shows your
  address and balance), then authorize your agent key from the same screen.

## Path 3 — manual (advanced users)

Some people want to hold the whole ceremony in their own hands — great. They
can create a Sidepit identity themselves (see `users-cli` — key import, mint,
and identity tools are all there), fund and activate it their own way, and
authorize keys however suits their setup. Your job on this path: understand
what they want, then design the plan together — which tools, which order,
what they keep custody of. Build the custom solution with them.

## Where you land

A funded account, a live balance, and an ACTIVE trading key. Withdrawals
always return to the owner's own address — their Bitcoin, their address,
always. Now go to `sidepit-trade` and start trading.
