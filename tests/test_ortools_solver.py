"""OR-Tools integration tests (optional dependency)."""

from __future__ import annotations

import unittest

from vrp_model import Model, TimeWindowFlex, TravelEdgeAttrs, TravelEdgesMap
from vrp_model.core.errors import SolverNotInstalledError
from vrp_model.solvers.ortools import ORToolsSolver

try:
    import ortools  # noqa: F401
except ModuleNotFoundError:
    _ORTOOLS_INSTALLED = False
else:
    _ORTOOLS_INSTALLED = True


@unittest.skipIf(not _ORTOOLS_INSTALLED, "ortools extra not installed")
class TestORToolsSolver(unittest.TestCase):
    def test_tiny_instance_feasible(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([10], d)
        m.add_job(3, location=(1.0, 0.0), label="j0")
        m.add_job(4, location=(2.0, 0.0), label="j1")

        solver = ORToolsSolver({"time_limit": 5.0})
        result = solver.solve(m)
        sol = m.solution
        self.assertIsNotNone(sol)
        assert sol is not None
        self.assertTrue(m.is_solution_feasible())
        self.assertIn(result.mapped_status.name, ("FEASIBLE", "OPTIMAL"))
        self.assertEqual(result.solver_name, "ortools")
        self.assertTrue(result.solution_found)
        covered = {j.label for r in sol.routes for j in r.jobs}
        self.assertEqual(covered, {"j0", "j1"})

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

        solver = ORToolsSolver({"time_limit": 5.0})
        result = solver.solve(m)
        sol = m.solution
        assert sol is not None
        self.assertIn(result.mapped_status.name, ("FEASIBLE", "OPTIMAL"))
        self.assertTrue(m.is_solution_feasible())
        covered = {j.label for r in sol.routes for j in r.jobs}
        self.assertEqual(covered, {"j0", "j1"})

    def test_time_windows(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([10], d, time_window=(0, 10_000))
        m.add_job(1, location=(1.0, 0.0), time_window=(0, 5000), service_time=1)
        m.validate()
        result = ORToolsSolver({"time_limit": 10.0}).solve(m)
        self.assertTrue(m.is_solution_feasible())
        self.assertIn(result.mapped_status.name, ("FEASIBLE", "OPTIMAL"))

    def test_skills_routes_compatible_vehicle(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([10], d, skills={"A"})
        m.add_vehicle([10], d, skills={"B"})
        m.add_job(1, location=(1.0, 0.0), skills_required={"A"})
        m.add_job(1, location=(2.0, 0.0), skills_required={"B"})
        m.validate()
        ORToolsSolver({"time_limit": 20.0}).solve(m)
        self.assertTrue(m.is_solution_feasible())
        for r in m.solution.routes:
            if not r.jobs:
                continue
            vs = r.vehicle.skills
            for j in r.jobs:
                req = j.skills_required
                if req:
                    self.assertTrue(req <= vs)

    def test_fixed_use_cost_and_route_caps_do_not_crash(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle(
            [10],
            d,
            fixed_use_cost=100,
            max_route_distance=1_000_000,
            max_route_time=1_000_000,
            max_slack_time=500_000,
            time_window=(0, 10_000_000),
        )
        m.add_job(1, location=(1.0, 0.0), service_time=0, time_window=(0, 10_000_000))
        m.validate()
        r = ORToolsSolver({"time_limit": 10.0}).solve(m)
        self.assertIn(r.mapped_status.name, ("FEASIBLE", "OPTIMAL"))

    def test_flexible_time_window_soft_latest(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([10], d, time_window=(0, 10_000))
        flex = TimeWindowFlex(soft_latest=100, penalty_per_unit_after_soft_latest=1)
        m.add_job(
            1,
            location=(1.0, 0.0),
            time_window=(0, 500),
            time_window_flex=flex,
            service_time=1,
        )
        m.validate()
        r = ORToolsSolver({"time_limit": 10.0}).solve(m)
        self.assertIn(r.mapped_status.name, ("FEASIBLE", "OPTIMAL"))

    def test_interleaved_nodes_ortools(self) -> None:
        m = Model()
        d0 = m.add_depot(location=(0.0, 0.0))
        m.add_job(2, location=(1.0, 0.0), label="mid")
        d1 = m.add_depot(location=(3.0, 0.0))
        m.add_vehicle([10], d0, end_depot=d1)
        m.add_job(1, location=(2.0, 0.0), label="last")
        m.validate()
        result = ORToolsSolver({"time_limit": 15.0}).solve(m)
        sol = m.solution
        assert sol is not None
        self.assertIn(result.mapped_status.name, ("FEASIBLE", "OPTIMAL"))
        labels = {j.label for r in sol.routes for j in r.jobs}
        self.assertEqual(labels, {"mid", "last"})


class TestORToolsSolverNotInstalled(unittest.TestCase):
    def test_raises_without_dependency(self) -> None:
        if _ORTOOLS_INSTALLED:
            self.skipTest("ortools is installed")

        from vrp_model.solvers.ortools import solver as ortools_solver_module

        self.assertIsNone(ortools_solver_module.PyWrapCP)
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([10], d)
        m.add_job(1, location=(1.0, 0.0))
        m.validate()
        with self.assertRaises(SolverNotInstalledError):
            fake = ortools_solver_module.ORToolsSolver({"time_limit": 1.0})
            fake._run(m)


if __name__ == "__main__":
    unittest.main()
