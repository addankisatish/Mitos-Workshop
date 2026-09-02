"""Day 1: run the minimal model-and-tools agent loop.

The loop teaches orchestration while keeping provider translation, tool policy,
and event presentation at explicit seams.  Tool failures become observations,
messages stay neutral, and a hard turn limit guarantees bounded execution.
"""

from __future__ import annotations

from typing import Any, Callable

from mitos import provider


def run_loop(
    model: str,
    system: str,
    messages: list[dict[str, Any]],
    tools: dict[str, Any],
    on_event: Callable[[str, Any], None],
    before_tool: Callable[[dict[str, Any]], str | None],
    max_turns: int = 80,
    before_turn: Callable[[list[dict[str, Any]]], list[dict[str, Any]]] | None = None,
) -> str:
    """Run model turns and ordered tool calls until the model returns plain text."""
    specs = [tool.spec for tool in tools.values()]
    for _ in range(max_turns):
        if before_turn is not None:
            messages[:] = before_turn(messages)
        reply = provider.complete(model, system, messages, specs)
        assistant = {
            "role": "assistant",
            "text": reply["text"],
            "tool_calls": reply["tool_calls"],
        }
        messages.append(assistant)
        on_event("assistant", assistant)
        if not reply["tool_calls"]:
            return reply["text"]
        for call in reply["tool_calls"]:
            on_event("tool_start", call)
            reason = before_tool(call)
            if reason is not None:
                result = f"BLOCKED: {reason}"
            elif call["name"] not in tools:
                result = f"ERROR: unknown tool {call['name']}"
            else:
                try:
                    result = str(tools[call["name"]].run(**call["args"]))
                except Exception as exc:  # A broken tool is evidence, not a broken loop.
                    result = f"ERROR: {type(exc).__name__}: {exc}"
            tool_message = {"role": "tool", "name": call["name"], "text": result}
            messages.append(tool_message)
            on_event("tool_end", tool_message)

    messages.append({"role": "user", "text": "Turn limit reached; wrap up now."})
    reply = provider.complete(model, system, messages, [])
    assistant = {
        "role": "assistant",
        "text": reply["text"],
        "tool_calls": reply["tool_calls"],
    }
    messages.append(assistant)
    on_event("assistant", assistant)
    return reply["text"]

