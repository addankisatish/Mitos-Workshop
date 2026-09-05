"""Day 3 verification: exercise compaction, fresh memory, and loaded skills."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from demos.day3_context import project_tools
from mitos.context import compact
from mitos.loop import run_loop
from mitos.memory import build_system_prompt, remember
from mitos.security import Policy
from mitos.skills import catalog_prompt


def reply(text: str = "", calls: list[dict] | None = None) -> dict:
    """Create one provider-neutral reply used by deterministic agent tests."""
    return {"text": text, "tool_calls": calls or [], "usage": {"input": 1, "output": 1}}


class DayThreeVerificationTests(unittest.TestCase):
    """Compose production Day 1–3 sockets around controlled model decisions."""

    def setUp(self) -> None:
        """Create a clean persistent workspace for each acceptance scenario."""
        self.temporary = tempfile.TemporaryDirectory()
        self.root = self.temporary.name

    def tearDown(self) -> None:
        """Remove the acceptance workspace."""
        self.temporary.cleanup()

    def test_five_files_manifest_and_mid_run_compaction(self) -> None:
        """Real tools build and verify all files while compaction visibly fires."""
        task = (
            "Create five files one.txt through five.txt, each with 20 lines of the "
            "word ping, one write_file at a time with a read back after each; then "
            "MANIFEST.md listing each file and its line count verified with wc -l"
        )
        ping = "ping\n" * 20
        names = ["one.txt", "two.txt", "three.txt", "four.txt", "five.txt"]
        signature = "opaque-" + "x" * 1200
        decisions: list[dict] = []
        for name in names:
            decisions.append(reply(calls=[{
                "name": "write_file", "args": {"path": name, "content": ping},
                "signature": signature,
            }]))
            decisions.append(reply(calls=[{
                "name": "read_file", "args": {"path": name}, "signature": signature,
            }]))
        manifest = "\n".join(f"{name}: 20 lines" for name in names) + "\n"
        decisions.append(reply(calls=[{
            "name": "write_file", "args": {"path": "MANIFEST.md", "content": manifest},
            "signature": signature,
        }]))
        command = "wc -l " + " ".join([*names, "MANIFEST.md"])
        decisions.append(reply(calls=[{
            "name": "bash", "args": {"command": command}, "signature": signature,
        }]))
        decisions.append(reply("Created and verified five 20-line files and MANIFEST.md."))
        compact_calls: list[list[dict]] = []

        def fake_complete(model: str, system: str, messages: list[dict], tools: list[dict]) -> dict:
            if system.startswith("You compress agent transcripts."):
                compact_calls.append(messages)
                return reply("Task and verified file progress preserved.")
            return decisions.pop(0)

        tools = {item.name: item for item in project_tools(self.root)}
        messages = [{"role": "user", "text": task}]
        with mock.patch("mitos.loop.provider.complete", side_effect=fake_complete), \
             mock.patch("mitos.context.provider.complete", side_effect=fake_complete):
            answer = run_loop(
                "test-model", build_system_prompt(self.root), messages, tools,
                lambda *_: None, Policy("yolo").check,
                before_turn=lambda current: compact("test-model", current, 1500),
            )
        self.assertIn("verified", answer)
        self.assertGreater(len(compact_calls), 0)
        self.assertEqual(decisions, [])
        for name in names:
            with open(os.path.join(self.root, name), encoding="utf-8") as handle:
                self.assertEqual(handle.read().splitlines(), ["ping"] * 20)
        with open(os.path.join(self.root, "MANIFEST.md"), encoding="utf-8") as handle:
            self.assertEqual(handle.read(), manifest)
        bash_results = [message["text"] for message in messages
                        if message.get("role") == "tool" and message.get("name") == "bash"]
        self.assertIn("20 one.txt", bash_results[0])

    def test_memory_answers_in_a_completely_fresh_conversation(self) -> None:
        """A saved fact reaches a new model call through its system prompt alone."""
        fact = "The launch codename is Firefly."
        remember(self.root, fact)
        system = build_system_prompt(self.root)
        messages = [{"role": "user", "text": "What is the launch codename?"}]

        def answer_from_system(model: str, prompt: str, history: list[dict], tools: list[dict]) -> dict:
            self.assertIn(fact, prompt)
            self.assertEqual(history, messages[:1])
            self.assertEqual(tools, [])
            return reply("The launch codename is Firefly.")

        with mock.patch("mitos.loop.provider.complete", side_effect=answer_from_system):
            answer = run_loop("test-model", system, messages, {}, lambda *_: None,
                              Policy("read-only").check)
        self.assertEqual(answer, "The launch codename is Firefly.")
        self.assertEqual(len(messages), 2)

    def test_brand_voice_skill_changes_copy_without_code_changes(self) -> None:
        """The model loads pirate guidance, writes copy, and leaves files untouched."""
        directory = os.path.join(self.root, "skills", "brand-voice")
        os.makedirs(directory)
        skill = (
            "---\ndescription: Write marketing copy in pirate speak\n---\n\n"
            "For writing tasks, use cheerful pirate speech with words like ahoy and matey.\n"
        )
        skill_path = os.path.join(directory, "SKILL.md")
        with open(skill_path, "w", encoding="utf-8") as handle:
            handle.write(skill)
        before = Path(skill_path).read_text(encoding="utf-8")
        decisions = [
            reply(calls=[{
                "name": "use_skill", "args": {"name": "brand-voice"},
                "signature": "skill-sig",
            }]),
            reply("Ahoy, matey! Fresh coffee treasure awaits in every cup."),
        ]
        tools = {item.name: item for item in project_tools(self.root)}
        system = build_system_prompt(self.root, catalog_prompt(self.root))
        messages = [{"role": "user", "text": "Write a coffee shop tagline."}]
        with mock.patch("mitos.loop.provider.complete", side_effect=decisions):
            answer = run_loop("test-model", system, messages, tools, lambda *_: None,
                              Policy("yolo").check)
        self.assertIn("Ahoy", answer)
        self.assertIn("matey", answer)
        self.assertEqual(Path(skill_path).read_text(encoding="utf-8"), before)
        files = [os.path.relpath(os.path.join(root, name), self.root)
                 for root, _, names in os.walk(self.root) for name in names]
        self.assertEqual(files, [os.path.join("skills", "brand-voice", "SKILL.md")])


if __name__ == "__main__":
    unittest.main()
