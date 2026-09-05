"""Day 3: compact long conversations through the existing turn socket.

The context engine uses a transparent character estimate, summarizes only old
history in one model call, preserves a recent working tail, and prevents an
orphaned tool result from becoming the first message after compaction.
"""

from __future__ import annotations

from typing import Any

from mitos import provider

CHARS_PER_TOKEN = 4
KEEP_RECENT = 6
_CLIP_CHARS = 2000
_SUMMARY_SYSTEM = (
    "You compress agent transcripts. Preserve: the original task, every file "
    "created or edited and its purpose, key decisions, unresolved errors, and "
    "what remains to be done. Be dense and factual."
)


def estimate_tokens(messages: list[dict[str, Any]]) -> float:
    """Estimate tokens as the messages' string lengths divided by four."""
    return sum(len(str(message)) for message in messages) / CHARS_PER_TOKEN


def _render(message: dict[str, Any]) -> str:
    role = str(message.get("role", "unknown"))
    if message.get("name"):
        role += f" {message['name']}"
    text = str(message.get("text", ""))[:_CLIP_CHARS]
    names = [str(call.get("name", "unknown")) for call in message.get("tool_calls", [])]
    calls = f" tool calls: {', '.join(names)}" if names else ""
    return f"{role}: {text}{calls}"


def compact(model: str, messages: list[dict[str, Any]],
            budget_tokens: int) -> list[dict[str, Any]]:
    """Summarize old messages when the estimated context exceeds its budget."""
    if estimate_tokens(messages) <= budget_tokens or len(messages) <= KEEP_RECENT + 1:
        return messages
    old, recent = messages[:-KEEP_RECENT], messages[-KEEP_RECENT:]
    while recent and recent[0].get("role") == "tool":
        recent = recent[1:]
    transcript = "\n".join(_render(message) for message in old)
    reply = provider.complete(
        model,
        _SUMMARY_SYSTEM,
        [{"role": "user", "text": transcript}],
        [],
    )
    summary = {"role": "user", "text": f"[Conversation so far, compacted]\n{reply['text']}"}
    return [summary, *recent]
