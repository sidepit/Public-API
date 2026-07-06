"""Central config for sidepit_trader.

SAFETY MODEL:
  * Production (default): every FUND-SAFETY value (deposit, keys, db) is
    HARD-CODED — env IGNORED, so no stray SIDEPIT_* can redirect a real lock, key
    store, or db. (HOST is operational, not fund-safety — SIDEPIT_HOST stays
    settable in production too, e.g. localhost for a local run.)
  * Testnet (SIDEPIT_TESTNET=true): the run-varying values may be overridden by
    SIDEPIT_* env vars (the examples/hello_taker.py + sourceable-secrets pattern,
    `set -a; . run.env; set +a`) — BUT any value that matches a PRODUCTION
    resource (the prod deposit address, ~/.sidepit/keys, ~/.sidepit/state.db, or
    api.sidepit.com) is a HARD FAULT. A "test" is never allowed to touch prod, and
    an unset override won't silently fall back to production.
"""
import os
import sys
from pathlib import Path

# --- production-pinned values (immutable unless SIDEPIT_TESTNET) ---
PROD_DEPOSIT_ADDRESS = "bc1qn9szw2tfte4m2l7enhentvjpvnque932xr2m03"  # sp::dataset.kDepositAddress
PROD_HOST = "api.sidepit.com"
PROD_KEYS_DIR = Path("~/.sidepit/keys").expanduser()
PROD_STATE_DB = Path("~/.sidepit/state.db").expanduser()

# chain infra — same on mainnet regardless (the test IS real mainnet BTC)
ESPLORA = "https://blockstream.info/api"
MEMPOOL_FEES = "https://mempool.space/api/v1/fees/recommended"

TESTNET = os.environ.get("SIDEPIT_TESTNET", "").strip().lower() in ("1", "true", "yes", "on")

# every fund-safety production resource a testnet override may NEVER equal
_PROD_RESOURCES = {PROD_DEPOSIT_ADDRESS, str(PROD_KEYS_DIR), str(PROD_STATE_DB)}


def _fault(msg: str):
    sys.exit(f"sidepit config refused: {msg}")


def _resolve(env_var: str, prod_value):
    """Production -> the hardcoded prod value (env IGNORED). Testnet -> the env
    override, which MUST be set AND must not match any production resource."""
    if not TESTNET:
        return prod_value
    raw = os.environ.get(env_var)
    if not raw:
        _fault(f"SIDEPIT_TESTNET set but {env_var} unset — refusing to fall back to production")
    value = Path(raw).expanduser() if isinstance(prod_value, Path) else raw
    if str(value) in _PROD_RESOURCES:
        _fault(f"{env_var}={raw!r} matches a PRODUCTION resource — refusing to test against prod")
    return value


DEPOSIT_ADDRESS = _resolve("SIDEPIT_DEPOSIT_ADDRESS", PROD_DEPOSIT_ADDRESS)
KEYS_DIR = _resolve("SIDEPIT_KEYS_DIR", PROD_KEYS_DIR)
STATE_DB = _resolve("SIDEPIT_STATE_DB", PROD_STATE_DB)

# HOST is operational (which exchange to dial), NOT a fund-safety resource — so it
# stays env-settable in PRODUCTION too (e.g. SIDEPIT_HOST=localhost in prod.env).
# The only rule: a testnet run may not point at the production host.
HOST = os.environ.get("SIDEPIT_HOST", PROD_HOST)
if TESTNET and HOST == PROD_HOST:
    _fault("SIDEPIT_TESTNET set but SIDEPIT_HOST is the production host — refusing")
