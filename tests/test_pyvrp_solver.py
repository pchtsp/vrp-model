"""PyVRP integration tests (optional dependency)."""

from __future__ import annotations

import unittest

from tests._limits import pyvrp_options
from tests.tiny_line_solver import run_tiny_line_two_jobs
from vrp_model import (
    Model,
    Route,
    Solution,
    TravelEdgeAttrs,
    TravelEdgesMap,
    Vehicle,
)
from vrp_model.solvers._helpers import skill_violations
from vrp_model.solvers.pyvrp.bindings import PYVRP_MAX_VALUE, PyVRPResultLike

try:
    import pyvrp  # noqa: F401

    from vrp_model.solvers.pyvrp import PyVRPSolver

    _PYVRP_INSTALLED = True
except ModuleNotFoundError:
    _PYVRP_INSTALLED = False


@unittest.skipIf(not _PYVRP_INSTALLED, "pyvrp extra not installed")
class TestPyVRPSolver(unittest.TestCase):
    def test_tiny_instance_feasible(self) -> None:
        result, _m = run_tiny_line_two_jobs(PyVRPSolver(pyvrp_options()))
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

        solver = PyVRPSolver(pyvrp_options())
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

        solver = PyVRPSolver(pyvrp_options())
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
        solver = PyVRPSolver(pyvrp_options())
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

        solver = PyVRPSolver(pyvrp_options())
        result = solver.solve(m)
        sol = m.solution
        assert sol is not None
        self.assertEqual(result.mapped_status.name, "FEASIBLE")
        self.assertTrue(m.is_solution_feasible())

    def test_skills_routes_compatible_vehicle(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([10], d, skills={1})
        m.add_vehicle([10], d, skills={2})
        m.add_job(1, location=(1.0, 0.0), skills_required={1})
        m.add_job(1, location=(2.0, 0.0), skills_required={2})
        m.validate()
        PyVRPSolver(pyvrp_options()).solve(m)
        self.assertTrue(m.is_solution_feasible())
        for r in m.solution.routes:
            if not r.jobs:
                continue
            vs = r.vehicle.skills
            for j in r.jobs:
                req = j.skills_required
                if req:
                    self.assertTrue(req <= vs)

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
        solver = PyVRPSolver(pyvrp_options())
        result = solver.solve(m)
        self.assertEqual(result.mapped_status.name, "FEASIBLE")
        self.assertTrue(m.is_solution_feasible())

    def test_pickup_delivery_precedence_and_same_vehicle(self) -> None:
        """Pairs map to PyVRP shipments, so both jobs share a route in pickup-first order."""
        m = Model()
        d = m.add_depot(location=(0.0, 0.0), label="D")
        m.add_vehicle([10], d, label="v0")
        m.add_vehicle([10], d, label="v1")
        p1 = m.add_job(3, location=(1.0, 1.0), label="p1")
        d1 = m.add_job(0, location=(4.0, 1.0), label="d1")
        m.add_job(2, location=(2.0, 3.0), label="plain")
        p2 = m.add_job(4, location=(-1.0, 2.0), label="p2")
        d2 = m.add_job(0, location=(-3.0, 0.5), label="d2")
        m.add_pickup_delivery(p1, d1)
        m.add_pickup_delivery(p2, d2)
        m.validate()

        result = PyVRPSolver(pyvrp_options()).solve(m)
        sol = m.solution
        assert sol is not None
        self.assertEqual(result.mapped_status.name, "FEASIBLE")
        self.assertTrue(m.is_solution_feasible())

        labels = {j.label for r in sol.routes for j in r.jobs}
        self.assertEqual(labels, {"p1", "d1", "plain", "p2", "d2"})

        pos = {j.label: (ri, k) for ri, r in enumerate(sol.routes) for k, j in enumerate(r.jobs)}
        for pickup, delivery in (("p1", "d1"), ("p2", "d2")):
            (pr, pk), (dr, dk) = pos[pickup], pos[delivery]
            self.assertEqual(pr, dr, f"{pickup}/{delivery} must share a route")
            self.assertLess(pk, dk, f"{pickup} must precede {delivery}")


@unittest.skipIf(not _PYVRP_INSTALLED, "pyvrp extra not installed")
class TestPyVRPSkillProfiles(unittest.TestCase):
    """Vehicle-job compatibility is expressed as one routing profile per blocked job set."""

    def test_no_job_skills_uses_single_profile(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([10], d, skills={1})
        m.add_vehicle([10], d, skills={2, 3})
        m.add_job(1, location=(1.0, 0.0))
        m.validate()

        data = PyVRPSolver(pyvrp_options()).build_solver_model(m)
        self.assertEqual(data.num_profiles, 1)

    def test_profiles_keyed_on_blocked_jobs_not_skill_sets(self) -> None:
        """Skills no job asks for must not split vehicles across profiles."""
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([10], d, skills={1})
        m.add_vehicle([10], d, skills={1, 7})  # 7 is not required anywhere
        m.add_vehicle([10], d, skills={1, 2})
        m.add_job(1, location=(1.0, 0.0), skills_required={1})
        m.add_job(1, location=(2.0, 0.0), skills_required={2})
        m.validate()

        data = PyVRPSolver(pyvrp_options()).build_solver_model(m)
        # {1} and {1, 7} both serve exactly job 1, so they share a profile; {1, 2} serves
        # both jobs and gets the unrestricted one.
        self.assertEqual(data.num_profiles, 2)
        profiles = [data.vehicle_type(i).profile for i in range(data.num_vehicle_types)]
        self.assertEqual(profiles[0], profiles[1])
        self.assertNotEqual(profiles[0], profiles[2])

    def test_incompatible_arcs_are_blocked_in_profile_matrix(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([10], d, skills={1})
        m.add_vehicle([10], d, skills={1, 2})
        m.add_job(1, location=(1.0, 0.0), skills_required={1})
        m.add_job(1, location=(2.0, 0.0), skills_required={2})
        m.validate()

        data = PyVRPSolver(pyvrp_options()).build_solver_model(m)
        restricted = data.vehicle_type(0).profile
        unrestricted = data.vehicle_type(1).profile
        blocked = data.distance_matrix(profile=restricted)
        allowed = data.distance_matrix(profile=unrestricted)

        # Locations are depots first, then jobs: node 2 (skills {2}) is location index 2.
        self.assertEqual(int(blocked[0, 2]), PYVRP_MAX_VALUE)
        self.assertEqual(int(blocked[1, 2]), PYVRP_MAX_VALUE)
        self.assertEqual(int(blocked[2, 2]), 0)  # diagonal stays zero
        self.assertEqual(int(blocked[0, 1]), int(allowed[0, 1]))  # compatible job untouched
        self.assertNotEqual(int(allowed[0, 2]), PYVRP_MAX_VALUE)

    def test_solution_respects_skills(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([10], d, skills={1})
        m.add_vehicle([10], d, skills={2})
        m.add_job(1, location=(1.0, 0.0), skills_required={1})
        m.add_job(1, location=(2.0, 0.0), skills_required={2})
        m.validate()

        status = PyVRPSolver(pyvrp_options()).solve(m)
        self.assertEqual(status.mapped_status.name, "FEASIBLE")
        self.assertIsNone(status.error_message)
        sol = m.solution
        assert sol is not None
        self.assertEqual(skill_violations(m, sol), [])

    def test_skill_violation_downgrades_status(self) -> None:
        """Profile blocking prices incompatible arcs out but cannot forbid them.

        Stand in for PyVRP taking such an arc anyway, and check the run is reported
        INFEASIBLE rather than passed off as a feasible solution.
        """
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([10], d, skills={1}, label="v0")
        m.add_vehicle([10], d, label="v1")  # no skills at all
        m.add_job(1, location=(1.0, 0.0), skills_required={1}, label="j0")
        m.validate()

        class _MisassigningSolver(PyVRPSolver):
            def find_solution_values(self, model: Model, result: PyVRPResultLike) -> Solution:
                """Hand every route to v1, which has none of the skills j0 needs."""
                mapped = super().find_solution_values(model, result)
                return Solution(
                    routes=[
                        Route(
                            vehicle=Vehicle(model, 1),
                            start_depot=r.start_depot,
                            end_depot=r.end_depot,
                            jobs=r.jobs,
                        )
                        for r in mapped.routes
                    ],
                )

        status = _MisassigningSolver(pyvrp_options()).solve(m)
        self.assertEqual(status.mapped_status.name, "INFEASIBLE")
        self.assertEqual(status.stop_reason.name, "INFEASIBLE")
        assert status.error_message is not None
        self.assertIn("j0", status.error_message)
        self.assertIn("v1", status.error_message)


if __name__ == "__main__":
    unittest.main()
