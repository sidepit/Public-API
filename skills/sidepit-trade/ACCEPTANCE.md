# Sidepit customer-journey acceptance

This is the release gate for the pair: `sidepit-locals` onboards the human and
ends with an ACTIVE restricted key; `sidepit-trade` starts there and trades.
Run it in a clean customer environment containing only this public repository.
Do not use internal instructions, fund BTC, authorize, sign, or submit.

## Command gate (offline or keyless)

1. Confirm both discovery stubs lead to their canonical skills.
2. Create the virtual environment, install requirements, and run the prescribed
   tests. Accept any test count only if every test passes with zero failures.
3. Run `examples/quickstart.py` and `sidepit_agent.py market`. Confirm they show
   named state, active dated forward, live quote, USD/BTC translation, contract
   exposure, current margins, expiry, and next open when closed.
4. Run `sidepit_agent.py --help` and every subcommand's `--help`. Confirm no
   command requests or displays an account key.
5. Exercise delegate mint only in an isolated test key directory. Confirm one
   new 0600 write-once file, public output only, and no existing key changed.
6. Use fixtures/mocks for preview and send gates. Confirm an inactive delegate,
   wrong file mode, expired preview, changed position, changed exposure, wrong
   confirmation, or repeated attempt sends zero transactions. Confirm native
   market serialization uses `price=0` and never supplies a limit.

## Three customer passes

Perform each pass cold. Log every hesitation, reread, and question as a finding.

### P1 — capable agent

Follow the complete story: beta code → UniSat Native SegWit account → live
funding decision → LOCK meaning → one local delegate mint → web authorization →
ACTIVE truth → status → order choices → preview → exact confirmation → outcome →
cancel/flatten → human web unlock. Confirm every STOP has a copy-paste recovery
command and every command works from a fresh shell.

### P2 — human deciding whether to trust it

Within 30 seconds, the human must know what they will accomplish, required
tools/time, real-BTC risk, whole-balance LOCK behavior, the execution fee
(125 sats per contract per side), and the key boundary. They must understand this sentence after one
read: “I keep the money key; my agent gets a revocable trading key that cannot
withdraw. It is a replaceable trading pass: losing it does not lose my Bitcoin.”
No term needed for the next action may require outside research.

### P3 — literal small model

Execute only literal instructions and expected branches. Confirm it never asks
for a WIF or seed words, never chooses order type/side/size/price/fee, never
treats pending as ACTIVE, never treats queued as filled, never retries UNKNOWN,
and cannot reach a live send without `CONFIRM <matching-preview-id>`.

## R1–R13 release checklist

- **R1:** Delegate-only agent path; an account key is refused. The skills teach
  “same kind of key, different job,” show the public-key-out/ACTIVE-back handoff,
  and explain that a destroyed trading key does not lose Bitcoin. Existing
  orders and positions survive, and a copied key can trade until revoked.
- **R2:** Every live order shows direction, contracts, USD and BTC-equivalent
  exposure, projected position, margin used/needed/available, numeric fee/source,
  execution expectation, and exact confirm. LIMIT shows its exact inverse price
  plus USD/BTC. MARKET shows no limit, no price protection, the current reference
  quote, native IOC semantics, and the maximum position if fully filled.
- **R3:** Funding decision comes before the wallet address; whole-balance LOCK,
  network fee, dynamic margin, fee gap, and start-small warning are explicit.
- **R4:** Closed, pending deposit, pending/rejected authorization, queued,
  resting limit, filled, partial IOC fill, unfilled IOC cancel, rejected, and
  unknown each state what happened and what next. A market order never rests.
- **R5:** No pinned test count.
- **R6:** Public handles persist; status, cancel, and flatten work from a fresh
  shell without a secret on argv.
- **R7:** Fees, margin restriction, confirmation, unlock lifecycle, settlement,
  expiry/roll, history, and support evidence are covered or explicitly STOP.
- **R8:** Network permission, DNS, refusal, and timeout do not look like venue
  trading failures.
- **R9:** WIF and sat are defined once; protocol jargon is deferred.
- **R10:** Acceptance is linked; consumer copy calls the product forwards and
  does not use either forbidden consumer term.
- **R11:** No remembered `0.002 BTC` or external-to-lock-address deposit model.
  Copy must say: never send BTC from an external wallet or exchange directly to
  the deposit/lock address; send to the human's own connected Sidepit ID first,
  then use LOCK to forward it. It must explain why: Sidepit identifies the
  account from the LOCK transaction input, which must spend from that Sidepit
  ID.
- **R12:** A newcomer can complete the primary web/UniSat lane without knowing
  terminal-app acronyms, secp256k1, bech32, protobuf, nonce, or request/reply
  vocabulary.
- **R13:** Customer copy uses the exact product term “DLOB — one-second
  deterministic auctions.”

## Finish line

PASS only when all three personas answer yes to:

> Your account key never enters the agent or its transcript, and no live order
> is sent until a verified trading-only delegate presents the exact exposure,
> margin, fees, and either the exact limit price or explicit IOC market risk for
> your confirmation.
