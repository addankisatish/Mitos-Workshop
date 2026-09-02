"""Day 1 verification: exercise the required demo and text-only transcripts."""

from __future__ import annotations

import contextlib
import io
import unittest
from unittest import mock

from demos import day1_dice
from mitos.loop import run_loop


class DayOneVerificationTests(unittest.TestCase):
    """Verify Day 1 behavior without relying on network access or randomness."""

    def test_dice_transcript_has_all_four_stages(self) -> None:
        """The demo prints user, assistant call, tool result, and final answer."""
        replies = [
            {
                "text": "",
                "tool_calls": [
                    {"name": "roll_dice", "args": {"count": "3"}, "signature": "sig"}
                ],
                "usage": {"input": 1, "output": 1},
            },
            {
                "text": "The total is 12, so it beats 10.",
                "tool_calls": [],
                "usage": {"input": 1, "output": 1},
            },
        ]
        output = io.StringIO()
        with (
            mock.patch("mitos.loop.provider.complete", side_effect=replies),
            mock.patch("demos.day1_dice.random.randint", side_effect=[3, 4, 5]),
            contextlib.redirect_stdout(output),
        ):
            day1_dice.main()
        transcript = output.getvalue()
        self.assertIn("USER: Roll 3 dice", transcript)
        self.assertIn("ASSISTANT tool call:", transcript)
        self.assertIn("TOOL result: [3, 4, 5]", transcript)
        self.assertIn("ASSISTANT: The total is 12", transcript)

    def test_coffee_shop_prompt_returns_text_without_tool_calls(self) -> None:
        """A plain writing prompt finishes immediately without a tool message."""
        reply = {
            "text": "A warm, inviting coffee-shop landing page.",
            "tool_calls": [],
            "usage": {"input": 8, "output": 9},
        }
        messages = [{"role": "user", "text": "Build a landing page for a coffee shop"}]
        with mock.patch("mitos.loop.provider.complete", return_value=reply) as complete:
            answer = run_loop("test-model", "Be helpful.", messages, {}, lambda *_: None,
                              lambda _: None)
        self.assertEqual(answer, reply["text"])
        self.assertEqual(messages[-1]["tool_calls"], [])
        self.assertFalse(any(message["role"] == "tool" for message in messages))
        self.assertEqual(complete.call_args.args[3], [])


if __name__ == "__main__":
    unittest.main()
