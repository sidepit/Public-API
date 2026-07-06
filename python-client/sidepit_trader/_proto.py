"""Locate and re-export the generated protobuf module.

The generated `sidepit_api_pb2` lives in `python-client/proto/`. This shim makes
the SDK importable regardless of the caller's working directory by putting that
directory on `sys.path` once, then re-exporting the module as `pb`.
"""
import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
_proto_dir = os.path.abspath(os.path.join(_here, "..", "proto"))
if _proto_dir not in sys.path:
    sys.path.insert(0, _proto_dir)

import sidepit_api_pb2 as pb  # noqa: E402

__all__ = ["pb"]
