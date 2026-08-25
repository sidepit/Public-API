"""Order verbs return the full orderid string "{sidepit_id}:{timestamp_ns}" —
the handle that appears on every feed. Pure construction, NO network
(Submitter built without a socket; _push stubbed)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import pytest  # noqa: E402

from sidepit_trader import wallet  # noqa: E402
from sidepit_trader.submit import Submitter, order_id  # noqa: E402


@pytest.fixture(scope="module")
def ident():
    return wallet.gen_key()


@pytest.fixture()
def sub(ident):
    s = Submitter.__new__(Submitter)
    s._signer = ident.signer()
    s._sent = []
    s._push = s._sent.append
    return s


def test_new_order_returns_full_orderid(sub, ident):
    oid = sub.new_order(side=1, size=1, price=1500, ticker="USDBTCM26")
    sid, _, ts = oid.partition(":")
    assert sid == ident.sidepit_id
    assert oid == order_id(ident.sidepit_id, int(ts))
    assert int(ts) == sub._sent[0].transaction.timestamp


def test_market_order_returns_full_orderid(sub, ident):
    oid = sub.market_order(side=1, size=1, ticker="USDBTCM26")
    assert oid.startswith(ident.sidepit_id + ":")
    tx = sub._sent[0].transaction.new_order
    assert tx.price == 0
    assert tx.side == 1
    assert tx.size == 1
    assert tx.ticker == "USDBTCM26"
    assert "price" not in {field.name for field, _value in tx.ListFields()}


def test_cancel_returns_cancel_txs_own_orderid(sub, ident):
    target = sub.new_order(side=1, size=1, price=1500, ticker="USDBTCM26")
    cancel_oid = sub.cancel(target)
    assert cancel_oid.startswith(ident.sidepit_id + ":")
    assert cancel_oid != target
    assert sub._sent[1].transaction.cancel_orderid == target


def test_cancel_replace_returns_replacement_orderid(sub, ident):
    target = sub.new_order(side=1, size=1, price=1500, ticker="USDBTCM26")
    new_oid = sub.cancel_replace(target, price=1501)
    assert new_oid.startswith(ident.sidepit_id + ":")
    assert new_oid != target
    tx = sub._sent[1].transaction
    assert tx.replace_order.ref_orderid == target
    assert new_oid == order_id(ident.sidepit_id, tx.timestamp)
