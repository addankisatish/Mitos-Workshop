"""Day 3: compose compaction, durable memory, and on-demand skills.

The demo keeps yesterday's loop and tools unchanged.  New behavior enters only
through the system prompt, two ordinary tools, and the existing before-turn
socket, while a disposable workspace contains every demonstration side effect.
"""

from __future__ import annotations

import json
import sys
import tempfile
from typing import Any

from mitos.context import compact
from mitos.loop import run_loop
from mitos.memory import build_system_prompt, remember as save_memory
from mitos.provider import DEFAULT_MODEL
from mitos.security import Policy
from mitos.skills import catalog_prompt, read_skill
from mitos.tools import Tool, core_tools, tool

DEFAULT_TASK = (
    "Create five files one.txt through five.txt, each with 20 lines of the word "
    "ping, one write_file at a time with a read back after each; then MANIFEST.md "
    "listing each file and its line count verified with wc -l"
)


def project_tools(workdir: str) -> list[Tool]:
    """Add memory and skill loading to the six core workspace tools."""
    @tool("Store a durable project fact", note="Fact to remember")
    def remember(note: str) -> str:
        """Append one fact to MITOS.md."""
        return save_memory(workdir, note)

    @tool("Load a project skill's full instructions", name="Skill name")
    def use_skill(name: str) -> str:
        """Read one cataloged SKILL.md document."""
        return read_skill(workdir, name)

    return [*core_tools(workdir), remember, use_skill]


def on_event(kind: str, payload: Any) -> None:
    """Print assistant and tool events as a compact transcript."""
    if kind == "assistant" and payload["tool_calls"]:
        print("ASSISTANT tool calls:", json.dumps(payload["tool_calls"]))
    elif kind == "assistant" and payload["text"]:
        print("ASSISTANT:", payload["text"])
    elif kind == "tool_start":
        print("TOOL start:", payload["name"])
    elif kind == "tool_end":
        print("TOOL result:", payload["text"])


def run_task(task: str, workdir: str, budget_tokens: int = 1500) -> str:
    """Run one task with Day 3 prompt, tools, policy, and compaction wiring."""
    available = project_tools(workdir)
    tools = {item.name: item for item in available}
    system = build_system_prompt(workdir, catalog_prompt(workdir))
    messages = [{"role": "user", "text": task}]
    print("WORKDIR:", workdir)
    print("USER:", task)
    return run_loop(
        DEFAULT_MODEL,
        system,
        messages,
        tools,
        on_event,
        Policy("yolo").check,
        before_turn=lambda current: compact(DEFAULT_MODEL, current, budget_tokens),
    )


def main() -> None:
    """Run a command-line task or the Day 3 file-building demonstration."""
    task = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else DEFAULT_TASK
    with tempfile.TemporaryDirectory(prefix="mitos-day3-") as workdir:
        run_task(task, workdir)


if __name__ == "__main__":
    main()
