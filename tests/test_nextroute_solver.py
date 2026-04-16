"""Nextmv Nextroute integration tests (optional dependency)."""

from __future__ import annotations

import unittest

from tests.toy_instances import build_tiny_line_two_jobs

try:
    import nextroute  # noqa: F401

    from vrp_model.solvers.nextroute import NextrouteSolver
except ModuleNotFoundError:
    NextrouteSolver = None  # type: ignore[misc, assignment]


@unittest.skipIf(NextrouteSolver is None, "nextroute extra not installed")
class TestNextrouteSolver(unittest.TestCase):
    def test_tiny_instance_feasible(self) -> None:
        m = build_tiny_line_two_jobs()

        solver = NextrouteSolver({"time_limit": 5.0})
        result = solver.solve(m)
        sol = m.solution
        self.assertIsNotNone(sol)
        assert sol is not None
        self.assertTrue(m.is_solution_feasible())
        self.assertEqual(result.mapped_status.name, "FEASIBLE")
        self.assertEqual(result.solver_name, "nextroute")
        self.assertTrue(result.solution_found)
        if result.wall_time_seconds is not None:
            self.assertGreaterEqual(result.wall_time_seconds, 0.0)
        covered = {j.label for r in sol.routes for j in r.jobs}
        self.assertEqual(covered, {"j0", "j1"})


if __name__ == "__main__":
    unittest.main()
