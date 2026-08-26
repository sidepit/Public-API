#!/usr/bin/env python3
"""Offline smoke test for an installed Sidepit distribution."""

from __future__ import annotations

import os
import tempfile


def main() -> int:
    bitcoinlib_dir = tempfile.mkdtemp(prefix="sidepit-bitcoinlib-")
    os.environ["BCL_DATA_DIR"] = bitcoinlib_dir

    import qrcode
    import sidepit_trader
    import sidepit_tui
    from sidepit_trader import mnemonic, wallet
    from sidepit_trader.proto import sidepit_api_pb2

    assert sidepit_trader.__file__
    assert sidepit_tui.__file__
    assert sidepit_api_pb2.RequestReply()
    assert len(mnemonic.wordlist()) == 2048
    words = mnemonic.entropy_to_words(bytes(16))
    assert mnemonic.words_to_entropy(words) == bytes(16)
    qr = qrcode.QRCode(border=1)
    qr.add_data("sidepit")
    qr.make(fit=True)
    assert qr.get_matrix()

    identity = wallet.from_wif(wallet.priv_to_wif("01".zfill(64)))
    wallet.utxos = lambda _address: [
        {"txid": "01" * 32, "vout": 0, "value": 100_000}
    ]
    wallet.fee_rate_sat_vb = lambda: 1
    raw, plan = wallet.build_lock_tx(identity, 50_000)
    assert raw and plan.amount_sats == 50_000 and plan.change_sats > 0
    print("installed Sidepit smoke test: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
