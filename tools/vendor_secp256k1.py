#!/usr/bin/env python3
"""Fetch the upstream secp256k1 0.14.0 source distribution for a bundled build.

Platforms where upstream publishes no wheel (Windows, Intel macOS) get the
compiled module inside sidepit's own platform wheel. The C code that goes
into that wheel is exactly the audited upstream tarball: this script refuses
anything whose SHA-256 differs from the pin below.

Usage: python tools/vendor_secp256k1.py   # extracts to build/secp256k1-0.14.0
"""
from __future__ import annotations

import hashlib
import pathlib
import sys
import tarfile
import urllib.request

VERSION = "0.14.0"
SHA256 = "82c06712d69ef945220c8b53c1a0d424c2ff6a1f64aee609030df79ad8383397"
URL = ("https://files.pythonhosted.org/packages/source/s/secp256k1/"
       f"secp256k1-{VERSION}.tar.gz")
ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
DEST = BUILD / f"secp256k1-{VERSION}"


def main() -> int:
    if (DEST / "libsecp256k1" / "src" / "secp256k1.c").exists():
        print(DEST)
        return 0
    BUILD.mkdir(exist_ok=True)
    tarball = BUILD / f"secp256k1-{VERSION}.tar.gz"
    if not tarball.exists():
        with urllib.request.urlopen(URL) as r:
            tarball.write_bytes(r.read())
    digest = hashlib.sha256(tarball.read_bytes()).hexdigest()
    if digest != SHA256:
        tarball.unlink()
        print(f"secp256k1-{VERSION}.tar.gz: SHA-256 {digest} != pinned {SHA256}",
              file=sys.stderr)
        return 1
    with tarfile.open(tarball) as tf:
        for m in tf.getmembers():
            if m.name.startswith("/") or ".." in pathlib.PurePosixPath(m.name).parts:
                print(f"refusing path in tarball: {m.name}", file=sys.stderr)
                return 1
        tf.extractall(BUILD)
    if not (DEST / "libsecp256k1" / "src" / "secp256k1.c").exists():
        print(f"unexpected layout under {DEST}", file=sys.stderr)
        return 1
    print(DEST)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
