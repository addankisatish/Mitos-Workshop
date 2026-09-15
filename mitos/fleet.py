"""Day 5: run independent Mitos jobs concurrently without losing input order.

Fleet workers share no conversation state: each creates a harness for its own
directory and task.  Worker failures become ordinary reports, and ordered map
semantics make the returned result list deterministic despite concurrent work.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable


def _run_job(job: dict[str, Any], make_harness: Callable[[str], Any]) -> dict[str, Any]:
    name = job["name"]
    try:
        harness = make_harness(job["workdir"])
        report = harness.run(job["task"])
    except Exception as exc:
        return {
            "name": name,
            "ok": False,
            "report": f"{type(exc).__name__}: {exc}",
        }
    return {"name": name, "ok": True, "report": report}


def run_fleet(
    jobs: list[dict[str, Any]],
    make_harness: Callable[[str], Any],
    max_workers: int = 4,
) -> list[dict[str, Any]]:
    """Run jobs concurrently and return normalized reports in input order."""
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(executor.map(lambda job: _run_job(job, make_harness), jobs))
