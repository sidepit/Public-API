"""cffi builder for the bundled secp256k1 module (platforms with no upstream wheel).

Same cdefs, module name (`secp256k1._libsecp256k1`) and module set (ecdh,
recovery, schnorrsig, extrakeys) as upstream's own bundled build, so the
unmodified upstream Python package runs on top of it. The one difference:
libsecp256k1 (the copy inside the pinned upstream sdist) is compiled straight
into the extension as a single translation unit instead of through autotools
and pkg-config, which do not exist under MSVC.

Defines match upstream configure's defaults for the bundled build:
ECMULT_WINDOW_SIZE=15, ECMULT_GEN_PREC_BITS=4 (the shipped static table
requires window <= 15). Proven byte-exact against the SDK's golden signing
vectors on win_amd64 (sp1-windows, 2026-10-28) and Linux.

SECP_SRC may point at the unpacked sdist; default is what
tools/vendor_secp256k1.py produces.
"""
import os
import pathlib

from cffi import FFI

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = pathlib.Path(os.environ.get("SECP_SRC", ROOT / "build" / "secp256k1-0.14.0"))
LIB = SRC / "libsecp256k1"
HEADERS = ["secp256k1.h", "secp256k1_ecdh.h", "secp256k1_recovery.h",
           "secp256k1_schnorrsig.h", "secp256k1_extrakeys.h"]

ffi = FFI()
for h in HEADERS:
    ffi.cdef((SRC / "_cffi_build" / h).read_text())

ffi.set_source(
    "_libsecp256k1",
    "\n".join(f"#include <{h}>" for h in HEADERS) + "\n#define PY_USE_BUNDLED",
    # relative: distutils mirrors the source path under build/temp*, and an
    # absolute path can exceed MAX_PATH on Windows
    sources=[os.path.relpath(LIB / "src" / "secp256k1.c")],
    include_dirs=[str(LIB / "include"), str(LIB / "src"), str(LIB)],
    define_macros=[
        ("ECMULT_WINDOW_SIZE", "15"),
        ("ECMULT_GEN_PREC_BITS", "4"),
        ("ENABLE_MODULE_ECDH", "1"),
        ("ENABLE_MODULE_RECOVERY", "1"),
        ("ENABLE_MODULE_EXTRAKEYS", "1"),
        ("ENABLE_MODULE_SCHNORRSIG", "1"),
        ("CFFI_ENABLE_RECOVERY", None),
    ],
)
