"""Day 4 sub-agent tests: verify schema, isolation factory, and depth limits."""

from __future__ import annotations

import unittest

from mitos.subagent import subagent_tool


class FakeHarness:
    """Record a child task and return a deterministic final report."""

    def __init__(self) -> None:
        """Start without a delegated task."""
        self.task: str | None = None

    def run(self, task: str) -> str:
        """Record the task and stand in for a child's final response."""
        self.task = task
        return "child report"


class SubagentTests(unittest.TestCase):
    """Exercise the generated tool below and at its recursion boundary."""

    def test_tool_schema_describes_clean_context_and_required_task(self) -> None:
        """The generated provider schema advertises the exact delegation contract."""
        item = subagent_tool(lambda depth: FakeHarness())
        schema = item.spec["schema"]
        self.assertEqual(item.name, "spawn_agent")
        self.assertIn("fresh sub-agent", schema["description"])
        self.assertIn("cannot see this conversation", schema["description"])
        self.assertEqual(schema["parameters"]["required"], ["task"])

    def test_child_receives_next_depth_and_task(self) -> None:
        """Allowed delegation creates one child and returns only its report."""
        observed: list[tuple[int, FakeHarness]] = []

        def make(depth: int) -> FakeHarness:
            child = FakeHarness()
            observed.append((depth, child))
            return child

        item = subagent_tool(make, depth=1, max_depth=2)
        self.assertEqual(item.run(task="write utils.py"), "child report")
        self.assertEqual(observed[0][0], 2)
        self.assertEqual(observed[0][1].task, "write utils.py")

    def test_depth_limit_does_not_construct_a_child(self) -> None:
        """At maximum depth the tool reports the exact error locally."""
        calls: list[int] = []
        item = subagent_tool(lambda depth: calls.append(depth), depth=2, max_depth=2)
        self.assertEqual(
            item.run(task="delegate again"),
            "ERROR: sub-agent depth limit reached; do this task yourself",
        )
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
