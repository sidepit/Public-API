---
name: sidepit-locals
description: "Onboard a human to Sidepit without exposing the account key: enter the beta, connect a Native SegWit UniSat wallet, make a live funding decision, authorize a locally minted trading-only agent key, and verify it ACTIVE. Use when a customer needs a Sidepit account or delegate before trading."
---

# Sidepit Locals — the human gets into the pits

Secure your Bitcoin from the big bad AI agents — with your own local AI agent.

You keep the money key. Your agent creates a different, trading-only key that
you can revoke. The protocol lets that key trade and prevents it from
withdrawing or authorizing another agent.

Outcome: in about 10 minutes plus Bitcoin confirmation time, the human has a
Sidepit account with an ACTIVE agent key stored locally. You need a desktop
browser, the UniSat Chrome extension, a Native SegWit Bitcoin address (starts
`bc1q`), this repository, Python 3.10+, and real mainnet BTC. There is no demo
venue: never fund, sign, or authorize without the human at the relevant screen.
A sat is one hundred-millionth of a Bitcoin.

Read the paired [acceptance test](../sidepit-trade/ACCEPTANCE.md) before real
money moves. If any step asks for a private key, WIF, or seed words, STOP. A WIF
is a secret spending key; it and seed words never enter an agent, chat, command
line, or support message.

## The funding invariant — never reverse these two steps

**Never send Bitcoin from an external wallet or exchange directly to Sidepit's
deposit/lock address.**

1. First send BTC to the human's own Sidepit ID—the connected UniSat `bc1q`
   address the human controls.
2. Only after it arrives there, use **LOCK** in Sidepit to forward that balance
   to the exchange.

This two-step path is how Sidepit identifies which account to credit. The LOCK
transaction must spend from the human's Sidepit ID; Sidepit recovers that
address's public key from the transaction input. An external wallet or exchange
sending straight to the lock address does not identify the intended account. If
any instruction says to skip the Sidepit ID, STOP and do not send.

## The wall: two people, two keys, two crossings

- The human's account key stays inside UniSat. It controls funds, agent
  authorization, revocation, and unlock requests.
- The agent's separate key lives in one protected local file. It can place and
  cancel orders for the account. It cannot withdraw, authorize, or revoke.
- Exactly two public facts cross the wall: the agent's public key goes to the
  human; an ACTIVE result comes back to the agent. Nothing secret crosses.

## 1. Prove the client before onboarding

From the Public-API repository root:

```sh
python3 -m venv python-client/.venv
python-client/.venv/bin/pip install -r python-client/requirements.txt
python-client/.venv/bin/python -m pytest python-client/tests -q
```

Expected: all tests pass with zero failures. Warnings are acceptable. If any
test fails, STOP and report the failing test; do not continue.

Read the current forward without a key:

```sh
python-client/.venv/bin/python examples/quickstart.py
```

Expected: named exchange state, active forward, live quote, familiar USD/BTC
price, one contract's USD exposure, and current initial and maintenance margin.
If it cannot connect, the command distinguishes network permission, DNS,
refusal, and timeout; fix that specific problem and rerun.

## 2. Make the funding decision before showing an address

Tell the human these facts before opening a wallet:

1. The `initial margin` printed above is the engine minimum per contract, not a
   recommended deposit. Adverse P&L and fees also consume margin.
2. Trading costs one kind of fee: an execution fee on fills — 125 sats per
   contract per side, so a full open-and-close round turn costs the trader
   250 sats (~$0.25 at $100,000/BTC). The engine does not yet deduct it; the
   schedule is stated so the human can size deposits. There is no published
   universal safety buffer — size conservatively.
3. LOCK forwards the connected address's entire confirmed on-chain balance to
   Sidepit; the Bitcoin network fee comes out of that balance. Use a dedicated
   `bc1q` address holding only the amount the human intends to lock.
4. Start small. Dated forwards can lose BTC. A margin-restricted account may
   only reduce risk; the server is the final margin check.
5. Confirm the human is eligible for the beta and obtain the current margin
   stress/forced-reduction terms from the web experience or beta operator. The
   public API reports restriction state but does not publish that policy. If
   the terms are unavailable, STOP before funding.

Do not use a remembered minimum such as `0.002 BTC`. Contract margin changes;
the live contract response above is the current source.

## 3. Human: enter the beta and create the account

The human performs this section in the browser:

