"""Tests for :class:`~vrp_model.solvers.status.SolutionStatus`."""

from __future__ import annotations

import unittest

from vrp_model import SolveStatus
from vrp_model.solvers.status import SolutionStatus, SolverStopReason


class TestSolutionStatus(unittest.TestCase):
    def test_construct_with_solver_status(self) -> None:
        s = SolutionStatus(
            mapped_status=SolveStatus.FEASIBLE,
            solver_name="x",
            wall_time_seconds=1.0,
            optimality_gap=None,
            solver_reported_cost=0.0,
            stop_reason=SolverStopReason.COMPLETED,
            solution_found=True,
            iterations=0,
            error_message=None,
            solver_status="custom solver message",
        )
        self.assertEqual(s.mapped_status, SolveStatus.FEASIBLE)
        self.assertEqual(s.solver_name, "x")
        self.assertEqual(s.solver_status, "custom solver message")

    def test_solver_status_defaults_empty(self) -> None:
        s = SolutionStatus(
            mapped_status=SolveStatus.UNKNOWN,
            solver_name="test",
            wall_time_seconds=None,
            optimality_gap=None,
            solver_reported_cost=None,
            stop_reason=SolverStopReason.UNKNOWN,
            solution_found=False,
            iterations=None,
            error_message=None,
        )
        self.assertEqual(s.solver_status, "")


if __name__ == "__main__":
    unittest.main()
