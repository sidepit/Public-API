"""sidepit // cockpit — the human terminal over the sidepit_trader SDK.

Implements the TUI-Design-Handoff (2026-06-10): three-panel cockpit, prompt +
tagged-log loop as the primary surface, transparent 5-level book with depth
shading and the DLOB one-second deterministic-auction countdown,
BTC-denominated risk envelope.
Where the mockup and the real exchange disagree, the real exchange wins:
dated inverse forwards (no perps), 1s epochs (no µs theater), and honest
delegation status instead of fictional ML-KEM pairing.

Three tabs: the cockpit, fund (deposit→LOCK, UNLOCK withdraw with the
full lifecycle), and delegates (mint an agent key, appoint, revoke) —
the last two are the onboarding surface the handoff leaves to us.

All exchange I/O lives in bridge.py on its own thread; this module is pure UI.
Log grammar: `HH:MM:SS [tag] message` — [sys] cyan · [cmd] gold · [fill]/[ok]
green · [warn] gold · [err] red.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from textual import events
from textual.app import App, ComposeResult
from textual.containers import Container, Grid, Horizontal, Vertical
from textual.coordinate import Coordinate
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import (Button, DataTable, Input, Label, RichLog, Select,
                             Static, TabbedContent, TabPane)

from .bridge import Bridge, Snap
from .intents import HELP, Intent, parse

HOST_DEFAULT = "api.sidepit.com"

# palette (TUI-Design-Handoff — restrained phosphor green + warm action gold)
BG = "#0a0e0a"
PANEL = "#0e140e"
BGCARD = "#101810"
BORDER = "#1a2620"
TEXT = "#b8c4b0"
DIM = "#5a6a55"
BRIGHT = "#e8f0d8"
GREEN = "#6fcf6f"
GREEN_DIM = "#3a6a3a"
GOLD = "#c9a84c"
RED = "#c45b4a"
RED_DIM = "#6e352b"
CYAN = "#5ab4c4"

TRY_PROMPTS = [
    "show me the book before i send",
    "what's my risk in btc terms",
    "buy 1 at market",
    "cancel all working orders",
    "go flat and exit",
]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def ui_update(fn):
    """Interval/bridge-driven UI refreshers race app teardown: a timer can fire
    while the base screen's widgets are unmounting and query_one raises
    NoMatches. Nothing to update then — swallow and exit."""
    def inner(self, *a, **k):
        try:
            return fn(self, *a, **k)
        except NoMatches:
            pass
    return inner


def btc(v_sats: int, signed: bool = False) -> str:
    s = v_sats / 1e8
    return f"{s:+.5f} ₿" if signed else f"{s:.5f} ₿"


def equity_sats(s) -> tuple[int, int]:
    """(equity, open_pnl) in sats. While OPEN: available balance + realized +
    open P&L. While CLOSED: just the settled available balance — the daily
    mark-to-market already folded the pnl in, so no math."""
    if not s.is_open:
        return s.available_balance, 0
    unreal = 0
    for p in s.positions:
        if p["contracts"] and s.last and p["entry_price"]:
            unreal += int(p["contracts"] * (s.last - p["entry_price"])
                          * s.tick_value_sats / max(s.tick_size_sats, 1))
    return s.available_balance + s.realized_pnl + unreal, unreal


def usd_hint(price_sats: int) -> str:
    """sats-per-USD → the $/BTC a human recognizes."""
    if price_sats <= 0:
        return "—"
    return f"${1e8 / price_sats:,.0f}/BTC"


def title(text: str) -> str:
    """Track short labels for the cockpit feel; keep long headings unbroken."""
    label = text.lower()
    if len(label) <= 16:
        label = " ".join(label)
    return f"[{DIM}]──[/] [bold {BRIGHT}]{label}[/] [{DIM}]──[/]"


def qr_unicode(data: str) -> str:
    """Half-height unicode QR (▀▄█), scannable from most terminals."""
    import qrcode
    qr = qrcode.QRCode(border=1)
    qr.add_data(data)
    qr.make(fit=True)
    m = [list(row) for row in qr.get_matrix()]
    if len(m) % 2:
        m.append([False] * len(m[0]))
    lines = []
    for y in range(0, len(m), 2):
        line = ""
        for x in range(len(m[0])):
            top, bot = m[y][x], m[y + 1][x]
            line += "█" if top and bot else "▀" if top else "▄" if bot else " "
        lines.append(line)
    return "\n".join(lines)


def hhmm_left(close_ms: int) -> str:
    left = close_ms / 1000 - time.time()
    if left <= 0:
        return ""
    h, rem = divmod(int(left), 3600)
    return f"{h}h{rem // 60:02d}m" if h else f"{rem // 60}m{rem % 60:02d}s"


class WorkingOrders(DataTable):
    """Open orders with right-click = cancel (the pit gesture). Left click just
    selects; the cancel rides the same bridge command as the prompt's."""

    def on_click(self, event: events.Click) -> None:
        if event.button != 3:          # right button only
            return
        event.stop()
        if self.hover_row < 0:
            return
        try:
            oid = self.coordinate_to_cell_key(
                Coordinate(self.hover_row, 0)).row_key.value
        except Exception:
            return
        self.app.right_click_cancel(oid)


# ---------------------------------------------------------------------------
# modals
# ---------------------------------------------------------------------------
class Confirm(ModalScreen[bool]):
    """Yes/no gate for the button paths that move money."""

    def __init__(self, text: str, yes: str = "Confirm"):
        super().__init__()
        self._text = text
        self._yes = yes

    def compose(self) -> ComposeResult:
        with Grid(id="confirm-grid"):
            yield Label(self._text, id="confirm-text")
            yield Button(self._yes, variant="error", id="yes")
            yield Button("Cancel", variant="default", id="no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")


class ShowSecret(ModalScreen[None]):
    """One-time display of a freshly minted key. Never logged anywhere."""

    def __init__(self, title_text: str, body: str):
        super().__init__()
        self._title = title_text
        self._body = body

    def compose(self) -> ComposeResult:
        with Grid(id="secret-grid"):
            yield Label(f"[b]{self._title}[/b]", id="secret-title")
            yield Static(self._body, id="secret-body")
            yield Button("I saved it — close", variant="primary", id="done")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)


