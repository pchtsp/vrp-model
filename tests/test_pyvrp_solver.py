"""PyVRP integration tests (optional dependency)."""

from __future__ import annotations

import unittest

from tests.tiny_line_solver import run_tiny_line_two_jobs
from vrp_model import Model, TravelEdgeAttrs, TravelEdgesMap

try:
    import pyvrp  # noqa: F401

    from vrp_model.solvers.pyvrp import PyVRPSolver
except ModuleNotFoundError:
    PyVRPSolver = None  # type: ignore[misc, assignment]


@unittest.skipIf(PyVRPSolver is None, "pyvrp extra not installed")
class TestPyVRPSolver(unittest.TestCase):
    def test_tiny_instance_feasible(self) -> None:
        result, _m = run_tiny_line_two_jobs(PyVRPSolver({"time_limit": 2.0, "msg": False}))
        self.assertEqual(result.mapped_status.name, "FEASIBLE")
        self.assertEqual(result.solver_name, "pyvrp")
        self.assertTrue(result.solution_found)
        if result.wall_time_seconds is not None:
            self.assertGreaterEqual(result.wall_time_seconds, 0.0)

    def test_without_locations_uses_full_travel_edges(self) -> None:
        m = Model()
        d = m.add_depot()
        m.add_vehicle([10], d)
        m.add_job(3, label="j0")
        m.add_job(4, label="j1")
        edges: TravelEdgesMap = {}
        for i in range(3):
            for j in range(3):
                if i == j:
                    continue
                edges[(i, j)] = TravelEdgeAttrs(distance=1, duration=1)
        m.set_travel_edges(edges)
        m.validate()

        solver = PyVRPSolver({"time_limit": 2.0, "msg": False})
        result = solver.solve(m)
        sol = m.solution
        assert sol is not None
        self.assertEqual(result.mapped_status.name, "FEASIBLE")
        self.assertTrue(m.is_solution_feasible())
        covered = {j.label for r in sol.routes for j in r.jobs}
        self.assertEqual(covered, {"j0", "j1"})

    def test_travel_matrices_distinct_duration(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([10], d)
        m.add_job(3, location=(1.0, 0.0), label="j0")
        m.add_job(4, location=(2.0, 0.0), label="j1")
        dist = [[0, 1, 2], [1, 0, 1], [2, 1, 0]]
        duration = [[0, 100, 200], [100, 0, 50], [200, 50, 0]]
        edges: TravelEdgesMap = {}
        for i in range(3):
            for j in range(3):
                if i == j:
                    continue
                edges[(i, j)] = TravelEdgeAttrs(distance=dist[i][j], duration=duration[i][j])
        m.set_travel_edges(edges)
        m.validate()

        solver = PyVRPSolver({"time_limit": 2.0, "msg": False})
        result = solver.solve(m)
        sol = m.solution
        assert sol is not None
        self.assertEqual(result.mapped_status.name, "FEASIBLE")
        self.assertTrue(m.is_solution_feasible())

    def test_interleaved_nodes_pyvrp(self) -> None:
        m = Model()
        d0 = m.add_depot(location=(0.0, 0.0))
        m.add_job(2, location=(1.0, 0.0), label="mid")
        d1 = m.add_depot(location=(3.0, 0.0))
        m.add_vehicle([10], d0, end_depot=d1)
        m.add_job(1, location=(2.0, 0.0), label="last")
        solver = PyVRPSolver({"time_limit": 2.0, "msg": False})
        result = solver.solve(m)
        sol = m.solution
        assert sol is not None
        self.assertEqual(result.mapped_status.name, "FEASIBLE")
        labels = {j.label for r in sol.routes for j in r.jobs}
        self.assertEqual(labels, {"mid", "last"})

    def test_fixed_cost_route_limits_supported(self) -> None:
        """PyVRP receives fixed cost, max distance, and max route time when set."""
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle(
            [10],
            d,
            fixed_use_cost=100,
            max_route_distance=10_000,
            max_route_time=10_000,
        )
        m.add_job(1, location=(1.0, 0.0), label="j0")
        m.validate()

        solver = PyVRPSolver({"time_limit": 2.0, "msg": False})
        result = solver.solve(m)
        sol = m.solution
        assert sol is not None
        self.assertEqual(result.mapped_status.name, "FEASIBLE")
        self.assertTrue(m.is_solution_feasible())

    def test_route_time_overtime_pyvrp(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle(
            [10],
            d,
            max_route_time=3,
            max_route_overtime=10,
            route_overtime_unit_cost=0,
        )
        m.add_job(1, location=(1.0, 0.0), label="a")
        m.add_job(1, location=(2.0, 0.0), label="b")
        m.validate()
        solver = PyVRPSolver({"time_limit": 3.0, "msg": False})
        result = solver.solve(m)
        self.assertEqual(result.mapped_status.name, "FEASIBLE")
        self.assertTrue(m.is_solution_feasible())


if __name__ == "__main__":
    unittest.main()
