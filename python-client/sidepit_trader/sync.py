"""Mid-session snapshot sync — the authoritative view of resting orders.

Protocol (mirrors the Rust trader's sync.rs and trader.h:sync_orderbook):
subscribe 12129 FIRST, trigger `SNAPSHOT` on 12125 (the immediate empty reply is just an
ACK), then drain 12129 until the END sentinel. Sentinels ride in `OrderData.version`:
-1 = start, -2 = done — and BOTH sentinel messages can carry orders, so they are
processed, not skipped (a whole snapshot can be just the -1 and -2 messages).

This is the source the cancel-all/flatten tool uses: it is the only complete list of
resting orders for an account (your local view may have missed feed messages while
disconnected).
"""
import logging
import time

from . import wire
from ._proto import pb

log = logging.getLogger("sync")

START_SYNC = -1   # OrderData.version sentinel: snapshot begins (carries orders too)
END_SYNC = -2     # OrderData.version sentinel: snapshot complete (carries orders too)


def snapshot_sync(host: str, sidepit_id: str | None = None,
                  timeout_ms: int = 15000) -> tuple[dict, int]:
    """Full open-order sync. Returns ({orderid: BookOrder} of OPEN orders, sync_epoch).

    `sidepit_id` filters to one account's orders (None = the whole book). Raises
    pynng.Timeout if the stream stalls past `timeout_ms` (exchange closed / no worker).
    After this returns, switch to the live order feed (12124) and fold deltas.
    """
    snap = wire.open_sub(host, wire.Ports.SNAPSHOT)
    snap.recv_timeout = timeout_ms
    time.sleep(0.05)   # let the subscription register server-side before triggering

    req = wire.open_req(host, wire.Ports.POSITION)
    try:
        req.send(pb.RequestReply(TypeMask=pb.SNAPSHOT).SerializeToString())
        req.recv()     # empty ReplyRequest = ACK; the data arrives on 12129
    finally:
        req.close()

    orders: dict = {}
    sync_epoch = 0
    started = False
    try:
        while True:
            od = pb.OrderData()
            od.ParseFromString(snap.recv())
            if od.version == START_SYNC:
                if started:
                    log.warning("second START_SYNC — restarting accumulation")
                orders.clear()
                started = True
            for bo in od.bookorders:
                if sidepit_id and bo.traderid != sidepit_id:
                    continue
                if bo.remaining_qty > 0:
                    orders[bo.orderid] = bo
                else:
                    orders.pop(bo.orderid, None)
            if od.epoch:
                sync_epoch = od.epoch
            if od.version == END_SYNC:
                break
    finally:
        snap.close()
    log.info("snapshot synced: %d open order(s)%s up to epoch=%d", len(orders),
             f" for {sidepit_id}" if sidepit_id else "", sync_epoch)
    return orders, sync_epoch
