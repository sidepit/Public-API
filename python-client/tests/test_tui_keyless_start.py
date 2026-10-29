"""The cockpit starts with no identity at all: market first, keys optional.

Jay 2026-10-28: "the ability to start without any keys — now it forces a watch
address — can we do without that?" First run starts the bridge keyless (price,
bars, book, auction clock) and shows the identity doors on top; Escape or
"just look" dismisses them to a live, read-only cockpit. ctrl+a adds an
identity later. A keyless bridge never polls the account door, the chain, or
the rejection feed — there is no address to ask about.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve()
                       .parents[2] / "users-cli"))

from sidepit_tui import onboard  # noqa: E402
from sidepit_tui.bridge import Bridge  # noqa: E402


class _App:
    def __init__(self):
        self.started = []
        self.screens = []
        self.bridge = None

    def start_bridge(self, address, wif, name=None):
        self.started.append((address, wif, name))
        self.bridge = object()

    def push_screen(self, screen):
        self.screens.append(type(screen).__name__)


def test_first_run_starts_keyless_then_offers_identity(monkeypatch):
    monkeypatch.setattr(onboard.keystore, "active_identity", lambda: None)
    app = _App()
    onboard.load_or_onboard(app)
    assert app.started == [("", None, None)]          # market is live, no key
    assert app.screens == ["OnboardScreen"]           # doors offered, not forced


def test_active_identity_skips_onboarding(monkeypatch):
    monkeypatch.setattr(onboard.keystore, "active_identity",
                        lambda: {"sidepit_id": "bc1qme", "wif": None, "name": "w"})
    app = _App()
    onboard.load_or_onboard(app)
    assert app.started == [("bc1qme", None, "w")]
    assert app.screens == []


def test_keyless_bridge_never_asks_about_an_account():
    b = Bridge("example.invalid", on_snap=lambda s: None,
               on_event=lambda k, t: None)
    b.set_identity("", None)
    assert b.snap.watch_only and b.snap.address == ""

    def forbidden(*a, **k):
        raise AssertionError("keyless bridge touched an account door")
    b._poll_account = forbidden
    b._poll_chain = forbidden
    b._rq = forbidden
    b._poll_exchange = lambda: None
    b._last = {"quote": -1e9, "account": -1e9, "chain": -1e9}
    b._tick()                                         # would poll everything due
    b._drain_rejections()                             # no address → no feed
    assert b._rejects is None
