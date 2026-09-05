"""Day 3: discover and load project-local instruction skills on demand.
Skills stay as Markdown; discovery is shallow, and full text loads only on request."""

from __future__ import annotations

import os
from pathlib import Path

SKILLS_DIR = "skills"


def _description(text: str) -> str:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, separator, value = line.partition(":")
        if separator and key.strip().lower() == "description":
            return value.strip().strip("'\"")
    return ""


def catalog(workdir: str | os.PathLike[str]) -> dict[str, dict[str, str]]:
    """Catalog direct child skills and their front-matter descriptions."""
    root = Path(os.path.realpath(os.fspath(workdir))) / SKILLS_DIR
    found: dict[str, dict[str, str]] = {}
    if not root.is_dir():
        return found
    for directory in sorted(root.iterdir(), key=lambda path: path.name):
        document = directory / "SKILL.md"
        if directory.is_dir() and document.is_file():
            text = document.read_text(encoding="utf-8")
            found[directory.name] = {"description": _description(text), "path": str(document)}
    return found


def catalog_prompt(workdir: str | os.PathLike[str]) -> str:
    """Render compact skill metadata for inclusion in the system prompt."""
    skills = catalog(workdir)
    if not skills:
        return ""
    lines = ["Skills available (load one with the use_skill tool when relevant):"]
    lines.extend(f"- {name}: {item['description']}" for name, item in skills.items())
    return "\n".join(lines)


def read_skill(workdir: str | os.PathLike[str], name: str) -> str:
    """Return one complete skill document or an informative miss result."""
    skills = catalog(workdir)
    if name not in skills:
        available = ", ".join(skills) or "(none)"
        return f"ERROR: no skill named {name}. Available: {available}"
    return Path(skills[name]["path"]).read_text(encoding="utf-8")
