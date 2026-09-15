"""Day 5 fleet tests: verify concurrency, ordering, and failure normalization."""

from __future__ import annotations

import threading
import time
import unittest

from mitos import run_fleet


class FakeHarness:
    """Run a configured task while recording concurrent worker activity."""

    def __init__(self, workdir: str, active: list[int], lock: threading.Lock) -> None:
        """Store the job directory and shared concurrency counters."""
        self.workdir = workdir
        self.active = active
        self.lock = lock

    def run(self, task: str) -> str:
        """Return a report after a task-specific delay or raise on request."""
        if task == "fail":
            raise ValueError("broken job")
        delay = float(task)
        with self.lock:
            self.active[0] += 1
            self.active[1] = max(self.active[1], self.active[0])
        time.sleep(delay)
        with self.lock:
            self.active[0] -= 1
        return f"{self.workdir}:{task}"


class FleetTests(unittest.TestCase):
    """Exercise independent worker construction and deterministic results."""

    def test_results_stay_in_input_order_while_jobs_overlap(self) -> None:
        """A slower first job remains first even though later work finishes sooner."""
        active = [0, 0]
        lock = threading.Lock()
        jobs = [
            {"name": "slow", "workdir": "one", "task": "0.04"},
            {"name": "fast", "workdir": "two", "task": "0.01"},
        ]
        results = run_fleet(jobs, lambda workdir: FakeHarness(workdir, active, lock), 2)
        self.assertEqual([item["name"] for item in results], ["slow", "fast"])
        self.assertEqual([item["report"] for item in results], ["one:0.04", "two:0.01"])
        self.assertTrue(all(item["ok"] for item in results))
        self.assertEqual(active[1], 2)

    def test_worker_exception_becomes_failed_report(self) -> None:
        """One failed job does not raise from or cancel the rest of the fleet."""
        active = [0, 0]
        lock = threading.Lock()
        jobs = [
            {"name": "bad", "workdir": "broken", "task": "fail"},
            {"name": "good", "workdir": "healthy", "task": "0"},
        ]
        results = run_fleet(jobs, lambda workdir: FakeHarness(workdir, active, lock))
        self.assertEqual(results[0],
                         {"name": "bad", "ok": False, "report": "ValueError: broken job"})
        self.assertEqual(results[1], {"name": "good", "ok": True, "report": "healthy:0"})

    def test_empty_fleet_returns_empty_list(self) -> None:
        """No jobs require no harness construction and produce no reports."""
        calls: list[str] = []
        self.assertEqual(run_fleet([], lambda workdir: calls.append(workdir)), [])
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
