"""Day 5: expose the composed Mitos harness through a small terminal front door.

The CLI keeps automation non-interactive, makes human approval the safe default,
and renders tool evidence compactly while durable sessions preserve interrupted work.
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Sequence

from mitos.harness import Harness
from mitos.security import Policy

_DIM = "\033[2m"
_RESET = "\033[0m"


def _clip(value: Any, limit: int = 160) -> str:
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _event(kind: str, payload: Any) -> None:
    if kind == "assistant":
        if payload.get("text"):
            print(payload["text"])
        for call in payload.get("tool_calls", []):
            print(f"→ {call['name']} {_clip(call.get('args', {}))}")
    elif kind == "tool_end":
        lines = str(payload.get("text", "")).splitlines()
        first = lines[0] if lines else ""
        print(f"  {_DIM}{first}{_RESET}")


def _approve(call: dict[str, Any], reason: str) -> bool:
    print(f"{call.get('name', 'tool')} {_clip(call.get('args', {}))}: {reason}")
    answer = input(f"approve {call.get('name', 'tool')}? [y/N] ")
    return answer.strip().lower() in {"y", "yes"}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mitos", description="A small, sharp agent harness")
    parser.add_argument("-p", "--prompt", help="run one headless task")
    parser.add_argument("-d", "--workdir", default=".", help="jailed working directory")
    parser.add_argument("-m", "--model", help="provider model name")
    parser.add_argument("--mode", choices=("safe", "yolo", "read-only"))
    parser.add_argument("--resume", action="store_true", help="resume the newest session")
    parser.add_argument("--max-turns", type=int, default=120)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one headless task or an interactive, resumable prompt loop."""
    args = _parser().parse_args(argv)
    mode = args.mode or ("yolo" if args.prompt is not None else "safe")
    policy = Policy(mode, _approve)
    harness = Harness(
        workdir=args.workdir,
        model=args.model,
        policy=policy,
        on_event=_event,
        max_turns=args.max_turns,
    )
    if args.resume:
        harness.resume()
    if args.prompt is not None:
        harness.run(args.prompt)
        return 0

    print(f"Mitos | model {harness.model} | mode {mode} | jail {harness.workdir}")
    while True:
        try:
            task = input("mitos> ").strip()
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print()
            continue
        if not task:
            continue
        try:
            harness.run(task)
        except KeyboardInterrupt:
            print("\nInterrupted. The session log is safe; --resume continues it.")
