"""Tests for ``Solver`` orchestration."""

from __future__ import annotations

import unittest

from vrp_model import Feature, Model, Route, Solution, Solver, SolveStatus
from vrp_model.solvers.status import SolutionStatus, SolverStopReason


class FakeSolver(Solver):
    name = "fake"
    supported_features = frozenset(Feature)

    def __init__(self) -> None:
        self.solve_called = False

    def _run(self, model: Model) -> SolutionStatus:
        self.solve_called = True
        d = next(iter(model.depots))
        v = next(iter(model.vehicles))
        routes: list[Route] = []
        jobs = list(model.jobs)
        if jobs:
            routes = [Route(vehicle=v, start_depot=d, end_depot=d, jobs=[jobs[0]])]
        model._solution = Solution(routes=routes)
        return SolutionStatus(
            mapped_status=SolveStatus.FEASIBLE,
            solver_name=self.name,
            wall_time_seconds=0.0,
            optimality_gap=None,
            solver_reported_cost=0.0,
            stop_reason=SolverStopReason.COMPLETED,
            solution_found=True,
            iterations=None,
            error_message=None,
            solver_status="",
        )


class TestSolverSolve(unittest.TestCase):
    def test_validate_and_compatibility_and_solution_attachment(self) -> None:
        m = Model()
        d = m.add_depot()
        m.add_vehicle([], d)
        m.add_job(0, location=(0.0, 0.0))

        s = FakeSolver()
        status = s.solve(m)
        self.assertEqual(status.mapped_status, SolveStatus.FEASIBLE)
        self.assertEqual(status.solver_name, "fake")
        self.assertTrue(s.solve_called)
        assert m.solution is not None
        self.assertTrue(m.is_solution_feasible())


if __name__ == "__main__":
    unittest.main()
