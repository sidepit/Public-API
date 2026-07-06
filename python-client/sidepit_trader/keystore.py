"""Flat-file identity store — keys NEVER live in a database.

One identity per file in `~/.sidepit/keys/` (dir 0700, files 0600), in the same
sourceable env format as the agent key files the TUI mints, so every key file
in ~/.sidepit works the same way (`set -a; source <file>; set +a`):

    # sidepit identity "trader"
    export SIDEPIT_ID=bc1q...
    export SIDEPIT_WIF=...          # absent for a watch-only identity

`ACTIVE` (a plain file holding a name) selects the active identity. Importing a
key = dropping a file here (or `python -m sidepit_tui import`). Switching =
changing ACTIVE (`python -m sidepit_tui use <name>`).

Process env wins: if SIDEPIT_WIF (or SIDEPIT_ID alone, watch-only) is set,
`active_identity()` returns that without touching disk — bots keep their
existing env-based flow.

Migration: identities found in the legacy TakerStore sqlite rows are written
out as files once, then the wif/priv columns are SCRUBBED (set NULL) so no
secret remains in the database. The rows themselves stay (names/addresses are
not secrets).
"""
from __future__ import annotations

import os
from pathlib import Path

from .config import KEYS_DIR, STATE_DB   # centralized; SIDEPIT_KEYS_DIR / SIDEPIT_STATE_DB override

ACTIVE_FILE = KEYS_DIR / "ACTIVE"


def _ensure_dir() -> None:
    KEYS_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(KEYS_DIR, 0o700)


def _path(name: str) -> Path:
    safe = "".join(c for c in name if c.isalnum() or c in "-_") or "id"
    return KEYS_DIR / f"{safe}.env"


def _parse(path: Path) -> dict:
    out = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line.startswith("export ") and "=" in line:
            k, v = line[len("export "):].split("=", 1)
            out[k.strip()] = v.strip().strip('"')
    return out


def save_identity(name: str, sidepit_id: str, wif: str | None = None,
                  active: bool = True, mnemonic: str | None = None) -> Path:
    """Write one identity file (0600). wif=None ⇒ watch-only. `mnemonic` (the
    12-word BIP39 backup, for identities minted from words) is stored alongside
    the WIF — same secrecy class, same file, same 0600.

    CORE RULE: private keys are NEVER deleted or overwritten. A key file is
    write-once — if `name` already holds DIFFERENT key material, the new
    identity is saved under an auto-suffixed name instead. (Rewriting the
    identical identity, or upgrading a watch-only file to its own key, is fine.)
    There is deliberately no delete function in this module."""
    _ensure_dir()
    p = _path(name)
    n = 2
    while p.exists():
        d = _parse(p)
        same = d.get("SIDEPIT_ID") == sidepit_id and d.get("SIDEPIT_WIF") in (wif, None)
        if same:
            break                       # idempotent rewrite / watch-only upgrade
        p = KEYS_DIR / f"{p.stem.rstrip('0123456789').rstrip('-') or 'id'}-{n}.env"
        n += 1
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(f'# sidepit identity "{p.stem}"\n')
        f.write(f"export SIDEPIT_ID={sidepit_id}\n")
        if wif:
            f.write(f"export SIDEPIT_WIF={wif}\n")
        if mnemonic:
            f.write(f'export SIDEPIT_MNEMONIC="{mnemonic}"\n')
    if active:
        set_active(p.stem)
    return p


def identities() -> list[dict]:
    """[{name, sidepit_id, has_key, active}] — never returns secrets."""
    _migrate_from_store()
    if not KEYS_DIR.is_dir():
        return []
    act = active_name()
    out = []
    for p in sorted(KEYS_DIR.glob("*.env")):
        d = _parse(p)
        if "SIDEPIT_ID" not in d:
            continue
        out.append({"name": p.stem, "sidepit_id": d["SIDEPIT_ID"],
                    "has_key": "SIDEPIT_WIF" in d, "active": p.stem == act})
    return out


def active_name() -> str | None:
    try:
        return ACTIVE_FILE.read_text().strip() or None
    except FileNotFoundError:
        return None


def set_active(name: str) -> None:
    _ensure_dir()
    if not _path(name).exists():
        raise FileNotFoundError(f"no identity '{name}' in {KEYS_DIR}")
    ACTIVE_FILE.write_text(name + "\n")


def active_identity() -> dict | None:
    """{name, sidepit_id, wif|None} for the active identity, or None.

    Resolution order: process env (SIDEPIT_WIF, or SIDEPIT_ID alone for
    watch-only) → the ACTIVE flat file → the single identity if exactly one
    file exists → None (caller onboards)."""
    wif = os.environ.get("SIDEPIT_WIF")
    if wif:
        from .wallet import from_wif   # lazy: avoid import cycle at module load
        ident = from_wif(wif)
        sid = os.environ.get("SIDEPIT_ID", ident.sidepit_id)
        return {"name": "(env)", "sidepit_id": sid, "wif": wif}
    if os.environ.get("SIDEPIT_ID"):
        return {"name": "(env)", "sidepit_id": os.environ["SIDEPIT_ID"], "wif": None}
    _migrate_from_store()
    name = active_name()
    if name is None:
        files = list(KEYS_DIR.glob("*.env")) if KEYS_DIR.is_dir() else []
        if len(files) != 1:
            return None
        name = files[0].stem
    p = _path(name)
    if not p.exists():
        return None
    d = _parse(p)
    if "SIDEPIT_ID" not in d:
        return None
    return {"name": name, "sidepit_id": d["SIDEPIT_ID"],
            "wif": d.get("SIDEPIT_WIF")}


_migrated = False


def _migrate_from_store() -> None:
    """One-time: lift identities out of the legacy sqlite rows into files,
    then SCRUB the secret columns. Quiet no-op when there is nothing to move."""
    global _migrated
    if _migrated:
        return
    _migrated = True
    db = STATE_DB
    if not db.exists():
        return
    import sqlite3
    try:
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT name, sidepit_id, wif, priv_hex, active FROM sidepit_identity "
            "WHERE wif IS NOT NULL OR priv_hex IS NOT NULL").fetchall()
    except sqlite3.Error:
        return
    def _wif_on_disk(wif: str) -> bool:
        if not KEYS_DIR.is_dir():
            return False
        return any(_parse(p).get("SIDEPIT_WIF") == wif
                   for p in KEYS_DIR.glob("*.env"))

    moved = 0
    for r in rows:
        wif = r["wif"]
        if not wif and r["priv_hex"]:
            from .wallet import priv_to_wif
            wif = priv_to_wif(r["priv_hex"])
        if not wif:
            continue
        if not _wif_on_disk(wif):        # save_identity auto-suffixes, never clobbers
            save_identity(r["name"], r["sidepit_id"], wif,
                          active=bool(r["active"]) and active_name() is None)
            moved += 1
        # CORE RULE: move, never delete — scrub THIS row only after verifying
        # byte-for-byte that its key now lives in a flat file.
        if _wif_on_disk(wif):
            with conn:
                conn.execute("UPDATE sidepit_identity SET wif=NULL, priv_hex=NULL "
                             "WHERE name=?", (r["name"],))
    conn.close()
    if moved:
        import logging
        logging.getLogger("keystore").info(
            "migrated %d identity key(s) from state.db to %s and scrubbed the "
            "database columns", moved, KEYS_DIR)