# ---------------------------------------------------------------------------
# app
# ---------------------------------------------------------------------------
class SidepitApp(App):
    TITLE = "sidepit // cockpit"
    BINDINGS = [("ctrl+q", "quit", "quit"), ("ctrl+r", "refresh", "refresh"),
                ("ctrl+a", "accounts", "accounts"),
                ("ctrl+d", "doggie", "doggie view")]
    CSS = f"""
    Screen {{ background: {BG}; color: {TEXT}; }}
    #topbar {{ height: 3; background: {PANEL}; border-bottom: solid {BORDER};
               align-vertical: middle; }}
    #titlebar {{ height: 3; width: 1fr; background: {PANEL}; color: {DIM};
                 padding: 0 1; content-align-vertical: middle; }}
    #wallet-pick {{ width: 30; height: 1; background: {PANEL}; }}
    #denom-pick {{ width: 12; height: 1; background: {PANEL}; }}
    #wallet-pick SelectCurrent, #denom-pick SelectCurrent {{ height: 1; border: none;
                                                            background: {PANEL};
                                                            color: {GOLD}; }}
    #wallet-pick SelectOverlay, #denom-pick SelectOverlay {{ border: tall {GOLD}; }}
    #statbar  {{ height: 1; background: {PANEL}; color: {DIM}; padding: 0 1; }}
    TabbedContent {{ height: 1fr; }}
    Tabs {{ background: {BG}; }}
    .panel {{ border: solid {BORDER}; background: {PANEL}; padding: 0 1;
              height: auto; }}
    #left  {{ width: 36; height: 1fr; background: #0c110c; padding: 0 1; }}
    #mid   {{ width: 1fr; height: 1fr; margin: 0 1; }}
    #right {{ width: 38; height: 1fr; background: #0c110c; padding: 0 1; }}
    .paneltitle {{ margin-top: 1; }}
    #envelope {{ border: solid {GREEN_DIM}; background: {PANEL}; padding: 0 1;
                 height: auto; }}
    #book {{ height: auto; }}
    #activity-title {{ height: 1; margin-top: 1; }}
    #log {{ height: 1fr; min-height: 9; background: {PANEL};
            border: solid {BORDER}; padding: 0 1; }}
    #promptrow {{ height: 3; background: {BGCARD}; border: solid {GREEN_DIM};
                  padding: 0 1; align-vertical: middle; }}
    #promptlabel {{ width: 19; height: 1; color: {GREEN}; background: {BGCARD};
                    text-style: bold; }}
    #prompt {{ width: 1fr; height: 1; background: {BGCARD}; border: none;
               color: {BRIGHT}; }}
    #prompt:focus {{ border: none; }}
    #prompt .input--placeholder {{ color: {DIM}; text-style: italic; }}
    #prompt .input--cursor {{ background: {GREEN}; color: {BG}; }}
    #prompt .input--selection {{ background: {GREEN_DIM}; }}
    .try {{ height: 1; padding: 0; min-width: 0; border: none;
            background: {PANEL}; color: {DIM}; text-align: left; }}
    .try:hover {{ color: {BRIGHT}; }}
    DataTable {{ height: auto; max-height: 12; background: {PANEL}; }}
    DataTable > .datatable--header {{ background: {PANEL}; color: {DIM};
                                      text-style: none; }}
    DataTable > .datatable--cursor {{ background: {BORDER}; }}
    DataTable > .datatable--hover {{ background: {BORDER}; }}
    Tab {{ color: {DIM}; }}
    Tab.-active {{ color: {BRIGHT}; text-style: bold; }}
    Underline > .underline--bar {{ color: {GREEN_DIM}; }}
    #working {{ background: {PANEL}; border: solid {BORDER}; }}
    .hint {{ color: {DIM}; height: auto; }}
    .flow-shell {{ width: 120; max-width: 100%; height: auto; align-horizontal: center;
                   margin-top: 1; }}
    .flow-row {{ width: 120; max-width: 100%; height: auto; align-horizontal: center; }}
    .flow-card {{ width: 58; max-width: 50%; height: auto; margin: 0 1;
                  padding: 1 2; border: solid {BORDER}; background: {BGCARD};
                  overflow: hidden hidden; }}
    .flow-card .paneltitle {{ margin-top: 0; }}
    #tab-fund, #tab-withdraw, #tab-delegates {{ align: center top; }}
    #fund-state {{ width: 116; max-width: 100%; margin: 1 1 0 1; }}
    #delegate-shell {{ width: 112; max-width: 100%; height: auto;
                       align-horizontal: center; margin-top: 1; }}
    #delegate-card {{ width: 112; max-width: 100%; height: auto; padding: 1 2;
                      border: solid {BORDER}; background: {BGCARD}; }}
    .formrow {{ width: 52; max-width: 100%; height: 3; }}
    .bigbtn {{ width: 52; max-width: 100%; min-width: 0; height: 3; text-style: bold;
               margin: 0 0 0 0; }}
    .formrow Input {{ width: 1fr; min-width: 0; }}
    .formrow Button {{ width: auto; min-width: 16; }}
    /* the amount row is a STEP, not a footnote: label above, full-width
       field with a gold edge so the eye lands on it before the button */
    .fieldlabel {{ height: 1; margin-top: 1; }}
    .amtrow {{ width: 52; max-width: 100%; height: 3; }}
    .amtrow Input {{ width: 1fr; min-width: 0; border: tall {GOLD};
                     background: {BG}; }}
    .amtrow Input:focus {{ border: tall {BRIGHT}; }}
    .chip {{ width: 9; height: 3; margin-left: 1; }}
    #confirm-grid, #secret-grid {{
        grid-size: 2; grid-gutter: 1 2; grid-rows: auto auto;
        padding: 1 2; width: 72; height: auto;
        border: solid {GOLD}; background: {PANEL};
    }}
    #confirm-text, #secret-title, #secret-body {{ column-span: 2; }}
    #secret-grid {{ width: 86; }}
    #qr {{ width: auto; color: {BRIGHT}; }}
    """

    def __init__(self, host: str = HOST_DEFAULT):
        super().__init__()
        self.host = host
        self.bridge: Bridge | None = None
        self.snap = Snap()
        self.denom = "BTC"

    def _q(self, selector, _type=None):
        """Query the BASE screen — widget updates must keep landing while a
        modal or the doggie skin sits on top of the stack (self.query_one
        targets the top screen and would raise NoMatches there)."""
        base = self.screen_stack[0]
        return base.query_one(selector) if _type is None else base.query_one(selector, _type)

    def money(self, v_sats: int, signed: bool = False) -> str:
        """Format a satoshi amount in the user's global display denomination."""
        if self.denom == "SATS":
            sign = "+" if signed and v_sats >= 0 else ""
            return f"{sign}{v_sats:,} sats"
        return btc(v_sats, signed=signed)

    @staticmethod
    def _parse_money_input(raw: str, denom: str) -> int | None:
        """Unlock text → sats. Blank and MAX both mean the full amount."""
        value = raw.strip().replace(",", "")
        if not value or value.upper() == "MAX":
            return None
        if denom == "SATS":
            if not value.isdigit() or int(value) <= 0:
                raise ValueError("enter a positive whole number of sats")
            return int(value)
        try:
            amount = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("enter a positive BTC amount") from exc
        if not amount.is_finite():
            raise ValueError("enter a positive BTC amount")
        sats_exact = amount * Decimal(100_000_000)
        if amount <= 0 or sats_exact != sats_exact.to_integral_value():
            raise ValueError("BTC supports at most 8 decimal places")
        return int(sats_exact)

    @staticmethod
    def _money_input(v_sats: int, denom: str) -> str:
        if denom == "SATS":
            return f"{v_sats:,}"
        return format(Decimal(v_sats) / Decimal(100_000_000), "f")

    # --- composition --------------------------------------------------------
    def compose(self) -> ComposeResult:
        with Horizontal(id="topbar"):
            yield Static("sidepit // cockpit · connecting…", id="titlebar")
            # Always-visible wallet switcher — ctrl+a still opens the full
            # table, but nobody has to know the shortcut exists.
            yield Select([("₿ BTC", "BTC"), ("sat SATS", "SATS")], value="BTC",
                         id="denom-pick", allow_blank=False)
            yield Select([], id="wallet-pick", prompt="wallet", allow_blank=True)
        with TabbedContent(initial="tab-cockpit"):
            with TabPane("cockpit", id="tab-cockpit"):
                with Horizontal(id="cockpit-grid"):
                    with Vertical(id="left"):
                        yield Static(title("positions"), classes="paneltitle")
                        yield Static("", id="positions", classes="panel")
                        yield Static("", id="envelope")
                    with Vertical(id="mid"):
                        yield Static("", id="book", classes="panel")
                        yield Static(title("activity"), id="activity-title")
                        yield RichLog(markup=True, wrap=True, id="log")
                        with Horizontal(id="promptrow"):
                            yield Label("trader@sidepit ›", id="promptlabel")
                            yield Input(placeholder='say what you want. plain english. '
                                                    'e.g. "go flat and exit"',
                                        id="prompt")
                    with Vertical(id="right"):
                        yield Static(title("session"), classes="paneltitle")
                        yield Static("", id="session", classes="panel")
                        yield Static(title("working orders"), classes="paneltitle")
                        yield WorkingOrders(id="working")
                        yield Static(f"[{DIM}]right-click a row to cancel[/]",
                                     classes="hint")
                        yield Static(title("try"), classes="paneltitle")
                        for i, p in enumerate(TRY_PROMPTS):
                            yield Button(f"› {p}", classes="try", id=f"try-{i}")
            with TabPane("fund", id="tab-fund"):
                with Horizontal(id="fund-flow", classes="flow-shell"):
                    with Vertical(classes="flow-card"):
                        yield Static(title("1 · fund"), classes="paneltitle")
                        yield Button("FUND — send btc to this address",
                                     id="fund-show", classes="bigbtn")
                        yield Static("", id="deposit")
                        yield Static("", id="qr")
                        yield Button("refresh on-chain", id="chain-refresh")
                    with Vertical(classes="flow-card"):
                        yield Static(title("2 · lock"), classes="paneltitle")
                        yield Button("LOCK — fund the account", id="lock-all",
                                     classes="bigbtn")
                        yield Static("", id="lock-status", classes="hint")
                        yield Static(f"[{DIM}]money OUT (unlock · exit) lives on "
                                     f"the withdraw tab[/]", classes="hint")
            with TabPane("withdraw", id="tab-withdraw"):
                with Vertical(id="withdraw-flow", classes="flow-shell"):
                    with Horizontal(classes="flow-row"):
                        with Container(classes="flow-card"):
                            yield Static(title("1 · unlock"), classes="paneltitle")
                            yield Static(f"[{BRIGHT}]how much?[/]  "
                                         f"[{DIM}]leave it empty for everything[/]",
                                         classes="fieldlabel")
                            with Horizontal(classes="amtrow"):
                                yield Input(placeholder="BTC (e.g. 0.005)",
                                            id="unlock-amt")
                                yield Button("MAX", id="unlock-max",
                                             classes="chip")
                            yield Button("UNLOCK — request funds back",
                                         id="unlock-all", classes="bigbtn")
                            yield Static("", id="unlock-status", classes="hint")
                        with Container(classes="flow-card"):
                            yield Static(title("2 · exit"), classes="paneltitle")
                            with Horizontal(classes="formrow"):
                                yield Input(placeholder="destination bc1q… address",
                                            id="exit-dest")
                            yield Button("EXIT — leave sidepit", id="exit-all",
                                         classes="bigbtn")
                            yield Static("", id="exit-status", classes="hint")
                    yield Static("", id="fund-state", classes="panel")
            with TabPane("delegates", id="tab-delegates"):
                with Vertical(id="delegate-shell"):
                    with Container(id="delegate-card"):
                        yield Static(title("delegated trading"), classes="paneltitle")
                        yield Label(f"[{DIM}]the custody key appoints; a delegate can "
                                    f"trade, but can never appoint, revoke, or withdraw[/]")
                        yield DataTable(id="delegates")
                        with Horizontal(classes="formrow"):
                            yield Button("mint agent key", variant="primary", id="mint")
                            yield Button("revoke selected", variant="warning", id="revoke")
                        yield Static(title("register a delegate"), classes="paneltitle")
                        with Horizontal(classes="formrow"):
                            yield Input(placeholder="delegate pubkey (33-byte hex) — "
                                                    "address is derived, never typed",
                                        id="del-pub")
                            yield Button("register", variant="success", id="register")
                        yield Static("", id="del-derived")
        yield Static("", id="statbar")

    open_doggie_on_start = False       # set by `sidepit doggie`

    def on_mount(self) -> None:
        self.refresh_wallets()
        if self.open_doggie_on_start:
            # after onboarding/bridge start, so the view opens with live state
            self.call_after_refresh(self.action_doggie)
        w = self._q("#working", WorkingOrders)
        w.add_columns("side", "qty", "px", "id")
        w.cursor_type = "row"
        d = self._q("#delegates", DataTable)
        d.add_columns("trader_id", "status", "active", "pending")
        d.cursor_type = "row"
        self.set_interval(0.25, self._refresh_book)   # countdown ticks at 4 Hz
        self.set_interval(1.0, self._refresh_bars)
        from .onboard import load_or_onboard
        load_or_onboard(self)

    # --- bridge lifecycle (called by onboard / account switcher) -------------
    wallet_name: str | None = None      # which WALLET this session runs on

    def start_bridge(self, address: str, wif: str | None,
                     name: str | None = None) -> None:
        # The session's identity is the WALLET, not the account address: an
        # agent key and that account's own key share an address but are
        # different sessions (AGENT vs SIGNING). Track the name.
        self.wallet_name = name
        if self.bridge is not None:      # switching: retire the old thread
            self.bridge.stop()
            self.bridge = None
            self.snap = Snap()
            qrw = self._q("#qr", Static)
            qrw.update("")
            qrw._qr_done = False
        self.bridge = Bridge(self.host,
                             on_snap=lambda s: self.call_from_thread(self.apply_snap, s),
                             on_event=lambda k, t: self.call_from_thread(self.add_event, k, t))
        self.bridge.set_identity(address, wif)
        self.bridge.start()
        mode = "watch-only" if wif is None else "custody key loaded"
        self.add_event("sys", f"session {address} · {mode} · host {self.host}")
        self.refresh_wallets()     # keep the dropdown honest after any switch
        self.add_event("sys", HELP)
        # A delegate may TRADE and cancel — never move money or change who is
        # authorized (the courier rule; the engine enforces it too). Offering
        # those buttons to a delegate only produces confusing rejections.
        deleg = self.bridge is not None and self.bridge.snap.is_delegate
        for bid in ("lock-all", "unlock-all", "exit-all", "mint", "revoke",
                    "register"):
            self._q(f"#{bid}", Button).disabled = wif is None or deleg
        if deleg:
            self.add_event("sys", "delegate key: trading enabled · fund, "
                                  "withdraw and delegate changes need the "
                                  "account owner's key")

    def right_click_cancel(self, oid: str) -> None:
        if self.bridge is None or self.snap.watch_only:
            self.add_event("err", "watch-only session — cannot cancel")
            return
        self.add_event("sys", f"right-click → CANCEL ·…{oid[-18:]}")
        self.bridge.cmd("cancel", oid)

    def action_accounts(self) -> None:
        from .onboard import AccountsScreen
        self.push_screen(AccountsScreen())

    def action_doggie(self) -> None:
        """The consumer skin — same bridge, opposite audience (ctrl+d toggles)."""
        from .doggie import DoggieScreen
        if not isinstance(self.screen, DoggieScreen):
            self.push_screen(DoggieScreen())

    def on_unmount(self) -> None:
        if self.bridge:
            self.bridge.stop()

    # --- snapshot → widgets ---------------------------------------------------
    @ui_update
    def apply_snap(self, s: Snap) -> None:
        # A retiring bridge can post one last snapshot AFTER a wallet switch;
        # applying it repaints the old account over the new session (the
        # picker appears to do nothing). Each Bridge owns its own Snap, so
        # identity tells us whether this one is still ours.
        if self.bridge is None or s is not self.bridge.snap:
            return
        self.snap = s
        self._refresh_bars()
        self._refresh_book()
        # positions (BTC-denominated, per the handoff)
        lines = []
        for p in s.positions:
            qty = p["contracts"]
            side = (f"[{GREEN}]LONG[/]" if qty > 0
                    else f"[{RED}]SHORT[/]" if qty < 0 else f"[{DIM}]FLAT[/]")
            notional = abs(qty) * s.contract_usd * (p["entry_price"] or s.last)
            upnl = 0
            if qty and s.last and p["entry_price"]:
                upnl = int(qty * (s.last - p["entry_price"])
                           * s.tick_value_sats / max(s.tick_size_sats, 1))
            color = GREEN if upnl >= 0 else RED
            lines.append(
                f"[{BRIGHT}]{p['ticker']}[/] {side} {abs(qty)} "
                f"[{DIM}]·[/] [{BRIGHT}]{self.money(notional)}[/]\n"
                f"  entry {p['entry_price']} · mark {s.last or '—'} · "
                f"pnl [{color}]{self.money(upnl, signed=True)}[/]\n"
                f"  [{DIM}]entry resets daily at settlement · "
                f"{p['open_bids']}b/{p['open_asks']}a working[/]")
        self._q("#positions", Static).update(
            "\n".join(lines) or f"[{DIM}]no positions[/]")
        # risk envelope — real numbers, BTC-denominated
        used = sum(p["margin_required"] for p in s.positions)
        equity, unreal_total = equity_sats(s)
        eq_usd = equity / s.last if s.last else 0.0   # sats ÷ sats-per-USD
        frac = min(1.0, used / equity) if equity > 0 else 0.0
        barw = 22
        fill = int(frac * barw)
        state = (f"[{RED}]RESTRICTED — reduce only[/]" if s.is_restricted
                 else f"[{GREEN}]SAFE[/]")
        self._q("#envelope", Static).update(
            f"{title('risk')}\n"
            f"equity    [{BRIGHT}]{self.money(equity)}[/] [{DIM}]${eq_usd:,.0f}[/]\n"
            f"margin    [{BRIGHT}]{self.money(used)}[/]\n"
            f"free      [{BRIGHT}]{self.money(s.available_margin)}[/]\n"
            f"unlocking [{BRIGHT}]{self.money(s.pending_unlock)}[/]\n"
            + (f"realized  [{GREEN if s.realized_pnl >= 0 else RED}]"
               f"{self.money(s.realized_pnl, signed=True)}[/]\n"
               f"open      [{GREEN if unreal_total >= 0 else RED}]"
               f"{self.money(unreal_total, signed=True)}[/]\n" if s.is_open else
               f"[{DIM}]settled: marked-to-market[/]\n")
            + f"[{GREEN_DIM}]{'█' * fill}{'░' * (barw - fill)}[/] {state}\n"
            + f"[{DIM}]btc-denominated[/]")
        # session / delegation (honest, per the handoff)
        active = [d for d in s.delegates if d["is_active"]]
        pend = [d for d in s.delegates if d["pending"]]
        # Three honest modes: WATCH (no key) · SIGNING (the account's own key,
        # can move money) · AGENT (a delegate key — trades this account, can
        # never withdraw or appoint). AGENT also states whether the ENGINE has
        # verified it, because an unverified agent's orders bounce RC_ID.
        if s.watch_only:
            mode = f"[{DIM}]WATCH[/]"
        elif s.is_delegate:
            mode = (f"[{GREEN}]AGENT[/] · verified" if s.delegate_active
                    else f"[{RED}]AGENT[/] · not authorized yet")
        else:
            mode = f"[{GOLD}]SIGNING[/]"
        dlines = [f"account  [{BRIGHT}]{s.address[:14]}…{s.address[-4:]}[/]" if s.address
                  else "account  —",
                  f"mode     {mode}"]
        if s.is_delegate:
            dlines.append(f"[{DIM}]trading only — fund/withdraw need the "
                          f"account key[/]")
        for d in active:
            dlines.append(f"[{GREEN}]● delegate[/] {d['trader_id'][:14]}… active")
        for d in pend:
            dlines.append(f"[{GOLD}]⏍ delegate[/] {d['trader_id'][:14]}… pending apply")
        if not s.delegates:
            dlines.append(f"[{DIM}]no delegates — mint one on the delegates tab[/]")
        self._q("#session", Static).update("\n".join(dlines))
        # working orders (right panel, authoritative sync; right-click cancels)
        wt = self._q("#working", WorkingOrders)
        rows = [(o["orderid"], o["side"], str(o["remaining"]), str(o["price"]),
                 "…" + o["orderid"][-13:]) for o in s.open_orders[:12]]
        if rows != getattr(wt, "_rows_cache", None):
            wt._rows_cache = rows
            wt.clear()
            for oid, side, qty, px, tail in rows:
                c = GREEN if side == "buy" else RED
                wt.add_row(f"[{c}]{side}[/]", qty, px, f"[{DIM}]{tail}[/]", key=oid)
        # fund tab
        self._q("#deposit", Static).update(
            f"[{BRIGHT}]{s.address}[/]\n"
            f"on-chain [{BRIGHT}]{self.money(s.chain_confirmed)}[/] confirmed · "
            f"{self.money(s.chain_mempool)} incoming\n"
            f"[{DIM}](updated "
            f"{datetime.fromtimestamp(s.chain_at).strftime('%H:%M:%S') if s.chain_at else 'never'})[/]")
        qrw = self._q("#qr", Static)
        if s.address and not getattr(qrw, "_qr_done", False):
            qrw.update(qr_unicode(s.address))
            qrw._qr_done = True
        self._update_fund_buttons(s)
        ulines = [
            f"equity {self.money(equity)} (${eq_usd:,.2f}) · withdrawable now "
            f"{self.money(s.available_margin)} · pending unlock "
            f"{self.money(s.pending_unlock)}",
            f"[{DIM}]unlock lifecycle: RESERVED (margin debited) → PROCESSING "
            f"(BTC broadcast) → COMPLETED — or REJECTED · one open unlock per "
            f"account[/]"]
        for u in s.unlock_records[-5:]:
            st = u["status_name"].removeprefix("UNLOCK_")
            c = (GREEN if st == "COMPLETED" else RED if st == "REJECTED" else GOLD)
            row = (f"[{c}]{st}[/] {self.money(u['amount_sats'])}"
                   f" [{DIM}]{u['oid'][-14:]}[/]")
            if u["btc_txid"]:
                # Textual markup needs the value QUOTED — a bare URL (with its
                # ':' and '//') is parsed as markup and raises MarkupError.
                row += (f" [link='https://mempool.space/tx/{u['btc_txid']}']"
                        f"mempool.space/tx/{u['btc_txid'][:12]}…[/link]")
            ulines.append(row)
        self._q("#fund-state", Static).update("\n".join(ulines))
        dt = self._q("#delegates", DataTable)
        dt.clear()
        for d in s.delegates:
            dt.add_row(d["trader_id"], d["status"],
                       "yes" if d["is_active"] else "no",
                       "yes" if d["pending"] else "", key=d["trader_id"])

    @ui_update
    def _update_fund_buttons(self, s: Snap) -> None:
        """FUND -> LOCK and UNLOCK -> EXIT, lit by where the money is. The user
        never types an amount: lock locks ALL, unlock requests MAX, exit sweeps
        ALL. We're not a wallet."""
        equity, _ = equity_sats(s)
        # unconfirmed counts — we forward straight from the mempool, no waiting
        local = s.chain_confirmed + s.chain_mempool
        fund = self._q("#fund-show", Button)
        lock = self._q("#lock-all", Button)
        unlock = self._q("#unlock-all", Button)
        exit_ = self._q("#exit-all", Button)
        # FUND: the green door when there's nothing anywhere yet
        fund.variant = "success" if (local == 0 and equity <= 0) else "default"
        # LOCK: lights up the moment funds are SEEN (mempool included)
        if local > 0:
            lock.variant = "success"
            lock.label = f"LOCK — fund the account ({self.money(local)})"
            self._q("#lock-status", Static).update(
                f"[{GREEN}]funds detected[/] — one tap forwards your ENTIRE "
                f"balance (unconfirmed included) to the exchange; the network "
                f"fee comes out of it")
        else:
            lock.variant = "default"
            lock.label = "LOCK — fund the account"
            self._q("#lock-status", Static).update(
                f"[{DIM}]nothing on-chain yet — FUND first[/]")

        # UNLOCK: lights up when there's equity on the exchange. The amount
        # field decides MAX vs an explicit request — the label follows it so
        # the button always states what the tap will actually do.
        if equity > 0:
            raw = self._q("#unlock-amt", Input).value
            invalid = None
            try:
                want = self._parse_money_input(raw, self.denom)
            except ValueError as exc:
                want, invalid = None, str(exc)
            unlock.variant = "success"
            unlock.label = (f"UNLOCK — request {self.money(want)} back" if want
                            else f"UNLOCK — request funds back ({self.money(equity)})")
            if invalid:
                self._q("#unlock-status", Static).update(
                    f"[{RED}]{invalid}[/] — or click MAX")
            elif want and want > s.available_margin:
                self._q("#unlock-status", Static).update(
                    f"[{GOLD}]{self.money(want)} is more than the "
                    f"{self.money(s.available_margin)} withdrawable now[/] — send it "
                    f"and the exchange decides; a rejected unlock shows in the "
                    f"records below")
            else:
                self._q("#unlock-status", Static).update(
                    f"[{GREEN}]you have funds on sidepit[/] — "
                    + (f"requesting {self.money(want)}" if want else
                       "MAX requests EVERYTHING withdrawable")
                    + " back to your address (applies live in-session)")
        else:
            unlock.variant = "default"
            unlock.label = "UNLOCK — request funds back"
            self._q("#unlock-status", Static).update(
                f"[{DIM}]no exchange balance to withdraw[/]")

        # EXIT: available whenever there is a local balance to leave with
        if local > 0:
            exit_.variant = "warning"
            self._q("#exit-status", Static).update(
                f"[{GOLD}]sweeps your ENTIRE on-chain balance "
                f"({self.money(local)}) to the address above — leaving sidepit[/]")
        else:
            exit_.variant = "default"
            self._q("#exit-status", Static).update(
                f"[{DIM}]nothing on-chain to sweep — UNLOCK lands here first[/]")


    @ui_update
    def _refresh_bars(self) -> None:
        s = self.snap
        dot = f"[{GREEN}]●[/]" if s.is_open else f"[{DIM}]●[/]"
        mode = ("watch" if s.watch_only else
                ("agent" if s.delegate_active else "agent · unverified")
                if s.is_delegate else "signing")
        spread = s.ask - s.bid if s.ask and s.bid else 0
        account = (f"{s.address[:10]}…{s.address[-4:]}" if s.address else "—")
        self._q("#titlebar", Static).update(
            f"[{BRIGHT}]sidepit // cockpit[/] [{DIM}]v1[/]   "
            f"{dot} [{BRIGHT}]{s.state.removeprefix('EXCHANGE_')}[/]   "
            f"[{BRIGHT}]{s.ticker or 'NO CONTRACT'}[/]   "
            f"[{GOLD}]last {s.last or '—'}[/]  [{BRIGHT}]{usd_hint(s.last)}[/]   "
            f"[{GREEN}]bid {s.bid or '—'} × {s.bidsize or '—'}[/]   "
            f"[{RED}]ask {s.ask or '—'} × {s.asksize or '—'}[/]   "
            f"[{DIM}]spread {spread or '—'}[/]\n"
            f"[{DIM}]account[/] [{BRIGHT}]{account}[/]  [{DIM}]· {mode} ·[/]  "
            f"[{DIM}]contract[/] [{BRIGHT}]${s.contract_usd:,}[/]  "
            f"[{DIM}]tick[/] [{BRIGHT}]{s.tick_size_sats} sat/USD → "
            f"{s.tick_value_sats} sat[/]  [{DIM}]· ctrl+d[/] [{GOLD}]doggie[/]  "
            f"[{DIM}]· session {s.session_id or '—'}[/]"
            + (f"  [{DIM}]· closes {hhmm_left(s.close_ms)}[/]" if s.is_open else ""))
        env = "RESTRICTED" if s.is_restricted else "SAFE"
        self._q("#statbar", Static).update(
            f"{dot} auction sync · envelope: "
            f"[{RED if s.is_restricted else GREEN}]{env}[/] · book: transparent · "
            f"denom: [{GOLD}]{self.denom}[/] · session {s.session_id or '—'}")

    @ui_update
    def _refresh_book(self) -> None:
        """5-level transparent book + spread bar with the DLOB countdown."""
        s = self.snap
        out = [title("book · transparent · DLOB 1s deterministic auctions")]
        if not s.depth_bids and not s.depth_asks:
            out.append(f"[{DIM}]no live book (exchange {s.state})[/]")
        else:
            allsz = [sz for _, sz in (s.depth_bids[:5] + s.depth_asks[:5])] or [1]
            mx = max(allsz)
            for px, sz in reversed(s.depth_asks[:5]):
                bar = "█" * max(1, int(sz / mx * 22))
                out.append(f"  [{RED}]{px:>7}[/]  {sz:>4}  [{RED_DIM}]{bar}[/]")
            t_left = 1.0 - (time.time() % 1.0)
            badge = (f"[{GOLD}]AUCTION ARMED[/] [{DIM}]·[/] "
                     f"[{GOLD}]t-{t_left:.2f}s[/]" if s.is_open
                     else f"[{DIM}]auction idle ({s.state})[/]")
            spread = (s.depth_asks[0][0] - s.depth_bids[0][0]
                      if s.depth_asks and s.depth_bids else 0)
            out.append("")
            out.append(f"  [{GOLD}]last {s.last or '—'}[/]  "
                       f"[{BRIGHT}]{usd_hint(s.last)}[/]  "
                       f"[{DIM}]spread {spread}[/]   {badge}")
            out.append("")
            for px, sz in s.depth_bids[:5]:
                bar = "█" * max(1, int(sz / mx * 22))
                out.append(f"  [{GREEN}]{px:>7}[/]  {sz:>4}  [{GREEN_DIM}]{bar}[/]")
        self._q("#book", Static).update("\n".join(out))

    # --- log (the handoff's grammar) -------------------------------------------
    TAGS = {"sys": (CYAN, "[sys]"), "cmd": (GOLD, "[cmd]"),
            "fill": (GREEN, "[fill]"), "ok": (GREEN, "[ok]"),
            "warn": (GOLD, "[warn]"), "err": (RED, "[err]"),
            # bridge kinds map onto the grammar
            "info": (CYAN, "[sys]"), "success": (GREEN, "[ok]"),
            "warning": (GOLD, "[warn]"), "error": (RED, "[err]")}

    @ui_update
    def add_event(self, kind: str, text: str) -> None:
        # repeat-suppressor: a failing poll can emit the same error every few
        # seconds (e.g. during the open->close transition) — log/toast it once,
        # then stay quiet about identical text for 60s.
        now = time.monotonic()
        if not hasattr(self, "_event_seen"):
            self._event_seen = {}
        last = self._event_seen.get(text, 0.0)
        self._event_seen[text] = now
        if now - last < 60.0:
            return
        if len(self._event_seen) > 200:
            self._event_seen = {t: m for t, m in self._event_seen.items()
                                if now - m < 60.0}
        color, tag = self.TAGS.get(kind, (TEXT, "[sys]"))
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        self._q("#log", RichLog).write(
            f"[{DIM}]{ts}[/] [{color}]{tag}[/] [{TEXT}]{text}[/]")
        # outcomes must reach the user on WHATEVER screen/tab they're on (the
        # log lives on the cockpit tab) — toast everything that isn't chatter
        sev = {"success": "information", "ok": "information",
               "warning": "warning", "warn": "warning",
               "error": "error", "err": "error"}.get(kind)
        if sev:
            self.notify(text, severity=sev, timeout=7)

    # --- the prompt loop ---------------------------------------------------------
    def refresh_wallets(self) -> None:
        """(Re)fill the wallet dropdown from the keystore and show the active
        one. Called at mount and after every switch/import/mint."""
        from sidepit_trader import keystore
        try:
            ids = keystore.identities()
        except Exception:
            return
        sel = self._q("#wallet-pick", Select)
        opts = [(f"{i['name']}  {i['sidepit_id'][-6:]}"
                 f"{'' if i['has_key'] else ' (watch)'}", i["name"])
                for i in ids]
        sel.set_options(opts)
        # Show the wallet the SESSION is on — by NAME first (two wallets can
        # share an account: its own key and an agent key), then by address,
        # then the ACTIVE file. A dropdown already showing a name can't be
        # re-picked, so getting this wrong strands the human.
        names = {i["name"] for i in ids}
        cur = self.wallet_name if self.wallet_name in names else None
        cur = cur or next((i["name"] for i in ids
                           if i["sidepit_id"] == self.snap.address), None)
        cur = cur or next((i["name"] for i in ids if i["active"]), None)
        if cur:
            with self.prevent(Select.Changed):     # don't re-switch on refill
                sel.value = cur

    @ui_update
    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "denom-pick":
            new_denom = str(event.value)
            if new_denom not in ("BTC", "SATS") or new_denom == self.denom:
                return
            field = self._q("#unlock-amt", Input)
            raw = field.value
            try:
                amount = self._parse_money_input(raw, self.denom)
            except ValueError:
                amount = None
            self.denom = new_denom
            field.placeholder = ("BTC (e.g. 0.005)" if new_denom == "BTC"
                                 else "sats (e.g. 500,000)")
            if raw.strip().upper() == "MAX":
                field.value = "MAX"
            elif amount is not None:
                field.value = self._money_input(amount, new_denom)
            if self.bridge is not None and self.snap is self.bridge.snap:
                self.apply_snap(self.snap)
            else:
                self._refresh_bars()
                self._update_fund_buttons(self.snap)
            return
        if event.select.id != "wallet-pick":
            return
        from sidepit_trader import keystore
        name = str(event.value)
        # The "nothing selected" sentinel differs across Textual versions
        # (BLANK / NULL) — trust the keystore instead of the sentinel name.
        if name not in {i["name"] for i in keystore.identities()}:
            return
        keystore.set_active(name)
        # by-name, NOT active_identity(): env vars outrank the keystore there,
        # so an exported SIDEPIT_WIF would silently keep the old session.
        row = keystore.identity(name)
        if not row:
            self.add_event("err", f"wallet '{name}' could not be loaded")
            return
        # Compare WALLET NAMES, not addresses: an agent key and its account's
        # own key report the same account, so an address check made
        # agent -> custody -> agent a silent no-op.
        if name == self.wallet_name:
            return
        if os.environ.get("SIDEPIT_WIF") or os.environ.get("SIDEPIT_ID"):
            self.add_event("warn", "SIDEPIT_WIF/ID are set in your shell — the "
                                   "picker now wins for this session; unset "
                                   "them to avoid confusion")
        self.add_event("sys", f"switched to '{name}'")
        self.start_bridge(row["sidepit_id"], row["wif"], name=name)

    def on_input_changed(self, event: Input.Changed) -> None:
        """The unlock button must always state what the tap will do, so the
        amount field re-labels it on every keystroke."""
        if event.input.id == "unlock-amt":
            self._update_fund_buttons(self.snap)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "prompt":
            return
        text = event.value.strip()
        event.input.value = ""
        if not text:
            return
        self.add_event("cmd", f'"{text}"')
        try:
            it = parse(text, last_sats=self.snap.last,
                       contract_usd=self.snap.contract_usd)
        except ValueError as e:
            self.add_event("err", str(e))
            return
        self.add_event("sys", it.summary)
        self._execute(it)

    def _execute(self, it: Intent) -> None:
        b = self.bridge
        s = self.snap
        if it.kind in ("HELP", "BOOK"):
            return   # the parse echo / always-on book IS the answer
        if it.kind == "RISK":
            used = sum(p["margin_required"] for p in s.positions)
            equity, unreal = equity_sats(s)
            eq_usd = equity / s.last if s.last else 0.0
            pnl = (f"realized {self.money(s.realized_pnl, signed=True)} · open "
                   f"{self.money(unreal, signed=True)}" if s.is_open
                   else "settled: marked-to-market")
            self.add_event("sys",
                           f"equity {self.money(equity)} (${eq_usd:,.2f}) · margin used "
                           f"{self.money(used)} · withdrawable "
                           f"{self.money(s.available_margin)} · "
                           f"{pnl} · "
                           f"{'RESTRICTED' if s.is_restricted else 'SAFE'}")
            return
        if b is None or s.watch_only:
            self.add_event("err", "watch-only session — no signing key loaded")
            return
        if it.kind == "LMT":
            b.cmd("order", it.side, it.price, it.size)
        elif it.kind == "MKT":
            b.cmd("market", it.side, it.size)
        elif it.kind == "CANCEL_ALL":
            b.cmd("cancel_all")
        elif it.kind == "FLATTEN_ALL":
            b.cmd("flatten")
        elif it.kind == "CANCEL":
            full = next((o["orderid"] for o in s.open_orders
                         if o["orderid"].endswith(it.orderid)), it.orderid)
            b.cmd("cancel", full)

    # --- buttons (fund / delegates / TRY) ----------------------------------------
    def action_refresh(self) -> None:
        if self.bridge:
            self.bridge.cmd("sync_now")
            self.bridge.cmd("chain_refresh")

    def _selected_key(self, table_id: str) -> str | None:
        t = self._q(f"#{table_id}", DataTable)
        if t.row_count == 0:
            return None
        try:
            return t.coordinate_to_cell_key(
                Coordinate(t.cursor_row, 0)).row_key.value
        except Exception:
            return None

    def _int(self, input_id: str) -> int | None:
        raw = self._q(f"#{input_id}", Input).value.strip().replace(",", "")
        if not raw:
            return None
        try:
            v = int(raw)
            return v if v > 0 else None
        except ValueError:
            return None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        b = self.bridge
        if bid.startswith("try-"):
            p = self._q("#prompt", Input)
            p.value = TRY_PROMPTS[int(bid.split("-")[1])]
            p.focus()
            return
        if b is None:
            return
        if bid == "chain-refresh":
            b.cmd("chain_refresh")
        elif bid == "fund-show":
            self.add_event("ok", f"send BTC to {self.snap.address} — it appears "
                                 f"here automatically, then LOCK goes green")
        elif bid == "lock-all":
            total = self.snap.chain_confirmed + self.snap.chain_mempool
            if total <= 0:
                self.add_event("warn", f"nothing on-chain yet — FUND first: send "
                                       f"BTC to {self.snap.address}")
                return
            self.push_screen(
                Confirm(f"Fund the account?\nYour ENTIRE on-chain balance "
                        f"({self.money(total)}) is forwarded to the exchange — "
                        f"the network fee comes out of it. This broadcasts a "
                        f"REAL Bitcoin transaction.", yes="FUND"),
                lambda ok: ok and b.cmd("lock_all"))
        elif bid == "unlock-max":
            self._q("#unlock-amt", Input).value = "MAX"
            self._update_fund_buttons(self.snap)       # label follows instantly
            return
        elif bid == "unlock-all":
            equity, _ = equity_sats(self.snap)
            if equity <= 0:
                self.add_event("warn", "no exchange balance to withdraw — LOCK "
                                       "funds first, then trade")
                return
            raw = self._q("#unlock-amt", Input).value
            try:
                amount = self._parse_money_input(raw, self.denom)
            except ValueError as exc:
                self.add_event("err", f"unlock: {exc}, or click MAX")
                return
            what = (self.money(amount) if amount
                    else "EVERYTHING withdrawable")
            self.push_screen(
                Confirm(f"Request {what} back to your own address?\n"
                        f"Applies live in-session; the "
                        f"exchange sends the BTC — you sign nothing more."),
                lambda ok: ok and b.cmd("unlock", amount))
        elif bid == "exit-all":
            dest = self._q("#exit-dest", Input).value.strip()
            if not dest.startswith("bc1"):
                self.add_event("err", "exit: paste the destination bc1q… address first")
                return
            total = self.snap.chain_confirmed + self.snap.chain_mempool
            if total <= 0:
                self.add_event("warn", "nothing on-chain to sweep — UNLOCK from "
                                       "the exchange lands here first")
                return
            self.push_screen(
                Confirm(f"EXIT sidepit?\nYour ENTIRE on-chain balance "
                        f"({self.money(total)}, minus the network fee) is swept "
                        f"to:\n{dest}\nThis broadcasts a REAL Bitcoin "
                        f"transaction.", yes="EXIT"),
                lambda ok: ok and b.cmd("exit_all", dest))
        elif bid == "mint":
            self._mint_agent_key()
        elif bid == "register":
            pub = self._q("#del-pub", Input).value.strip()
            try:
                from sidepit_trader.wallet import sidepit_id_from_pubkey
                tid = sidepit_id_from_pubkey(pub)   # spec: derive, never typed
            except Exception:
                self.add_event("err", "register: need the delegate's 33-byte "
                                      "compressed pubkey (66 hex chars)")
                return
            self._q("#del-derived", Static).update(
                f"[{DIM}]derived trader_id: {tid}[/]")
            self.push_screen(
                Confirm(f"Register delegate {tid}\n(derived from the pubkey — the "
                        f"server enforces this match)?\nThis key will be able to "
                        f"TRADE this account (never withdraw/appoint); applies "
                        f"live in-session."),
                lambda ok: ok and b.cmd("register_delegate", tid, pub))
        elif bid == "revoke":
            tid = self._selected_key("delegates")
            if tid:
                self.push_screen(
                    Confirm(f"Revoke delegate {tid}?"),
                    lambda ok: ok and b.cmd("revoke_delegate", tid))

    def _mint_agent_key(self) -> None:
        """Mint a hot key for an agent, save its env file (0600), show it ONCE,
        and pre-fill the register form. The secret never reaches the log."""
        import os
        from sidepit_trader import wallet
        ident = wallet.gen_key()
        path = os.path.expanduser(f"~/.sidepit/agent-{ident.sidepit_id[-8:]}.env")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(f"# Sidepit agent delegate key — give this file to YOUR agent only\n"
                    f"export SIDEPIT_ID={self.snap.address}\n"
                    f"export SIDEPIT_WIF={ident.wif}\n"
                    f"export SIDEPIT_TRADER_ID={ident.sidepit_id}\n")
        self._q("#del-pub", Input).value = ident.pubkey_hex
        self._q("#del-derived", Static).update(
            f"[{DIM}]derived trader_id: {ident.sidepit_id}[/]")
        self.push_screen(ShowSecret(
            "agent key minted — shown ONCE",
            f"trader_id : {ident.sidepit_id}\n"
            f"pubkey    : {ident.pubkey_hex}\n"
            f"WIF       : {ident.wif}\n\n"
            f"saved (0600) to {path}\n"
            f"the register form is pre-filled — press register to authorize it.\n"
            f"the agent trades with Signer.as_delegate(hot_key, custody_id)."))
        self.add_event("sys", f"agent key minted for {ident.sidepit_id} "
                              f"(env file written; secret not logged)")


def main(start_doggie: bool = False) -> None:
    import contextlib
    import logging
    import os
    # The terminal belongs to the TUI. Anything that leaks to stderr (pynng
    # prints a literal traceback when a feed port refuses at session close;
    # logging's last-resort handler writes warnings) splatters over the raw
    # screen — route ALL of it to a logfile instead.
    logpath = os.path.expanduser("~/.sidepit/tui.log")
    os.makedirs(os.path.dirname(logpath), exist_ok=True)
    logging.basicConfig(filename=logpath, level=logging.INFO, force=True,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    with open(logpath, "a") as errlog, contextlib.redirect_stderr(errlog):
        app = SidepitApp(host=os.environ.get("SIDEPIT_HOST", HOST_DEFAULT))
        app.open_doggie_on_start = start_doggie
        app.run()
