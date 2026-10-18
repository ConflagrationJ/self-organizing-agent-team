#!/usr/bin/env python3
"""Switch the installed skill between automatic and explicit invocation.

The source of truth is ``agents/openai.yaml``. This helper only changes the
``allow_implicit_invocation`` boolean; it does not edit the skill rules.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


POLICY_RE = re.compile(r"^(\s*)allow_implicit_invocation:\s*(true|false)\s*$", re.MULTILINE)


def policy_path(skill_root: Path) -> Path:
    return skill_root / "agents" / "openai.yaml"


def read_mode(skill_root: Path) -> str:
    path = policy_path(skill_root)
    if not path.is_file():
        raise SystemExit(f"missing policy file: {path}")
    text = path.read_text(encoding="utf-8")
    match = POLICY_RE.search(text)
    if not match:
        raise SystemExit(f"allow_implicit_invocation not found in {path}")
    return "auto" if match.group(2) == "true" else "explicit"


def set_mode(skill_root: Path, mode: str) -> str:
    path = policy_path(skill_root)
    if not path.is_file():
        raise SystemExit(f"missing policy file: {path}")
    text = path.read_text(encoding="utf-8")
    value = "true" if mode == "auto" else "false"
    updated, count = POLICY_RE.subn(lambda m: f"{m.group(1)}allow_implicit_invocation: {value}", text)
    if count != 1:
        raise SystemExit(f"expected one allow_implicit_invocation entry in {path}, found {count}")
    path.write_text(updated, encoding="utf-8")
    return mode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Switch Codex skill invocation mode.")
    parser.add_argument("--skill-root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--mode", choices=("auto", "explicit"))
    parser.add_argument("--check", action="store_true", help="Print the current mode without changing it.")
    args = parser.parse_args(argv)

    if args.check:
        print(read_mode(args.skill_root))
        return 0
    if not args.mode:
        parser.error("use --mode auto|explicit or --check")
    set_mode(args.skill_root, args.mode)
    print(f"mode={args.mode} policy={policy_path(args.skill_root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
