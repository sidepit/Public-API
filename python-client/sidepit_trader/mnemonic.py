"""BIP39 12-word backup + BIP84 derivation — standards-compatible, stdlib-first.

A human can't be asked to copy a WIF; 12 words they can. This module makes the
words REAL: `identity_from_words()` derives m/84'/0'/0'/0/0 exactly per
BIP39/BIP32/BIP84, so the same 12 words restore the same key (and address) in
any standard wallet — the backup is not a Sidepit-proprietary encoding.

Vendored wordlist: data/bip39_english.txt (sha256 2f5eed53…dbda, the canonical
list — verified at import). Crypto: hashlib/hmac (PBKDF2-HMAC-SHA512, HMAC-
SHA512) from the stdlib; only the pubkey computation reuses the SDK's existing
libsecp256k1 dependency. Self-test pins the published BIP39/BIP84 vectors
(zero-entropy mnemonic; first address bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu).

NOTE: 12 words encode the 128-bit seed entropy of a NEW identity. A key
imported as a bare WIF has no mnemonic (the mapping only goes words → key).
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets

_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
_WORDLIST_SHA256 = "2f5eed53a4727b4bf8880d8f3f199efc90e58503646d9ff8eff3a2ed3b24dbda"
_words: list[str] | None = None


def wordlist() -> list[str]:
    global _words
    if _words is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "data", "bip39_english.txt")
        raw = open(path, "rb").read()
        if hashlib.sha256(raw).hexdigest() != _WORDLIST_SHA256:
            raise RuntimeError("bip39 wordlist failed integrity check")
        _words = raw.decode().split()
        assert len(_words) == 2048
    return _words


# --- BIP39 -----------------------------------------------------------------
def entropy_to_words(entropy: bytes) -> str:
    """128-bit entropy → 12 words (entropy + 4-bit sha256 checksum, 11 bits/word)."""
    if len(entropy) != 16:
        raise ValueError("12 words = exactly 16 bytes of entropy")
    cs_bits = 4
    chk = hashlib.sha256(entropy).digest()[0] >> (8 - cs_bits)
    n = (int.from_bytes(entropy, "big") << cs_bits) | chk
    total = len(entropy) * 8 + cs_bits           # 132 bits = 12 * 11
    ws = wordlist()
    out = []
    for i in range(total // 11 - 1, -1, -1):
        out.append(ws[(n >> (i * 11)) & 0x7FF])
    return " ".join(out)


def words_to_entropy(words: str) -> bytes:
    """Validate 12 words (incl. checksum) → 16-byte entropy. Raises ValueError."""
    ws = wordlist()
    idx = []
    for w in words.lower().split():
        if w not in ws:
            raise ValueError(f"not a bip39 word: '{w}'")
        idx.append(ws.index(w))
    if len(idx) != 12:
        raise ValueError("expected exactly 12 words")
    n = 0
    for i in idx:
        n = (n << 11) | i
    chk = n & 0xF
    entropy = (n >> 4).to_bytes(16, "big")
    if hashlib.sha256(entropy).digest()[0] >> 4 != chk:
        raise ValueError("bad mnemonic checksum — a word is wrong or out of order")
    return entropy


def words_to_seed(words: str, passphrase: str = "") -> bytes:
    norm = " ".join(words.lower().split())
    return hashlib.pbkdf2_hmac("sha512", norm.encode(),
                               b"mnemonic" + passphrase.encode(), 2048)


# --- BIP32 / BIP84 ----------------------------------------------------------
def _ckd_priv(k: int, c: bytes, i: int) -> tuple[int, bytes]:
    if i >= 0x80000000:                      # hardened
        data = b"\x00" + k.to_bytes(32, "big") + i.to_bytes(4, "big")
    else:
        from secp256k1 import PrivateKey
        pub = PrivateKey(k.to_bytes(32, "big"), raw=True).pubkey.serialize()
        data = pub + i.to_bytes(4, "big")
    I = hmac.new(c, data, hashlib.sha512).digest()
    il = int.from_bytes(I[:32], "big")
    child = (il + k) % _N
    if il >= _N or child == 0:               # ~2^-127; per spec, skip — we raise
        raise ValueError("invalid child key (try the next index)")
    return child, I[32:]


def seed_to_bip84_priv(seed: bytes) -> str:
    """seed → m/84'/0'/0'/0/0 private key (hex) — the standard first
    native-segwit key, so the address matches any BIP84 wallet."""
    I = hmac.new(b"Bitcoin seed", seed, hashlib.sha512).digest()
    k, c = int.from_bytes(I[:32], "big"), I[32:]
    H = 0x80000000
    for i in (84 + H, 0 + H, 0 + H, 0, 0):
        k, c = _ckd_priv(k, c, i)
    return k.to_bytes(32, "big").hex()


# --- identity bridge ----------------------------------------------------------
def new_identity_words():
    """Mint a NEW identity from fresh 128-bit entropy. Returns (words, Identity)."""
    from .wallet import Identity, priv_to_wif, sidepit_id_from_priv
    words = entropy_to_words(secrets.token_bytes(16))
    priv = seed_to_bip84_priv(words_to_seed(words))
    from secp256k1 import PrivateKey
    pub = PrivateKey(bytes.fromhex(priv), raw=True).pubkey.serialize().hex()
    return words, Identity(priv, priv_to_wif(priv), pub, sidepit_id_from_priv(priv))


def identity_from_words(words: str):
    """12 words → the same Identity, forever (BIP84 m/84'/0'/0'/0/0)."""
    from .wallet import Identity, priv_to_wif, sidepit_id_from_priv
    words_to_entropy(words)                  # validates checksum loudly
    priv = seed_to_bip84_priv(words_to_seed(words))
    from secp256k1 import PrivateKey
    pub = PrivateKey(bytes.fromhex(priv), raw=True).pubkey.serialize().hex()
    return Identity(priv, priv_to_wif(priv), pub, sidepit_id_from_priv(priv))


def looks_like_words(text: str) -> bool:
    parts = text.lower().split()
    return len(parts) == 12 and all(w in wordlist() for w in parts)


# --- self-test (published vectors) --------------------------------------------
def _selftest() -> bool:
    ok = True
    # BIP39 vector: zero entropy -> abandon×11 about; TREZOR seed prefix
    m = entropy_to_words(b"\x00" * 16)
    ok &= m == "abandon " * 11 + "about"
    print("[{}] bip39 zero-entropy mnemonic".format("ok" if ok else "FAIL"))
    s = words_to_seed(m, "TREZOR")
    want = "c55257c360c07c72029aebc1b53c05ed0362ada38ead3e3e9efa3708e53495531f09a6987599d18264c1e1c92f2cf141630c7a3c4ab7c81b2f001698e7463b04"
    v = s.hex() == want
    ok &= v
    print(f"[{'ok' if v else 'FAIL'}] bip39 TREZOR seed vector")
    # BIP84 vector: same mnemonic -> first address bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu
    from .wallet import sidepit_id_from_priv
    addr = sidepit_id_from_priv(seed_to_bip84_priv(words_to_seed(m)))
    v = addr == "bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu"
    ok &= v
    print(f"[{'ok' if v else 'FAIL'}] bip84 m/84'/0'/0'/0/0 address vector ({addr})")
    # round-trip: fresh words -> entropy -> words; words -> same identity twice
    w, ident = new_identity_words()
    v = entropy_to_words(words_to_entropy(w)) == w
    ok &= v
    print(f"[{'ok' if v else 'FAIL'}] entropy round-trip")
    v = identity_from_words(w).sidepit_id == ident.sidepit_id
    ok &= v
    print(f"[{'ok' if v else 'FAIL'}] words -> identity deterministic")
    print("ALL PASS" if ok else "*** SELFTEST FAILED ***")
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
