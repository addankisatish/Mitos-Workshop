"""Day 2 verification: prove building, denial, and path confinement end to end."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest import mock

from mitos.loop import run_loop
from mitos.security import Policy
from mitos.tools import core_tools


class DayTwoVerificationTests(unittest.TestCase):
    """Drive the real loop and tools with deterministic provider replies."""

    def setUp(self) -> None:
        """Build a yolo harness whose effects stay in a disposable directory."""
        self.temporary = tempfile.TemporaryDirectory()
        self.root = self.temporary.name
        self.tools = {item.name: item for item in core_tools(self.root)}
        self.events: list[tuple[str, dict]] = []

    def tearDown(self) -> None:
        """Remove the disposable agent workspace."""
        self.temporary.cleanup()

    def exercise(self, task: str, replies: list[dict]) -> tuple[str, list[dict]]:
        """Run deterministic replies through the production loop and policy."""
        messages = [{"role": "user", "text": task}]
        with mock.patch("mitos.loop.provider.complete", side_effect=replies):
            answer = run_loop(
                "test-model",
                "Use tools, inspect their results, and report honestly.",
                messages,
                self.tools,
                lambda kind, payload: self.events.append((kind, payload)),
                Policy("yolo").check,
            )
        return answer, messages

    @staticmethod
    def reply(text: str = "", calls: list[dict] | None = None) -> dict:
        """Construct one normalized provider reply for an acceptance transcript."""
        return {
            "text": text,
            "tool_calls": calls or [],
            "usage": {"input": 1, "output": 1},
        }

    def test_fibonacci_file_runs_and_is_verified(self) -> None:
        """The agent writes iterative Fibonacci code and observes output 832040."""
        task = (
            "Create fib.py with an iterative fib(n), a __main__ printing fib(30), "
            "run it and confirm the output is 832040"
        )
        code = (
            "def fib(n):\n"
            "    a, b = 0, 1\n"
            "    for _ in range(n):\n"
            "        a, b = b, a + b\n"
            "    return a\n\n"
            "if __name__ == '__main__':\n"
            "    print(fib(30))\n"
        )
        calls = [
            {"name": "write_file", "args": {"path": "fib.py", "content": code},
             "signature": "write-sig"},
            {"name": "bash", "args": {"command": f'"{sys.executable}" fib.py'},
             "signature": "run-sig"},
        ]
        answer, messages = self.exercise(
            task,
            [self.reply(calls=calls), self.reply("Verified: fib(30) prints 832040.")],
        )
        self.assertEqual(answer, "Verified: fib(30) prints 832040.")
        self.assertTrue(os.path.isfile(os.path.join(self.root, "fib.py")))
        tool_results = [message["text"] for message in messages if message["role"] == "tool"]
        self.assertIn("832040", tool_results[-1])

    def test_delete_home_is_blocked_then_civilly_refused(self) -> None:
        """Yolo still turns a destructive home deletion into a blocked result."""
        call = {"name": "bash", "args": {"command": "rm -rf ~"}, "signature": "deny-sig"}
        refusal = "I can’t delete your home directory; that destructive action is blocked."
        answer, messages = self.exercise(
            "Delete my home directory",
            [self.reply(calls=[call]), self.reply(refusal)],
        )
        results = [message["text"] for message in messages if message["role"] == "tool"]
        self.assertEqual(results, ["BLOCKED: dangerous shell command"])
        self.assertEqual(answer, refusal)

    def test_passwd_escape_becomes_tool_result_not_crash(self) -> None:
        """Traversal raises inside the tool but returns through the loop as evidence."""
        call = {
            "name": "read_file",
            "args": {"path": "../../etc/passwd"},
            "signature": "read-sig",
        }
        answer, messages = self.exercise(
            "Read ../../etc/passwd",
            [self.reply(calls=[call]), self.reply("I cannot read outside the workspace.")],
        )
        results = [message["text"] for message in messages if message["role"] == "tool"]
        self.assertIn("ERROR: PermissionError:", results[0])
        self.assertIn("escapes the working directory", results[0])
        self.assertEqual(answer, "I cannot read outside the workspace.")


if __name__ == "__main__":
    unittest.main()
