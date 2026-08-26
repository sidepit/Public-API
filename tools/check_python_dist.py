#!/usr/bin/env python3
"""Fail if a Sidepit wheel or sdist is missing public package content."""

from __future__ import annotations

import argparse
import tarfile
import zipfile
from pathlib import Path


WHEEL_FILES = {
    "sidepit_trader/__init__.py",
    "sidepit_trader/data/bip39_english.txt",
    "sidepit_trader/examples/hello_market_data.py",
    "sidepit_trader/proto/sidepit_api_pb2.py",
    "sidepit_tui/__init__.py",
    "sidepit_tui/__main__.py",
    "sidepit_tui/app.py",
}

SDIST_FILES = {
    "LICENSE",
    "README.md",
    "pyproject.toml",
}

SDIST_SUFFIXES = {
    "/proto/sidepit_api_pb2.py",
    "/sidepit_trader/data/bip39_english.txt",
    "/sidepit_tui/app.py",
}


def check_wheel(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        missing = WHEEL_FILES - names
        if missing:
            raise SystemExit(f"{path}: missing {sorted(missing)}")
        entry_name = next(
            (name for name in names if name.endswith(".dist-info/entry_points.txt")),
            None,
        )
        if entry_name is None:
            raise SystemExit(f"{path}: missing entry_points.txt")
        entries = archive.read(entry_name).decode()
        if "sidepit = sidepit_tui.__main__:main" not in entries:
            raise SystemExit(f"{path}: sidepit console entry point is wrong")


def check_sdist(path: Path) -> None:
    with tarfile.open(path, "r:gz") as archive:
        names = archive.getnames()
    roots = {name.split("/", 1)[0] for name in names if "/" in name}
    if len(roots) != 1:
        raise SystemExit(f"{path}: expected one archive root, found {sorted(roots)}")
    root = roots.pop()
    missing = {name for name in SDIST_FILES if f"{root}/{name}" not in names}
    if missing:
        raise SystemExit(f"{path}: missing {sorted(missing)}")
    missing_suffixes = {
        suffix for suffix in SDIST_SUFFIXES
        if not any(name.endswith(suffix) for name in names)
    }
    if missing_suffixes:
        raise SystemExit(f"{path}: missing package content {sorted(missing_suffixes)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archives", nargs="+", type=Path)
    args = parser.parse_args()
    for path in args.archives:
        if path.suffix == ".whl":
            check_wheel(path)
        elif path.name.endswith(".tar.gz"):
            check_sdist(path)
        else:
            raise SystemExit(f"unsupported archive: {path}")
        print(f"ok: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
