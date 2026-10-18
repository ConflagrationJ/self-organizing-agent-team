#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("set_invocation_mode.py")
SPEC = importlib.util.spec_from_file_location("set_invocation_mode", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MOD)


class InvocationModeTests(unittest.TestCase):
    def with_skill(self):
        tmp = tempfile.TemporaryDirectory(dir=Path.cwd())
        root = Path(tmp.name)
        (root / "agents").mkdir()
        (root / "agents" / "openai.yaml").write_text(
            "interface:\n  display_name: test\npolicy:\n  allow_implicit_invocation: true\n", encoding="utf-8"
        )
        self.addCleanup(tmp.cleanup)
        return root

    def test_auto_default_and_check(self):
        root = self.with_skill()
        self.assertEqual(MOD.read_mode(root), "auto")
        MOD.set_mode(root, "explicit")
        self.assertEqual(MOD.read_mode(root), "explicit")

    def test_set_back_to_auto(self):
        root = self.with_skill()
        MOD.set_mode(root, "explicit")
        MOD.set_mode(root, "auto")
        self.assertEqual(MOD.read_mode(root), "auto")

    def test_missing_policy_fails(self):
        tmp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(tmp.cleanup)
        with self.assertRaises(SystemExit):
            MOD.read_mode(Path(tmp.name))


if __name__ == "__main__":
    unittest.main(verbosity=2)
