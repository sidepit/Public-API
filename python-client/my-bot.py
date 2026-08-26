"""my-bot — the smallest possible Sidepit trading bot.

Reads your key from the environment (see .env.example), prints the live quote,
and is yours to extend. Run:  python my-bot.py
"""
import os
from sidepit_trader.signer import signer_from_env
from sidepit_trader.reqrep import ReqRep

signer = signer_from_env()          # SIDEPIT_WIF (+ SIDEPIT_ID for delegate mode)
print(f"trading as {signer.sidepit_id}" + (f" via agent {signer.trader_id}" if signer.trader_id else ""))

req = ReqRep()
try:
    tp = req.positions(signer.sidepit_id)
    print(f"available margin: {int(tp.accountstate.available_margin):,} sats")
finally:
    req.close()
# Your strategy goes here — see skills/sidepit-trade and AGENTS.md.
