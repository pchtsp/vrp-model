"""Solver capability checks."""

from __future__ import annotations

import unittest

from tests._limits import ORTOOLS_TIME_LIMIT, pyvrp_options
from vrp_model import Model, SolverCapabilityError

try:
    import pyvrp  # noqa: F401

    from vrp_model.solvers.pyvrp import PyVRPSolver

    _PYVRP_INSTALLED = True
except ModuleNotFoundError:
    _PYVRP_INSTALLED = False

try:
    import ortools  # noqa: F401
except ModuleNotFoundError:
    _ORTOOLS_INSTALLED = False
else:
    _ORTOOLS_INSTALLED = True

try:
    import vroom  # noqa: F401

    from vrp_model.solvers.vroom import VroomSolver

    _VROOM_INSTALLED = True
except ModuleNotFoundError:
    _VROOM_INSTALLED = False


class TestSolverCapability(unittest.TestCase):
    @unittest.skipIf(not _PYVRP_INSTALLED, "pyvrp extra not installed")
    def test_pyvrp_accepts_skills(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([10], d, skills={1})
        m.add_job(1, location=(1.0, 0.0), skills_required={1})
        m.validate()

        PyVRPSolver(pyvrp_options()).solve(m)
        self.assertIsNotNone(m.solution)
        self.assertTrue(m.is_solution_feasible())

    @unittest.skipIf(not _ORTOOLS_INSTALLED, "ortools extra not installed")
    def test_ortools_accepts_time_windows(self) -> None:
        from vrp_model.solvers.ortools import ORToolsSolver

        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([10], d, time_window=(0, 10_000))
        m.add_job(1, time_window=(0, 100), location=(1.0, 0.0), service_time=0)

        solver = ORToolsSolver({"time_limit": ORTOOLS_TIME_LIMIT})
        solver.solve(m)
        self.assertIsNotNone(m.solution)

    @unittest.skipIf(not _VROOM_INSTALLED, "vroom extra not installed")
    def test_vroom_rejects_job_groups(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([10], d)
        a = m.add_job(1, location=(1.0, 0.0))
        b = m.add_job(1, location=(2.0, 0.0))
        m.add_job_group([a, b])
        m.validate()

        with self.assertRaises(SolverCapabilityError):
            VroomSolver().solve(m)


if __name__ == "__main__":
    unittest.main()
