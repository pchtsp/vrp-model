"""Nextmv Nextroute integration tests (optional dependency)."""

from __future__ import annotations

import unittest

from tests.tiny_line_solver import run_tiny_line_two_jobs

try:
    import nextroute  # noqa: F401

    from vrp_model.solvers.nextroute import NextrouteSolver
except ModuleNotFoundError:
    NextrouteSolver = None  # type: ignore[misc, assignment]


@unittest.skipIf(NextrouteSolver is None, "nextroute extra not installed")
class TestNextrouteSolver(unittest.TestCase):
    def test_tiny_instance_feasible(self) -> None:
        result, _m = run_tiny_line_two_jobs(NextrouteSolver({"time_limit": 5.0}))
        self.assertEqual(result.mapped_status.name, "FEASIBLE")
        self.assertEqual(result.solver_name, "nextroute")
        self.assertTrue(result.solution_found)
        if result.wall_time_seconds is not None:
            self.assertGreaterEqual(result.wall_time_seconds, 0.0)


if __name__ == "__main__":
    unittest.main()
