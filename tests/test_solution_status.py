"""Tests for :class:`~vrp_model.solvers.status.SolutionStatus`."""

from __future__ import annotations

import unittest

from vrp_model import Model, SolveStatus
from vrp_model.solvers.status import SolutionStatus, SolverStopReason


class TestSolutionStatus(unittest.TestCase):
    def test_from_mapped_delegates_to_model_map_status(self) -> None:
        m = Model()
        s = SolutionStatus.from_mapped(m, "weird", solver_name="test")
        self.assertEqual(s.mapped_status, SolveStatus.UNKNOWN)
        self.assertEqual(s.solver_name, "test")
        self.assertEqual(s.stop_reason, SolverStopReason.UNKNOWN)

    def test_from_mapped_passes_through_solve_status(self) -> None:
        m = Model()
        s = SolutionStatus.from_mapped(m, SolveStatus.FEASIBLE, solver_name="x")
        self.assertEqual(s.mapped_status, SolveStatus.FEASIBLE)


if __name__ == "__main__":
    unittest.main()
