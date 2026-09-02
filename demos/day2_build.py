"""Day 2: let an agent build safely inside a disposable workspace.

The demo composes yesterday's loop with today's generated tools and policy
socket.  A scratch directory contains side effects, events expose the full
transcript, and even yolo mode retains the irreversible-command denylist.
"""

from __future__ import annotations

import json
import sys
import tempfile
from typing import Any

from mitos.loop import run_loop
from mitos.provider import DEFAULT_MODEL
from mitos.security import Policy
from mitos.tools import core_tools

DEFAULT_TASK = (
    "Create fib.py with an iterative fib(n), a __main__ printing fib(30), "
    "run it and confirm the output is 832040"
)


def on_event(kind: str, payload: Any) -> None:
    """Print assistant and tool events as a compact teaching transcript."""
    if kind == "assistant":
        if payload["tool_calls"]:
            print("ASSISTANT tool calls:", json.dumps(payload["tool_calls"]))
        if payload["text"]:
            print("ASSISTANT:", payload["text"])
    elif kind == "tool_start":
        print("TOOL start:", payload["name"], json.dumps(payload.get("args", {})))
    elif kind == "tool_end":
        print("TOOL result:", payload["text"])


def run_task(task: str) -> str:
    """Run one coding task with core tools rooted in a fresh scratch directory."""
    with tempfile.TemporaryDirectory(prefix="mitos-day2-") as workdir:
        available = core_tools(workdir)
        tools = {item.name: item for item in available}
        policy = Policy("yolo")
        messages = [{"role": "user", "text": task}]
        system = (
            "You are a careful coding agent. Use tools to do and verify the work. "
            f"The Python executable is {sys.executable!r}. Never claim success "
            "without checking tool output."
        )
        print("WORKDIR:", workdir)
        print("USER:", task)
        return run_loop(
            DEFAULT_MODEL,
            system,
            messages,
            tools,
            on_event,
            policy.check,
        )


def main() -> None:
    """Run the requested command-line task, or the Day 2 Fibonacci task."""
    task = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else DEFAULT_TASK
    run_task(task)


if __name__ == "__main__":
    main()
