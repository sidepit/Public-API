"""RC1 12125/TPO account-operation contract — client-side projection tests.

Pins the semantics from the FullMonte-Merge-wip@98ff22d handoff:
  - account_requests are receipts/history keyed by oid; is_pending=True means
    received/displayed, NOT accepted; terminal lands on the SAME oid with
    is_pending=False and reject_code deciding applied vs rejected (proto3 may
    omit false — absence of the field IS the terminal marker, never activation).
  - unlock display truth is accountops.unlock_records; a restart-rebuilt
    RESERVED row may be sparse (no unlock_tx) and must still render.
  - a non-zero ReplyRequest.reject_code on the door REP raises DoorRejectedError.
No network anywhere.
"""
import pytest

from sidepit_trader._proto import pb
from sidepit_trader.errors import DoorRejectedError
from sidepit_trader.reqrep import (RequestClient, project_account_requests,
                                   project_unlock_records)


def _tpo():
    return pb.TraderPositionOrders(traderid="bc1qcustody")


def _delegate_receipt(tpo, oid, agent, *, pending, reject=pb.RC_NONE):
    r = tpo.accountops.account_requests.add()
    r.oid = oid
    r.is_pending = pending
    r.reject_code = reject
    r.account_tx.new_delegate.agent_id = agent
    return r


def test_pending_receipt_is_received_not_active():
    tpo = _tpo()
    _delegate_receipt(tpo, "bc1qcustody:1", "bc1qagent", pending=True)
    (r,) = project_account_requests(tpo)
    assert r["verb"] == "new_delegate" and r["agent_id"] == "bc1qagent"
    assert r["is_pending"] and not r["applied"] and not r["rejected"]


def test_terminal_applied_vs_rejected_on_same_oid():
    tpo = _tpo()
    _delegate_receipt(tpo, "bc1qcustody:1", "bc1qagent", pending=False)
    _delegate_receipt(tpo, "bc1qcustody:2", "bc1qother", pending=False,
                      reject=pb.RC_ID)
    ok, bad = project_account_requests(tpo)
    assert ok["applied"] and not ok["rejected"] and ok["reject_name"] == "RC_NONE"
    assert bad["rejected"] and not bad["applied"] and bad["reject_name"] == "RC_ID"


def test_absent_is_pending_is_terminal_not_activation():
    # Wire round-trip with is_pending unset (proto3 omits false): the receipt
    # must read as terminal-applied, and nothing here claims delegate ACTIVE —
    # activation truth lives in delegate_data, which stays empty.
    tpo = _tpo()
    r = tpo.accountops.account_requests.add()
    r.oid = "bc1qcustody:3"
    r.account_tx.new_delegate.agent_id = "bc1qagent"
    reparsed = pb.TraderPositionOrders()
    reparsed.ParseFromString(tpo.SerializeToString())
    (rec,) = project_account_requests(reparsed)
    assert not rec["is_pending"] and rec["applied"]
    assert len(reparsed.accountops.delegate_data) == 0   # no settled truth conjured


def test_unlock_and_revoke_verbs_project():
    tpo = _tpo()
    u = tpo.accountops.account_requests.add()
    u.oid = "bc1qcustody:4"; u.is_pending = True
    u.account_tx.unlock_req.minmax = pb.MAX
    v = tpo.accountops.account_requests.add()
    v.oid = "bc1qcustody:5"; v.is_pending = True
    v.account_tx.revoke_delegate = "bc1qagent"
    ru, rv = project_account_requests(tpo)
    assert ru["verb"] == "unlock" and ru["agent_id"] == ""
    assert rv["verb"] == "revoke_delegate" and rv["agent_id"] == "bc1qagent"


def test_sparse_reserved_unlock_row_renders_without_unlock_tx():
    tpo = _tpo()
    r = tpo.accountops.unlock_records.add()
    r.status = pb.UnlockRecord.UNLOCK_RESERVED
    r.oid = "bc1qcustody:6"
    r.amount_sats = 100_000
    # no unlock_tx, no btc_txid, no updatetime — the restart-rebuilt shape
    (row,) = project_unlock_records(tpo)
    assert row["status_name"] == "UNLOCK_RESERVED"
    assert row["amount_sats"] == 100_000 and row["btc_txid"] == ""
    assert row["updatetime"] == {} and row["oid"] == "bc1qcustody:6"


def test_unlock_lifecycle_names_and_txid():
    tpo = _tpo()
    r = tpo.accountops.unlock_records.add()
    r.status = pb.UnlockRecord.UNLOCK_COMPLETED
    r.btc_txid = "ab" * 32
    r.updatetime[1000] = pb.UnlockRecord.UNLOCK_RESERVED
    r.updatetime[2000] = pb.UnlockRecord.UNLOCK_COMPLETED
    (row,) = project_unlock_records(tpo)
    assert row["status_name"] == "UNLOCK_COMPLETED"
    assert row["updatetime"] == {1000: "UNLOCK_RESERVED",
                                 2000: "UNLOCK_COMPLETED"}
    assert row["btc_txid"] == "ab" * 32


def test_door_reject_raises():
    class FakeSock:
        def __init__(self, rep_bytes): self._rep = rep_bytes
        def send(self, data): pass
        def recv(self): return self._rep

    rc = RequestClient.__new__(RequestClient)   # no dial
    rejected = pb.ReplyRequest(reject_code=pb.RC_OTHER)
    rc._sock = FakeSock(rejected.SerializeToString())
    with pytest.raises(DoorRejectedError) as ei:
        rc._submit_account_tx(pb.SignedTransaction(), pb.UNLOCK)
    assert ei.value.code_name == "RC_OTHER"

    accepted = pb.ReplyRequest()                # RC_NONE — no raise
    rc._sock = FakeSock(accepted.SerializeToString())
    rep = rc._submit_account_tx(pb.SignedTransaction(), pb.UNLOCK)
    assert rep.reject_code == pb.RC_NONE
