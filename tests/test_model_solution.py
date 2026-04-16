"""Tests for solution-dependent :class:`~vrp_model.core.model.Model` APIs."""

from __future__ import annotations

import unittest

from vrp_model import Model, Route, Solution, SolutionUnavailableError, TravelEdgeAttrs


class TestModelSolutionAPIs(unittest.TestCase):
    def test_solution_unavailable_without_attachment(self) -> None:
        m = Model()
        d = m.add_depot()
        m.add_vehicle([], d)
        m.add_job(1, location=(0.0, 0.0))
        for call in (
            lambda: m.solution_cost(),
            lambda: m.solution_travel_distance(),
            lambda: m.is_solution_feasible(),
            lambda: m.unassigned_jobs(),
            lambda: m.mandatory_unassigned_jobs(),
        ):
            with self.subTest(call=call):
                with self.assertRaises(SolutionUnavailableError):
                    call()

    def test_unassigned_jobs_empty_when_all_on_route(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        v = m.add_vehicle([10], d)
        j = m.add_job(1, location=(1.0, 0.0))
        m._solution = Solution(routes=[Route(vehicle=v, start_depot=d, end_depot=d, jobs=[j])])
        self.assertEqual(m.unassigned_jobs(), [])

    def test_solution_cost_sparse_matches_manual_sum(self) -> None:
        m = Model()
        d = m.add_depot()
        v = m.add_vehicle([], d)
        j = m.add_job(0, location=(0.0, 0.0))
        m.set_travel_edges(
            {
                (0, j.node_id): TravelEdgeAttrs(distance=5),
                (j.node_id, 0): TravelEdgeAttrs(distance=7),
            },
        )
        m.validate()
        m._solution = Solution(routes=[Route(vehicle=v, start_depot=d, end_depot=d, jobs=[j])])
        self.assertEqual(m.solution_travel_distance(), 12.0)
        self.assertEqual(m.solution_cost(), 12.0)

    def test_solution_cost_includes_fixed_vehicle_use(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        v = m.add_vehicle([10], d, fixed_use_cost=100)
        j = m.add_job(0, location=(1.0, 0.0))
        m._solution = Solution(routes=[Route(vehicle=v, start_depot=d, end_depot=d, jobs=[j])])
        self.assertEqual(m.solution_travel_distance(), 2.0)
        self.assertEqual(m.solution_cost(), 102.0)

    def test_is_solution_feasible_false_on_capacity(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        v = m.add_vehicle([1], d)
        j = m.add_job(99, location=(1.0, 0.0))
        m._solution = Solution(routes=[Route(vehicle=v, start_depot=d, end_depot=d, jobs=[j])])
        self.assertFalse(m.is_solution_feasible())


if __name__ == "__main__":
    unittest.main()
