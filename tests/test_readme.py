"""Day 5 README tests: keep product claims, commands, and examples executable."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


class ReadmeTests(unittest.TestCase):
    """Verify the final documentation covers every requested product surface."""

    @classmethod
    def setUpClass(cls) -> None:
        """Load the repository README once for documentation assertions."""
        cls.text = Path(__file__).resolve().parents[1].joinpath("README.md").read_text(
            encoding="utf-8"
        )

    def test_positioning_and_environment_are_documented(self) -> None:
        """The introduction states scope, dependencies, runtime, and credential."""
        self.assertIn("smallest agent harness", self.text)
        self.assertIn("ten core files", self.text)
        self.assertIn("zero third-party", self.text)
        self.assertIn("Python 3.10", self.text)
        self.assertIn("MITOS_API_KEY", self.text)

    def test_three_cli_forms_and_every_day_are_present(self) -> None:
        """Interactive, headless, and resume commands accompany all five lessons."""
        commands = re.findall(r"^python3 -m mitos.*$", self.text, re.MULTILINE)
        self.assertEqual(len(commands), 3)
        self.assertTrue(any(" -p " in command for command in commands))
        self.assertTrue(any("--resume" in command for command in commands))
        for day in range(1, 6):
            self.assertIn(f"| {day} |", self.text)

    def test_composition_example_is_valid_python(self) -> None:
        """The extra-tool example remains syntactically executable Python."""
        blocks = re.findall(r"```python\n(.*?)```", self.text, re.DOTALL)
        self.assertEqual(len(blocks), 1)
        compile(blocks[0], "README.md example", "exec")
        self.assertIn("extra_tools=[count_words]", blocks[0])


if __name__ == "__main__":
    unittest.main()
