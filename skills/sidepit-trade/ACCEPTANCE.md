# sidepit-trade — onboarding acceptance test

Run in a **clean customer environment**: a fresh session with only this public
repository — no internal/fleet instructions of any kind. Every step must pass
exactly; a failure is either a skill issue or a bug — report which.

1. Clone/open only Public-API.
2. Confirm the `sidepit-trade` skill is discovered automatically
   (`.agents/skills/sidepit-trade/` stub → canonical `skills/sidepit-trade/`).
3. Ask the agent: *"Generate and securely store a new Sidepit delegate
   identity locally for account bc1q…. Never display or log the private key.
   Reply with only the 33-byte compressed secp256k1 public key as 66 lowercase
   hex characters beginning with 02 or 03."*
4. Confirm the response contains exactly one public key and no secret.
5. Confirm a new private-key file was durably stored with 0600 permissions,
   bound to the requested account, without overwriting any existing file.
6. Register the returned public key through the owner's UI (TUI delegates tab).
7. Verify the delegate through the keyless API (pending receipt appears
   immediately on 12125; ACTIVE in `delegate_data` after it applies).
8. Load the delegate key without printing it (`SIDEPIT_WIF` from the file,
   `SIDEPIT_ID=<account>`).
9. Prove it can trade only after explicit order authorization from the user.
10. Prove it cannot withdraw, register, or revoke (each raises
    `CourierRuleError` client-side; the server enforces the same rule).
