"""Solver capability checks."""

import unittest

from vrp_model import Model, SolverCapabilityError
from vrp_model.solvers.ortools import ORToolsSolver


class TestSolverCapability(unittest.TestCase):
    def test_ortools_rejects_time_windows(self) -> None:
        m = Model()
        d = m.add_depot()
        m.add_vehicle([10], d)
        m.add_job(1, time_window=(0, 10), location=(0.0, 0.0))

        solver = ORToolsSolver()
        with self.assertRaises(SolverCapabilityError):
            solver.solve(m, None)


if __name__ == "__main__":
    unittest.main()
