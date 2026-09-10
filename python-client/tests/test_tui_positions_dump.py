"""`sidepit positions [address]` dumps the raw POSITIONS reply — keyless, unprojected."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "users-cli"))

from sidepit_trader._proto import pb  # noqa: E402
from sidepit_tui import __main__ as cli  # noqa: E402


class _FakeClient:
    def __init__(self, host): self.host = host
    def positions(self, address):
        tpo = pb.TraderPositionOrders(traderid=address)
        tpo.accountstate.available_margin = 307_694
        return tpo
    def close(self): pass


def test_positions_dump_prints_raw_protobuf_text(monkeypatch, capsys):
    import sidepit_trader.reqrep as reqrep
    monkeypatch.setattr(reqrep, "RequestClient", _FakeClient)
    assert cli._cli(["positions", "bc1qexample"]) == 0
    out = capsys.readouterr().out
    assert "# POSITIONS bc1qexample via" in out
    assert 'traderid: "bc1qexample"' in out and "available_margin: 307694" in out


def test_positions_dump_needs_an_address_when_no_active_wallet(monkeypatch, capsys):
    from sidepit_trader import keystore
    monkeypatch.setattr(keystore, "active_identity", lambda: None)
    assert cli._cli(["positions"]) == 2
