"""Tests for ``Solver`` orchestration."""

from __future__ import annotations

import unittest

from vrp_model import Feature, Model, Solution, Solver, SolveStatus


class FakeSolver(Solver):
    name = "fake"
    supported_features = frozenset(Feature)

    def __init__(self) -> None:
        self.solve_called = False

    def _run(self, model: Model, options: dict) -> tuple[object, Solution]:
        self.solve_called = True
        return SolveStatus.FEASIBLE, Solution(
            routes=[],
            cost=0.0,
            feasible=True,
            unassigned=[],
        )


class TestSolverSolve(unittest.TestCase):
    def test_validate_and_compatibility_and_solution_attachment(self) -> None:
        m = Model()
        d = m.add_depot()
        m.add_vehicle([], d)
        m.add_job(0, location=(0.0, 0.0))

        s = FakeSolver()
        status = s.solve(m, None)
        self.assertEqual(status, SolveStatus.FEASIBLE)
        self.assertTrue(s.solve_called)
        assert m.solution is not None
        self.assertEqual(m.solution.feasible, True)


if __name__ == "__main__":
    unittest.main()
