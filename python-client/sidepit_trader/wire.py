"""NNG endpoints and socket factories for the SDK.

The SDK consumes the standard exchange surface: the price feed, the 1-minute
bar feed, the order/fills feed, positions via request/reply, order intake,
rejections, and the snapshot stream.

Feeds are pub/sub
(Sub0), transaction submission is push (Push0), positions/reply-requests are
request/reply (Req0). Drained synchronously (see feeds.py) — no asyncio.
"""
import logging

import pynng

from .config import PROD_HOST as DEFAULT_HOST   # single source; SIDEPIT_HOST + testnet guard live in config

log = logging.getLogger("wire")


class Ports:
    CLIENT_API = 12121   # Push:  signed transaction submission
    PRICE_FEED = 12122   # Sub:   MarketData (quote + in-progress bar)
    ORDER = 12124        # Sub:   OrderData (post-match book + fills)
    POSITION = 12125     # Req:   RequestReply <-> ReplyRequest (positions, bars, active)
    BAR = 12127          # Sub:   EpochBar (1-minute closed bars)
    BARS = BAR           # alias (authoritative port-map name)
    REJECTIONS = 12128   # Sub:   RejectedTransaction (RC_CREJ/RC_CDUP are expected, not errors)
    SNAPSHOT = 12129     # Sub:   OrderData snapshot stream (triggered via SNAPSHOT on 12125)


def url(host: str, port: int) -> str:
    return f"tcp://{host}:{port}"


def _dial(sock, addr: str, what: str):
    """Dial with the working client's pattern (sidepit_nng_client.init_trading): the pynng
    DEFAULT dial (block=None) does a blocking connect first, then falls back to background
    retry — so the pipe is up before we use it, and it self-heals. Surface a hard failure."""
    try:
        sock.dial(addr)
    except Exception as e:
        log.error("%s connect failed (%s): %s", what, addr, e)
        sock.close()
        raise
    return sock


SEND_TIMEOUT_MS = 5000   # NNG_OPT_SENDTIMEO: a send that can't reach a live pipe raises
                         # pynng.Timeout instead of hanging forever / silently vanishing.


def open_push(host: str, port: int = Ports.CLIENT_API) -> pynng.Push0:
    s = pynng.Push0()
    s.tcp_keepalive = True            # NNG_OPT_TCP_KEEPALIVE — keep the idle pipe alive
    s.send_timeout = SEND_TIMEOUT_MS
    return _dial(s, url(host, port), "push(12121)")


def open_sub(host: str, port: int) -> pynng.Sub0:
    s = pynng.Sub0()
    s.subscribe(b"")   # empty topic = subscribe to everything (matches the C++/mmbot clients)
    return _dial(s, url(host, port), f"sub({port})")


REQ_RECV_TIMEOUT_MS = 5000   # NNG_OPT_RECVTIMEO: a missing/slow reply raises pynng.Timeout
                             # instead of blocking forever. The taker polls active_product
                             # every ~2s on its main loop; without this, an unresponsive
                             # exchange (restart / between sessions) hangs the whole bot —
                             # no price polling, no SIGINT. Callers wrap reqrep in try/except.


def open_req(host: str, port: int = Ports.POSITION) -> pynng.Req0:
    s = pynng.Req0()
    s.recv_timeout = REQ_RECV_TIMEOUT_MS
    return _dial(s, url(host, port), f"req({port})")
