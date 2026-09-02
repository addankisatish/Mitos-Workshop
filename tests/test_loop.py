"""Day 1: verify orchestration, policy, failure isolation, and limits.

Tests replace the provider with deterministic replies, proving the state machine
without network access while retaining complete neutral-message transcripts.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock

from mitos.loop import run_loop


def _reply(text: str = "", calls: list[dict] | None = None) -> dict:
    return {"text": text, "tool_calls": calls or [], "usage": {"input": 1, "output": 1}}


class LoopTests(unittest.TestCase):
    """Exercise every Day 1 control-flow outcome."""

    @mock.patch("mitos.loop.provider.complete")
    def test_tool_transcript_then_answer(self, complete: mock.Mock) -> None:
        """A tool call is executed, observed, and followed by a final answer."""
        call = {"name": "roll", "args": {"count": "3"}, "signature": "sig"}
        complete.side_effect = [_reply(calls=[call]), _reply("The total beats 10.")]
        tool = SimpleNamespace(spec={"schema": {"name": "roll"}}, run=lambda **_: [4, 5, 6])
        messages = [{"role": "user", "text": "roll"}]
        events: list[tuple[str, object]] = []
        answer = run_loop("model", "system", messages, {"roll": tool},
                          lambda kind, value: events.append((kind, value)), lambda _: None)
        self.assertEqual(answer, "The total beats 10.")
        self.assertEqual([message["role"] for message in messages],
                         ["user", "assistant", "tool", "assistant"])
        self.assertEqual([kind for kind, _ in events],
                         ["assistant", "tool_start", "tool_end", "assistant"])

    @mock.patch("mitos.loop.provider.complete")
    def test_block_unknown_and_exception_are_results(self, complete: mock.Mock) -> None:
        """Policy and tool failures are returned to the model rather than raised."""
        calls = [
            {"name": "blocked", "args": {}, "signature": None},
            {"name": "missing", "args": {}, "signature": None},
            {"name": "broken", "args": {}, "signature": None},
        ]
        complete.side_effect = [_reply(calls=calls), _reply("done")]
        broken = SimpleNamespace(
            spec={"schema": {"name": "broken"}},
            run=lambda: (_ for _ in ()).throw(ValueError("bad input")),
        )
        messages = [{"role": "user", "text": "try tools"}]
        run_loop("model", "system", messages, {"broken": broken}, lambda *_: None,
                 lambda call: "not allowed" if call["name"] == "blocked" else None)
        results = [message["text"] for message in messages if message["role"] == "tool"]
        self.assertEqual(results, ["BLOCKED: not allowed", "ERROR: unknown tool missing",
                                   "ERROR: ValueError: bad input"])

    @mock.patch("mitos.loop.provider.complete")
    def test_turn_limit_requests_tool_free_wrap_up(self, complete: mock.Mock) -> None:
        """Exhaustion appends the required instruction and disables final tools."""
        call = {"name": "missing", "args": {}, "signature": None}
        complete.side_effect = [_reply(calls=[call]), _reply("wrapped")]
        messages = [{"role": "user", "text": "loop"}]
        answer = run_loop("model", "system", messages, {}, lambda *_: None,
                          lambda _: None, max_turns=1)
        self.assertEqual(answer, "wrapped")
        self.assertEqual(messages[-2]["text"], "Turn limit reached; wrap up now.")
        self.assertEqual(complete.call_args_list[-1].args[3], [])

    @mock.patch("mitos.loop.provider.complete")
    def test_before_turn_replaces_messages_in_place(self, complete: mock.Mock) -> None:
        """The future compaction seam preserves list identity while replacing content."""
        complete.return_value = _reply("done")
        messages = [{"role": "user", "text": "long history"}]
        original_id = id(messages)
        run_loop("model", "system", messages, {}, lambda *_: None, lambda _: None,
                 before_turn=lambda _: [{"role": "user", "text": "compact"}])
        self.assertEqual(id(messages), original_id)
        self.assertEqual(messages[0]["text"], "compact")


if __name__ == "__main__":
    unittest.main()
