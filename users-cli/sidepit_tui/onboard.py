"""Onboarding — the first-run identity flow.

Three doors, on the SDK flat-file keystore (`~/.sidepit/keys/`, one 0600 env
file per identity — keys NEVER live in a database; bots read the same files,
so onboarding here IS provisioning for an agent):

  create   mint a key, store it, then offer the backup (12 words / WIF,
           hidden until asked). Skipping is safe: the file is the key.
  import   paste a WIF (also: `python -m sidepit_tui import`, or just drop an
           env file into ~/.sidepit/keys/).
  watch    just an address — read-only everywhere (verbs disabled).
  look     nothing at all — the market only; add an identity later (ctrl+a).

SIDEPIT_WIF / SIDEPIT_ID in the environment override everything (bot-style).
"""
from __future__ import annotations

import os
from textual.app import ComposeResult
from textual.containers import Grid, Horizontal
from textual.coordinate import Coordinate
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Static

from sidepit_trader import keystore, wallet



def load_or_onboard(app) -> None:
    """Start the bridge from the active identity (env → ~/.sidepit/keys/),
    or run onboarding."""
    row = keystore.active_identity()
    if row is not None:
        app.start_bridge(row["sidepit_id"], row["wif"], name=row["name"])
    else:
        # No identity yet: the market comes up first (price, bars, book, the
        # auction clock) and the identity doors sit on top. Escape or "just
        # look" leaves a live read-only cockpit; ctrl+a adds a key later.
        app.start_bridge("", None)
        app.push_screen(OnboardScreen())


class OnboardScreen(ModalScreen[None]):
    """Modal over the app until an identity is chosen. Escape backs out: to the
    cockpit as-is when a session already exists (reached via ctrl+a → add
    identity), or to a no-identity cockpit on first run."""

    BINDINGS = [("escape", "cancel", "back")]

    def action_cancel(self) -> None:
        self.dismiss(None)
        if not getattr(self.app.snap, "address", ""):
            self.app.add_event("sys", "no identity — market only. ctrl+a adds "
                                      "one when you want to trade")

    def compose(self) -> ComposeResult:
        with Grid(id="onboard-grid"):
            yield Label("[b]Welcome to Sidepit[/b] — choose an identity "
                        "[dim](esc = back)[/dim]",
                        id="onboard-title")
            yield Button("Create a new identity (12-word backup)",
                         variant="primary", id="ob-create")
            yield Button("Import — 12 words or WIF", id="ob-import")
            yield Button("Watch an address (read-only)", id="ob-watch")
            yield Button("Just look — no identity, market only", id="ob-look")
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
                mnemonic: str | None = None):
        path = keystore.save_identity(name, sidepit_id, wif, active=True,
                                      mnemonic=mnemonic)
        self.app.start_bridge(sidepit_id, wif, name=name)
        self.dismiss(None)
        return path

    def _msg(self, text: str) -> None:
        self.query_one("#ob-msg", Static).update(text)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        raw = self.query_one("#ob-input", Input).value.strip()
        if event.button.id == "ob-create":
            from sidepit_trader import mnemonic
            words, ident = mnemonic.new_identity_words()
            # stored first: skipping the backup is safe, the key is on disk
            path = self._finish("tui", ident.sidepit_id, ident.wif, mnemonic=words)
            self.app.push_screen(BackupScreen("tui", ident.sidepit_id, ident.wif,
                                              words, str(path), first_time=True))
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
        elif event.button.id == "ob-look":
            self.action_cancel()


HIDDEN = "•••• hidden — press show"


