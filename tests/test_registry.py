"""Solver registry tests."""

import unittest

from vrp_model import SolveStatus
from vrp_model.solvers.base import Solver
from vrp_model.solvers.registry import get, register
from vrp_model.solvers.status import SolutionStatus, SolverStopReason


class _Dummy(Solver):
    name = "dummy"
    supported_features = frozenset()

    def _run(self, model):  # noqa: ARG002
        return SolutionStatus(
            mapped_status=SolveStatus.UNKNOWN,
            solver_name=self.name,
            wall_time_seconds=None,
            optimality_gap=None,
            solver_reported_cost=None,
            stop_reason=SolverStopReason.UNKNOWN,
            solution_found=False,
            iterations=None,
            error_message=None,
            solver_status="",
        )


class TestRegistry(unittest.TestCase):
    def test_register_and_get(self) -> None:
        register("vrp_model_test_dummy_solver", _Dummy)
        self.assertIs(get("vrp_model_test_dummy_solver"), _Dummy)

    def test_unknown_raises(self) -> None:
        with self.assertRaises(KeyError):
            get("no_such_solver_ever")


if __name__ == "__main__":
    unittest.main()
