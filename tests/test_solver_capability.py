"""Solver capability checks."""

from __future__ import annotations

import unittest

from vrp_model import Model, SolverCapabilityError
from vrp_model.solvers.pyvrp import PyVRPSolver

try:
    import ortools  # noqa: F401
except ModuleNotFoundError:
    _ORTOOLS_INSTALLED = False
else:
    _ORTOOLS_INSTALLED = True


class TestSolverCapability(unittest.TestCase):
    def test_pyvrp_rejects_skills(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([10], d, skills={"x"})
        m.add_job(1, location=(1.0, 0.0), skills_required={"x"})

        solver = PyVRPSolver()
        with self.assertRaises(SolverCapabilityError):
            solver.solve(m)

    @unittest.skipIf(not _ORTOOLS_INSTALLED, "ortools extra not installed")
    def test_ortools_accepts_time_windows(self) -> None:
        from vrp_model.solvers.ortools import ORToolsSolver

        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([10], d, time_window=(0, 10_000))
        m.add_job(1, time_window=(0, 100), location=(1.0, 0.0), service_time=0)

        solver = ORToolsSolver({"time_limit": 5.0})
        solver.solve(m)
        self.assertIsNotNone(m.solution)


if __name__ == "__main__":
    unittest.main()
