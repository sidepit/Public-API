# sidepit // cockpit

A terminal app for trading on [Sidepit](https://sidepit.com) — a Bitcoin-margined
forwards exchange powered by DLOB one-second deterministic auctions. Best price
wins; fastest machine does not.

You can do everything here: **create your account → fund it → trade → withdraw
→ leave** (and, if you want, hand trading to an agent along the way). Your keys never leave your machine.

## Install & run

```sh
git clone https://github.com/sidepit/Public-API && cd Public-API
./install_sidepit          # once — builds the environment, installs `sidepit`
sidepit                    # the cockpit
```

Then, any time:

```sh
sidepit                  # cockpit: book, positions, plain-english prompt
sidepit doggie           # wallet view: your wealth as one number, two buttons
sidepit list             # your wallets     sidepit use <name>   switch wallet
sidepit import           # add a key (12 words or WIF, hidden input)
sidepit positions [addr] # debugging: dump the raw POSITIONS reply, keyless
```

### Running the TUI from a local checkout (lower level)

`sidepit` is a launcher: it runs `python -m sidepit_tui` from `users-cli/` with the
repo's own environment at `python-client/.venv`. If you want the pieces:

- **Python 3.10+.**
- **One venv for SDK + TUI** — `install_sidepit` creates `python-client/.venv` and
  installs three things into it. To do it by hand (or into a venv you made yourself):

  ```sh
  python3 -m venv python-client/.venv
  source python-client/.venv/bin/activate
  pip install -r python-client/requirements.txt    # the SDK: protobuf, pynng, secp256k1, …
  pip install -r users-cli/requirements.txt        # the TUI: textual, qrcode
  pip install -e .                                 # from the repo root: makes `sidepit_tui`
                                                   # and `sidepit_trader` importable anywhere
  ```

- **Run it** with that venv active, from any directory:

  ```sh
  source python-client/.venv/bin/activate
  python -m sidepit_tui            # the cockpit (same as `sidepit`)
  python -m sidepit_tui list       # wallet subcommands work the same way
  ```

  Without the `pip install -e .` step, run from `users-cli/` so the package is on the path.

- **If you see `ModuleNotFoundError: No module named 'textual'`**, the wrong Python is
  running — the system interpreter, or a venv without `users-cli/requirements.txt`.
  Activate `python-client/.venv` (or install the TUI requirements into your venv).

The published `pip install sidepit` package is a separate, versioned copy of this code;
a local checkout does not update it and it does not update the checkout.

## First run — your identity

Pick one of three doors:

- **Create** — mints a fresh key and shows you **12 words, once**. Write them
  down. The words ARE the account: they restore your key here or in any
  standard Bitcoin wallet (BIP39/84), and there is no other recovery.
- **Import** — paste 12 words or a WIF private key.
- **Watch** — just an address; everything works read-only, nothing can be signed.

Keys are stored as plain files in `~/.sidepit/keys/` (one per identity,
owner-readable only). **This app has no feature that deletes a key, by
design.** Switch accounts any time with `ctrl+a`.

## Fund (the `fund` tab)

1. **FUND** — send BTC from anywhere to *your own address* (shown with a QR).
2. **LOCK** — the button turns green the moment your deposit is seen; one tap
   forwards your **entire** balance to the exchange. The network fee comes out
   of the amount. No amounts to type, no change to manage.

## Trade (the `cockpit` tab)

Type plain english at the `trader@sidepit ›` prompt. You always see what the
parser understood before anything executes:

```
buy 5 @ 1610            limit: 5 contracts at 1610 sats-per-USD
sell 0.001 btc at market market = native IOC; unfilled remainder cancels
cancel all · go flat    cancel everything / close everything
risk · book · help      your envelope · the live book · the grammar
```

The top-bar **BTC / SATS** selector changes money amounts everywhere in the
cockpit, including the unlock input. Switching it converts an amount exactly;
the exchange still receives integer sats on the wire.

Things to know about the venue (the UI repeats them where it matters):

- **Nothing resolves on button press.** Orders resolve in the next DLOB
  one-second deterministic auction —
  watch *working orders* (right panel). **Right-click a working order to
  cancel it.**
- **Market orders are immediate-or-cancel:** they take available opposite
  liquidity and cancel every unfilled remainder in that same auction.
- Prices are sats-per-USD; your risk is **BTC-denominated** (equity = available
  balance + realized + open P&L while the session is open).

`ctrl+d` flips to **doggie // wallet** — two buttons, BTC and USD; each tap
shifts one contract of exposure. The same account, the simplest possible view.

## Delegate (the `delegates` tab)

Hand trading to a bot or AI agent **without giving it your money**:

1. **Mint agent key** — creates a hot key, saves it as an env file for your
   agent, shows it once.
2. **Register** — your custody key authorizes it (applies live in-session).
   The agent can then trade your account but can **never** withdraw,
   appoint, or revoke — only your custody key can. Revoke any time.

## Withdraw & leave (the `withdraw` tab)

- **UNLOCK** — enter an amount in the selected BTC/SATS denomination, or click
  **MAX** to put `MAX` in the field and request **everything withdrawable**.
  The exchange sends BTC to your own address (there is no destination to
  mistype, by design). One open unlock at a time.
- **EXIT** — sweeps your entire on-chain balance to any address you choose.

## Handy

```sh
python -m sidepit_tui import [name]   # paste 12 words or a WIF (hidden input)
python -m sidepit_tui watch <bc1q…>   # read-only identity
python -m sidepit_tui list            # your identities (never prints secrets)
python -m sidepit_tui use <name>      # switch; in-app: ctrl+a
```

If right-click is pasting instead of canceling, your terminal is eating the
click — disable right-click-paste for the profile, or type
`cancel <orderid-tail>` at the prompt.

---
*For developers: the app is a thin UI over the `sidepit_trader` SDK
(`../python-client`) — see the module docstrings in `sidepit_tui/`.*
