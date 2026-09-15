"""Day 4: delegate isolated work through the ordinary Mitos tool protocol.

Sub-agents receive a fresh harness context, return one final report, and obey a
small depth bound so recursive delegation remains explicit and finite.
"""

from __future__ import annotations

from typing import Any, Callable

from mitos.tools import Tool, tool


def subagent_tool(make_harness: Callable[[int], Any], depth: int = 0, max_depth: int = 2) -> Tool:
    """Create a depth-limited ``spawn_agent`` tool around a harness factory."""

    @tool(
        "Delegate a self-contained task to a fresh sub-agent with its own clean "
        "context. The child cannot see this conversation. Returns the child's final report.",
        task="Self-contained task for the child",
    )
    def spawn_agent(task: str) -> str:
        """Run one isolated child task or report the delegation depth limit."""
        if depth >= max_depth:
            return "ERROR: sub-agent depth limit reached; do this task yourself"
        child = make_harness(depth + 1)
        return child.run(task)

    return spawn_agent
