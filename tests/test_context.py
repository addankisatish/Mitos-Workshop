"""Day 3 context tests: prove thresholds, rendering, and safe recent tails."""

from __future__ import annotations

import unittest
from unittest import mock

from mitos.context import CHARS_PER_TOKEN, KEEP_RECENT, compact, estimate_tokens


class ContextTests(unittest.TestCase):
    """Exercise the public estimate and the one-call compaction boundary."""

    def test_estimate_uses_string_length_divided_by_constant(self) -> None:
        """The estimator remains intentionally transparent and deterministic."""
        messages = [{"role": "user", "text": "hello"}, {"role": "tool", "text": "ok"}]
        expected = sum(len(str(message)) for message in messages) / CHARS_PER_TOKEN
        self.assertEqual(estimate_tokens(messages), expected)

    def test_within_budget_returns_same_list_without_provider_call(self) -> None:
        """Small contexts preserve both their contents and list identity."""
        messages = [{"role": "user", "text": "small"}]
        with mock.patch("mitos.context.provider.complete") as complete:
            result = compact("model", messages, 1000)
        self.assertIs(result, messages)
        complete.assert_not_called()

    def test_short_conversation_is_unchanged_even_over_budget(self) -> None:
        """At most seven messages are never compacted regardless of their size."""
        messages = [{"role": "user", "text": "x" * 1000} for _ in range(KEEP_RECENT + 1)]
        with mock.patch("mitos.context.provider.complete") as complete:
            self.assertIs(compact("model", messages, 1), messages)
        complete.assert_not_called()

    def test_compaction_renders_old_history_and_drops_orphan_tools(self) -> None:
        """One summary call names tools and the retained tail starts coherently."""
        messages = [
            {"role": "user", "text": "original task"},
            {"role": "assistant", "text": "", "tool_calls": [{"name": "write_file"}]},
            {"role": "tool", "name": "write_file", "text": "wrote old.txt"},
            {"role": "assistant", "text": "working", "tool_calls": []},
            {"role": "tool", "name": "read_file", "text": "orphan one"},
            {"role": "tool", "name": "grep", "text": "orphan two"},
            {"role": "assistant", "text": "recent", "tool_calls": []},
            {"role": "user", "text": "continue"},
            {"role": "assistant", "text": "more", "tool_calls": []},
            {"role": "user", "text": "finish"},
        ]
        reply = {"text": "dense summary", "tool_calls": [], "usage": {}}
        with mock.patch("mitos.context.provider.complete", return_value=reply) as complete:
            result = compact("gemini", messages, 1)
        self.assertEqual(result[0]["text"], "[Conversation so far, compacted]\ndense summary")
        self.assertEqual(result[1]["role"], "assistant")
        args = complete.call_args.args
        self.assertEqual((args[0], args[3]), ("gemini", []))
        self.assertIn("tool calls: write_file", args[2][0]["text"])
        self.assertIn("tool write_file: wrote old.txt", args[2][0]["text"])


if __name__ == "__main__":
    unittest.main()
