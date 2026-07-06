"""Typed error hierarchy for sidepit_trader.

Only errors the SDK itself decides to raise live here. Transport errors
(pynng.Timeout etc.) are deliberately NOT wrapped yet — consumers (the TUI)
catch them by their raw types today.
"""


class SidepitError(Exception):
    """Base class for every error the sidepit_trader SDK raises on purpose."""


class CourierRuleError(SidepitError, ValueError):
    """A delegate signer attempted an account verb (unlock / register_delegate /
    revoke_delegate). Account verbs are custody-signed — a delegate cannot
    appoint, revoke, or withdraw (the courier rule). Also a ValueError so
    pre-existing `except ValueError` handlers keep working."""
