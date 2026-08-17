"""The deterministic delegate-key mint contract (agent_key) — offline.

Pins the 8-point contract from the first customer-sim run: validate account
first, unique 0600 non-overwriting file, bind to the account, verify after
write, public output only, nonzero exit + no file on bad input.
"""
import stat

import pytest

from sidepit_trader import agent_key, keystore
from sidepit_trader.wallet import gen_key

ACCT = "bc1qn9szw2tfte4m2l7enhentvjpvnque932xr2m03"   # valid P2WPKH shape


@pytest.fixture
def keys_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(keystore, "KEYS_DIR", tmp_path)
    monkeypatch.setattr(keystore, "ACTIVE_FILE", tmp_path / "ACTIVE")
    monkeypatch.setattr(keystore, "_migrated", True)   # no sqlite migration probe
    return tmp_path


def test_invalid_account_rejected_before_any_write(keys_dir):
    for bad in ("", "notanaddress", "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",
                "bc1qtooshort"):
        with pytest.raises(ValueError):
            agent_key.mint(bad)
    assert list(keys_dir.glob("*.env")) == []          # nothing written


def test_mint_binds_account_0600_and_returns_public_only(keys_dir):
    r = agent_key.mint(ACCT)
    assert set(r) == {"pubkey", "trader_id", "account", "path"}
    assert r["account"] == ACCT
    assert len(r["pubkey"]) == 66 and r["pubkey"][:2] in ("02", "03")
    assert r["trader_id"].startswith("bc1q") and r["trader_id"] != ACCT
    p = keys_dir / f"agent-{r['trader_id'][-8:]}.env"
    assert str(p) == r["path"] and p.exists()
    assert stat.S_IMODE(p.stat().st_mode) == 0o600
    d = keystore._parse(p)
    assert d["SIDEPIT_ID"] == ACCT                     # delegate-mode binding
    assert "SIDEPIT_WIF" in d
    # the WIF must not appear anywhere in the public result
    assert d["SIDEPIT_WIF"] not in str(r)


def test_mint_never_steals_active_identity(keys_dir):
    keystore.save_identity("owner", ACCT, gen_key().wif, active=True)
    agent_key.mint(ACCT)
    assert keystore.active_name() == "owner"


def test_mint_never_overwrites(keys_dir):
    from pathlib import Path
    a = agent_key.mint(ACCT)
    b = agent_key.mint(ACCT)                           # different key, new file
    assert a["path"] != b["path"]
    wif_a = keystore._parse(Path(a["path"]))["SIDEPIT_WIF"]
    wif_b = keystore._parse(Path(b["path"]))["SIDEPIT_WIF"]
    assert wif_a != wif_b                              # first key untouched


def test_cli_public_output_only(keys_dir, capsys):
    rc = agent_key._cli(["new", "--account", ACCT])
    out = capsys.readouterr()
    assert rc == 0
    files = list(keys_dir.glob("agent-*.env"))
    assert len(files) == 1
    wif = keystore._parse(files[0])["SIDEPIT_WIF"]
    assert wif not in out.out and wif not in out.err
    assert "pubkey" in out.out and "trader_id" in out.out

    assert agent_key._cli(["--help"]) == 0
    assert agent_key._cli(["frobnicate"]) == 2
    assert agent_key._cli(["new", "--account", "garbage"]) == 1
    assert len(list(keys_dir.glob("agent-*.env"))) == 1   # failures wrote nothing
