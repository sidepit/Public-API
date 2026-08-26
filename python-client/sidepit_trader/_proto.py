"""Re-export the generated protobuf module bundled with the SDK wheel."""

try:
    # Installed wheel: setuptools maps python-client/proto into this package.
    from .proto import sidepit_api_pb2 as pb
except ModuleNotFoundError:
    # Source checkout: the generated file remains in its canonical sibling
    # directory. Keep direct repo usage working without duplicating generated
    # protocol code inside sidepit_trader.
    import os
    import sys

    _proto_dir = os.path.abspath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "proto"))
    if _proto_dir not in sys.path:
        sys.path.insert(0, _proto_dir)
    import sidepit_api_pb2 as pb  # noqa: E402

__all__ = ["pb"]
