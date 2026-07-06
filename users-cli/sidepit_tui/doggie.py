"""doggie // wallet — the consumer skin. The opposite end of the spectrum.

Per the design handoff's DoggieWallet section: TWO BUTTONS, BTC and USD. Each
tap shifts one unit of exposure between them; the user is choosing what
currency their wealth is measured in (a denomination dial), and all the
machinery — the inverse future, the 1s auction, the crossing — stays hidden.
Deliberately separate visual identity (orange/green on navy, big tactile
buttons); do not blend with the cockpit's hacker-green.

It is a SKIN over the same client core: same Bridge, same Snap, same
`market` command the cockpit prompt uses — proof the architecture supports
"cockpit view" and "doggie view" as two faces of one client (the handoff's
stated test of doing it right).

v0 honesty (the concept note marks mechanics TBD; the sim's $10k unit is NOT
decided product): here one tap = ONE contract (= $`Contract.unit_size`,
currently $500) via a marketable limit into the next auction. Mapping on the
inverse future: account equity starts 100% BTC (it IS bitcoin margin); being
LONG p contracts of USDBTC = holding $p×size synthetically = hedged; p past
your whole equity = net SHORT bitcoin; p negative = LEVERAGED long. Fully
hedged ⇒ the USD value freezes while price swings — visible right here on the
big number.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Digits, Static

# DoggieWallet palette (handoff: orange/green/navy — NOT the cockpit palette)
ORANGE = "#F7931A"
DGREEN = "#3FB950"
NAVY = "#0d1b2a"
NAVY2 = "#16283c"
INK = "#dfe9f3"
MUT = "#7d93ab"


class DoggieScreen(Screen):
    """ctrl+d toggles back to the cockpit. Reads app.snap on a timer; taps go
    through the same bridge `market` command as the cockpit prompt."""

    BINDINGS = [("ctrl+d", "app.pop_screen", "cockpit"),
                ("escape", "app.pop_screen", "cockpit")]

    DEFAULT_CSS = f"""
    DoggieScreen {{ background: {NAVY}; color: {INK}; align: center middle; }}
    #dog-frame {{ width: 76; height: auto; background: {NAVY2};
                  border: round {MUT}; padding: 1 4; }}
    #dog-title {{ text-align: center; color: {MUT}; height: 1; }}
    #dog-value {{ width: 1fr; color: {INK}; }}
    #dog-sub {{ text-align: center; color: {MUT}; height: 1; }}
    #dog-stance {{ text-align: center; height: 2; text-style: bold; }}
    #dog-meter {{ text-align: center; height: 2; }}
    #dog-buttons {{ height: 7; align: center middle; }}
    #tap-btc {{ width: 1fr; height: 7; background: {ORANGE}; color: {NAVY};
                text-style: bold; border: round {ORANGE}; margin: 0 1; }}
    #tap-usd {{ width: 1fr; height: 7; background: {DGREEN}; color: {NAVY};
                text-style: bold; border: round {DGREEN}; margin: 0 1; }}
    #tap-btc:hover, #tap-usd:hover {{ border: round {INK}; }}
    #dog-foot {{ text-align: center; color: {MUT}; height: 3; }}
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="dog-frame"):
            yield Static("doggie // wallet · v0 · mechanics TBD · ctrl+d = cockpit",
                         id="dog-title")
            yield Digits("0.00", id="dog-value")
            yield Static("", id="dog-sub")
            yield Static("", id="dog-stance")
            yield Static("", id="dog-meter")
            with Horizontal(id="dog-buttons"):
                yield Button("₿  BTC", id="tap-btc")
                yield Button("$  USD", id="tap-usd")
            yield Static("", id="dog-foot")

    def on_mount(self) -> None:
        self.set_interval(0.5, self._update_view)
        self._update_view()
        if self.app.snap.watch_only:
            self.query_one("#tap-btc", Button).disabled = True
            self.query_one("#tap-usd", Button).disabled = True

    # --- the denomination dial ------------------------------------------------
    def _equity_sats(self, s) -> int:
        """OPEN: available balance + realized + open P&L; CLOSED: the settled
        available balance, no math (pnl already folded in at settlement)."""
        from .app import equity_sats
        return equity_sats(s)[0]

    def _position(self, s) -> int:
        return sum(p["contracts"] for p in s.positions)

    def _update_view(self) -> None:
        s = self.app.snap
        eq = self._equity_sats(s)
        pos = self._position(s)
        hedged_usd = pos * s.contract_usd
        eq_usd = eq / s.last if s.last else 0.0          # sats ÷ sats-per-USD
        self.query_one("#dog-value", Digits).update(f"{eq_usd:,.2f}")
        self.query_one("#dog-sub", Static).update(
            f"[{MUT}]your wealth · ${eq_usd:,.2f} · {eq / 1e8:.5f} ₿ · "
            f"{'live' if s.is_open else s.state}[/]")
        # THE POSITION is the star. Jay's format:
        #   Position(p) SIDE <btc> BITCOIN $<usd>
        # p = the venue position in contracts (+ = long USD = hedging bitcoin);
        # side/amounts = your NET bitcoin exposure (balance minus the hedge):
        # p=0 still reads LONG — you're long the bitcoin you hold.
        net_usd = eq_usd - hedged_usd
        net_btc = net_usd * s.last / 1e8 if s.last else 0.0
        if pos != 0 and net_usd > eq_usd + 0.5:
            side, color = "LEVERAGED LONG", ORANGE   # exposure beyond your equity
        elif net_usd > 0.5:
            side, color = "LONG", ORANGE
        elif net_usd < -0.5:
            side, color = "SHORT", DGREEN
        else:
            side, color = "HEDGED", DGREEN
        btc_str = f"{abs(net_btc):.3f}".lstrip("0") or "0"
        stance = (f"{side} {btc_str} BITCOIN · ${abs(net_usd):,.0f}"
                  if side != "HEDGED" else "HEDGED · value frozen in USD")
        self.query_one("#dog-stance", Static).update(
            f"[{MUT}]position({pos})[/]  [{color}]{stance}[/]")
        frac = 1.0 - (hedged_usd / eq_usd) if eq_usd else 1.0
        width = 40
        marker = max(0, min(width - 1, int((frac + 0.5) / 2.0 * width)))
        bar = "".join("●" if i == marker else "─" for i in range(width))
        self.query_one("#dog-meter", Static).update(
            f"[{MUT}]short[/] [{color}]{bar}[/] [{MUT}]levered[/]")
        self.query_one("#dog-foot", Static).update(
            f"[{MUT}]one tap = ${s.contract_usd} (1 contract) into the next "
            f"1s auction[/]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        b = self.app.bridge
        s = self.app.snap
        if b is None or s.watch_only:
            return
        if not s.is_open:
            self.app.add_event("warn", "doggie: exchange is closed — tap ignored")
            return
        if event.button.id == "tap-usd":
            # toward dollars: hedge $unit more = BUY one USDBTC contract
            b.cmd("market", 1, 1)
            self.app.add_event("ok", f"doggie tap → USD (+${s.contract_usd} hedged)")
        elif event.button.id == "tap-btc":
            # toward bitcoin: unwind $unit of hedge = SELL one contract
            b.cmd("market", -1, 1)
            self.app.add_event("ok", f"doggie tap → BTC (−${s.contract_usd} hedged)")
