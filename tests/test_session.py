"""Day 4 session tests: verify naming, JSONL durability, and crash repair."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mitos.session import SESSION_DIR, append, latest, load, new_session


class SessionTests(unittest.TestCase):
    """Exercise session lifecycle behavior inside a disposable project."""

    def setUp(self) -> None:
        """Create a fresh work directory for one session test."""
        self.temporary = tempfile.TemporaryDirectory()
        self.root = self.temporary.name

    def tearDown(self) -> None:
        """Remove the disposable session project."""
        self.temporary.cleanup()

    def test_new_session_slugifies_and_clips_the_label(self) -> None:
        """Session names use a timestamp and at most forty safe slug characters."""
        with mock.patch("mitos.session.time.time", return_value=1234567890):
            path = new_session(self.root, " My Long_Label! " * 8)
        filename = Path(path).name
        self.assertTrue(filename.startswith("1234567890-"))
        slug = filename.removeprefix("1234567890-").removesuffix(".jsonl")
        self.assertLessEqual(len(slug), 40)
        self.assertRegex(slug, r"^[a-z0-9-]+$")
        self.assertTrue(Path(self.root, SESSION_DIR).is_dir())

    def test_append_writes_one_unicode_json_object_per_line(self) -> None:
        """Unicode text stays readable and every append produces one JSONL record."""
        path = new_session(self.root)
        append(path, {"role": "user", "text": "Ahoy café"})
        append(path, {"role": "assistant", "text": "Ready", "tool_calls": []})
        lines = Path(path).read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[0])["text"], "Ahoy café")
        self.assertIn("café", lines[0])

    def test_load_stops_at_torn_tail_and_repairs_missing_results(self) -> None:
        """Valid history survives a torn line and unfinished calls gain observations."""
        path = new_session(self.root)
        append(path, {"role": "user", "text": "Build two files"})
        append(path, {
            "role": "assistant", "text": "", "tool_calls": [
                {"name": "write_file", "args": {"path": "one.txt"}},
                {"name": "write_file", "args": {"path": "two.txt"}},
            ],
        })
        append(path, {"role": "tool", "name": "write_file", "text": "Wrote one.txt"})
        with open(path, "a", encoding="utf-8") as handle:
            handle.write('{"role": "tool", "name":')
        messages = load(path)
        self.assertEqual(len(messages), 4)
        self.assertEqual(messages[-1], {
            "role": "tool", "name": "write_file",
            "text": "Interrupted before this ran (process restarted).",
        })

    def test_repair_adds_each_unanswered_call_in_order(self) -> None:
        """A crash before execution receives one synthetic result per pending call."""
        path = new_session(self.root)
        append(path, {"role": "assistant", "text": "", "tool_calls": [
            {"name": "first", "args": {}}, {"name": "second", "args": {}},
        ]})
        repaired = load(path)
        self.assertEqual([item["name"] for item in repaired[1:]], ["first", "second"])

    def test_latest_returns_newest_jsonl_or_none(self) -> None:
        """Resume discovery ignores other files and selects the newest session."""
        self.assertIsNone(latest(self.root))
        first = new_session(self.root, "first")
        second = new_session(self.root, "second")
        Path(first).touch()
        Path(second).touch()
        os.utime(first, (1_700_000_000, 1_700_000_000))
        os.utime(second, (1_700_000_010, 1_700_000_010))
        Path(self.root, SESSION_DIR, "ignore.txt").touch()
        self.assertEqual(latest(self.root), second)


if __name__ == "__main__":
    unittest.main()
