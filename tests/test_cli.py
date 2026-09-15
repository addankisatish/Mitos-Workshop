"""Day 5 CLI tests: verify modes, rendering, approval, and interruption behavior."""

from __future__ import annotations

import contextlib
import io
import unittest
from unittest import mock

from mitos import cli


class CliTests(unittest.TestCase):
    """Exercise the terminal boundary without invoking the network provider."""

    def test_event_printer_renders_calls_and_only_first_result_line(self) -> None:
        """Tool arguments stay on one clipped line and observations are dimmed."""
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            cli._event("assistant", {
                "text": "Working",
                "tool_calls": [{"name": "write_file", "args": {"content": "x" * 300}}],
            })
            cli._event("tool_end", {"text": "first line\nsecond line"})
        lines = output.getvalue().splitlines()
        self.assertEqual(lines[0], "Working")
        self.assertTrue(lines[1].startswith("→ write_file"))
        self.assertIn("…", lines[1])
        self.assertIn("\033[2mfirst line\033[0m", lines[2])
        self.assertNotIn("second line", output.getvalue())

    def test_approver_shows_call_and_accepts_only_yes(self) -> None:
        """Interactive approval defaults to refusal and accepts y or yes."""
        call = {"name": "bash", "args": {"command": "python tests.py"}}
        with mock.patch("builtins.input", return_value="yes"), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertTrue(cli._approve(call, "bash may change files"))
        self.assertIn("python tests.py", output.getvalue())
        with mock.patch("builtins.input", return_value=""), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(cli._approve(call, "reason"))

    def test_headless_defaults_to_yolo_resumes_and_runs_once(self) -> None:
        """A prompt selects yolo unless overridden and exits after one task."""
        harness = mock.Mock()
        with mock.patch("mitos.cli.Policy") as policy, \
             mock.patch("mitos.cli.Harness", return_value=harness) as constructor:
            result = cli.main(["-p", "build it", "-d", "project", "--resume", "--max-turns", "9"])
        self.assertEqual(result, 0)
        policy.assert_called_once_with("yolo", cli._approve)
        constructor.assert_called_once_with(
            workdir="project", model=None, policy=policy.return_value,
            on_event=cli._event, max_turns=9,
        )
        harness.resume.assert_called_once_with()
        harness.run.assert_called_once_with("build it")

    def test_interactive_defaults_safe_and_reports_interrupted_run(self) -> None:
        """Interactive Ctrl-C keeps looping and explains how to resume safely."""
        harness = mock.Mock(model="model-x", workdir="C:/jail")
        harness.run.side_effect = KeyboardInterrupt
        inputs = ["do work", EOFError()]

        def prompt(_: str) -> str:
            value = inputs.pop(0)
            if isinstance(value, BaseException):
                raise value
            return value

        output = io.StringIO()
        with mock.patch("mitos.cli.Policy") as policy, \
             mock.patch("mitos.cli.Harness", return_value=harness), \
             mock.patch("builtins.input", side_effect=prompt), \
             contextlib.redirect_stdout(output):
            result = cli.main([])
        self.assertEqual(result, 0)
        policy.assert_called_once_with("safe", cli._approve)
        self.assertIn("model-x | mode safe | jail C:/jail", output.getvalue())
        self.assertIn("session log is safe; --resume continues it", output.getvalue())

    def test_explicit_read_only_mode_reaches_policy(self) -> None:
        """The third policy mode is accepted for headless automation."""
        with mock.patch("mitos.cli.Policy") as policy, \
             mock.patch("mitos.cli.Harness"):
            self.assertEqual(cli.main(["-p", "inspect", "--mode", "read-only"]), 0)
        policy.assert_called_once_with("read-only", cli._approve)


if __name__ == "__main__":
    unittest.main()
