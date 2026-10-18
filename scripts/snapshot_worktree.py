#!/usr/bin/env python3
"""Print a reproducible worktree snapshot revision.

The output is `worktree-snapshot:<sha256>`, which the task contract accepts as an
immutable `base_rev` when the project has no usable VCS revision. The hash covers
every regular file under the root, ordered by its POSIX relative path:

    sha256( for each file: relpath + NUL + ("link:" + target | "file:" + bytes) )

Directory names in the exclusion set are skipped anywhere in the tree, so
platform caches and local state do not make an unchanged tree look changed.

This is a drift detector, not a proof of authorship or content quality.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

EXCLUDED_DIRS = {
    ".git",
    ".dsh",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    ".sot-tmp",
    "dist",
    "build",
}


def _iter_entries(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in EXCLUDED_DIRS)
        current = Path(dirpath)
        for name in sorted(filenames):
            path = current / name
            if path.is_symlink():
                try:
                    target = os.readlink(path)
                except OSError:
                    continue
                yield path, b"link:" + target.encode("utf-8", "surrogateescape")
                continue
            try:
                data = path.read_bytes()
            except OSError as exc:
                raise SystemExit(f"cannot read {path}: {exc}") from exc
            yield path, b"file:" + data


def snapshot(root: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    count = 0
    for path, payload in _iter_entries(root):
        rel = path.relative_to(root).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(payload)
        digest.update(b"\0")
        count += 1
    return digest.hexdigest(), count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Print worktree-snapshot:<sha256> for a directory tree."
    )
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Tree to snapshot; defaults to the current directory.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(argv)

    root = Path(args.root)
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2

    digest, count = snapshot(root.resolve())
    revision = f"worktree-snapshot:{digest}"
    if args.json:
        print(json.dumps({"revision": revision, "files": count, "root": str(root)}))
    else:
        print(revision)
    return 0


if __name__ == "__main__":
    sys.exit(main())
