"""Flatten — cancel every resting order, close the net position, verify flat.

The emergency-exit / end-of-strategy tool, runnable directly:

    SIDEPIT_ID=bc1q... SIDEPIT_WIF=... python -m sidepit_trader.flatten

Order list comes from the SNAPSHOT sync (12129) — the complete list of resting
orders for an account. Net position comes from accountstate
(contract_margins -> positions). Residual position is closed with a marketable limit.
"""
import logging
import os
import sys
import time

from . import wire
from ._proto import pb
from .reqrep import RequestClient
from .signer import Signer, signer_from_env
from .submit import Submitter
from .sync import snapshot_sync

log = logging.getLogger("flatten")


def net_positions(req: RequestClient, sidepit_id: str) -> dict:
    """{ticker: signed net qty} from accountstate (contract_margins -> positions)."""
    acct = req.positions(sidepit_id).accountstate
    out = {}
    for cm in acct.contract_margins.values():
        for ticker, tpos in cm.positions.items():
            if tpos.position.position:
                out[ticker] = tpos.position.position
    return out


def flatten(signer: Signer, host: str, *, cross_ticks: int = 2,
            settle_secs: float = 3.0) -> bool:
    """Cancel all resting orders, close all net positions, return True when flat."""
    sid = signer.sidepit_id
    req = RequestClient(host)
    sub = Submitter(signer, host)

    # 1. Cancel everything resting (authoritative list = snapshot sync).
    orders, _ = snapshot_sync(host, sidepit_id=sid)
    for oid in orders:
        sub.cancel(oid)
    if orders:
        log.info("canceled %d resting order(s)", len(orders))
        time.sleep(settle_secs)   # let the cancels land in an epoch

    # 2. Close any net position with a marketable limit per ticker.
    for ticker, net in net_positions(req, sid).items():
        q = req.quote(ticker).quote
        side = -1 if net > 0 else 1
        oid, px = sub.market_order(side, abs(net), ticker, bid=q.bid, ask=q.ask,
                                   last=q.last, cross_ticks=cross_ticks)
        log.info("closing %+d %s with %s %d @ %s", net, ticker,
                 "SELL" if side < 0 else "BUY", abs(net), px)
    time.sleep(settle_secs)

    # 3. Verify.
    remaining = net_positions(req, sid)
    leftovers, _ = snapshot_sync(host, sidepit_id=sid)
    for oid in leftovers:         # e.g. our own close order resting unfilled
        sub.cancel(oid)
    flat = not remaining
    log.info("flatten %s: positions=%s open_orders=%d", "OK" if flat else "INCOMPLETE",
             remaining or "{}", len(leftovers))
    req.close()
    return flat


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    try:
        # Delegate-aware: SIDEPIT_WIF=<agent key> + SIDEPIT_ID=<custody> builds
        # an as_delegate signer (agent_id stamped); same/absent SIDEPIT_ID = direct.
        signer = signer_from_env()
    except ValueError as e:
        sys.exit(str(e))
    host = os.environ.get("SIDEPIT_HOST", wire.DEFAULT_HOST)
    ok = flatten(signer, host)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