1. Open [app.sidepit.com](https://app.sidepit.com).
2. Enter beta code `sidepit2025`.
3. Install or open the official UniSat Chrome extension.
4. In UniSat, create or select a **Native SegWit** address beginning `bc1q`.
   If UniSat creates seed words, the human backs them up privately without
   showing them to the agent.
5. Connect UniSat to Sidepit. The connected `bc1q` address is the Sidepit
   account ID. Record that public address; never record the wallet secret.

If the site asks the human to paste a private key or seed words, STOP. The
expected flow asks UniSat to sign inside the extension.

## 4. Human: fund and LOCK exactly what was chosen

1. Send the chosen mainnet BTC amount from any source to the human's connected
   `bc1q` Sidepit ID first. This is the human's own Bitcoin address. **Do not
   send from that external source directly to Sidepit's deposit/lock address.**
2. Wait until the wallet shows the deposit as confirmed.
3. In the Sidepit web flow, review LOCK. It must say the entire balance is being
   forwarded and the network fee comes out of it. Confirm the amount in UniSat,
   then sign. If the amount or meaning is unclear, cancel and STOP.
4. Record the public Bitcoin transaction ID. Never retry an ambiguous send;
   inspect the address and transaction first.

Check credit from a fresh shell (replace the public account address):

```sh
python-client/.venv/bin/python skills/sidepit-trade/scripts/sidepit_agent.py \
  public-account --account bc1qACCOUNT
```

`pending` means seen but not yet credited. Confirmation count and timing are not
promised by the current public API; do not repeat an old “five minutes” claim.
Rerun the same command as the Bitcoin transaction confirms. `credited` and
nonzero available margin mean funding reached the account. If it remains
unseen, give support only the public account ID and Bitcoin transaction ID.

## 5. Agent: mint one restricted identity locally

Only after the human explicitly asks, run exactly one mint for their public
account address:

```sh
cd python-client
.venv/bin/python -m sidepit_trader.agent_key new --account bc1qACCOUNT
cd ..
```

Expected output has five public facts: `pubkey`, `trader_id`, `account`, a
`saved` path ending in `(0600, write-once)`, and the next action. It never prints
the secret. Check:

- `pubkey` is exactly 66 lowercase hex characters beginning `02` or `03`.
- `trader_id` begins `bc1q` and differs from the account.
- `account` exactly matches the human's address.
- the saved path is a new file with mode `0600`, meaning only the current
  operating-system user can read or write it.

On any mismatch, STOP. Do not inspect, modify, replace, or delete a key file.
Give the human the public key and derived `trader_id`; keep the saved path for
the ACTIVE check. A minimal prompt the web UI may show is:

> Generate and securely store one new Sidepit trading-only agent identity
> locally for account `bc1q…`. Never display or log the private key. Give me
> the 66-character public key and derived agent ID.

## 6. Human: authorize that public key in the web app

1. Choose **Authorize trading agent**.
2. Paste the 66-character public key.
3. Confirm the derived agent Sidepit ID exactly matches the `trader_id` printed
   by the mint command.
4. Sign in UniSat.

Submitted is not ACTIVE. The human can revoke the agent from the same web
interface at any time. Revocation removes its ability to trade; it never grants
the agent withdrawal authority.

## 7. Agent: wait for settled ACTIVE truth

Use the saved key-file path without sourcing or printing it:

```sh
python-client/.venv/bin/python skills/sidepit-trade/scripts/sidepit_agent.py \
  delegate-status --key-file /absolute/path/from-the-mint.env
```

Expected:

```text
delegate         ACTIVE
key file         /absolute/path/from-the-mint.env (secret not displayed)
```

`PENDING` means received, not active: wait and rerun the same command. A named
reject means the human reviews the public key and account in the web UI before
signing a new request. Never resubmit while a receipt is pending.

Your agent's key is ACTIVE and lives in `<file>`; hand off to the
`sidepit-trade` skill.

## High-assurance local mint (optional)

For a dedicated offline machine, prepare the repository and virtual environment
while online, copy the complete folder to that machine, disconnect every network
interface, and then run the Step 1 tests followed by the Step 5 mint. Require
all tests to pass and every public-output check to match; otherwise STOP. Carry
only the new 0600 agent file to the trading machine using encrypted removable
media, restore mode `0600`, and perform Steps 6–7 online. The account key remains
in UniSat throughout; the offline machine creates only the restricted agent key.

## Owner exit and help

The agent never unlocks funds. The human uses **Sidepit Account → Unlock funds**
in the web app, enters an integer sat amount or chooses MAX, confirms the same
account ID, and signs in UniSat. The web app tracks received, reserved,
processing, completed, or rejected and shows the Bitcoin transaction ID when
available. Funds return only to the same account address. The public API does
not promise a completion time; follow the named UI state and never resubmit a
pending unlock.

When stuck, stop and collect only public facts: account ID, agent ID, order ID,
request receipt ID, and Bitcoin transaction ID. Contact the Sidepit beta
operator who issued access. Never provide a key, seed words, or the contents of
the saved agent file.