def backup_text(path: str, sidepit_id: str, words: str | None,
                wif: str | None, shown: bool) -> str:
    """The backup panel body. Secrets appear only when `shown`."""
    if shown and words:
        ws = words.split()
        grid = "\n".join("   ".join(f"{i + 1:>2}. {w:<10}" for i, w in
                                    list(enumerate(ws))[r * 4:r * 4 + 4])
                         for r in range(3))
    elif words:
        grid = HIDDEN + "\n\n"          # same height as the grid: nothing jumps
    else:
        grid = "(imported from a WIF — no words; the WIF is the backup)\n\n"
    return (f"stored on this computer, readable only by you:\n  {path}\n\n"
            f"sidepit_id : {sidepit_id}\n\n"
            f"12 words   :\n{grid}\n\n"
            f"WIF        : {wif if shown else HIDDEN}\n\n"
            f"Back it up when you have a minute — any one of these restores "
            f"the account:\n"
            f"write the 12 words down · copy the WIF into a password manager · "
            f"keep a copy of the file above.\n"
            f"Any time: ctrl+a → backup.")


class BackupScreen(ModalScreen[None]):
    """Show one identity's backup material, hidden until the human asks."""

    BINDINGS = [("escape", "dismiss(None)", "close")]

    def __init__(self, name: str, sidepit_id: str, wif: str | None,
                 words: str | None, path: str, first_time: bool = False):
        super().__init__()
        self._name, self._id, self._wif, self._words, self._path = (
            name, sidepit_id, wif, words, path)
        self._first = first_time
        self._shown = False

    def compose(self) -> ComposeResult:
        title = ("[b]Identity created and saved[/b] — back it up now or later"
                 if self._first else f"[b]backup[/b] — {self._name}")
        with Grid(id="backup-grid"):
            yield Label(title, id="backup-title")
            yield Static(backup_text(self._path, self._id, self._words,
                                     self._wif, False), id="backup-body")
            with Horizontal(id="backup-buttons"):
                yield Button("show", id="bk-show")
                yield Button("copy words", id="bk-copy-words",
                             disabled=not self._words)
                yield Button("copy WIF", id="bk-copy-wif", disabled=not self._wif)
                yield Button("Later — it's saved here" if self._first else "close",
                             variant="primary", id="bk-done")
            yield Static("", id="backup-msg")

    DEFAULT_CSS = """
    #backup-grid {
        grid-size: 1; grid-gutter: 1; padding: 1 2;
        width: 86; height: auto; border: thick $primary; background: $surface;
    }
    #backup-buttons { height: 3; }
    #backup-buttons Button { margin-right: 1; }
    """

    def _copy(self, what: str, text: str) -> None:
        self.app.copy_to_clipboard(text)
        self.query_one("#backup-msg", Static).update(
            f"{what} copied to the clipboard — paste it somewhere safe, then "
            f"copy something else to clear it")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "bk-show":
            self._shown = not self._shown
            self.query_one("#backup-body", Static).update(
                backup_text(self._path, self._id, self._words, self._wif,
                            self._shown))
            event.button.label = "hide" if self._shown else "show"
        elif event.button.id == "bk-copy-words" and self._words:
            self._copy("12 words", self._words)
        elif event.button.id == "bk-copy-wif" and self._wif:
            self._copy("WIF", self._wif)
        elif event.button.id == "bk-done":
            self.dismiss(None)


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
                yield Button("backup", id="acct-backup")
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
        row = keystore.identity(name)      # by-name: env must not outrank a
        if not row:                        # wallet the human just picked
            self.app.add_event("err", f"wallet '{name}' could not be loaded")
            return
        self.app.add_event("sys", f"switched to '{name}'")
        self.app.start_bridge(row["sidepit_id"], row["wif"], name=name)
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
        elif event.button.id == "acct-backup":
            name = self._selected()
            row = keystore.identity(name) if name else None
            if not row:
                return
            if not row["wif"]:
                self.app.add_event("sys", f"'{name}' is watch-only — nothing to back up")
                return
            self.app.push_screen(BackupScreen(name, row["sidepit_id"], row["wif"],
                                              row.get("mnemonic"),
                                              str(keystore.identity_path(name))))
        elif event.button.id == "acct-close":
            self.dismiss(None)
