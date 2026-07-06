"""Wallet layer for the Sidepit SDK — identity + on-chain, extracted/enhanced from the
old `users-cli` (id_manager.py + bitcoin_manager.py) into the `sidepit_trader` SDK.

Identity (keygen / derive / import), read-only on-chain queries (Blockstream esplora),
and the deposit/lock path. SAFE BY DEFAULT: `plan_lock` is a pure dry-run, and
`build_lock_tx` builds + signs but broadcasts NOTHING unless `broadcast=True` is passed
explicitly (the money step). CLI: `python -m sidepit_trader.wallet new` mints an
identity; bare invocation self-tests derivation.

Design choices:
- p2wpkh sidepit_id derivation is **pure stdlib** (hashlib + vendored bech32 below) — honors
  the sidepit-locals dep-free push and avoids the famous RIPEMD160 "abc" typo (we validate
  against REAL pubkey→address vectors, not a constant).
- esplora reads use stdlib `urllib` (no `requests`).
- keygen reuses `secp256k1` (already an SDK dep via signer.py); the pure-stdlib pubkey path
  lives in the locals `mint_agent_key.py` and can be merged to drop the C dep.

Deposit (forward bitcoin to lock) attribution, server side (BitcoinApi.h): a LOCK is a tx whose
input is your sidepit_id (pubkey recovered from witness) and whose output funds kDepositAddress;
the exchange credits your account. Withdraw/UNLOCK is NOT built here — it's a signed request the
exchange acts on (that's why users-cli `unlock()` was empty); it belongs with submit.py.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import urllib.request
from dataclasses import dataclass

import base58
from secp256k1 import PrivateKey

from .signer import Signer, wif_to_priv_hex

# Deposit/lock address + chain endpoints — centralized in config (optional
# SIDEPIT_* env overrides; production defaults pinned there). Re-exported here so
# `wallet.DEPOSIT_ADDRESS` etc. keep working. verify_deposit_address() still
# re-checks the format at runtime — never send to an unverified address.
from .config import DEPOSIT_ADDRESS, ESPLORA, MEMPOOL_FEES

# ---------------------------------------------------------------------------
# bech32 (BIP173) — vendored, pure stdlib, so address derivation needs no deps
# ---------------------------------------------------------------------------
_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"


def _bech32_polymod(values):
    gen = [0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3]
    chk = 1
    for v in values:
        b = chk >> 25
        chk = (chk & 0x1ffffff) << 5 ^ v
        for i in range(5):
            chk ^= gen[i] if ((b >> i) & 1) else 0
    return chk


def _hrp_expand(hrp):
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]


def _create_checksum(hrp, data):
    values = _hrp_expand(hrp) + data
    polymod = _bech32_polymod(values + [0, 0, 0, 0, 0, 0]) ^ 1
    return [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]


def _bech32_encode(hrp, data):
    combined = data + _create_checksum(hrp, data)
    return hrp + "1" + "".join(_CHARSET[d] for d in combined)


def _bech32_decode(bech):
    if any(ord(x) < 33 or ord(x) > 126 for x in bech):
        return (None, None)
    if bech.lower() != bech and bech.upper() != bech:
        return (None, None)
    bech = bech.lower()
    pos = bech.rfind("1")
    if pos < 1 or pos + 7 > len(bech) or len(bech) > 90:
        return (None, None)
    if not all(x in _CHARSET for x in bech[pos + 1:]):
        return (None, None)
    hrp = bech[:pos]
    data = [_CHARSET.find(x) for x in bech[pos + 1:]]
    if _bech32_polymod(_hrp_expand(hrp) + data) != 1:
        return (None, None)
    return (hrp, data[:-6])


def _convertbits(data, frombits, tobits, pad=True):
    acc = 0
    bits = 0
    ret = []
    maxv = (1 << tobits) - 1
    max_acc = (1 << (frombits + tobits - 1)) - 1
    for value in data:
        if value < 0 or (value >> frombits):
            return None
        acc = ((acc << frombits) | value) & max_acc
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            ret.append((acc >> bits) & maxv)
    if pad:
        if bits:
            ret.append((acc << (tobits - bits)) & maxv)
    elif bits >= frombits or ((acc << (tobits - bits)) & maxv):
        return None
    return ret


def encode_segwit_v0(witprog: bytes, hrp: str = "bc") -> str:
    return _bech32_encode(hrp, [0] + _convertbits(list(witprog), 8, 5))


def decode_segwit(addr: str, hrp: str = "bc"):
    """Return (witver, program_bytes) or (None, None) if not a valid bech32 segwit address."""
    hrpgot, data = _bech32_decode(addr)
    if hrpgot != hrp or not data:
        return (None, None)
    decoded = _convertbits(data[1:], 5, 8, False)
    if decoded is None or not (2 <= len(decoded) <= 40) or data[0] > 16:
        return (None, None)
    return (data[0], bytes(decoded))


# ---------------------------------------------------------------------------
# hashing
# ---------------------------------------------------------------------------
def _ripemd160(b: bytes) -> bytes:
    # hashlib's ripemd160 is CORRECT (the "…0bff for abc" vector is a decades-old typo; truth
    # is "…0bfc"). Some OpenSSL-3 builds disable it; fall back to the `ripemd` pkg if needed.
    try:
        return hashlib.new("ripemd160", b).digest()
    except Exception:
        from ripemd.ripemd160 import ripemd160  # users-cli dep, pure-python
        return bytes.fromhex(ripemd160(b).hex()) if not isinstance(ripemd160(b), (bytes, bytearray)) else bytes(ripemd160(b))


def _hash160(b: bytes) -> bytes:
    return _ripemd160(hashlib.sha256(b).digest())


# ---------------------------------------------------------------------------
# identity
# ---------------------------------------------------------------------------
def sidepit_id_from_pubkey(pubkey_hex: str) -> str:
    """p2wpkh bech32 address (= sidepit_id) from a 33-byte compressed pubkey hex."""
    return encode_segwit_v0(_hash160(bytes.fromhex(pubkey_hex)))


def sidepit_id_from_priv(priv_hex: str) -> str:
    pub = PrivateKey(bytes.fromhex(priv_hex), raw=True).pubkey.serialize()
    return sidepit_id_from_pubkey(pub.hex())


def priv_to_wif(priv_hex: str, compressed: bool = True) -> str:
    body = b"\x80" + bytes.fromhex(priv_hex) + (b"\x01" if compressed else b"")
    checksum = hashlib.sha256(hashlib.sha256(body).digest()).digest()[:4]
    return base58.b58encode(body + checksum).decode()


@dataclass
class Identity:
    """A Sidepit trading identity: private key + its derived sidepit_id."""
    priv_hex: str
    wif: str
    pubkey_hex: str
    sidepit_id: str

    def __repr__(self) -> str:
        """Secret-safe: address + pubkey only — NEVER the WIF or priv_hex.
        (Log lines, tracebacks, and REPL echoes all go through here.)"""
        return f"Identity(sidepit_id={self.sidepit_id}, pubkey={self.pubkey_hex})"

    def signer(self) -> Signer:
        """Bridge to the trading Signer (signer.py) — for submitting orders/requests."""
        return Signer(self.priv_hex, self.sidepit_id)


def gen_key() -> Identity:
    """Mint a fresh keypair + sidepit_id. (Cold/offline use should prefer the locals
    pure-stdlib mint; this reuses secp256k1 already in the SDK.)"""
    priv = secrets.token_bytes(32)
    pk = PrivateKey(priv, raw=True)
    priv_hex = priv.hex()
    pub_hex = pk.pubkey.serialize().hex()
    return Identity(priv_hex, priv_to_wif(priv_hex), pub_hex, sidepit_id_from_pubkey(pub_hex))


def from_wif(wif: str) -> Identity:
    priv_hex = wif_to_priv_hex(wif)
    pub_hex = PrivateKey(bytes.fromhex(priv_hex), raw=True).pubkey.serialize().hex()
    return Identity(priv_hex, wif.strip(), pub_hex, sidepit_id_from_pubkey(pub_hex))


# ---------------------------------------------------------------------------
# on-chain (READ-ONLY)
# ---------------------------------------------------------------------------
def _get(url: str):
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.loads(r.read().decode())


def balance(address: str) -> tuple[int, int]:
    """(confirmed_sats, mempool_sats) for an address, via Blockstream esplora."""
    d = _get(f"{ESPLORA}/address/{address}")
    c = d["chain_stats"]["funded_txo_sum"] - d["chain_stats"]["spent_txo_sum"]
    m = d["mempool_stats"]["funded_txo_sum"] - d["mempool_stats"]["spent_txo_sum"]
    return c, m


def utxos(address: str) -> list:
    return _get(f"{ESPLORA}/address/{address}/utxo")


def fee_rate_sat_vb() -> int:
    try:
        return int(_get(MEMPOOL_FEES).get("economyFee", 10))
    except Exception:
        return 10


# ---------------------------------------------------------------------------
# deposit / lock — PLAN ONLY (no signing, no broadcast)
# ---------------------------------------------------------------------------
def verify_deposit_address(addr: str = DEPOSIT_ADDRESS) -> bool:
    """Re-derive that the pinned deposit address is a valid bech32 p2wpkh (v0, 20-byte
    program). Mirrors the locals verify_lock_address.py 'DO NOT SEND BITCOIN' guard."""
    ver, prog = decode_segwit(addr)
    return ver == 0 and prog is not None and len(prog) == 20


@dataclass
class LockPlan:
    sidepit_id: str
    deposit_address: str
    amount_sats: int
    fee_sats: int
    fee_rate: int
    change_sats: int
    n_inputs: int
    total_in_sats: int


def plan_lock(identity: Identity, amount_sats: int,
              fee_from_amount: bool = False) -> LockPlan:
    """Dry-run a lock (deposit): pick the sidepit_id's UTXOs, estimate fee, compute change,
    and target the VERIFIED deposit address. Returns a plan — builds/signs/broadcasts NOTHING.
    Inspect this before any real broadcast.

    fee_from_amount=True: `amount_sats` is the TOTAL the user spends — the fee
    comes out of it and `plan.amount_sats` becomes what actually arrives at the
    deposit (the wallet UX). False (default): `amount_sats` arrives at the
    deposit and the fee is paid on top."""
    if not verify_deposit_address():
        raise RuntimeError("DEPOSIT ADDRESS FAILED VERIFICATION — refusing to plan a lock")
    us = utxos(identity.sidepit_id)
    total_in = sum(u["value"] for u in us)
    n_in = len(us)
    rate = fee_rate_sat_vb()
    # p2wpkh vsize estimate: ~11 overhead + ~68/in + ~31/out (assume 2 outs: deposit + change)
    vsize = 11 + 68 * max(n_in, 1) + 31 * 2
    fee = vsize * rate
    if fee_from_amount:
        deposit = amount_sats - fee
        if deposit <= 546:
            raise ValueError(f"amount too small: {amount_sats} sats minus {fee} fee "
                             f"leaves {deposit} (dust)")
        if total_in < amount_sats:
            raise ValueError(f"insufficient: have {total_in} sats, requested "
                             f"{amount_sats} across {n_in} utxo(s)")
        return LockPlan(identity.sidepit_id, DEPOSIT_ADDRESS, deposit, fee, rate,
                        max(total_in - amount_sats, 0), n_in, total_in)
    change = total_in - amount_sats - fee
    if total_in < amount_sats + fee:
        raise ValueError(
            f"insufficient: have {total_in} sats, need {amount_sats}+{fee} fee "
            f"(={amount_sats + fee}) across {n_in} utxo(s)")
    return LockPlan(identity.sidepit_id, DEPOSIT_ADDRESS, amount_sats, fee, rate,
                    max(change, 0), n_in, total_in)


def build_lock_tx(identity: Identity, amount_sats: int, broadcast: bool = False,
                  fee_from_amount: bool = False):
    """FAITHFUL port of the WORKING users-cli lock/forward
    (bitcoin_manager.create_and_broadcast_transaction) — the only working Python that builds +
    signs a real Bitcoin tx. Spends identity's UTXOs, sends to the VERIFIED
    deposit address, returns change. Returns (raw_signed_hex, LockPlan).

    fee_from_amount=True: `amount_sats` is the user's TOTAL spend — the network
    fee is subtracted from it and the remainder arrives at the deposit (the
    wallet UX). False (default): `amount_sats` arrives and the fee is on top.

    SAFE BY DEFAULT: builds and SIGNS but sends NOTHING unless broadcast=True (the money step).
    Requires `bitcoinlib` (lazy import — kept off the module top so identity/reads work without
    it). Inspect the returned plan before any send.
    """
    if not verify_deposit_address():
        raise RuntimeError("DEPOSIT ADDRESS FAILED VERIFICATION — refusing to build a lock")
    from bitcoinlib.keys import Key            # lazy: only the money path needs bitcoinlib
    from bitcoinlib.transactions import Transaction

    us = utxos(identity.sidepit_id)
    if not us:
        raise ValueError(f"no UTXOs on {identity.sidepit_id} — nothing to lock")
    total_in = sum(u["value"] for u in us)
    rate = fee_rate_sat_vb()
    key = Key(identity.wif)

    def _build(deposit, change):
        t = Transaction(network="bitcoin")
        for u in us:
            t.add_input(prev_txid=u["txid"], output_n=u["vout"], keys=key,
                        script_type="sig_pubkey", value=u["value"],
                        address=identity.sidepit_id, sequence=0xffffffff, witnesses=None)
        t.add_output(deposit, DEPOSIT_ADDRESS)
        if change > 546:                        # dust threshold, as in users-cli
            t.add_output(change, identity.sidepit_id)
        return t

    # fee from a signed dry build (matches users-cli get_actual_tx_size)
    dry = _build(amount_sats, total_in - amount_sats)
    dry.sign()
    fee = (len(dry.raw_hex()) // 2) * rate
    if fee_from_amount:
        deposit = amount_sats - fee
        if deposit <= 546:
            raise ValueError(f"amount too small: {amount_sats} sats minus {fee} fee "
                             f"leaves {deposit} (dust)")
        if total_in < amount_sats:
            raise ValueError(f"insufficient: have {total_in}, requested {amount_sats}")
        change = total_in - amount_sats
    else:
        deposit = amount_sats
        if total_in < amount_sats + fee:
            raise ValueError(f"insufficient: have {total_in}, need {amount_sats}+{fee} fee")
        change = total_in - amount_sats - fee
    tx = _build(deposit, change)
    tx.sign()
    raw = tx.raw_hex()
    plan = LockPlan(identity.sidepit_id, DEPOSIT_ADDRESS, deposit, fee, rate,
                    max(change, 0), len(us), total_in)
    if not broadcast:
        return raw, plan                        # built + signed, NOT sent
    # ---- MONEY STEP (only with explicit broadcast=True) ----
    req = urllib.request.Request(f"{ESPLORA}/tx", data=raw.encode(), method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode().strip(), plan  # returns txid


def build_sweep_tx(identity: Identity, dest: str, broadcast: bool = False):
    """EXIT: spend the ENTIRE on-chain balance to `dest` (everything-minus-fee,
    single output, no change — this is leaving, not wallet management).
    Returns (txid_or_raw_hex, LockPlan) with deposit_address = dest.

    Guards: dest must be a valid mainnet bech32 segwit address, not your own
    address, and not the exchange deposit address (that's what LOCK is for).
    SAFE BY DEFAULT: broadcasts nothing unless broadcast=True."""
    ver, prog = decode_segwit(dest)
    if ver is None or prog is None:
        raise ValueError(f"not a valid bc1 address: {dest}")
    if dest == identity.sidepit_id:
        raise ValueError("that is your own address — nothing would leave")
    if dest == DEPOSIT_ADDRESS:
        raise ValueError("that is the exchange deposit address — use LOCK to fund")
    from bitcoinlib.keys import Key
    from bitcoinlib.transactions import Transaction

    us = utxos(identity.sidepit_id)
    if not us:
        raise ValueError(f"no UTXOs on {identity.sidepit_id} — nothing to exit")
    total_in = sum(u["value"] for u in us)
    rate = fee_rate_sat_vb()
    key = Key(identity.wif)

    def _build(out_amount):
        t = Transaction(network="bitcoin")
        for u in us:
            t.add_input(prev_txid=u["txid"], output_n=u["vout"], keys=key,
                        script_type="sig_pubkey", value=u["value"],
                        address=identity.sidepit_id, sequence=0xffffffff,
                        witnesses=None)
        t.add_output(out_amount, dest)
        return t

    dry = _build(total_in)
    dry.sign()
    fee = (len(dry.raw_hex()) // 2) * rate
    out = total_in - fee
    if out <= 546:
        raise ValueError(f"balance too small: {total_in} sats minus {fee} fee "
                         f"leaves {out} (dust)")
    tx = _build(out)
    tx.sign()
    raw = tx.raw_hex()
    plan = LockPlan(identity.sidepit_id, dest, out, fee, rate, 0, len(us), total_in)
    if not broadcast:
        return raw, plan
    req = urllib.request.Request(f"{ESPLORA}/tx", data=raw.encode(), method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode().strip(), plan


# ---------------------------------------------------------------------------
# CLI — `python -m sidepit_trader.wallet new` (mint) / no args (self-test)
# ---------------------------------------------------------------------------
def _cmd_new(save_name: str | None = None):
    """Mint a fresh identity and print everything needed to fund and trade it."""
    ident = gen_key()
    print("NEW SIDEPIT IDENTITY")
    print(f"  sidepit_id : {ident.sidepit_id}")
    print(f"  WIF        : {ident.wif}")
    print(f"  priv_hex   : {ident.priv_hex}")
    print(f"  pubkey     : {ident.pubkey_hex}")
    print()
    print("  *** SAVE THE WIF (or priv_hex) SECURELY NOW — it IS the account. ***")
    print("  *** There is no recovery. Anyone holding it controls the funds.  ***")
    print()
    print("  Fund it:  send BTC to the sidepit_id address (your own address),")
    print("            then forward it to the exchange: wallet.build_lock_tx()")
    print("  Trade it: SIDEPIT_ID=… SIDEPIT_WIF=…  (examples/hello_taker.py)")
    if save_name:
        from . import keystore
        p = keystore.save_identity(save_name, ident.sidepit_id, ident.wif, active=True)
        print(f"  Saved as active identity '{save_name}' → {p} (0600 flat file)")
    return ident



def _selftest():
    ok = True
    # pubkey -> sidepit_id derivation vectors (fixed test keys, deterministic).
    vectors = [
        ("034f355bdcb7cc0af728ef3cceb9615d90684bb5b2ca5f859ab0f0b704075871aa",
         "bc1ql3e9pgs3mmwuwrh95fecme0s0qtn2880lsvsd5"),
        ("02466d7fcae563e5cb09a0d1870bb580344804617879a14949cf22285f1bae3f27",
         "bc1q2vfxp232rx0z9rzn0hay9jptagk8c86d9w4l7k"),
    ]
    for pub, want in vectors:
        got = sidepit_id_from_pubkey(pub)
        status = "ok" if got == want else "FAIL"
        ok &= got == want
        print(f"[{status}] derive {pub[:10]}… -> {got}  (want {want})")
    # WIF round-trip
    ident = gen_key()
    rt = from_wif(ident.wif)
    status = "ok" if rt.sidepit_id == ident.sidepit_id else "FAIL"
    ok &= rt.sidepit_id == ident.sidepit_id
    print(f"[{status}] WIF round-trip: gen -> wif -> from_wif -> same sidepit_id ({ident.sidepit_id})")
    # deposit address verify
    status = "ok" if verify_deposit_address() else "FAIL"
    ok &= verify_deposit_address()
    ver, prog = decode_segwit(DEPOSIT_ADDRESS)
    print(f"[{status}] deposit addr {DEPOSIT_ADDRESS} verifies (v{ver}, {len(prog) if prog else '?'}-byte program)")
    print("ALL PASS" if ok else "*** SELFTEST FAILED ***")
    return ok


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "new":
        _cmd_new(sys.argv[2] if len(sys.argv) > 2 else None)
        sys.exit(0)
    sys.exit(0 if _selftest() else 1)
