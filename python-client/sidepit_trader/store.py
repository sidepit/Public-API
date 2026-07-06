"""Local persistence the SDK owns — a single SQLite file, opened transparently.

Zero-install: `sqlite3` is stdlib, so `pip install` already has it — no server,
no native wheel, nothing for the bot author to set up. This is "the beginning of
statedb": on first use it creates `~/.sidepit/state.db` with the tables a taker
needs (1-minute bars + a trading identity), so sample code ships ready to trade.

Shared file with operations/hl_bars.py — we use DISTINCT table names
(`sidepit_bars`, not `bars`) so the two never collide.

Storage rule (load-bearing): keep proto payloads as VERBATIM bytes
(`SerializeToString`) in BLOB columns and rebuild them with `ParseFromString` —
never decompose to JSON and re-serialize. Signatures/Merkle leaves are taken over
the exact serialized bytes, so a re-serialize round-trip can silently break them.
Queryable fields live in their own columns next to the blob.
"""
import os
import sqlite3
from pathlib import Path

from ._proto import pb

from .config import STATE_DB
DEFAULT_PATH = str(STATE_DB)   # config-sourced; SIDEPIT_STATE_DB overrides

_SCHEMA = [
    # 1-minute bars, verbatim EpochBar blob + queryable (ticker, epoch).
    """CREATE TABLE IF NOT EXISTS sidepit_bars (
           ticker  TEXT NOT NULL,
           epoch   INTEGER NOT NULL,
           open    INTEGER, high INTEGER, low INTEGER, close INTEGER, volume INTEGER,
           blob    BLOB NOT NULL,
           PRIMARY KEY (ticker, epoch)
       )""",
    "CREATE INDEX IF NOT EXISTS sidepit_bars_ticker_epoch ON sidepit_bars (ticker, epoch)",
    # Trading identities. The active row (active=1) is what the bot trades with
    # unless overridden by env. `wif` is the secret — this DB is local-only.
    """CREATE TABLE IF NOT EXISTS sidepit_identity (
           name        TEXT PRIMARY KEY,
           sidepit_id  TEXT NOT NULL,
           wif         TEXT,
           priv_hex    TEXT,
           active      INTEGER NOT NULL DEFAULT 0
       )""",
    # Which (ticker, session_id) sessions are fully backfilled. A CLOSED session's
    # bars are immutable, so once `complete=1` we never re-fetch it — startup
    # backfill walks back via prev_session_id and stops at the first complete row.
    """CREATE TABLE IF NOT EXISTS sidepit_sessions (
           ticker      TEXT NOT NULL,
           session_id  TEXT NOT NULL,
           complete    INTEGER NOT NULL DEFAULT 0,
           PRIMARY KEY (ticker, session_id)
       )""",
]


class TakerStore:
    """A thin WAL-mode SQLite wrapper with the taker schema baked in.

    >>> s = TakerStore(":memory:")
    >>> s.upsert_bar(bar); s.recent_bars("USDBTCM26", limit=10)
    """

    def __init__(self, path: str = DEFAULT_PATH):
        self.path = path if path == ":memory:" else os.path.expanduser(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.migrate(_SCHEMA)

    def migrate(self, statements) -> None:
        with self.conn:
            for stmt in statements:
                self.conn.execute(stmt)

    # --- bars --------------------------------------------------------------
    def upsert_bar(self, bar) -> None:
        """Persist one EpochBar (idempotent on (ticker, epoch)). Verbatim blob +
        queryable columns. Re-inserting the same epoch overwrites (a corrected bar)."""
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO sidepit_bars "
                "(ticker, epoch, open, high, low, close, volume, blob) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (bar.ticker, bar.epoch, bar.open, bar.high, bar.low, bar.close,
                 bar.volume, bar.SerializeToString()))

    def upsert_bars(self, bars) -> int:
        n = 0
        for b in bars:
            self.upsert_bar(b)
            n += 1
        return n

    def recent_bars(self, ticker: str, limit: int = 500):
        """The most recent `limit` bars for `ticker`, returned OLDEST-first (the order
        a swing tracker wants to consume). Rebuilt from the verbatim blob."""
        rows = self.conn.execute(
            "SELECT blob FROM sidepit_bars WHERE ticker=? ORDER BY epoch DESC LIMIT ?",
            (ticker, limit)).fetchall()
        out = []
        for r in reversed(rows):
            b = pb.EpochBar()
            b.ParseFromString(r["blob"])
            out.append(b)
        return out

    def last_epoch(self, ticker: str) -> int | None:
        row = self.conn.execute(
            "SELECT MAX(epoch) AS e FROM sidepit_bars WHERE ticker=?", (ticker,)).fetchone()
        return row["e"] if row and row["e"] is not None else None

    # --- sessions (backfill bookkeeping) -----------------------------------
    def mark_session_complete(self, ticker: str, session_id: str) -> None:
        """Record that a CLOSED session's bars are fully stored — never re-fetched."""
        if not session_id:
            return
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO sidepit_sessions (ticker, session_id, complete) "
                "VALUES (?,?,1)", (ticker, session_id))

    def session_complete(self, ticker: str, session_id: str) -> bool:
        if not session_id:
            return False
        row = self.conn.execute(
            "SELECT complete FROM sidepit_sessions WHERE ticker=? AND session_id=?",
            (ticker, session_id)).fetchone()
        return bool(row and row["complete"])

    # --- identity ----------------------------------------------------------
    # Secrets do NOT live in this database. These methods delegate to the
    # flat-file keystore (~/.sidepit/keys/, one 0600 env file per identity);
    # any wif/priv found in old rows is migrated out and scrubbed on first use.
    # Kept here so existing callers keep working unchanged.

    def set_identity(self, name: str, sidepit_id: str, *, wif: str | None = None,
                     priv_hex: str | None = None, active: bool = True) -> None:
        """Store (and optionally activate) a trading identity — as a flat file."""
        from . import keystore
        if not wif and priv_hex:
            from .wallet import priv_to_wif
            wif = priv_to_wif(priv_hex)
        keystore.save_identity(name, sidepit_id, wif, active=active)

    def active_identity(self):
        """The active identity (or None) as a dict with the legacy row keys:
        name / sidepit_id / wif / priv_hex / active."""
        from . import keystore
        d = keystore.active_identity()
        if d is None:
            return None
        return {"name": d["name"], "sidepit_id": d["sidepit_id"],
                "wif": d["wif"], "priv_hex": None, "active": 1}

    def close(self) -> None:
        self.conn.close()
