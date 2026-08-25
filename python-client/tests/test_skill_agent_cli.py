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

    # Own-key mode (Jay 2026-08-25): the account key loads in direct mode.
    direct = _delegate_file(tmp_path / "owner.env", owner.sidepit_id, owner.wif)
    own = agent.load_delegate(str(direct))
    assert own.account == owner.sidepit_id
    assert own.agent_id == owner.sidepit_id


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
    market = agent._expectation(1, None, 1554, 1555, is_market=True)
    assert market.startswith("IOC MARKET")
    assert "cancels every unfilled remainder" in market
    assert "no price protection" in market
    assert "USD hedge" in agent._direction(1, 500, 2)


def test_records_are_write_once(tmp_path):
    path = tmp_path / "record.json"
    agent._write_once(path, {"public": "handle"})
    assert json.loads(path.read_text()) == {"public": "handle"}
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    with pytest.raises(FileExistsError):
        agent._write_once(path, {"public": "changed"})


def test_expired_preview_stops_before_key_or_network(tmp_path, monkeypatch):
    preview = {
        "schema": 1,
        "action": "order",
        "expires_ns": 1,  # long past
    }
    preview["preview_id"] = agent._preview_id(preview)
    path = tmp_path / "preview.json"
    path.write_text(json.dumps(preview))
    monkeypatch.setattr(agent, "load_delegate",
                        lambda _path: pytest.fail("key must not load for an expired preview"))
    args = SimpleNamespace(preview_file=str(path), key_file="unused")
    with pytest.raises(agent.Stop, match="expired"):
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
        key_file="unused", side="buy", contracts=1, limit_price=1547, market=False,
        fee_sats=0, fee_source="current published beta terms 2026-08-17",
        expires_seconds=300,
    )
    assert agent.cmd_preview_order(args) == 0
    out = capsys.readouterr().out
    assert "ORDER PREVIEW — NOTHING SENT" in out
    assert "LIMIT BUY 1 contract(s) @ 1547" in out
    assert "200,000 sats additional allowance" in out
    files = list((tmp_path / "state").glob("order-preview-*.json"))
    assert len(files) == 1
    payload = json.loads(files[0].read_text())
    assert payload["projected_position"] == 1
    assert payload["order_type"] == "limit"
    assert payload["fee_sats"] == 0


def test_market_preview_has_no_limit_and_is_explicit_ioc(capsys):
    delegate = SimpleNamespace(account="bc1q-account", agent_id="bc1q-agent")
    accountstate = SimpleNamespace(available_margin=500_000, contract_margins={})
    tp = SimpleNamespace(accountstate=accountstate)
    market = {
        "ticker": "USDBTCU26", "bid": 1547, "ask": 1548, "last": 1548,
        "unit_usd": 500, "initial_margin_sats": 200_000,
    }
    args = SimpleNamespace(
        side="buy", contracts=1, limit_price=None, market=True,
        fee_sats=0, fee_source="current terms", expires_seconds=300,
    )
    payload = agent._order_payload(args, delegate, market, tp)
    assert payload["order_type"] == "market"
    assert payload["limit_price"] is None
    assert payload["reference_price"] == 1548
    assert payload["btc_equivalent_sats_at_reference"] == 774_000
    assert payload["expectation"].startswith("IOC MARKET")
    agent._print_order_preview(payload)
    out = capsys.readouterr().out
    assert "IOC MARKET BUY 1 contract(s)" in out
    assert "no limit price (wire price 0)" in out
    assert "no price protection" in out


def test_preview_parser_requires_limit_price_or_market():
    parser = agent.parser()
    common = [
        "preview-order", "--key-file", "/key", "--side", "buy",
        "--contracts", "1", "--fee-sats", "0", "--fee-source", "terms",
    ]
    market = parser.parse_args(common + ["--market"])
    assert market.market is True
    assert market.limit_price is None
    limit = parser.parse_args(common + ["--limit-price", "1548"])
    assert limit.market is False
    assert limit.limit_price == 1548
    with pytest.raises(SystemExit):
        parser.parse_args(common)


def test_ioc_results_distinguish_partial_and_unfilled_cancels():
    partial_order = SimpleNamespace(
        remaining_qty=0, filled_qty=1, canceled_qty=2, avg_price=1548.0,
    )
    partial = SimpleNamespace(
        orderfills={"oid": SimpleNamespace(order=partial_order)},
    )
    assert agent._result_for_order(partial, "oid") == (
        "PARTIAL FILL — 1 filled @ 1548.00; 2 remainder canceled"
    )

    canceled_order = SimpleNamespace(
        remaining_qty=0, filled_qty=0, canceled_qty=3, avg_price=0.0,
    )
    canceled = SimpleNamespace(
        orderfills={"oid": SimpleNamespace(order=canceled_order)},
    )
    assert agent._result_for_order(canceled, "oid") == (
        "CANCELED — 3 unfilled contract(s) canceled"
    )


def test_market_send_dispatches_without_a_limit_price():
    class FakeSubmitter:
        def market_order(self, side, contracts, ticker, timestamp_ns=None):
            assert (side, contracts, ticker, timestamp_ns) == (1, 2, "USDBTCU26", 123)
            return "account:123"

        def new_order(self, *_args, **_kwargs):
            pytest.fail("market preview must not dispatch a limit order")

    preview = {
        "order_type": "market", "side": 1, "contracts": 2,
        "ticker": "USDBTCU26", "limit_price": None,
    }
    assert agent._submit_preview(FakeSubmitter(), preview, 123) == "account:123"


def test_fee_defaults_to_published_schedule():
    # omitted fee → schedule: 125 sats/contract/side, source names the schedule
    args = SimpleNamespace(fee_sats=None, fee_source="")
    agent._fee_defaults(args, 3)
    assert args.fee_sats == 375
    assert "execution-fee schedule" in args.fee_source
    assert "125" in args.fee_source
    # sourced override passes through untouched
    args = SimpleNamespace(fee_sats=0, fee_source="beta terms 2026-08-17")
    agent._fee_defaults(args, 3)
    assert args.fee_sats == 0 and args.fee_source == "beta terms 2026-08-17"
    # unsourced override is refused
    with pytest.raises(agent.Stop, match="fee-source"):
        agent._fee_defaults(SimpleNamespace(fee_sats=99, fee_source=""), 1)


def test_fee_flags_are_optional_in_both_parsers():
    p = agent.build_parser() if hasattr(agent, "build_parser") else None
    if p is None:
        import inspect
        src = inspect.getsource(agent)
        assert 'q.add_argument("--fee-sats", type=int, default=None' in src
        assert src.count("--fee-sats") >= 2   # preview-order + preview-flatten
