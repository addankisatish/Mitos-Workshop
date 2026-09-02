"""Day 2 tools tests: verify schemas, confinement, edits, and finite output."""

from __future__ import annotations

import os
import tempfile
import unittest

from mitos.tools import core_tools, tool


class ToolDecoratorTests(unittest.TestCase):
    """Check that function signatures become the exact neutral tool schema."""

    def test_defaults_are_optional_and_all_parameters_are_strings(self) -> None:
        """Only arguments without Python defaults enter the required list."""
        @tool("Join text", left="First", right="Second")
        def join(left: str, right: str = "!") -> str:
            return left + right

        self.assertEqual(join.name, "join")
        self.assertEqual(join.run(left="hi"), "hi!")
        parameters = join.spec["schema"]["parameters"]
        self.assertEqual(parameters["required"], ["left"])
        self.assertEqual(parameters["properties"]["right"],
                         {"type": "string", "description": "Second"})


class CoreToolsTests(unittest.TestCase):
    """Exercise all core tools inside a disposable workspace."""

    def setUp(self) -> None:
        """Create a fresh real directory and name-indexed tool collection."""
        self.temporary = tempfile.TemporaryDirectory()
        self.root = self.temporary.name
        self.tools = {item.name: item for item in core_tools(self.root)}

    def tearDown(self) -> None:
        """Remove the disposable workspace."""
        self.temporary.cleanup()

    def test_tool_set_and_path_confinement(self) -> None:
        """The six names exist and traversal outside the workspace is rejected."""
        self.assertEqual(set(self.tools),
                         {"read_file", "write_file", "edit_file", "bash", "list_files", "grep"})
        with self.assertRaisesRegex(PermissionError, "escapes the working directory"):
            self.tools["read_file"].run("../outside.txt")

    def test_write_read_and_unique_edit(self) -> None:
        """Writing creates parents, reading numbers lines, and edits require uniqueness."""
        write = self.tools["write_file"].run
        edit = self.tools["edit_file"].run
        self.assertEqual(write("src/example.txt", "same\nsame\n"),
                         "Wrote 10 chars to src/example.txt")
        self.assertEqual(self.tools["read_file"].run("src/example.txt"),
                         "1\tsame\n2\tsame")
        self.assertIn("appears 2 times", edit("src/example.txt", "same", "new"))
        self.assertIn("not found", edit("src/example.txt", "missing", "new"))
        self.assertEqual(edit("src/example.txt", "same\nsame", "done"),
                         "Edited src/example.txt")

    def test_read_truncates_after_four_thousand_lines(self) -> None:
        """Large reads retain numbered beginnings and report the true line total."""
        content = "\n".join(f"line {number}" for number in range(4002))
        self.tools["write_file"].run("large.txt", content)
        result = self.tools["read_file"].run("large.txt")
        self.assertIn("4000\tline 3999", result)
        self.assertIn("4002 total lines", result)
        self.assertNotIn("4001\t", result)

    def test_list_and_grep_ignore_metadata(self) -> None:
        """Walking matches path/basename while pruning ignored directories."""
        write = self.tools["write_file"].run
        write("src/alpha.py", "needle here\n")
        write("src/readme.txt", "needle elsewhere\n")
        os.makedirs(os.path.join(self.root, ".git"), exist_ok=True)
        with open(os.path.join(self.root, ".git", "hidden.py"), "w", encoding="utf-8") as handle:
            handle.write("needle")
        self.assertEqual(self.tools["list_files"].run("*.py"), "src/alpha.py")
        self.assertEqual(self.tools["grep"].run("needle", "*.py"),
                         "src/alpha.py:1: needle here")

    def test_bash_returns_output_and_reports_empty_exit(self) -> None:
        """Shell commands run in the workspace and always return an observation."""
        output = self.tools["bash"].run("echo hello")
        self.assertIn("hello", output)
        empty = self.tools["bash"].run("exit 7")
        self.assertEqual(empty, "(exit 7, no output)")


if __name__ == "__main__":
    unittest.main()
