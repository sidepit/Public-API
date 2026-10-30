"""RIPEMD-160 without a compiled dependency.

`pip install sidepit` must not compile anything. The ripemd-hash package
built a C extension at install time and broke stock Windows and macOS; the
SDK now carries its own pure-Python fallback behind hashlib. Both paths
must agree with the published vectors, and the address path (hash160 →
bech32 = sidepit_id) must be byte-identical through either.
"""
import hashlib

import pytest

from sidepit_trader import ripemd160 as rmd
from sidepit_trader.wallet import sidepit_id_from_priv

VECTORS = {
    b"": "9c1185a5c5e9fc54612808977ee8f548b2258d31",
    b"abc": "8eb208f7e05d987a9b044a8e98c6b087f15a0bfc",
    b"message digest": "5d0689ef49d2fae572b881b123a85ffa21595f36",
    b"abcdefghijklmnopqrstuvwxyz": "f71c27109c692c1b56bbdceb5b9d2865b3708dbc",
    b"a" * 1000: hashlib.new("ripemd160", b"a" * 1000).hexdigest()
    if "ripemd160" in hashlib.algorithms_available else None,
}

# test key from the SDK's offline parity rig — never funded, never used live
RIG_PRIV = "91f50feda224198e7b226b57cc506ec924f20f3a4cb102e0a7af076b5cf6ff6c"
RIG_ADDR = "bc1qkucf363qyps6mr4ck34np9q7xg7zdewat9rtg5"


@pytest.mark.parametrize("msg,hexdigest", [(m, h) for m, h in VECTORS.items() if h])
def test_pure_python_matches_vectors(msg, hexdigest):
    assert rmd.ripemd160_pure(msg).hex() == hexdigest


@pytest.mark.parametrize("msg,hexdigest", [(m, h) for m, h in VECTORS.items() if h])
def test_default_path_matches_vectors(msg, hexdigest):
    assert rmd.ripemd160(msg).hex() == hexdigest


def test_fallback_is_taken_when_hashlib_lacks_ripemd160(monkeypatch):
    def no_ripemd(name, *a, **k):
        raise ValueError("unsupported hash type ripemd160")
    monkeypatch.setattr(rmd.hashlib, "new", no_ripemd)
    assert rmd.ripemd160(b"abc").hex() == VECTORS[b"abc"]
    # the whole address path survives on the fallback
    assert sidepit_id_from_priv(RIG_PRIV) == RIG_ADDR


def test_address_path_default():
    assert sidepit_id_from_priv(RIG_PRIV) == RIG_ADDR


def test_no_compiled_ripemd_dependency():
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[2]
    assert "ripemd-hash" not in (root / "pyproject.toml").read_text(encoding="utf-8")
    wallet_src = (root / "python-client/sidepit_trader/wallet.py").read_text(encoding="utf-8")
    assert "from ripemd" not in wallet_src
