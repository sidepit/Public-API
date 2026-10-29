"""Key material comes from the OS CSPRNG, with no fallback, and signing uses no RNG.

Jay 2026-10-28: private-key generation must use correct randomness — critical
when the secp256k1 library is compiled per platform — and there must be no
fallback to a weaker source. These tests pin that:

  * every private key and every mnemonic is exactly the bytes `secrets.token_bytes`
    returned — the compiled library only does the curve math, never the entropy;
  * no module in the shipped packages imports `random` or reaches for its own
    entropy source;
  * ECDSA signing is deterministic (RFC 6979 inside libsecp256k1), so a bad RNG
    in a compiled build cannot leak a key through a nonce.
"""
import pathlib
import re

import pytest

from sidepit_trader import mnemonic, wallet
from sidepit_trader._proto import pb
from sidepit_trader.signer import Signer

ROOT = pathlib.Path(__file__).resolve().parents[2]
SHIPPED = [ROOT / "python-client" / "sidepit_trader", ROOT / "users-cli" / "sidepit_tui"]

# test key from the SDK's offline parity rig — never funded, never used live
RIG_PRIV = "91f50feda224198e7b226b57cc506ec924f20f3a4cb102e0a7af076b5cf6ff6c"


def test_private_key_is_exactly_the_os_entropy(monkeypatch):
    fixed = bytes.fromhex(RIG_PRIV)
    monkeypatch.setattr(wallet.secrets, "token_bytes", lambda n: fixed[:n])
    ident = wallet.gen_key()
    assert ident.priv_hex == RIG_PRIV
    assert ident.sidepit_id == "bc1qkucf363qyps6mr4ck34np9q7xg7zdewat9rtg5"


def test_mnemonic_is_exactly_the_os_entropy(monkeypatch):
    fixed = bytes(range(16))
    calls = []

    def token_bytes(n):
        calls.append(n)
        return fixed[:n]

    monkeypatch.setattr(mnemonic.secrets, "token_bytes", token_bytes)
    words, _ident = mnemonic.new_identity_words()
    assert calls == [16]
    assert words == mnemonic.entropy_to_words(fixed)
    assert mnemonic.words_to_entropy(words) == fixed


def test_entropy_source_cannot_be_swapped_for_a_weaker_one():
    # `secrets` raises if the OS CSPRNG is unavailable; nothing may catch that or
    # use `random`, `os.urandom` with a fallback, or time/pid-seeded sources.
    forbidden = re.compile(r"^\s*(import random\b|from random\b|import os\.urandom|from os import urandom)",
                           re.M)
    for pkg in SHIPPED:
        for path in pkg.rglob("*.py"):
            src = path.read_text(encoding="utf-8")
            assert not forbidden.search(src), f"{path}: forbidden entropy source"
            assert "os.urandom(" not in src, f"{path}: use secrets.token_bytes, not os.urandom"
            # signing stays RFC 6979: no caller may hand libsecp256k1 or bitcoinlib its own nonce
            assert "custom_nonce" not in src, f"{path}: custom nonce forbidden"
            assert "use_rfc6979=False" not in src, f"{path}: RFC 6979 must stay on"
    gen_src = (SHIPPED[0] / "wallet.py").read_text(encoding="utf-8")
    assert "secrets.token_bytes(32)" in gen_src
    mn_src = (SHIPPED[0] / "mnemonic.py").read_text(encoding="utf-8")
    assert "secrets.token_bytes(16)" in mn_src


def test_signing_is_deterministic():
    tx = pb.Transaction()
    tx.version = 1
    tx.timestamp = 1755467890123456789
    tx.new_order.side = 1
    tx.new_order.size = 1
    tx.new_order.price = 1500
    tx.new_order.ticker = "USDBTCU26"
    signer = Signer(RIG_PRIV, "bc1qkucf363qyps6mr4ck34np9q7xg7zdewat9rtg5")
    a = signer.sign_digest(tx)
    b = signer.sign_digest(tx)
    assert a == b and len(a) == 128  # 64-byte compact signature, hex
