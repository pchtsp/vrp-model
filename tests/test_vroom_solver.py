"""VROOM (pyvroom) integration tests (optional dependency)."""

from __future__ import annotations

import unittest

import numpy as np

from tests.toy_instances import build_tiny_line_two_jobs

try:
    import vroom  # noqa: F401

    from vrp_model.solvers.vroom import VroomSolver
except ModuleNotFoundError:
    VroomSolver = None  # type: ignore[misc, assignment]
    _VROOM_MATRIX_OK = False
else:

    def _vroom_matrix_probe() -> bool:
        try:
            inp = vroom.Input()
            m = np.ascontiguousarray([[0, 1], [1, 0]], dtype=np.uint32)
            inp.set_durations_matrix("car", m)
        except RuntimeError:
            return False
        return True

    _VROOM_MATRIX_OK = _vroom_matrix_probe()


@unittest.skipIf(VroomSolver is None, "vroom extra not installed")
@unittest.skipUnless(_VROOM_MATRIX_OK, "pyvroom matrix API unavailable (e.g. NumPy 2 buffer issue)")
class TestVroomSolver(unittest.TestCase):
    def test_tiny_instance_feasible(self) -> None:
        m = build_tiny_line_two_jobs()

        solver = VroomSolver({"time_limit": 5.0})
        result = solver.solve(m)
        sol = m.solution
        self.assertIsNotNone(sol)
        assert sol is not None
        self.assertTrue(m.is_solution_feasible())
        self.assertEqual(result.mapped_status.name, "FEASIBLE")
        self.assertEqual(result.solver_name, "vroom")
        self.assertTrue(result.solution_found)
        if result.wall_time_seconds is not None:
            self.assertGreaterEqual(result.wall_time_seconds, 0.0)
        covered = {j.label for r in sol.routes for j in r.jobs}
        self.assertEqual(covered, {"j0", "j1"})


if __name__ == "__main__":
    unittest.main()
