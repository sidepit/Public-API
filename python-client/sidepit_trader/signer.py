"""Transaction signing — ECDSA/secp256k1 over the serialized Transaction.

Lifted from the working sidepit_nng_client / users-cli signing path so the SDK
produces exactly the bytes the exchange already accepts:

    sidepit_id is stamped on the Transaction, the Transaction is serialized and
    SHA-256'd, signed with raw ECDSA, and the 64-byte compact signature is
    hex-encoded onto SignedTransaction.signature (signature_version 0).
"""
import binascii
import os
from hashlib import sha256

import base58
from secp256k1 import PrivateKey

from ._proto import pb


def wif_to_priv_hex(wif: str) -> str:
    """Decode a Bitcoin WIF to a 32-byte private key (hex)."""
    decoded = base58.b58decode(wif)
    checksum = decoded[-4:]
    if sha256(sha256(decoded[:-4]).digest()).digest()[:4] != checksum:
        raise ValueError("Invalid WIF checksum")
    body = decoded[1:-4]
    if len(body) == 33 and body[-1] == 0x01:  # compressed-key flag
        body = body[:-1]
    return body.hex()


class Signer:
    """Holds one trading identity (private key + its sidepit_id address).

    Two modes:
      - Direct (default): the key IS the account. `Signer(priv_hex, sidepit_id)`;
        `trader_id` stays empty and the server treats sidepit_id as the signer.
      - Delegate: a registered hot key signs for a custody account.
        `Signer(hot_priv_hex, sidepit_id=custody_addr, trader_id=hot_addr)` —
        sidepit_id names WHOSE margin, trader_id names WHO SIGNED.
        (Register the hot key first: Submitter.register_delegate, signed by custody.)
    """

    def __init__(self, priv_hex: str, sidepit_id: str, trader_id: str = ""):
        self._priv = PrivateKey(bytes.fromhex(priv_hex), raw=True)
        self.sidepit_id = sidepit_id
        self.trader_id = trader_id
        self.pubkey_hex = binascii.hexlify(self._priv.pubkey.serialize()).decode()

    @classmethod
    def from_wif(cls, wif: str, sidepit_id: str, trader_id: str = "") -> "Signer":
        return cls(wif_to_priv_hex(wif), sidepit_id, trader_id)

    @classmethod
    def as_delegate(cls, hot_priv_hex: str, custody_sidepit_id: str) -> "Signer":
        """Delegate-mode signer; the hot key's own address (trader_id) is derived."""
        from .wallet import sidepit_id_from_priv  # lazy: wallet imports this module
        return cls(hot_priv_hex, custody_sidepit_id,
                   trader_id=sidepit_id_from_priv(hot_priv_hex))

    def sign_digest(self, tx) -> str:
        digest = sha256(tx.SerializeToString()).digest()
        sig = self._priv.ecdsa_sign(digest, raw=True)
        return binascii.hexlify(self._priv.ecdsa_serialize_compact(sig)).decode()

    def sign(self, tx) -> "pb.SignedTransaction":
        """Stamp sidepit_id (+ trader_id in delegate mode), sign, wrap."""
        tx.sidepit_id = self.sidepit_id
        if self.trader_id:
            tx.agent_id = self.trader_id
        stx = pb.SignedTransaction()
        stx.transaction.CopyFrom(tx)
        stx.signature_version = 0  # raw ECDSA compact, what the server expects
        stx.signature = self.sign_digest(stx.transaction)
        return stx


def signer_from_env() -> Signer:
    """Build a Signer from the standard env handoff — DELEGATE-AWARE.

    Reads SIDEPIT_WIF (or SIDEPIT_PRIV_HEX) and the optional SIDEPIT_ID:
      - SIDEPIT_ID absent, or equal to the key's own derived address
        → direct Signer (the key IS the account).
      - SIDEPIT_ID different from the key's own address → the key is a
        registered delegate (agent) signing for the custody account:
        returns Signer.as_delegate — sidepit_id = custody, trader_id = the
        key's own address, stamped on every transaction.

    This is the locals handoff (SKILL.md): `SIDEPIT_WIF=<agent key>
    SIDEPIT_ID=<custody bc1q>` just works. Raises ValueError when no key
    material is set."""
    wif = os.environ.get("SIDEPIT_WIF")
    priv = os.environ.get("SIDEPIT_PRIV_HEX")
    sid = os.environ.get("SIDEPIT_ID")
    if not (wif or priv):
        raise ValueError("set SIDEPIT_WIF (or SIDEPIT_PRIV_HEX); optionally "
                         "SIDEPIT_ID (custody address when the key is a delegate)")
    priv_hex = priv or wif_to_priv_hex(wif)
    from .wallet import sidepit_id_from_priv  # lazy: wallet imports this module
    own_id = sidepit_id_from_priv(priv_hex)
    if not sid or sid == own_id:
        return Signer(priv_hex, own_id)
    return Signer.as_delegate(priv_hex, sid)
