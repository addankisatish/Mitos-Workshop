"""Day 3 skills tests: verify shallow catalogs and on-demand full loading."""

from __future__ import annotations

import os
import tempfile
import unittest

from mitos.skills import SKILLS_DIR, catalog, catalog_prompt, read_skill


class SkillsTests(unittest.TestCase):
    """Exercise empty, populated, and missing project-local skill lookups."""

    def setUp(self) -> None:
        """Create a disposable project and its skills directory."""
        self.temporary = tempfile.TemporaryDirectory()
        self.root = self.temporary.name
        os.makedirs(os.path.join(self.root, SKILLS_DIR), exist_ok=True)

    def tearDown(self) -> None:
        """Remove the disposable skill catalog."""
        self.temporary.cleanup()

    def add_skill(self, name: str, text: str) -> str:
        """Write one direct child SKILL.md fixture and return its path."""
        directory = os.path.join(self.root, SKILLS_DIR, name)
        os.makedirs(directory)
        path = os.path.join(directory, "SKILL.md")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def test_empty_catalog_and_prompt(self) -> None:
        """Projects without skill documents expose no prompt noise."""
        self.assertEqual(catalog(self.root), {})
        self.assertEqual(catalog_prompt(self.root), "")
        self.assertEqual(read_skill(self.root, "missing"),
                         "ERROR: no skill named missing. Available: (none)")

    def test_catalog_reads_only_front_matter_description(self) -> None:
        """Catalog metadata comes from front matter while paths remain loadable."""
        text = "---\ndescription: 'Write like a pirate'\n---\n\nAlways say ahoy.\n"
        path = self.add_skill("brand-voice", text)
        self.add_skill("plain", "description: not front matter\nBody\n")
        entries = catalog(self.root)
        self.assertEqual(entries["brand-voice"],
                         {"description": "Write like a pirate", "path": path})
        self.assertEqual(entries["plain"]["description"], "")

    def test_prompt_is_sorted_and_read_returns_full_text(self) -> None:
        """The catalog prompt is stable and loading preserves the entire file."""
        zulu = "---\ndescription: Last skill\n---\nZulu body\n"
        alpha = "---\ndescription: First skill\n---\nAlpha body\n"
        self.add_skill("zulu", zulu)
        self.add_skill("alpha", alpha)
        prompt = catalog_prompt(self.root)
        self.assertEqual(
            prompt,
            "Skills available (load one with the use_skill tool when relevant):\n"
            "- alpha: First skill\n- zulu: Last skill",
        )
        self.assertEqual(read_skill(self.root, "zulu"), zulu)
        self.assertEqual(read_skill(self.root, "missing"),
                         "ERROR: no skill named missing. Available: alpha, zulu")


if __name__ == "__main__":
    unittest.main()
