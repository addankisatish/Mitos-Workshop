"""Day 1: verify provider translation, credentials, parsing, and usage.

Tests keep network access and real credentials out of the suite while exercising
the stable provider boundary that all later orchestration depends upon.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mitos import provider


class ProviderTests(unittest.TestCase):
    """Check the exact credential and neutral-message contracts."""

    @mock.patch.dict(os.environ, {"GEMINI_API_KEY": "fallback-key"}, clear=True)
    def test_api_key_falls_back_to_gemini_environment(self) -> None:
        """The conventional Gemini variable is accepted when Mitos is absent."""
        self.assertEqual(provider.api_key(), "fallback-key")

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_api_key_reads_script_without_executing_it(self) -> None:
        """A workshop shell assignment is parsed as inert text."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mitos.key.sh"
            path.write_text('export MITOS_API_KEY="file-key"\n', encoding="utf-8")
            with mock.patch.object(provider, "_KEY_FILES", (path,)):
                self.assertEqual(provider.api_key(), "file-key")

    def test_to_wire_round_trips_signature(self) -> None:
        """Assistant calls retain the opaque Gemini thought signature."""
        messages = [
            {"role": "user", "text": "roll"},
            {"role": "assistant", "text": "", "tool_calls": [
                {"name": "roll", "args": {"n": 1}, "signature": "sig"}
            ]},
            {"role": "tool", "name": "roll", "text": "[4]"},
        ]
        wire = provider._to_wire(messages)
        self.assertEqual(wire[1]["parts"][0]["thoughtSignature"], "sig")
        self.assertEqual(wire[2]["parts"][0]["functionResponse"]["response"],
                         {"result": "[4]"})

    @mock.patch.dict(os.environ, {"MITOS_API_KEY": "test-key"}, clear=True)
    @mock.patch("mitos.provider._post")
    def test_complete_builds_request_and_normalizes_response(self, post: mock.Mock) -> None:
        """Completion skips thoughts and returns normalized calls and usage."""
        post.return_value = {
            "candidates": [{"content": {"parts": [
                {"thought": True, "text": "hidden"}, {"text": "visible"},
                {"functionCall": {"name": "roll", "args": {"n": 2}},
                 "thoughtSignature": "opaque"},
            ]}}],
            "usageMetadata": {"promptTokenCount": 8, "candidatesTokenCount": 3},
        }
        result = provider.complete("gemini-test", "system",
                                   [{"role": "user", "text": "hello"}],
                                   [{"schema": {"name": "roll"}}])
        body = post.call_args.args[1]
        self.assertEqual(body["generationConfig"]["maxOutputTokens"], 65536)
        self.assertEqual(body["tools"][0]["functionDeclarations"], [{"name": "roll"}])
        self.assertEqual(result["text"], "visible")
        self.assertEqual(result["tool_calls"][0]["signature"], "opaque")
        self.assertEqual(result["usage"], {"input": 8, "output": 3})


if __name__ == "__main__":
    unittest.main()
