"""New identity: stored first, backup offered with secrets hidden until asked.

Jay 2026-10-30: the 12 words must be hidden by default, the screen must say
where the key is stored so skipping feels safe, one click copies, and a backup
door must exist later (ctrl+a → backup). Nothing secret is printed here.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "users-cli"))

from textual.app import App  # noqa: E402
from textual.widgets import Button, Static  # noqa: E402

from sidepit_trader import keystore  # noqa: E402
from sidepit_tui import onboard  # noqa: E402

WORDS = "abandon " * 11 + "about"
WIF = "KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFU73sVHnoWn"   # BIP32 test vector key


def test_backup_text_hides_secrets_until_shown():
    hidden = onboard.backup_text("/k/tui.env", "bc1qme", WORDS, WIF, False)
    assert "abandon" not in hidden and WIF not in hidden
    assert "/k/tui.env" in hidden and "ctrl+a" in hidden
    shown = onboard.backup_text("/k/tui.env", "bc1qme", WORDS, WIF, True)
    assert "12. about" in shown and WIF in shown


def test_backup_screen_show_toggle_and_copy():
    copied = []

    class T(App):
        def copy_to_clipboard(self, text):
            copied.append(text)

    async def run():
        app = T()
        async with app.run_test() as pilot:
            app.push_screen(onboard.BackupScreen("tui", "bc1qme", WIF, WORDS,
                                                 "/k/tui.env", first_time=True))
            await pilot.pause()
            body = app.screen.query_one("#backup-body", Static)
            assert "abandon" not in str(body.content)
            assert "Later" in str(app.screen.query_one("#bk-done", Button).label)
            await pilot.click("#bk-show")
            await pilot.pause(0.5)   # past the double-click window
            assert "12. about" in str(body.content)
            assert "hide" in str(app.screen.query_one("#bk-show", Button).label)
            await pilot.click("#bk-show")
            await pilot.pause(0.5)   # past the double-click window
            assert "abandon" not in str(body.content)
            await pilot.click("#bk-copy-words")
            await pilot.click("#bk-copy-wif")
            await pilot.pause()
            assert copied == [WORDS, WIF]
    asyncio.run(run())


def test_keystore_identity_returns_words_and_path(tmp_path, monkeypatch):
    monkeypatch.setattr(keystore, "KEYS_DIR", tmp_path)
    monkeypatch.setattr(keystore, "ACTIVE_FILE", tmp_path / "ACTIVE")
    p = keystore.save_identity("tui", "bc1qme", WIF, mnemonic=WORDS)
    row = keystore.identity("tui")
    assert row["mnemonic"] == WORDS and row["wif"] == WIF
    assert keystore.identity_path("tui") == p
