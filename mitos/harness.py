"""Day 4: compose the Mitos provider, loop, tools, policy, context, and state.

The Harness is the week's spine: construction assembles sockets, ``run`` owns
one transcript, and children share project state without hijacking its session.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from typing import Any

from mitos import context, memory, provider, session, skills
from mitos.loop import run_loop
from mitos.security import Policy
from mitos.subagent import subagent_tool
from mitos.tools import Tool, core_tools, tool


class Harness:
    """Compose one stateful Mitos agent around a single real working directory."""

    def __init__(
        self,
        workdir: str = ".",
        model: str | None = None,
        policy: Policy | None = None,
        extra_tools: Iterable[Tool] | None = None,
        system_extra: str = "",
        on_event: Callable[[str, Any], None] | None = None,
        budget_tokens: int = 600_000,
        max_turns: int = 120,
        session_path: str | None = None,
        enable_subagents: bool = True,
        persist: bool = True,
        _depth: int = 0,
    ) -> None:
        """Assemble core and optional capabilities for one agent conversation."""
        self.workdir = os.path.realpath(workdir)
        os.makedirs(self.workdir, exist_ok=True)
        self.model = model or os.environ.get("MITOS_MODEL") or provider.DEFAULT_MODEL
        self.policy = policy or Policy("yolo")
        self.system_extra = system_extra
        self.on_event = on_event or (lambda kind, payload: None)
        self.budget_tokens = budget_tokens
        self.max_turns = max_turns
        self.persist = persist
        self.messages: list[dict[str, Any]] = []
        self.session_path = session_path
        self._recorded = 0
        self._depth = _depth

        available = core_tools(self.workdir)

        @tool("Remember a durable project fact", note="Fact to save in MITOS.md")
        def remember(note: str) -> str:
            """Append a fact to this harness's project memory."""
            return memory.remember(self.workdir, note)

        available.append(remember)
        skill_catalog = skills.catalog(self.workdir)
        if skill_catalog:
            @tool("Load a project skill's full instructions", name="Skill name")
            def use_skill(name: str) -> str:
                """Load one project-local SKILL.md on demand."""
                return skills.read_skill(self.workdir, name)

            available.append(use_skill)

        if enable_subagents:
            def make_child(depth: int) -> Harness:
                """Construct an ephemeral child with shared project configuration."""
                return Harness(
                    self.workdir,
                    model=self.model,
                    policy=self.policy,
                    system_extra=self.system_extra,
                    on_event=self.on_event,
                    budget_tokens=self.budget_tokens,
                    max_turns=self.max_turns,
                    enable_subagents=True,
                    persist=False,
                    _depth=depth,
                )

            available.append(subagent_tool(make_child, self._depth))
        available.extend(extra_tools or [])
        self.tools = {item.name: item for item in available}
        additions = "\n\n".join(filter(None, (skills.catalog_prompt(self.workdir), system_extra)))
        self.system = memory.build_system_prompt(self.workdir, additions)

    def resume(self, path: str | None = None) -> bool:
        """Load an explicit or latest session and make it the active transcript."""
        chosen = path or session.latest(self.workdir)
        if chosen is None:
            return False
        self.messages = session.load(chosen)
        self.session_path = chosen
        self._recorded = len(self.messages)
        return bool(self.messages)

    def _record_new(self) -> None:
        if not self.persist or self.session_path is None:
            return
        self._recorded = min(self._recorded, len(self.messages))
        while self._recorded < len(self.messages):
            session.append(self.session_path, self.messages[self._recorded])
            self._recorded += 1

    def run(self, task: str) -> str:
        """Append a task, run the composed loop, and durably record its messages."""
        if self.persist and self.session_path is None:
            self.session_path = session.new_session(self.workdir, task[:32])
        self.messages.append({"role": "user", "text": task})
        self._record_new()

        def emit(kind: str, payload: Any) -> None:
            """Persist each completed message before forwarding its event."""
            self._record_new()
            self.on_event(kind, payload)

        def before_turn(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
            """Compact the live list and align the persistence cursor immediately."""
            compacted = context.compact(self.model, messages, self.budget_tokens)
            self._recorded = min(self._recorded, len(compacted))
            return compacted

        return run_loop(
            self.model,
            self.system,
            self.messages,
            self.tools,
            emit,
            self.policy.check,
            max_turns=self.max_turns,
            before_turn=before_turn,
        )
