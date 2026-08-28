"""`sidepit` — run the cockpit.  (`python -m sidepit_tui` does the same.)

    sidepit                      # the cockpit
    sidepit doggie               # open straight into the wallet view

Wallets, without the UI (flat files in ~/.sidepit/keys/, one 0600 env file
per wallet — see sidepit_trader/keystore.py):

    sidepit new [name]           # create a NEW wallet — shows 12 words ONCE
    sidepit import [name]        # paste 12 words or a WIF (hidden input)
    sidepit watch <bc1q…>        # add a watch-only wallet
    sidepit list                 # your wallets (no secrets printed)
    sidepit use <name>           # switch the active wallet

Keys are never deleted by this app, by design.
"""
import sys


def _cli(argv: list[str]) -> int:
    from sidepit_trader import keystore, wallet
    cmd = argv[0]
    if cmd in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    if cmd in ("new", "create"):
        import os
        from sidepit_trader import mnemonic
        # Seed words on stdout end up in scrollback, tmux buffers, screen
        # shares, CI logs, `script` recordings and AI-agent transcripts. So:
        # never emit them to anything but a real terminal a human is watching.
        if not (sys.stdout.isatty() and sys.stdin.isatty()):
            print("sidepit new: refusing to print seed words to a pipe, file "
                  "or non-interactive session.\nRun it in a terminal you are "
                  "sitting at — never inside an agent session, a script, or "
                  "with output redirected.", file=sys.stderr)
            return 2
        print("\nThis prints 12 secret words that ARE the wallet.")
        print("Anyone who reads them owns the money — check nobody is watching,")
        print("nothing is recording, and this window is not being shared.")
        if input("Type SHOW to continue: ").strip() != "SHOW":
            print("cancelled — nothing created.")
            return 1
        name = argv[1] if len(argv) > 1 else "trader"
        words, ident = mnemonic.new_identity_words()   # 128-bit CSPRNG entropy
        p = keystore.save_identity(name, ident.sidepit_id, ident.wif,
                                   active=False, mnemonic=words)
        w = words.split()
        print("\nNEW WALLET — write these 12 words down NOW.")
        print("They restore it here or in any standard Bitcoin wallet")
        print("(BIP39/84). There is no other recovery.\n")
        for r in range(3):                              # 3 rows of 4, readable
            print("   " + "   ".join(f"{i + 1:>2}. {w[i]:<10}"
                                     for i in range(r * 4, r * 4 + 4)))
        print(f"\n  address : {ident.sidepit_id}")
        print(f"  saved   : {p}  (0600)")
        input("\nPress Enter once they are written down — the screen clears. ")
        os.system("clear" if os.name != "nt" else "cls")
        print(f"wallet '{name}' created · {ident.sidepit_id}")
        print(f"make it active: sidepit use {name}\n")
        return 0
    if cmd == "import":
        import getpass
        from sidepit_trader import mnemonic
        name = argv[1] if len(argv) > 1 else "trader"
        raw = getpass.getpass("12 words or WIF (input hidden): ").strip()
        words = None
        if mnemonic.looks_like_words(raw):
            ident = mnemonic.identity_from_words(raw)   # validates the checksum
            words = " ".join(raw.lower().split())
        else:
            ident = wallet.from_wif(raw)                # validates the checksum
        p = keystore.save_identity(name, ident.sidepit_id, ident.wif, active=True,
                                   mnemonic=words)
        print(f"imported '{name}' → {ident.sidepit_id}\nsaved (0600): {p} (active)")
        return 0
    if cmd == "watch":
        if len(argv) < 2 or not argv[1].startswith("bc1"):
            print("usage: python -m sidepit_tui watch <bc1q…>")
            return 2
        p = keystore.save_identity(argv[1][-8:], argv[1], None, active=True)
        print(f"watching {argv[1]} (read-only)\nsaved: {p} (active)")
        return 0
    if cmd == "list":
        ids = keystore.identities()
        if not ids:
            print(f"no identities in {keystore.KEYS_DIR}")
            return 0
        for i in ids:
            mark = "*" if i["active"] else " "
            kind = "key" if i["has_key"] else "watch-only"
            print(f"{mark} {i['name']:<16} {i['sidepit_id']}  ({kind})")
        return 0
    if cmd == "use":
        if len(argv) < 2:
            print("usage: python -m sidepit_tui use <name>")
            return 2
        keystore.set_active(argv[1])
        print(f"active identity: {argv[1]}")
        return 0
    print(__doc__)
    return 2


def main(argv: list[str] | None = None) -> int | None:
    """Installed ``sidepit`` command and ``python -m sidepit_tui`` entry point."""
    from .app import main as run_app
    args = sys.argv[1:] if argv is None else argv
    if args and args[0] in ("doggie", "wallet"):
        run_app(start_doggie=True)       # same app, opens on the wallet view
        return None
    if args:
        return _cli(args)
    run_app()
    return None


if __name__ == "__main__":
    sys.exit(main())
