"""Deterministic delegate-key minting — the one command a customer's agent runs.

    python -m sidepit_trader.agent_key new --account bc1q...

Contract (exact, in order — from the first customer-sim run's findings):
  1. Validate the account address (mainnet P2WPKH bech32).
  2. Generate a new secp256k1 key with secure randomness (the SDK's gen_key).
  3. Derive the compressed public key and the key's own address (trader id).
  4. Create a unique owner-only (0600) file — NEVER overwriting anything.
  5. Bind it to the specified account (SIDEPIT_ID=<account> in the file, the
     delegate-mode env handoff shape — one key, one account).
  6. Verify derivations and file permissions by re-reading the written file.
  7. Print ONLY the public result — never the WIF/private key.
  8. Exit nonzero on any failure; all validation happens BEFORE the single
     atomic write, so no partial file is ever left behind. (A file that fails
     post-write verification is reported, never deleted — key files are
     write-once by core rule.)

An agent may run this ONLY on an explicit user request, and must not inspect
or modify existing keys. The minted key can trade the bound account once the
owner registers its public key — it can never withdraw, appoint, or revoke
(the courier rule, enforced server-side).
"""
from __future__ import annotations

import stat
import sys

from . import keystore
from .wallet import decode_segwit, gen_key


def mint(account: str) -> dict:
    """Mint one delegate key bound to `account`. Returns ONLY public facts:
    {pubkey, trader_id, account, path}. Raises ValueError before anything is
    written if the account address is invalid."""
    ver, prog = (None, None)
    try:
        ver, prog = decode_segwit(account)
    except Exception:
        pass
    if ver != 0 or prog is None or len(prog) != 20:
        raise ValueError(f"not a mainnet P2WPKH (bc1q…) address: {account!r}")

    ident = gen_key()                       # os.urandom-backed secp256k1
    # pre-write self-check: the identity must round-trip priv -> pubkey -> address
    from .wallet import sidepit_id_from_pubkey
    if sidepit_id_from_pubkey(ident.pubkey_hex) != ident.sidepit_id:
        raise RuntimeError("key self-check failed — nothing written")
    if ident.sidepit_id == account:
        raise ValueError("the account address IS this key — a delegate must be "
                         "a different key than the account it trades")

    name = f"agent-{ident.sidepit_id[-8:]}"
    # SIDEPIT_ID = the CUSTODY account (delegate-mode handoff shape);
    # active=False — minting must never steal the user's active identity.
    path = keystore.save_identity(name, account, ident.wif, active=False)

    # post-write verification, from the file itself
    mode = stat.S_IMODE(path.stat().st_mode)
    d = keystore._parse(path)
    from .wallet import from_wif
    reread = from_wif(d.get("SIDEPIT_WIF", ""))
    if mode != 0o600 or d.get("SIDEPIT_ID") != account \
            or reread.sidepit_id != ident.sidepit_id:
        raise RuntimeError(f"verification of written key file failed: {path} "
                           f"(file kept — key files are never deleted)")

    return {"pubkey": ident.pubkey_hex, "trader_id": ident.sidepit_id,
            "account": account, "path": str(path)}


def _cli(argv: list[str]) -> int:
    usage = ("usage: python -m sidepit_trader.agent_key new --account bc1q...\n"
             "Mints ONE new delegate key bound to the given account.\n"
             "Prints only the public key, its address, and the file path —\n"
             "never the private key. Files are 0600 and never overwritten.")
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(usage)
        return 0
    if argv[0] != "new" or len(argv) != 3 or argv[1] != "--account":
        print(usage, file=sys.stderr)
        return 2
    try:
        r = mint(argv[2])
    except (ValueError, RuntimeError) as e:
        print(f"agent_key: {e}", file=sys.stderr)
        return 1
    print(f"pubkey    {r['pubkey']}")
    print(f"trader_id {r['trader_id']}")
    print(f"account   {r['account']}")
    print(f"saved     {r['path']}  (0600, write-once)")
    print("next: the ACCOUNT owner registers this pubkey (TUI delegates tab "
          "or Submitter.register_delegate) — then trade with "
          f"SIDEPIT_WIF=<this file> SIDEPIT_ID={r['account']}")
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
