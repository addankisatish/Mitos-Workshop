"""Day 4 verification: hard-kill resume and two ephemeral sub-agent builds."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mitos import Harness


def reply(text: str = "", calls: list[dict] | None = None) -> dict:
    """Create one provider-neutral response for deterministic acceptance runs."""
    return {"text": text, "tool_calls": calls or [], "usage": {"input": 1, "output": 1}}


def call(name: str, **args: str) -> dict:
    """Create one signed tool call for a fake Gemini response."""
    return {"name": name, "args": args, "signature": f"{name}-signature"}


class DayFourVerificationTests(unittest.TestCase):
    """Verify recovery and delegation through the fully composed public Harness."""

    def setUp(self) -> None:
        """Create a disposable project for each disruptive scenario."""
        self.temporary = tempfile.TemporaryDirectory()
        self.root = self.temporary.name

    def tearDown(self) -> None:
        """Remove the disposable Day 4 project."""
        self.temporary.cleanup()

    def test_hard_kill_resume_repairs_and_finishes_six_files(self) -> None:
        """A killed process resumes with an interruption result and completes work."""
        task = "Create part1.txt through part5.txt one at a time, then SUMMARY.md describing each"
        first_replies = [
            reply(calls=[call("write_file", path="part1.txt", content="Part one\n")]),
            reply(calls=[call("write_file", path="part2.txt", content="Part two\n")]),
            reply(calls=[call("write_file", path="part3.txt", content="Part three\n")]),
        ]
        child_code = f"""
import sys
import time
from mitos import Harness
from mitos import provider

responses = iter({first_replies!r})
provider.complete = lambda *args: next(responses)

def event(kind, payload):
    if kind == "tool_start" and payload.get("args", {{}}).get("path") == "part3.txt":
        print("READY_TO_KILL", flush=True)
        time.sleep(60)

Harness(sys.argv[1], on_event=event, enable_subagents=False).run({task!r})
"""
        process = subprocess.Popen(
            [sys.executable, "-c", child_code, self.root],
            cwd=Path(__file__).resolve().parents[1],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            stdout, stderr = process.communicate(timeout=10)
            self.fail(f"crash runner exited before kill: {stdout} {stderr}")
        except subprocess.TimeoutExpired:
            process.kill()  # Windows' hard termination is the local kill -9 equivalent.
            stdout, stderr = process.communicate(timeout=10)
        self.assertIn("READY_TO_KILL", stdout, stderr)
        self.assertTrue(Path(self.root, "part1.txt").is_file())
        self.assertTrue(Path(self.root, "part2.txt").is_file())
        self.assertFalse(Path(self.root, "part3.txt").exists())

        resumed = Harness(self.root, enable_subagents=False)
        self.assertTrue(resumed.resume())
        interruptions = [item for item in resumed.messages
                         if "Interrupted before this ran" in item.get("text", "")]
        self.assertEqual(len(interruptions), 1)
        self.assertEqual(interruptions[0]["name"], "write_file")
        summary = "\n".join(f"part{number}.txt: completed part {number}" for number in range(1, 6))
        remaining = [
            reply(calls=[call("write_file", path="part3.txt", content="Part three\n")]),
            reply(calls=[call("write_file", path="part4.txt", content="Part four\n")]),
            reply(calls=[call("write_file", path="part5.txt", content="Part five\n")]),
            reply(calls=[call("write_file", path="SUMMARY.md", content=summary + "\n")]),
            reply("Created part1.txt through part5.txt and SUMMARY.md."),
        ]
        with mock.patch("mitos.loop.provider.complete", side_effect=remaining):
            answer = resumed.run("continue the task")
        self.assertIn("SUMMARY.md", answer)
        self.assertTrue(any("Interrupted before this ran" in item.get("text", "")
                            for item in resumed.messages))
        for filename in [*(f"part{number}.txt" for number in range(1, 6)), "SUMMARY.md"]:
            self.assertTrue(Path(self.root, filename).is_file(), filename)
        self.assertEqual(len(list(Path(self.root, ".mitos", "sessions").glob("*.jsonl"))), 1)

    def test_two_children_build_parent_runs_tests_one_session(self) -> None:
        """Two clean children write files while only the parent verifies and persists."""
        task = (
            "Use spawn_agent twice: delegate writing utils.py with a slugify(text) "
            "function to one child, and test_utils.py with five asserts to another; "
            "then run python3 test_utils.py yourself and report"
        )
        utils_task = "Write utils.py with a slugify(text) function."
        tests_task = "Write test_utils.py with five asserts for utils.slugify."
        utils_code = (
            "import re\n\ndef slugify(text):\n"
            "    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')\n"
        )
        tests_code = (
            "from utils import slugify\n\n"
            "assert slugify('Hello World') == 'hello-world'\n"
            "assert slugify('  Trim  ') == 'trim'\n"
            "assert slugify('A_B') == 'a-b'\n"
            "assert slugify('already-slug') == 'already-slug'\n"
            "assert slugify('123 Test') == '123-test'\n"
        )
        turns: dict[str, int] = {}

        def fake_complete(model: str, system: str, messages: list[dict], tools: list[dict]) -> dict:
            conversation = messages[0]["text"]
            turn = turns.get(conversation, 0)
            turns[conversation] = turn + 1
            if conversation == task:
                if turn == 0:
                    return reply(calls=[call("spawn_agent", task=utils_task),
                                        call("spawn_agent", task=tests_task)])
                if turn == 1:
                    command = f'"{sys.executable}" test_utils.py'
                    return reply(calls=[call("bash", command=command)])
                self.assertEqual(messages[-1]["name"], "bash")
                self.assertIn("exit 0", messages[-1]["text"])
                return reply("Both children completed their files; I ran the five asserts successfully.")
            if conversation == utils_task:
                self.assertEqual(messages[0], {"role": "user", "text": utils_task})
                return (reply(calls=[call("write_file", path="utils.py", content=utils_code)])
                        if turn == 0 else reply("Created utils.py."))
            if conversation == tests_task:
                self.assertEqual(messages[0], {"role": "user", "text": tests_task})
                return (reply(calls=[call("write_file", path="test_utils.py", content=tests_code)])
                        if turn == 0 else reply("Created test_utils.py with five asserts."))
            raise AssertionError(f"unexpected conversation {conversation!r}")

        parent = Harness(self.root)
        with mock.patch("mitos.loop.provider.complete", side_effect=fake_complete):
            answer = parent.run(task)
        self.assertIn("five asserts successfully", answer)
        self.assertEqual(Path(self.root, "utils.py").read_text(encoding="utf-8"), utils_code)
        self.assertEqual(Path(self.root, "test_utils.py").read_text(encoding="utf-8"), tests_code)
        self.assertEqual(tests_code.count("assert "), 5)
        parent_tool_names = [item["name"] for item in parent.messages if item["role"] == "tool"]
        self.assertEqual(parent_tool_names, ["spawn_agent", "spawn_agent", "bash"])
        sessions = list(Path(self.root, ".mitos", "sessions").glob("*.jsonl"))
        self.assertEqual(len(sessions), 1)


if __name__ == "__main__":
    unittest.main()
