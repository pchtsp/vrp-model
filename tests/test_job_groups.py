"""Job groups (mutually exclusive jobs)."""

from __future__ import annotations

import unittest

from vrp_model import Model, ValidationError


class TestJobGroupValidation(unittest.TestCase):
    def test_disjoint_groups(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([10], d)
        a = m.add_job(1, location=(1.0, 0.0))
        b = m.add_job(1, location=(2.0, 0.0))
        c = m.add_job(1, location=(3.0, 0.0))
        m.add_job_group([a, b])
        m.add_job_group([c, a])
        with self.assertRaisesRegex(ValidationError, "more than one job group"):
            m.validate()

    def test_prize_on_grouped_job_rejected(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([10], d)
        a = m.add_job(1, location=(1.0, 0.0), prize=100.0)
        b = m.add_job(1, location=(2.0, 0.0))
        m.add_job_group([a, b])
        with self.assertRaisesRegex(ValidationError, "prize set but belongs to a job group"):
            m.validate()

    def test_pickup_delivery_in_group_rejected(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([10], d)
        a = m.add_job(1, location=(1.0, 0.0))
        b = m.add_job(1, location=(2.0, 0.0))
        c = m.add_job(1, location=(3.0, 0.0))
        m.add_pickup_delivery(a, b)
        m.add_job_group([a, c])
        with self.assertRaisesRegex(ValidationError, "pickup_delivery"):
            m.validate()

    def test_solution_cost_optional_group_skip(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([10], d)
        ja = m.add_job(1, location=(100.0, 0.0))
        jb = m.add_job(1, location=(100.0, 2.0))
        m.add_job_group([ja, jb], skip_penalty=90)
        jm = m.add_job(1, location=(2.0, 0.0))
        m.validate()
        from vrp_model.core.solution import Route, Solution

        m._solution = Solution(
            routes=[
                Route(
                    vehicle=next(m.vehicles),
                    start_depot=d,
                    end_depot=d,
                    jobs=[jm],
                ),
            ],
        )
        d0 = m.solution_travel_distance()
        self.assertEqual(m.solution_cost(), float(d0 + 90))
        self.assertTrue(m.is_solution_feasible())


try:
    import ortools  # noqa: F401

    from vrp_model.solvers.ortools import ORToolsSolver
except ModuleNotFoundError:
    ORToolsSolver = None  # type: ignore[misc, assignment]

try:
    import pyvrp  # noqa: F401

    from vrp_model.solvers.pyvrp import PyVRPSolver
except ModuleNotFoundError:
    PyVRPSolver = None  # type: ignore[misc, assignment]


@unittest.skipIf(PyVRPSolver is None, "pyvrp extra not installed")
class TestJobGroupPyVRP(unittest.TestCase):
    def test_mandatory_group_one_of_two(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([10], d)
        a = m.add_job(1, location=(1.0, 0.0))
        b = m.add_job(1, location=(4.0, 0.0))
        m.add_job_group([a, b])
        m.validate()
        PyVRPSolver({"time_limit": 3.0, "msg": False}).solve(m)
        sol = m.solution
        assert sol is not None
        visited = {j.node_id for rt in sol.routes for j in rt.jobs}
        self.assertEqual(len(visited & {a.node_id, b.node_id}), 1)
        self.assertTrue(m.is_solution_feasible())

    def test_mandatory_group_one_of_three(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([10], d)
        a = m.add_job(1, location=(2.0, 0.0))
        b = m.add_job(1, location=(5.0, 0.0))
        c = m.add_job(1, location=(3.0, 4.0))
        m.add_job_group([a, b, c])
        m.validate()
        PyVRPSolver({"time_limit": 3.0, "msg": False}).solve(m)
        sol = m.solution
        assert sol is not None
        group_ids = {a.node_id, b.node_id, c.node_id}
        visited = {j.node_id for rt in sol.routes for j in rt.jobs}
        self.assertEqual(len(visited & group_ids), 1)
        self.assertTrue(m.is_solution_feasible())

    def test_optional_group_at_most_one_member(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([20], d)
        x = m.add_job(1, location=(8.0, 0.0))
        y = m.add_job(1, location=(8.0, 3.0))
        m.add_job_group([x, y], skip_penalty=40)
        m.validate()
        PyVRPSolver({"time_limit": 3.0, "msg": False}).solve(m)
        sol = m.solution
        assert sol is not None
        visits = [j.node_id for rt in sol.routes for j in rt.jobs]
        gx = sum(1 for nid in visits if nid in (x.node_id, y.node_id))
        self.assertLessEqual(gx, 1)
        self.assertTrue(m.is_solution_feasible())

    def test_optional_group_can_skip(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([10], d)
        a = m.add_job(5, location=(100.0, 0.0))
        b = m.add_job(5, location=(100.0, 1.0))
        m.add_job_group([a, b], skip_penalty=50)
        j = m.add_job(1, location=(1.0, 0.0))
        m.validate()
        PyVRPSolver({"time_limit": 3.0, "msg": False}).solve(m)
        sol = m.solution
        assert sol is not None
        visited = {x.node_id for rt in sol.routes for x in rt.jobs}
        self.assertIn(j.node_id, visited)

    def test_mandatory_group_plus_other_mandatory_job(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([15], d)
        req = m.add_job(2, location=(2.0, 0.0))
        alt_a = m.add_job(2, location=(10.0, 0.0))
        alt_b = m.add_job(2, location=(12.0, 0.0))
        m.add_job_group([alt_a, alt_b])
        m.validate()
        PyVRPSolver({"time_limit": 3.0, "msg": False}).solve(m)
        sol = m.solution
        assert sol is not None
        visited = {j.node_id for rt in sol.routes for j in rt.jobs}
        self.assertIn(req.node_id, visited)
        self.assertEqual(len(visited & {alt_a.node_id, alt_b.node_id}), 1)
        self.assertTrue(m.is_solution_feasible())


@unittest.skipIf(ORToolsSolver is None, "ortools extra not installed")
class TestJobGroupORTools(unittest.TestCase):
    def test_mandatory_group_one_of_two(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([10], d)
        a = m.add_job(1, location=(1.0, 0.0))
        b = m.add_job(1, location=(4.0, 0.0))
        m.add_job_group([a, b])
        m.validate()
        ORToolsSolver({"time_limit": 5.0}).solve(m)
        sol = m.solution
        assert sol is not None
        visited = {j.node_id for rt in sol.routes for j in rt.jobs}
        self.assertEqual(len(visited & {a.node_id, b.node_id}), 1)
        self.assertTrue(m.is_solution_feasible())

    def test_mandatory_group_one_of_three(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([10], d)
        a = m.add_job(1, location=(2.0, 0.0))
        b = m.add_job(1, location=(5.0, 0.0))
        c = m.add_job(1, location=(3.0, 4.0))
        m.add_job_group([a, b, c])
        m.validate()
        ORToolsSolver({"time_limit": 5.0}).solve(m)
        sol = m.solution
        assert sol is not None
        group_ids = {a.node_id, b.node_id, c.node_id}
        visited = {j.node_id for rt in sol.routes for j in rt.jobs}
        self.assertEqual(len(visited & group_ids), 1)
        self.assertTrue(m.is_solution_feasible())

    def test_optional_group_at_most_one_member(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([20], d)
        x = m.add_job(1, location=(8.0, 0.0))
        y = m.add_job(1, location=(8.0, 3.0))
        m.add_job_group([x, y], skip_penalty=40)
        m.validate()
        ORToolsSolver({"time_limit": 5.0}).solve(m)
        sol = m.solution
        assert sol is not None
        visits = [j.node_id for rt in sol.routes for j in rt.jobs]
        gx = sum(1 for nid in visits if nid in (x.node_id, y.node_id))
        self.assertLessEqual(gx, 1)
        self.assertTrue(m.is_solution_feasible())

    def test_optional_group_with_cheap_mandatory_job(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([10], d)
        a = m.add_job(5, location=(80.0, 0.0))
        b = m.add_job(5, location=(80.0, 2.0))
        m.add_job_group([a, b], skip_penalty=60)
        j = m.add_job(1, location=(1.0, 0.0))
        m.validate()
        ORToolsSolver({"time_limit": 5.0}).solve(m)
        sol = m.solution
        assert sol is not None
        visited = {x.node_id for rt in sol.routes for x in rt.jobs}
        self.assertIn(j.node_id, visited)

    def test_mandatory_group_plus_other_mandatory_job(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([15], d)
        req = m.add_job(2, location=(2.0, 0.0))
        alt_a = m.add_job(2, location=(10.0, 0.0))
        alt_b = m.add_job(2, location=(12.0, 0.0))
        m.add_job_group([alt_a, alt_b])
        m.validate()
        ORToolsSolver({"time_limit": 5.0}).solve(m)
        sol = m.solution
        assert sol is not None
        visited = {j.node_id for rt in sol.routes for j in rt.jobs}
        self.assertIn(req.node_id, visited)
        self.assertEqual(len(visited & {alt_a.node_id, alt_b.node_id}), 1)
        self.assertTrue(m.is_solution_feasible())


if __name__ == "__main__":
    unittest.main()
