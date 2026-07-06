"""sidepit facade — localhost JSON REST + WebSocket boundary over the NNG/protobuf core.

This is the ONLY surface external integrations (CCXT, scripts, UIs) talk to. It wraps
`sidepit_trader` (signing, feeds, reqrep, snapshot sync) and holds the signing key;
clients make plain HTTP/WS calls and never see protobuf, NNG, or key material.

Run:  python -m facade.server     (binds 127.0.0.1; see facade/README.md)
"""
