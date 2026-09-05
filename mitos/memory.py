"""Day 3: carry durable project facts into otherwise fresh conversations.

Memory stays inspectable as one Markdown file beside the project.  Prompt
construction is deterministic, notes are append-only, and each new run receives
the same operating rules plus its real platform and workspace identity.
"""

from __future__ import annotations

import os
import platform
from pathlib import Path

MEMORY_FILE = "MITOS.md"

BASE_SYSTEM_PROMPT = (
    "You are Mitos, a small, sharp coding agent working inside one directory "
    "with the tools provided. Act, don't narrate. Inspect before assuming. "
    "Prefer edit_file for small changes. Verify after building by running or "
    "re-reading. Never repeat a failing call unchanged. When complete, reply "
    "with a short summary and stop calling tools."
)


def build_system_prompt(workdir: str | os.PathLike[str], extra: str = "") -> str:
    """Build the base prompt with environment, durable memory, and extra rules."""
    root = os.path.realpath(os.fspath(workdir))
    sections = [
        BASE_SYSTEM_PROMPT,
        f"Platform: {platform.system()}. Working directory: {root}.",
    ]
    memory_path = Path(root) / MEMORY_FILE
    if memory_path.is_file():
        memory = memory_path.read_text(encoding="utf-8")
        sections.append(f"Project memory (MITOS.md):\n{memory}")
    if extra:
        sections.append(extra)
    return "\n\n".join(sections)


def remember(workdir: str | os.PathLike[str], note: str) -> str:
    """Append one Markdown bullet to the project's durable memory file."""
    memory_path = Path(os.path.realpath(os.fspath(workdir))) / MEMORY_FILE
    with memory_path.open("a", encoding="utf-8") as handle:
        handle.write(f"- {note}\n")
    return "Remembered in MITOS.md"
