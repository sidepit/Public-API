# Sidepit distribution record

Status: **v0.1.0 is live on PyPI** as `sidepit`.

This file records the distribution decisions made for the public client. It is
the durable boundary between what works today and what is deliberately next.

## The product journey today

```sh
pip install sidepit                 # familiar path, inside a venv when required
# or: pipx install sidepit          # isolated application install
git clone --recurse-submodules https://github.com/sidepit/Public-API
```

Then use two terminals:

```text
terminal 1                       terminal 2
──────────                       ──────────
sidepit                          cd Public-API
                                 claude
                                 > Read skills/sidepit-onboarding/SKILL.md
                                   and onboard me.
```

The cockpit and Claude are two views over the same Sidepit API. The human keeps
the money key; a delegated agent key can trade and cancel but cannot withdraw or
appoint another delegate.

## What `pip install sidepit` contains today

The PyPI distribution is source-visible Python code plus its runtime data and
console entry point. It contains:

- `sidepit_tui`: cockpit, Doggie wallet, identity picker, onboarding and command
  prompt;
- `sidepit_trader`: the Python SDK for public reads, feeds, signing, orders,
  cancellation, flattening, LOCK and UNLOCK;
- generated protobuf bindings;
- the BIP39 wordlist and mnemonic support;
- runnable SDK examples;
- the `sidepit` executable entry point; and
- declared runtime dependencies.

It deliberately does not contain the old `users-cli/cli` implementation, Git
history, repository tests, the protocol source tree, or the Claude skills.

The installed public names are `sidepit`, `sidepit_tui` and `sidepit_trader`.
Those names are the contract. Their source directories inside this repository
may move without changing user commands or imports.

## Next: bundle the agent skills

The next distribution step is to ship the complete skill bundles—not isolated
`SKILL.md` files—inside the same wheel:

- `sidepit-onboarding`;
- `sidepit-trade`; and
- `sidepit-charts`.

Scripts and referenced resources must travel with each skill. The intended UX:

```sh
sidepit skills install claude
```

That command will copy the bundled, version-matched skills into
`~/.claude/skills/`. It must:

1. report every target and installed version;
2. never silently overwrite a locally modified skill;
3. be idempotent;
4. offer an explicit upgrade/sync path; and
5. require no GitHub request after the original package installation.

Until that command ships, cloning this repository is the supported way to give
Claude the skills.

## One package, one update channel

The TUI, SDK and skills should share one release version:

```text
sidepit 0.2.0
├── TUI 0.2.0
├── SDK 0.2.0
└── skills 0.2.0
```

The intended update UX is:

```sh
sidepit update
```

It should check PyPI, upgrade the containing pipx installation when applicable,
then synchronize bundled skills while preserving local modifications. The TUI
may perform a quiet, rate-limited version check and display the available
version. Trading software and agent instructions must never update silently.

The underlying explicit operations remain:

```sh
pipx upgrade sidepit
sidepit skills sync claude
```

## Source-layout cleanup

`sidepit_tui` currently lives under `users-cli/`. It should move up to a
first-class source path after the legacy `users-cli/cli` tree is audited. The
old CLI is not part of the PyPI package today. Moving the TUI source later must
only change build mappings; installed imports and the `sidepit` command remain
stable.

## Windows, one step later

Windows users should eventually need neither Python nor a repository clone.
The practical first release is a signed standalone `sidepit.exe`, built on a
Windows runner and wrapped in an installer:

```powershell
winget install Sidepit.Sidepit
sidepit
```

The executable still renders the cockpit as a TUI. A Start-menu shortcut opens
it in Windows Terminal, falling back to the standard console when necessary.
The executable bundles Python, SDK, TUI, skills and native dependencies.

The Windows gate is a clean-machine proof for the `pynng` and `secp256k1`
native libraries, Authenticode signing to avoid SmartScreen warnings, and a
working install/upgrade/uninstall cycle. Prefer a packaged directory inside a
signed installer over a single-file freezer for the first release: native DLL
handling is clearer, startup is faster, and antivirus false positives are less
likely.

Windows updates should flow through:

```powershell
winget upgrade Sidepit.Sidepit
```

## Release posture

- PyPI production publishing uses GitHub Actions Trusted Publishing—no long-lived
  PyPI token.
- A version tag must exactly match the package version (`v0.1.0` → `0.1.0`).
- The protected `pypi` GitHub environment requires human approval and accepts
  only `v*` tags.
- Every release builds a wheel and source distribution, runs tests, checks
  metadata and archive contents, installs the exact wheel, and exercises the
  CLI plus offline SDK/TUI wallet paths before upload.
- Published versions are immutable. Version bumps are new releases, never
  replacements.

The north star is simple: one install gives a human the cockpit, a developer the
SDK, and an agent the playbook—then one explicit update keeps all three aligned.
