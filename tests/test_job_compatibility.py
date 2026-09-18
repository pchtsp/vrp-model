"""Job compatibility (incompatible job types cannot share a route)."""

from __future__ import annotations

import unittest

from tests._limits import ORTOOLS_TIME_LIMIT
from vrp_model import Feature, Model, ValidationError
from vrp_model.core.solution import Route, Solution

try:
    import ortools  # noqa: F401

    from vrp_model.solvers.ortools import ORToolsSolver

    _ORTOOLS_INSTALLED = True
except ModuleNotFoundError:
    _ORTOOLS_INSTALLED = False


def _two_typed_jobs(
    *,
    vehicles: int = 2,
    prize: float | None = None,
) -> tuple[Model, list, list]:
    m = Model()
    d = m.add_depot(location=(0.0, 0.0))
    vs = [m.add_vehicle([10], d) for _ in range(vehicles)]
    a = m.add_job(1, location=(1.0, 0.0), job_type=0, prize=prize)
    b = m.add_job(1, location=(2.0, 0.0), job_type=1, prize=prize)
    return m, vs, [a, b]


class TestJobCompatibilityValidation(unittest.TestCase):
    def test_self_pair_rejected(self) -> None:
        m, _, _ = _two_typed_jobs()
        m.add_job_type_incompatibility(0, 0)
        with self.assertRaisesRegex(ValidationError, "two distinct types"):
            m.validate()

    def test_negative_pair_type_rejected(self) -> None:
        m, _, _ = _two_typed_jobs()
        m.add_job_type_incompatibility(-1, 0)
        with self.assertRaisesRegex(ValidationError, "negative type"):
            m.validate()

    def test_negative_job_type_rejected(self) -> None:
        m, _, (a, _) = _two_typed_jobs()
        a.job_type = -3
        with self.assertRaisesRegex(ValidationError, "job_type must be non-negative"):
            m.validate()

    def test_incompatible_pickup_delivery_rejected(self) -> None:
        m, _, (a, b) = _two_typed_jobs()
        m.add_pickup_delivery(a, b)
        m.add_job_type_incompatibility(1, 0)
        with self.assertRaisesRegex(ValidationError, "incompatible job types"):
            m.validate()

    def test_feature_detected_only_with_pair(self) -> None:
        m, _, _ = _two_typed_jobs()
        self.assertNotIn(Feature.JOB_COMPATIBILITY, m.detect_features())
        m.add_job_type_incompatibility(0, 1)
        self.assertIn(Feature.JOB_COMPATIBILITY, m.detect_features())
        self.assertEqual(m.job_type_incompatibilities, [(0, 1)])


class TestJobCompatibilityFeasibility(unittest.TestCase):
    def _route(self, m: Model, vehicle, jobs: list) -> Route:
        d = next(m.depots)
        return Route(vehicle=vehicle, start_depot=d, end_depot=d, jobs=jobs)

    def test_incompatible_types_on_one_route_infeasible(self) -> None:
        m, (v0, v1), (a, b) = _two_typed_jobs()
        m.add_job_type_incompatibility(0, 1)
        m.validate()
        m._solution = Solution(routes=[self._route(m, v0, [a, b]), self._route(m, v1, [])])
        self.assertFalse(m.is_solution_feasible())
        m._solution = Solution(routes=[self._route(m, v0, [a]), self._route(m, v1, [b])])
        self.assertTrue(m.is_solution_feasible())

    def test_same_or_missing_type_may_share_route(self) -> None:
        m, (v0,), (a, b) = _two_typed_jobs(vehicles=1)
        c = m.add_job(1, location=(3.0, 0.0))
        b.job_type = 0
        m.add_job_type_incompatibility(0, 1)
        m.validate()
        m._solution = Solution(routes=[self._route(m, v0, [a, b, c])])
        self.assertTrue(m.is_solution_feasible())


@unittest.skipIf(not _ORTOOLS_INSTALLED, "ortools extra not installed")
class TestJobCompatibilityORTools(unittest.TestCase):
    def _solve(self, m: Model) -> list[set[int]]:
        ORToolsSolver({"time_limit": ORTOOLS_TIME_LIMIT}).solve(m)
        sol = m.solution
        assert sol is not None
        return [{j.node_id for j in rt.jobs} for rt in sol.routes if rt.jobs]

    def test_without_pair_jobs_share_route(self) -> None:
        m, _, _ = _two_typed_jobs()
        self.assertEqual(len(self._solve(m)), 1)

    def test_incompatible_jobs_split_routes(self) -> None:
        m, _, (a, b) = _two_typed_jobs()
        m.add_job_type_incompatibility(0, 1)
        routes = self._solve(m)
        self.assertEqual(sorted(routes, key=min), [{a.node_id}, {b.node_id}])
        self.assertTrue(m.is_solution_feasible())

    def test_single_vehicle_optional_jobs_serves_one(self) -> None:
        m, _, (a, b) = _two_typed_jobs(vehicles=1, prize=1000.0)
        m.add_job_type_incompatibility(0, 1)
        routes = self._solve(m)
        visited = set().union(*routes)
        self.assertEqual(len(visited & {a.node_id, b.node_id}), 1)
        self.assertTrue(m.is_solution_feasible())


if __name__ == "__main__":
    unittest.main()
