"""Day 4 package tests: verify exports, module execution, and runtime ignores."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

import mitos
from mitos.cli import main


class PackageTests(unittest.TestCase):
    """Exercise the public imports and executable package entry point."""

    def test_public_exports_are_exact(self) -> None:
        """The package root exposes only the requested extension surface."""
        self.assertEqual(mitos.__all__, ["Harness", "Policy", "Tool", "tool", "run_fleet"])
        self.assertTrue(all(hasattr(mitos, name) for name in mitos.__all__))

    def test_cli_and_module_execution_succeed(self) -> None:
        """Both direct and ``python -m mitos`` entry paths return successfully."""
        with mock.patch("builtins.input", side_effect=EOFError):
            self.assertEqual(main([]), 0)
        completed = subprocess.run(
            [sys.executable, "-m", "mitos"], input="", capture_output=True,
            text=True, timeout=10,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Mitos — model", completed.stdout)

    def test_runtime_sessions_are_gitignored(self) -> None:
        """Durable local transcripts stay outside repository history."""
        root = Path(__file__).resolve().parents[1]
        entries = root.joinpath(".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn(".mitos/", entries)


if __name__ == "__main__":
    unittest.main()
