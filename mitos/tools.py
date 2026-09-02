"""Day 2: turn ordinary functions into bounded workspace tools.

This module teaches the tool protocol, a single real-path confinement boundary,
and deliberately finite observations.  Tools use strings at the model boundary,
while their implementations remain plain standard-library Python callables.
"""

from __future__ import annotations

import fnmatch
import inspect
import os
import re
import subprocess
from dataclasses import dataclass
from typing import Any, Callable

_IGNORED = {".git", "node_modules", "__pycache__", ".venv"}


@dataclass(frozen=True)
class Tool:
    """Pair a provider schema and executable callable under one stable name."""

    name: str
    spec: dict[str, Any]
    run: Callable[..., Any]


def tool(description: str, **params: str) -> Callable[[Callable[..., Any]], Tool]:
    """Decorate a function as a string-parameter Mitos tool."""

    def decorate(fn: Callable[..., Any]) -> Tool:
        """Build a schema from the function signature and supplied descriptions."""
        signature = inspect.signature(fn)
        properties = {
            name: {"type": "string", "description": params.get(name, "")}
            for name in signature.parameters
        }
        required = [
            name
            for name, parameter in signature.parameters.items()
            if parameter.default is inspect.Parameter.empty
        ]
        schema = {
            "schema": {
                "name": fn.__name__,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            }
        }
        return Tool(fn.__name__, schema, fn)

    return decorate


def core_tools(workdir: str | os.PathLike[str]) -> list[Tool]:
    """Return the six core tools confined to the real path of ``workdir``."""
    root = os.path.realpath(os.fspath(workdir))

    def resolve(path: str) -> str:
        """Resolve a user path and reject lexical escapes and symlink escapes."""
        candidate = os.path.realpath(os.path.join(root, path))
        try:
            inside = os.path.commonpath((root, candidate)) == root
        except ValueError:
            inside = False
        if not inside:
            raise PermissionError(f"{path!r} escapes the working directory")
        return candidate

    @tool("Read a text file with numbered lines", path="File path")
    def read_file(path: str) -> str:
        """Read at most 4000 numbered lines from a workspace file."""
        with open(resolve(path), encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        numbered = [f"{number}\t{line}" for number, line in enumerate(lines[:4000], 1)]
        if len(lines) > 4000:
            numbered.append(f"...\t[truncated; {len(lines)} total lines]")
        return "\n".join(numbered)

    @tool("Write a text file", path="File path", content="Complete file contents")
    def write_file(path: str, content: str) -> str:
        """Create parent directories and replace a workspace file's contents."""
        target = resolve(path)
        parent = os.path.dirname(target)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(content)
        return f"Wrote {len(content)} chars to {path}"

    @tool("Replace one exact snippet in a text file", path="File path",
          old="Exact existing text", new="Replacement text")
    def edit_file(path: str, old: str, new: str) -> str:
        """Replace ``old`` only when it occurs exactly once."""
        target = resolve(path)
        with open(target, encoding="utf-8") as handle:
            content = handle.read()
        count = content.count(old)
        # Exact uniqueness prevents an apparently small edit from changing extra sites.
        if count == 0:
            return "ERROR: snippet not found — read the file and copy it exactly"
        if count > 1:
            return f"ERROR: snippet appears {count} times — include more context to make it unique"
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(content.replace(old, new, 1))
        return f"Edited {path}"

    @tool("Run a shell command in the workspace", command="Shell command",
          timeout="Timeout in seconds")
    def bash(command: str, timeout: str = "120") -> str:
        """Run a bounded shell command and return combined, clipped output."""
        try:
            completed = subprocess.run(
                command,
                shell=True,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=float(timeout),
            )
        except subprocess.TimeoutExpired:
            return f"ERROR: timed out after {timeout}s"
        output = completed.stdout + completed.stderr
        if len(output) > 12000:
            output = output[:6000] + "\n... output truncated ...\n" + output[-6000:]
        return output if output else f"(exit {completed.returncode}, no output)"

    def matching_files(pattern: str) -> list[str]:
        """Collect sorted workspace files matching relative path or basename."""
        matches: list[str] = []
        for directory, names, filenames in os.walk(root):
            names[:] = [name for name in names if name not in _IGNORED]
            for filename in filenames:
                full_path = os.path.join(directory, filename)
                relative = os.path.relpath(full_path, root).replace(os.sep, "/")
                if fnmatch.fnmatch(relative, pattern) or fnmatch.fnmatch(filename, pattern):
                    matches.append(relative)
        return sorted(matches)

    @tool("List files matching a glob", pattern="Glob for paths or basenames")
    def list_files(pattern: str = "**/*") -> str:
        """List up to 500 matching files while skipping dependency metadata."""
        matches = matching_files(pattern)
        visible = matches[:500]
        if len(matches) > 500:
            visible.append(f"and {len(matches) - 500} more")
        return "\n".join(visible)

    @tool("Search matching text files", regex="Regular expression",
          pattern="Glob for paths or basenames")
    def grep(regex: str, pattern: str = "*") -> str:
        """Return at most 200 clipped, line-oriented regular-expression hits."""
        expression = re.compile(regex)
        hits: list[str] = []
        for relative in matching_files(pattern):
            with open(resolve(relative), encoding="utf-8", errors="replace") as handle:
                for line_number, line in enumerate(handle, 1):
                    if expression.search(line):
                        hits.append(f"{relative}:{line_number}: {line.rstrip()[:200]}")
                        if len(hits) == 200:
                            return "\n".join(hits)
        return "\n".join(hits)

    return [read_file, write_file, edit_file, bash, list_files, grep]
