"""Sidepit TUI — human-operated onboarding and trading terminal.

This package is the human side of the platform: mint keys, fund (lock), trade,
appoint/revoke agent delegates, and withdraw (unlock) — all on the same
`sidepit_trader` SDK that bots and the public gateway use.

The SDK lives in `python-client/` in this repo (path-based, no pip package);
this bootstrap makes `import sidepit_trader` work from any CWD as long as the
repo layout is intact.
"""
import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
_pyclient = os.path.abspath(os.path.join(_here, "..", "..", "python-client"))
if _pyclient not in sys.path:
    sys.path.insert(0, _pyclient)
