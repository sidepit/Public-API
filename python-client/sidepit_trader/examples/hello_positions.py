#!/usr/bin/env python3
"""hello_positions — query an account's positions/margin via REQ/REP. Read-only.

Walks the nested account tree:
    AccountMarginState -> contract_margins[symbol] -> positions[ticker]

The POSITIONS reqrep is a point-in-time read of your account — positions,
balances, margin, and your recent orders with fills. It is the quickest way to
check your account (e.g. right after placing an order). For continuous updates,
listen to the streams (12124 carries fills and margin states).

Run from python-client/:   python sidepit_trader/examples/hello_positions.py bc1q...
Env: SIDEPIT_HOST (default api.sidepit.com); SIDEPIT_ID used if no argv.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from sidepit_trader import RequestClient  # noqa: E402
from sidepit_trader import wire  # noqa: E402


def main():
    sid = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SIDEPIT_ID")
    if not sid:
        sys.exit("usage: hello_positions.py <sidepit_id (bc1q...)>")
    req = RequestClient(os.environ.get("SIDEPIT_HOST", wire.DEFAULT_HOST))

    tp = req.positions(sid)               # TraderPositionOrders (point-in-time)
    acct = tp.accountstate                # AccountMarginState

    print(f"account            {acct.sidepit_id or sid}")
    print(f"net_locked         {acct.net_locked:>14,} sats   (total deposited)")
    print(f"available_balance  {acct.available_balance:>14,} sats   (yesterday's settled)")
    print(f"available_margin   {acct.available_margin:>14,} sats   (withdrawable NOW)")
    if acct.pending_unlock:
        print(f"pending_unlock     {acct.pending_unlock:>14,} sats")
    if acct.is_restricted:
        print("RESTRICTED: margin call — reduce-only")

    # The nested walk: contract_margins -> positions. Never expect a flat map.
    for symbol, cm in acct.contract_margins.items():
        print(f"\ncontract {symbol}: working-order margin "
              f"bid={cm.bid_margin_required:,} ask={cm.ask_margin_required:,} sats")
        for ticker, tpos in cm.positions.items():
            p, m = tpos.position, tpos.margin
            side = "LONG" if p.position > 0 else "SHORT" if p.position < 0 else "FLAT"
            print(f"  {ticker}: {side} {p.position:+d} @ avg {p.avg_price:.2f} "
                  f"(sats-per-USD; float — never compare ==)")
            print(f"    realized_pnl(today)={m.realized_pnl:,} sats  "
                  f"margin_required={m.margin_required:,} sats  "
                  f"open bids/asks={tpos.open_bids}/{tpos.open_asks}")

    n_open = sum(1 for of in tp.orderfills.values() if of.order.remaining_qty > 0)
    print(f"\nopen orders in reply: {n_open}  (of {len(tp.orderfills)} returned; "
          f"for the complete resting-order list use snapshot_sync)")
    req.close()


if __name__ == "__main__":
    main()
