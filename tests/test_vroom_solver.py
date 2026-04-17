"""VROOM (pyvroom) integration tests (optional dependency)."""

from __future__ import annotations

import unittest

from tests._vroom_probe import vroom_matrix_ok
from tests.tiny_line_solver import run_tiny_line_two_jobs

try:
    import vroom  # noqa: F401

    from vrp_model.solvers.vroom import VroomSolver
except ModuleNotFoundError:
    VroomSolver = None  # type: ignore[misc, assignment]
    _VROOM_MATRIX_OK = False
else:
    _VROOM_MATRIX_OK = vroom_matrix_ok()


@unittest.skipIf(VroomSolver is None, "vroom extra not installed")
@unittest.skipUnless(_VROOM_MATRIX_OK, "pyvroom matrix API unavailable (e.g. NumPy 2 buffer issue)")
class TestVroomSolver(unittest.TestCase):
    def test_tiny_instance_feasible(self) -> None:
        result, _m = run_tiny_line_two_jobs(VroomSolver({"time_limit": 5.0}))
        self.assertEqual(result.mapped_status.name, "FEASIBLE")
        self.assertEqual(result.solver_name, "vroom")
        self.assertTrue(result.solution_found)
        if result.wall_time_seconds is not None:
            self.assertGreaterEqual(result.wall_time_seconds, 0.0)


if __name__ == "__main__":
    unittest.main()
