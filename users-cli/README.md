# sidepit // cockpit

A terminal app for trading on [Sidepit](https://sidepit.com) — a Bitcoin-margined
forwards exchange where orders clear in one-second batch auctions. Best price
wins; fastest machine does not.

You can do everything here: **create your account → fund it → trade → withdraw
→ leave** (and, if you want, hand trading to an agent along the way). Your keys never leave your machine.

## Install & run

```sh
git clone https://github.com/sidepit/Public-API && cd Public-API
python3 -m venv python-client/.venv
python-client/.venv/bin/pip install -r python-client/requirements.txt -r users-cli/requirements.txt
cd users-cli && ../python-client/.venv/bin/python -m sidepit_tui
```

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
sell 0.001 btc at market market = a limit crossed through the touch
cancel all · go flat    cancel everything / close everything
risk · book · help      your envelope · the live book · the grammar
```

Things to know about the venue (the UI repeats them where it matters):

- **Nothing fills instantly.** Orders resolve at the next 1-second auction —
  watch *working orders* (right panel). **Right-click a working order to
  cancel it.**
- **Limit orders only**; "market" is a marketable limit.
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

- **UNLOCK** — one tap requests **everything withdrawable** back. The exchange
  sends BTC to your own address (there is no destination to mistype, by
  design). One open unlock at a time.
- **EXIT** — sweeps your entire on-chain balance to any address you choose.

## Handy

```sh
python -m sidepit_tui import [name]   # paste 12 words or a WIF (hidden input)
python -m sidepit_tui watch <bc1q…>   # read-only identity
python -m sidepit_tui list            # your identities (never prints secrets)
python -m sidepit_tui use <name>      # switch; in-app: ctrl+a
SIDEPIT_HOST=… python -m sidepit_tui  # point at another venue host
```

If right-click is pasting instead of canceling, your terminal is eating the
click — disable right-click-paste for the profile, or type
`cancel <orderid-tail>` at the prompt.

---
*For developers: the app is a thin UI over the `sidepit_trader` SDK
(`../python-client`) — see the module docstrings in `sidepit_tui/`.*
