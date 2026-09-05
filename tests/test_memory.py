"""Day 3 memory tests: verify stable prompts and append-only project facts."""

from __future__ import annotations

import os
import platform
import tempfile
import unittest

from mitos.memory import BASE_SYSTEM_PROMPT, MEMORY_FILE, build_system_prompt, remember


class MemoryTests(unittest.TestCase):
    """Exercise prompt assembly and durable note persistence."""

    def setUp(self) -> None:
        """Create a clean workspace for each memory test."""
        self.temporary = tempfile.TemporaryDirectory()
        self.root = self.temporary.name

    def tearDown(self) -> None:
        """Remove the disposable memory workspace."""
        self.temporary.cleanup()

    def test_base_prompt_names_rules_platform_and_real_directory(self) -> None:
        """A project without memory still receives every core operating rule."""
        prompt = build_system_prompt(self.root)
        self.assertIn(BASE_SYSTEM_PROMPT, prompt)
        self.assertIn("Act, don't narrate", prompt)
        self.assertIn(platform.system(), prompt)
        self.assertIn(os.path.realpath(self.root), prompt)
        self.assertNotIn("Project memory", prompt)

    def test_remember_appends_bullets_and_prompt_loads_them(self) -> None:
        """Multiple facts survive as readable bullets in a newly built prompt."""
        self.assertEqual(remember(self.root, "The accent color is amber."),
                         "Remembered in MITOS.md")
        remember(self.root, "Deploy from the main branch.")
        with open(os.path.join(self.root, MEMORY_FILE), encoding="utf-8") as handle:
            contents = handle.read()
        self.assertEqual(contents,
                         "- The accent color is amber.\n- Deploy from the main branch.\n")
        prompt = build_system_prompt(self.root)
        self.assertIn("Project memory (MITOS.md):\n" + contents, prompt)

    def test_extra_is_appended_only_when_nonempty(self) -> None:
        """Callers can add run-specific guidance as the final prompt section."""
        plain = build_system_prompt(self.root)
        extended = build_system_prompt(self.root, "Speak concisely.")
        self.assertEqual(extended, plain + "\n\nSpeak concisely.")


if __name__ == "__main__":
    unittest.main()
