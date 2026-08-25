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


class DoorRejectedError(SidepitError):
    """The 12125 door refused to inbox an account verb — the REP receipt came
    back with a non-zero reject_code (ReplyRequest.reject_code, e.g. the durable
    AccountOpWriter write failed). The verb was NOT queued; nothing will apply.
    Distinct from a terminal rejection AFTER intake, which is served on the
    request's own receipt (AccountRequest.reject_code via account_requests())."""

    def __init__(self, code: int, code_name: str):
        self.code = code
        self.code_name = code_name
        super().__init__(f"account-verb door rejected the submit: {code_name}")
