"""Day 1: demonstrate a complete model, tool, and model round trip.

The demo keeps presentation at the event seam, policy in ``before_tool``, and
tool behavior behind the same tiny ``spec``/``run`` protocol used by the loop.
"""

from __future__ import annotations

import json
import random
from typing import Any

from mitos.loop import run_loop
from mitos.provider import DEFAULT_MODEL


class RollDice:
    """Expose a hand-written six-sided dice tool to the agent."""

    spec = {
        "schema": {
            "name": "roll_dice",
            "description": "Roll count six-sided dice",
            "parameters": {
                "type": "object",
                "properties": {
                    "count": {"type": "string", "description": "How many dice"}
                },
                "required": ["count"],
            },
        }
    }

    @staticmethod
    def run(count: str) -> list[int]:
        """Return ``count`` independent random rolls in the range one to six."""
        return [random.randint(1, 6) for _ in range(int(count))]


def on_event(kind: str, payload: Any) -> None:
    """Print model replies and tool lifecycle events as a readable transcript."""
    if kind == "assistant":
        if payload["tool_calls"]:
            print("ASSISTANT tool call:", json.dumps(payload["tool_calls"]))
        if payload["text"]:
            print("ASSISTANT:", payload["text"])
    elif kind == "tool_start":
        print("TOOL start:", payload["name"])
    elif kind == "tool_end":
        print("TOOL result:", payload["text"])


def before_tool(call: dict[str, Any]) -> None:
    """Allow every tool call in this introductory demo."""
    del call
    return None


def main() -> None:
    """Ask Gemini to roll three dice and compare their total with ten."""
    task = "Roll 3 dice and tell me whether the total beats 10"
    messages = [{"role": "user", "text": task}]
    print("USER:", task)
    run_loop(
        DEFAULT_MODEL,
        "Use the available tool when the user asks you to roll dice.",
        messages,
        {"roll_dice": RollDice()},
        on_event,
        before_tool,
    )


if __name__ == "__main__":
    main()
