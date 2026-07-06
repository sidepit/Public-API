"""Onboarding — the first-run identity flow.

Three doors, on the SDK flat-file keystore (`~/.sidepit/keys/`, one 0600 env
file per identity — keys NEVER live in a database; bots read the same files,
so onboarding here IS provisioning for an agent):

  create   mint a key, show the WIF ONCE (it IS the account; no recovery),
           store it, continue funded onboarding on the Fund tab.
  import   paste a WIF (also: `python -m sidepit_tui import`, or just drop an
           env file into ~/.sidepit/keys/).
  watch    just an address — read-only everywhere (verbs disabled).

Legacy `~/.spwallets/.spwallet*` files (bare WIF, one per file) are detected
and offered for import so existing users keep their accounts. SIDEPIT_WIF /
SIDEPIT_ID in the environment override everything (bot-style).
"""
from __future__ import annotations

import os
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Grid, Horizontal
from textual.coordinate import Coordinate
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Static

from sidepit_trader import keystore, wallet

LEGACY_DIR = Path.home() / ".spwallets"


def _legacy_wifs() -> list[tuple[str, str]]:
    """[(name, wif)] from the old users-cli wallet folder, if any."""
    out = []
    if LEGACY_DIR.is_dir():
        for p in sorted(LEGACY_DIR.iterdir()):
            if p.is_file():
                try:
                    wif = p.read_text().strip()
                    wallet.from_wif(wif)   # validates checksum
                    out.append((p.name, wif))
                except Exception:
                    continue
    return out


def load_or_onboard(app) -> None:
    """Start the bridge from the active identity (env → ~/.sidepit/keys/),
    or run onboarding."""
    row = keystore.active_identity()
    if row is not None:
        app.start_bridge(row["sidepit_id"], row["wif"])
    else:
        app.push_screen(OnboardScreen())


class OnboardScreen(ModalScreen[None]):
    """Modal over the (empty) app until an identity exists."""

    def compose(self) -> ComposeResult:
        legacy = _legacy_wifs()
        with Grid(id="onboard-grid"):
            yield Label("[b]Welcome to Sidepit[/b] — choose an identity",
                        id="onboard-title")
            yield Button("Create a new identity (12-word backup)",
                         variant="primary", id="ob-create")
            yield Button("Import — 12 words or WIF", id="ob-import")
            yield Button("Watch an address (read-only)", id="ob-watch")
            if legacy:
                yield Button(f"Import legacy wallet ({legacy[0][0]})",
                             variant="warning", id="ob-legacy")
            yield Input(placeholder="paste 12 words, WIF, or bc1q… address here",
                        id="ob-input", password=True)
            yield Static("", id="ob-msg")

    DEFAULT_CSS = """
    #onboard-grid {
        grid-size: 1; grid-gutter: 1; padding: 1 2;
        width: 76; height: auto; border: thick $primary; background: $surface;
    }
    """

    def _finish(self, name: str, sidepit_id: str, wif: str | None,
                mnemonic: str | None = None) -> None:
        keystore.save_identity(name, sidepit_id, wif, active=True,
                               mnemonic=mnemonic)
        self.app.start_bridge(sidepit_id, wif)
        self.dismiss(None)

    def _msg(self, text: str) -> None:
        self.query_one("#ob-msg", Static).update(text)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        raw = self.query_one("#ob-input", Input).value.strip()
        if event.button.id == "ob-create":
            from sidepit_trader import mnemonic
            words, ident = mnemonic.new_identity_words()
            grid = "\n".join("   ".join(f"{i + 1:>2}. {w:<10}"
                             for i, w in list(enumerate(words.split()))[r * 4:r * 4 + 4])
                             for r in range(3))
            # show the secret BEFORE storing so the user must acknowledge it
            from .app import ShowSecret
            self.app.push_screen(ShowSecret(
                "NEW IDENTITY — write down the 12 words NOW (they ARE the "
                "account; no recovery)",
                f"{grid}\n\n"
                f"sidepit_id : {ident.sidepit_id}\n"
                f"WIF        : {ident.wif}\n\n"
                f"The 12 words restore this key in ANY standard wallet (BIP39/84)\n"
                f"and here (import → paste the words). Stored as a 0600 flat file\n"
                f"in ~/.sidepit/keys/; keep an offline copy of the words."),
                lambda _: self._finish("tui", ident.sidepit_id, ident.wif,
                                       mnemonic=words))
        elif event.button.id == "ob-import":
            from sidepit_trader import mnemonic
            words = None
            try:
                if mnemonic.looks_like_words(raw):
                    ident = mnemonic.identity_from_words(raw)
                    words = " ".join(raw.lower().split())
                else:
                    ident = wallet.from_wif(raw)
            except Exception as e:
                self._msg(f"[red]not a valid WIF or 12-word phrase — {e}[/red]")
                return
            self._finish("tui", ident.sidepit_id, ident.wif, mnemonic=words)
        elif event.button.id == "ob-watch":
            if not raw.startswith("bc1"):
                self._msg("[red]paste a bc1q… address in the box first[/red]")
                return
            self._finish("watch", raw, None)
        elif event.button.id == "ob-legacy":
            name, wif = _legacy_wifs()[0]
            ident = wallet.from_wif(wif)
            self._finish(name, ident.sidepit_id, ident.wif)


class AccountsScreen(ModalScreen[None]):
    """Quick account switcher (ctrl+a) — list the keystore, switch with one
    keypress, or add another identity through the onboarding doors. Mirrors the
    legacy CLI's 'manage' menu on the flat-file store."""

    BINDINGS = [("escape", "dismiss(None)", "close")]

    def compose(self) -> ComposeResult:
        with Grid(id="accounts-grid"):
            yield Label("[b]accounts[/b] — enter/switch activates · esc closes",
                        id="accounts-title")
            yield DataTable(id="accounts-table")
            with Horizontal(id="accounts-buttons"):
                yield Button("switch", variant="primary", id="acct-switch")
                yield Button("add identity", id="acct-add")
                yield Button("close", id="acct-close")

    DEFAULT_CSS = """
    #accounts-grid {
        grid-size: 1; grid-gutter: 1; padding: 1 2;
        width: 86; height: auto; border: thick $primary; background: $surface;
    }
    #accounts-table { height: auto; max-height: 12; }
    #accounts-buttons { height: 3; }
    """

    def on_mount(self) -> None:
        t = self.query_one("#accounts-table", DataTable)
        t.add_columns("", "name", "sidepit_id", "kind")
        t.cursor_type = "row"
        for i in keystore.identities():
            t.add_row("●" if i["active"] else "", i["name"], i["sidepit_id"],
                      "key" if i["has_key"] else "watch-only", key=i["name"])

    def _switch(self, name: str | None) -> None:
        if not name:
            return
        keystore.set_active(name)
        row = keystore.active_identity()
        self.app.add_event("sys", f"switched to '{name}'")
        self.app.start_bridge(row["sidepit_id"], row["wif"])
        self.dismiss(None)

    def _selected(self) -> str | None:
        t = self.query_one("#accounts-table", DataTable)
        if t.row_count == 0:
            return None
        try:
            return t.coordinate_to_cell_key(
                Coordinate(t.cursor_row, 0)).row_key.value
        except Exception:
            return None

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._switch(event.row_key.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "acct-switch":
            self._switch(self._selected())
        elif event.button.id == "acct-add":
            self.dismiss(None)
            self.app.push_screen(OnboardScreen())
        elif event.button.id == "acct-close":
            self.dismiss(None)
