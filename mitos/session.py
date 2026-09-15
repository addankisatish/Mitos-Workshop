"""Day 4: persist conversations as repairable append-only JSONL sessions.

Session records favor durability over cleverness: each message is independent,
a torn final line never destroys earlier work, and restart repair restores every
missing tool response required by the provider's call/response pairing rule.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

SESSION_DIR = ".mitos/sessions"
_INTERRUPTED = "Interrupted before this ran (process restarted)."


def new_session(workdir: str | os.PathLike[str], label: str = "session") -> str:
    """Create the session directory and return a timestamped JSONL path."""
    directory = Path(os.path.realpath(os.fspath(workdir))) / SESSION_DIR
    directory.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^A-Za-z0-9]+", "-", label).strip("-").lower()[:40]
    slug = slug or "session"
    return str(directory / f"{int(time.time())}-{slug}.jsonl")


def append(path: str | os.PathLike[str], message: dict[str, Any]) -> None:
    """Append one complete UTF-8 JSON object and newline to a session."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(message, ensure_ascii=False) + "\n")


def _repair(messages: list[dict[str, Any]]) -> None:
    for index in range(len(messages) - 1, -1, -1):
        assistant = messages[index]
        if assistant.get("role") == "assistant":
            break
    else:
        return
    calls = assistant.get("tool_calls", [])
    completed = sum(message.get("role") == "tool" for message in messages[index + 1:])
    # Missing results are durable evidence that restart interrupted execution.
    for call in calls[completed:]:
        messages.append({"role": "tool", "name": call["name"], "text": _INTERRUPTED})


def load(path: str | os.PathLike[str]) -> list[dict[str, Any]]:
    """Load valid JSONL up to a torn tail, then repair unfinished tool calls."""
    messages: list[dict[str, Any]] = []
    with Path(path).open("rb") as handle:
        for line in handle:
            try:
                messages.append(json.loads(line))
            except (json.JSONDecodeError, UnicodeDecodeError):
                break
    _repair(messages)
    return messages


def latest(workdir: str | os.PathLike[str]) -> str | None:
    """Return the newest project session path, or ``None`` when absent."""
    directory = Path(os.path.realpath(os.fspath(workdir))) / SESSION_DIR
    paths = list(directory.glob("*.jsonl")) if directory.is_dir() else []
    if not paths:
        return None
    return str(max(paths, key=lambda path: path.stat().st_mtime_ns))
