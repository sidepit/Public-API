"""Synchronous request/reply client for the taker (positions, active product, bars).

The taker uses reqrep for three things: seed/refresh the active product + session
state, read its own position (to reconcile the local estimate), and backfill the
1-minute bar history at startup (HISTORICAL_BARS) so the swing tracker has context
before the first live bar arrives.
"""
from . import wire
from ._proto import pb
from .config import HOST as _DEFAULT_HOST   # SIDEPIT_HOST env + testnet guard live in config
from .errors import DoorRejectedError


def _verb_of(tx) -> str:
    """Which account verb a receipt's Transaction carries."""
    which = tx.WhichOneof("tx")
    return {"new_delegate": "new_delegate", "revoke_delegate": "revoke_delegate",
            "unlock_req": "unlock"}.get(which, which or "?")


def project_account_requests(tpo) -> list[dict]:
    """accountops.account_requests → plain receipt dicts (contract projection —
    no client-side state machine). Semantics (RC1 12125/TPO contract):

      is_pending=True   the immediate self-echo — RECEIVED/displayed, NOT
                        accepted or active. For a brand-new account this is the
                        only thing that exists (an id shell + this receipt).
      is_pending=False  terminal, on the SAME oid (proto3 omits false — absence
                        of the field IS false; never infer activation from it):
                        reject_code RC_NONE → applied; non-zero → rejected.

    Settled delegate truth lives in accountops.delegate_data; the live routing
    set is accountstate.active_delegates. These receipts are history."""
    out = []
    for r in tpo.accountops.account_requests:
        tx = r.account_tx
        out.append({
            "oid": r.oid,
            "verb": _verb_of(tx),
            "agent_id": (tx.new_delegate.agent_id if tx.WhichOneof("tx") == "new_delegate"
                         else tx.revoke_delegate if tx.WhichOneof("tx") == "revoke_delegate"
                         else ""),
            "is_pending": r.is_pending,
            "reject_code": int(r.reject_code),
            "reject_name": pb.RejectCode.Name(r.reject_code),
            "applied": (not r.is_pending) and r.reject_code == pb.RC_NONE,
            "rejected": (not r.is_pending) and r.reject_code != pb.RC_NONE,
        })
    return out


def project_unlock_records(tpo) -> list[dict]:
    """accountops.unlock_records → plain dicts. A restart-rebuilt RESERVED row
    may be sparse — nothing here requires unlock_tx to render."""
    name = pb.UnlockRecord.UnlockStatus.Name
    return [{
        "status_name": name(r.status),
        "amount_sats": r.amount_sats,
        "btc_txid": r.btc_txid,
        "updatetime": {int(k): name(v) for k, v in r.updatetime.items()},
        "oid": r.oid,
    } for r in tpo.accountops.unlock_records]


class RequestClient:
    def __init__(self, host: str = _DEFAULT_HOST):
        self._sock = wire.open_req(host, wire.Ports.POSITION)

    def _request(self, type_mask: int, **fields):
        req = pb.RequestReply(TypeMask=type_mask, **fields)
        self._sock.send(req.SerializeToString())
        rep = pb.ReplyRequest()
        rep.ParseFromString(self._sock.recv())
        return rep

    def active_product(self, ticker: str | None = None):
        fields = {"ticker": ticker} if ticker else {}
        return self._request(pb.ACTIVE_PRODUCT, **fields).active_product

    def exchange_state(self):
        return self.active_product().exchange_status.status.estate

    def session_id(self) -> str:
        """Current trading session id (TradingSession, falling back to SessionStatus)."""
        es = self.active_product().exchange_status
        return es.session.session_id or es.status.session_id

    def is_open(self) -> bool:
        return self.exchange_state() == pb.EXCHANGE_OPEN

    def positions(self, trader_id: str):
        return self._request(pb.POSITIONS, traderid=trader_id).trader_positions

    def unlock_records(self, sidepit_id: str) -> list[dict]:
        """Unlock (withdraw) lifecycle records for an account, as plain data —
        one dict per record from TraderPositionOrders.accountops.unlock_records:

            {status_name, amount_sats, btc_txid, updatetime, oid}

        status_name is the UnlockStatus NAME (UNLOCK_NONE / UNLOCK_PENDING /
        UNLOCK_REJECTED / UNLOCK_RESERVED / UNLOCK_PROCESSING /
        UNLOCK_COMPLETED), never a bare int; updatetime is {time: status_name}.
        A REJECTED unlock is stored and served here — read this after
        Submitter.unlock to see the verdict. Sparse rows (restart-rebuilt
        RESERVED) still render — unlock_tx is never required."""
        return project_unlock_records(self.positions(sidepit_id))

    def account_requests(self, sidepit_id: str) -> list[dict]:
        """Account-operation receipts/history for an account, keyed by oid —
        see project_account_requests for the semantics (is_pending=True means
        received/displayed only; terminal is is_pending=False on the same oid,
        applied vs rejected by reject_code)."""
        return project_account_requests(self.positions(sidepit_id))

    def historical_bars(self, ticker: str = "", session_id: str = ""):
        """1-minute bar history (HISTORICAL_BARS). Empty ticker → the server's active
        ticker; empty session_id → today's live session. Returns a BarHistory (bars
        oldest-first; walk back via prev_session_id). Closed sessions are immutable."""
        fields = {}
        if ticker:
            fields["ticker"] = ticker
        if session_id:
            fields["session_id"] = session_id
        return self._request(pb.HISTORICAL_BARS, **fields).bars

    def quote(self, ticker: str | None = None):
        """Point-in-time MarketData (QUOTE). For continuous prices subscribe 12122."""
        fields = {"ticker": ticker} if ticker else {}
        return self._request(pb.QUOTE, **fields).market_data

    def schedules(self):
        """The trading calendar (SCHEDULES) — a CalendarSchedule of upcoming sessions."""
        return self._request(pb.SCHEDULES).calendar_schedule

    def _submit_account_tx(self, stx, typemask):
        """Post a signed account verb to the 12125 metadata door. The ack means
        received; the verb is verified and applied live in-session — confirm by
        reading account state (the receipt lands in account_requests, terminal
        outcome on the same oid). Account-verb masks dispatch with == — send
        them alone, never combined with read masks. Raises DoorRejectedError
        when the REP receipt itself carries a non-zero reject_code (inbox
        failure — the verb was NOT queued)."""
        req = pb.RequestReply(TypeMask=typemask)
        req.account_tx.CopyFrom(stx)
        self._sock.send(req.SerializeToString())
        rep = pb.ReplyRequest()
        rep.ParseFromString(self._sock.recv())
        if rep.reject_code != pb.RC_NONE:
            raise DoorRejectedError(int(rep.reject_code),
                                    pb.RejectCode.Name(rep.reject_code))
        return rep

    def submit_delegate(self, stx):
        """Queue a signed new_delegate/revoke_delegate (DELEGATE door)."""
        return self._submit_account_tx(stx, pb.DELEGATE)

    def submit_unlock(self, stx):
        """Queue a signed unlock_req (UNLOCK door). The ack means received;
        the request applies live in-session. Lifecycle: PENDING (inboxed) ->
        RESERVED (available_balance debited, pending_unlock credited; the
        exchange broadcasts the BTC outflow) -> COMPLETED when the chain
        outflow is matched — or UNLOCK_REJECTED, stored and served on POSITIONS
        (read unlock_records() for the verdict). Track progress via
        accountstate.pending_unlock."""
        return self._submit_account_tx(stx, pb.UNLOCK)

    def close(self):
        self._sock.close()
