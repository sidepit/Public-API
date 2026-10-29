"""Packaging for the `sidepit` distribution. Metadata lives in pyproject.toml.

Two builds come out of this file:

* the pure wheel (default): sidepit_trader + sidepit_tui, `secp256k1` as an
  ordinary dependency — Linux and Apple Silicon get upstream's wheels;
* the bundled platform wheel (SIDEPIT_BUNDLE_SECP256K1=1): the same code plus
  the upstream `secp256k1` Python package with libsecp256k1 compiled in, for
  platforms where upstream publishes no wheel (Windows, Intel macOS). Source
  comes from tools/vendor_secp256k1.py (SHA-256 pinned). pip prefers the
  platform wheel over the pure one, so `pip install sidepit` picks it up
  without the user doing anything.
"""
import os
import pathlib

from setuptools import setup

ROOT = pathlib.Path(__file__).resolve().parent
BUNDLE = os.environ.get("SIDEPIT_BUNDLE_SECP256K1") == "1"

DEPENDENCIES = [
    "protobuf==3.20.1",
    "pynng",
    "secp256k1",
    "base58",
    "bitcoinlib",
    "textual>=8.0",
    "qrcode>=7.0",
]

packages = [
    "sidepit_trader",
    "sidepit_trader.examples",
    "sidepit_trader.proto",
    "sidepit_trader.data",
    "sidepit_tui",
]
package_dir = {
    "sidepit_trader": "python-client/sidepit_trader",
    "sidepit_trader.examples": "python-client/sidepit_trader/examples",
    "sidepit_trader.proto": "python-client/proto",
    "sidepit_trader.data": "python-client/sidepit_trader/data",
    "sidepit_tui": "users-cli/sidepit_tui",
}
kwargs = {}

if BUNDLE:
    src = pathlib.Path(os.environ.get("SECP_SRC", ROOT / "build" / "secp256k1-0.14.0"))
    if not (src / "libsecp256k1" / "src" / "secp256k1.c").exists():
        raise SystemExit(f"bundled build: run tools/vendor_secp256k1.py first ({src} is missing)")
    packages.append("secp256k1")
    package_dir["secp256k1"] = os.path.relpath(src / "secp256k1", ROOT)
    DEPENDENCIES = [d for d in DEPENDENCIES if d != "secp256k1"] + ["cffi>=1.3.0"]
    kwargs.update(
        cffi_modules=["tools/secp256k1_ffi.py:ffi"],
        ext_package="secp256k1",
        zip_safe=False,
        # cffi builds against the stable ABI: one wheel per platform, built on
        # 3.10, serves every later CPython (cp310-abi3 tag).
        options={"bdist_wheel": {"py_limited_api": "cp310"}},
    )

setup(
    packages=packages,
    package_dir=package_dir,
    package_data={"sidepit_trader": ["data/*.txt"]},
    install_requires=DEPENDENCIES,
    **kwargs,
)
