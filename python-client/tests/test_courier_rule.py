"""Courier-rule + env-handoff tests — pure construction/refusal paths, NO network.

Covers SDK-USABILITY-REVIEW fix items 2 (CourierRuleError), 1 (signer_from_env
delegate semantics), 4 (pubkey-only register_delegate), 3 (secret-safe reprs).
Submitters are built without sockets (Submitter.__new__) — the courier gate
fires before any transport is touched.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from sidepit_trader import CourierRuleError, Signer, SidepitError, signer_from_env  # noqa: E402
from sidepit_trader import wallet  # noqa: E402
from sidepit_trader.submit import Submitter  # noqa: E402


@pytest.fixture(scope="module")
def custody():
    return wallet.gen_key()


@pytest.fixture(scope="module")
def hot():
    return wallet.gen_key()


def _submitter(signer: Signer) -> Submitter:
    """A Submitter with no push socket — only the signing gate is under test."""
    sub = Submitter.__new__(Submitter)
    sub._signer = signer
    return sub


# --- courier rule: delegate signer refused on every account verb -------------

def test_unlock_refused_for_delegate(custody, hot):
    sub = _submitter(Signer.as_delegate(hot.priv_hex, custody.sidepit_id))
    with pytest.raises(CourierRuleError):
        sub.unlock()


def test_register_delegate_refused_for_delegate(custody, hot):
    sub = _submitter(Signer.as_delegate(hot.priv_hex, custody.sidepit_id))
    with pytest.raises(CourierRuleError):
        sub.register_delegate(delegate_pubkey=hot.pubkey_hex)


def test_revoke_delegate_refused_for_delegate(custody, hot):
    sub = _submitter(Signer.as_delegate(hot.priv_hex, custody.sidepit_id))
    with pytest.raises(CourierRuleError):
        sub.revoke_delegate("ALL")


def test_courier_rule_error_is_valueerror_and_sidepit_error():
    # back-compat: pre-existing `except ValueError` handlers still catch it
    assert issubclass(CourierRuleError, ValueError)
    assert issubclass(CourierRuleError, SidepitError)


def test_direct_signer_account_sign_succeeds(custody):
    from sidepit_trader._proto import pb
    sub = _submitter(custody.signer())
    stx = sub._account_sign(pb.Transaction(version=1, timestamp=1))
    assert stx.transaction.sidepit_id == custody.sidepit_id
    assert stx.transaction.agent_id == ""
    assert stx.signature


# --- signer_from_env: delegate-vs-direct env parsing --------------------------

def test_env_direct_wif_only(monkeypatch, custody):
    monkeypatch.setenv("SIDEPIT_WIF", custody.wif)
    monkeypatch.delenv("SIDEPIT_ID", raising=False)
    monkeypatch.delenv("SIDEPIT_PRIV_HEX", raising=False)
    s = signer_from_env()
    assert s.sidepit_id == custody.sidepit_id
    assert s.trader_id == ""                      # direct: no agent stamp


def test_env_direct_matching_sidepit_id(monkeypatch, custody):
    monkeypatch.setenv("SIDEPIT_WIF", custody.wif)
    monkeypatch.setenv("SIDEPIT_ID", custody.sidepit_id)
    monkeypatch.delenv("SIDEPIT_PRIV_HEX", raising=False)
    s = signer_from_env()
    assert s.sidepit_id == custody.sidepit_id
    assert s.trader_id == ""


def test_env_delegate_custody_mismatch(monkeypatch, custody, hot):
    # THE locals handoff: agent WIF + custody SIDEPIT_ID => as_delegate signer
    monkeypatch.setenv("SIDEPIT_WIF", hot.wif)
    monkeypatch.setenv("SIDEPIT_ID", custody.sidepit_id)
    monkeypatch.delenv("SIDEPIT_PRIV_HEX", raising=False)
    s = signer_from_env()
    assert s.sidepit_id == custody.sidepit_id     # whose margin
    assert s.trader_id == hot.sidepit_id          # who signed
    from sidepit_trader._proto import pb
    stx = s.sign(pb.Transaction(version=1, timestamp=1))
    assert stx.transaction.sidepit_id == custody.sidepit_id
    assert stx.transaction.agent_id == hot.sidepit_id


def test_env_priv_hex_accepted(monkeypatch, hot):
    monkeypatch.delenv("SIDEPIT_WIF", raising=False)
    monkeypatch.delenv("SIDEPIT_ID", raising=False)
    monkeypatch.setenv("SIDEPIT_PRIV_HEX", hot.priv_hex)
    s = signer_from_env()
    assert s.sidepit_id == hot.sidepit_id and s.trader_id == ""


def test_env_missing_key_material_raises(monkeypatch):
    monkeypatch.delenv("SIDEPIT_WIF", raising=False)
    monkeypatch.delenv("SIDEPIT_PRIV_HEX", raising=False)
    monkeypatch.setenv("SIDEPIT_ID", "bc1qsomething")
    with pytest.raises(ValueError):
        signer_from_env()


def test_env_delegate_refused_on_account_verb(monkeypatch, custody, hot):
    # end-to-end refusal: env-built delegate signer hits the courier gate
    monkeypatch.setenv("SIDEPIT_WIF", hot.wif)
    monkeypatch.setenv("SIDEPIT_ID", custody.sidepit_id)
    monkeypatch.delenv("SIDEPIT_PRIV_HEX", raising=False)
    sub = _submitter(signer_from_env())
    with pytest.raises(CourierRuleError):
        sub.unlock()


# --- register_delegate: pubkey-only construction ------------------------------

def test_register_delegate_derives_trader_id(custody, hot):
    sub = _submitter(custody.signer())
    sent = []
    sub._door = lambda: type("Door", (), {"submit_delegate":
                                          staticmethod(sent.append)})()
    sub.register_delegate(delegate_pubkey=hot.pubkey_hex)
    assert sent[0].transaction.new_delegate.agent_id == hot.sidepit_id
    assert sent[0].transaction.new_delegate.agent_pubkey == hot.pubkey_hex


def test_register_delegate_mismatch_raises_before_send(custody, hot):
    sub = _submitter(custody.signer())
    sent = []
    sub._door = lambda: type("Door", (), {"submit_delegate":
                                          staticmethod(sent.append)})()
    with pytest.raises(ValueError):
        sub.register_delegate(custody.sidepit_id, hot.pubkey_hex)  # wrong address
    assert sent == []                              # nothing signed or sent


def test_register_delegate_requires_pubkey(custody, hot):
    sub = _submitter(custody.signer())
    with pytest.raises(ValueError):
        sub.register_delegate(hot.sidepit_id)      # address alone is refused


# --- secret safety -------------------------------------------------------------

def test_identity_repr_never_prints_secrets(custody):
    for rendered in (repr(custody), str(custody), f"{custody}"):
        assert custody.wif not in rendered
        assert custody.priv_hex not in rendered
        assert custody.sidepit_id in rendered
