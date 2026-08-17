"""Offline safety tests for the customer-facing delegate command."""
import importlib.util
import json
import stat
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from sidepit_trader.wallet import gen_key


SCRIPT = (Path(__file__).resolve().parents[2] / "skills" / "sidepit-trade" /
          "scripts" / "sidepit_agent.py")
SPEC = importlib.util.spec_from_file_location("sidepit_agent_skill", SCRIPT)
agent = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = agent
SPEC.loader.exec_module(agent)


def _delegate_file(path: Path, account: str, wif: str, mode: int = 0o600) -> Path:
    path.write_text(f"export SIDEPIT_ID={account}\nexport SIDEPIT_WIF={wif}\n")
    path.chmod(mode)
    return path


def test_delegate_loader_accepts_only_distinct_0600_key(tmp_path):
    owner = gen_key()
    hot = gen_key()
    path = _delegate_file(tmp_path / "agent.env", owner.sidepit_id, hot.wif)
    loaded = agent.load_delegate(str(path))
    assert loaded.account == owner.sidepit_id
    assert loaded.agent_id == hot.sidepit_id
    assert stat.S_IMODE(path.stat().st_mode) == 0o600

    direct = _delegate_file(tmp_path / "owner.env", owner.sidepit_id, owner.wif)
    with pytest.raises(agent.Stop, match="account key, not a delegate"):
        agent.load_delegate(str(direct))


def test_delegate_loader_rejects_loose_permissions(tmp_path):
    owner = gen_key()
    hot = gen_key()
    path = _delegate_file(tmp_path / "loose.env", owner.sidepit_id, hot.wif, 0o640)
    with pytest.raises(agent.Stop, match="expected 0600"):
        agent.load_delegate(str(path))


def test_preview_identity_is_stable_and_expectation_is_explicit():
    payload = {"side": 1, "size": 1, "price": 1555}
    assert agent._preview_id(payload) == agent._preview_id(dict(payload))
    assert agent._expectation(1, 1555, 1554, 1555).startswith("MARKETABLE")
    assert agent._expectation(1, 1554, 1554, 1555).startswith("RESTING")
    assert agent._expectation(-1, 1554, 1554, 1555).startswith("MARKETABLE")
    assert "USD hedge" in agent._direction(1, 500, 2)


def test_records_are_write_once(tmp_path):
    path = tmp_path / "record.json"
    agent._write_once(path, {"public": "handle"})
    assert json.loads(path.read_text()) == {"public": "handle"}
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    with pytest.raises(FileExistsError):
        agent._write_once(path, {"public": "changed"})


def test_wrong_confirmation_stops_before_key_or_network(tmp_path, monkeypatch):
    preview = {
        "schema": 1,
        "action": "order",
    }
    preview["preview_id"] = agent._preview_id(preview)
    path = tmp_path / "preview.json"
    path.write_text(json.dumps(preview))
    monkeypatch.setattr(agent, "load_delegate",
                        lambda _path: pytest.fail("key must not load before confirmation"))
    args = SimpleNamespace(preview_file=str(path), confirm="yes", key_file="unused")
    with pytest.raises(agent.Stop, match=f"expected exactly: CONFIRM {preview['preview_id']}"):
        agent.cmd_send_order(args)


def test_tampered_preview_is_rejected(tmp_path):
    preview = {"schema": 1, "action": "order", "contracts": 1}
    preview["preview_id"] = agent._preview_id(preview)
    preview["contracts"] = 100
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(preview))
    with pytest.raises(agent.Stop, match="integrity check failed"):
        agent._read_record(str(path), "order")


def test_preview_writes_public_gate_and_never_constructs_submitter(
        tmp_path, monkeypatch, capsys):
    delegate = SimpleNamespace(account="bc1q-account", agent_id="bc1q-agent",
                               path=tmp_path / "agent.env", signer=None)
    accountstate = SimpleNamespace(available_margin=500_000, contract_margins={})
    tp = SimpleNamespace(accountstate=accountstate)
    market = {
        "state": "EXCHANGE_OPEN", "ticker": "USDBTCU26",
        "bid": 1547, "ask": 1548, "last": 1548,
        "unit_usd": 500, "initial_margin_sats": 200_000,
    }
    req = SimpleNamespace(close=lambda: None)
    monkeypatch.setattr(agent, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(agent, "load_delegate", lambda _path: delegate)
    monkeypatch.setattr(agent, "_new_req", lambda: req)
    monkeypatch.setattr(agent, "market_snapshot", lambda _req: market)
    monkeypatch.setattr(agent, "require_active", lambda _req, _delegate: tp)
    monkeypatch.setattr(agent, "Submitter",
                        lambda *_a, **_k: pytest.fail("preview must never construct Submitter"))
    args = SimpleNamespace(
        key_file="unused", side="buy", contracts=1, limit_price=1547,
        fee_sats=0, fee_source="current published beta terms 2026-08-17",
        expires_seconds=300,
    )
    assert agent.cmd_preview_order(args) == 0
    out = capsys.readouterr().out
    assert "ORDER PREVIEW — NOTHING SENT" in out
    assert "BUY 1 contract(s) @ 1547" in out
    assert "200,000 sats additional allowance" in out
    files = list((tmp_path / "state").glob("order-preview-*.json"))
    assert len(files) == 1
    payload = json.loads(files[0].read_text())
    assert payload["projected_position"] == 1
    assert payload["fee_sats"] == 0
