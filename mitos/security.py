"""Day 2: place a small, explicit policy gate before tool execution.

The policy teaches defense in depth: a short denylist protects every mode,
read-only names are cheap to allow, and mutation in safe mode requires an
affirmative callback rather than an implicit prompt or ambient permission.
"""

from __future__ import annotations

import re
from typing import Any, Callable

READ_TOOLS = {"read_file", "list_files", "grep"}

# These patterns target irreversible shell shapes, not general command parsing.
DENY_PATTERNS = (
    r"\brm\s+(?=[^;&|\n]*(?:-[^\s]*r|--recursive))"
    r"(?=[^;&|\n]*(?:-[^\s]*f|--force))[^;&|\n]*\s(?:/|~|\$HOME)(?:\s|[;&|]|$)",
    r"\bsudo\b",
    r"\bmkfs(?:\.[a-z0-9]+)?\b",
    r"\bdd\s+[^;&|\n]*\bif\s*=",
    r"\bcurl\b[^|\n]*\|\s*(?:ba|z|k)?sh\b",
    r"\bgit\s+push\b[^;&|\n]*--force\b",
    r">{1,2}\s*/dev/sd[a-z](?:\d+)?\b",
)

Approver = Callable[[dict[str, Any], str], bool]


class Policy:
    """Allow, refuse, or request approval for neutral Mitos tool calls."""

    def __init__(self, mode: str = "safe", approver: Approver | None = None) -> None:
        """Create a policy in read-only, safe, or yolo mode."""
        if mode not in {"read-only", "safe", "yolo"}:
            raise ValueError(f"unknown policy mode {mode!r}")
        self.mode = mode
        self.approver = approver or (lambda call, reason: False)

    def check(self, call: dict[str, Any]) -> str | None:
        """Return ``None`` to allow a call or a human-readable block reason."""
        name = call.get("name", "")
        if name == "bash":
            command = str(call.get("args", {}).get("command", ""))
            if any(re.search(pattern, command, re.IGNORECASE) for pattern in DENY_PATTERNS):
                return "dangerous shell command"
        if name in READ_TOOLS or self.mode == "yolo":
            return None
        if self.mode == "read-only":
            return f"read-only mode blocks {name}"
        reason = f"{name} may change the working directory"
        if self.approver(call, reason) is True:
            return None
        return f"approval refused for {name}"
