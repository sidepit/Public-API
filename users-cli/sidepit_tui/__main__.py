"""`python -m sidepit_tui` — run the cockpit. SIDEPIT_HOST overrides the venue.

Key management without the UI (flat files in ~/.sidepit/keys/, one 0600 env
file per identity — see sidepit_trader/keystore.py):

    python -m sidepit_tui import [name]   # paste a WIF (hidden), save + activate
    python -m sidepit_tui watch <bc1q…>   # add a watch-only identity
    python -m sidepit_tui list            # identities (no secrets printed)
    python -m sidepit_tui use <name>      # switch the active identity
"""
import sys


def _cli(argv: list[str]) -> int:
    from sidepit_trader import keystore, wallet
    cmd = argv[0]
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


if __name__ == "__main__":
    if len(sys.argv) > 1:
        sys.exit(_cli(sys.argv[1:]))
    from .app import main
    main()
