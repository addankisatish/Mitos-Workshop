"""Day 4 Harness tests: verify composition, persistence, resume, and children."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mitos.harness import Harness
from mitos.security import Policy
from mitos.session import append, load, new_session
from mitos.tools import tool


def reply(text: str = "", calls: list[dict] | None = None) -> dict:
    """Create one normalized provider response for a deterministic harness turn."""
    return {"text": text, "tool_calls": calls or [], "usage": {"input": 1, "output": 1}}


class HarnessTests(unittest.TestCase):
    """Exercise the public facade without making network requests."""

    def setUp(self) -> None:
        """Create a disposable working directory for one harness test."""
        self.temporary = tempfile.TemporaryDirectory()
        self.root = self.temporary.name

    def tearDown(self) -> None:
        """Remove the disposable harness project."""
        self.temporary.cleanup()

    def test_constructor_composes_model_prompt_skills_and_extra_tools(self) -> None:
        """Construction discovers capabilities and lets explicitly extra tools win."""
        skill_dir = Path(self.root, "skills", "voice")
        skill_dir.mkdir(parents=True)
        skill_dir.joinpath("SKILL.md").write_text(
            "---\ndescription: Speak brightly\n---\nBe bright.\n", encoding="utf-8"
        )

        @tool("Replacement reader", path="Path")
        def read_file(path: str) -> str:
            return f"replacement {path}"

        with mock.patch.dict(os.environ, {"MITOS_MODEL": "environment-model"}):
            harness = Harness(self.root, extra_tools=[read_file], system_extra="Extra rule.")
        self.assertEqual(harness.model, "environment-model")
        self.assertEqual(harness.tools["read_file"].run(path="x"), "replacement x")
        self.assertIn("remember", harness.tools)
        self.assertIn("use_skill", harness.tools)
        self.assertIn("spawn_agent", harness.tools)
        self.assertIn("- voice: Speak brightly", harness.system)
        self.assertTrue(harness.system.endswith("Extra rule."))

    def test_run_persists_every_message_and_forwards_events(self) -> None:
        """One tool round trip is fully durable and visible to the event callback."""
        events: list[str] = []
        responses = [
            reply(calls=[{
                "name": "write_file", "args": {"path": "done.txt", "content": "done"},
                "signature": "sig",
            }]),
            reply("Finished."),
        ]
        harness = Harness(self.root, enable_subagents=False,
                          on_event=lambda kind, payload: events.append(kind))
        with mock.patch("mitos.loop.provider.complete", side_effect=responses):
            self.assertEqual(harness.run("Write done.txt"), "Finished.")
        self.assertIsNotNone(harness.session_path)
        self.assertEqual(load(harness.session_path), harness.messages)
        self.assertEqual([item["role"] for item in harness.messages],
                         ["user", "assistant", "tool", "assistant"])
        self.assertEqual(events, ["assistant", "tool_start", "tool_end", "assistant"])

    def test_resume_loads_latest_and_repairs_interrupted_call(self) -> None:
        """Resume discovers the latest log and exposes its synthetic interruption."""
        path = new_session(self.root, "crashed")
        append(path, {"role": "user", "text": "Write a file"})
        append(path, {"role": "assistant", "text": "", "tool_calls": [{
            "name": "write_file", "args": {"path": "x.txt", "content": "x"}
        }]})
        harness = Harness(self.root, enable_subagents=False)
        self.assertTrue(harness.resume())
        self.assertEqual(harness.session_path, path)
        self.assertEqual(harness.messages[-1]["role"], "tool")
        self.assertIn("Interrupted before this ran", harness.messages[-1]["text"])

    def test_ephemeral_child_creates_no_second_session(self) -> None:
        """A spawned child shares files but never competes for latest-session resume."""
        harness = Harness(self.root)
        responses = [reply("Child report."), reply("Parent report.")]
        with mock.patch("mitos.loop.provider.complete", side_effect=responses):
            child_report = harness.tools["spawn_agent"].run(task="Inspect the project")
            parent_report = harness.run("Summarize the child report")
        self.assertEqual((child_report, parent_report), ("Child report.", "Parent report."))
        sessions = list(Path(self.root, ".mitos", "sessions").glob("*.jsonl"))
        self.assertEqual(len(sessions), 1)


if __name__ == "__main__":
    unittest.main()
