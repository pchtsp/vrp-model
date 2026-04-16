"""Verify documented toy optima without running external solvers."""

from __future__ import annotations

import unittest

from tests.toy_instances import (
    TOY_CASES,
    brute_force_optimal_travel_single_vehicle,
    build_asymmetric_matrix_two_jobs,
    build_tiny_line_two_jobs,
)
from vrp_model import Route, Solution


class TestToyInstancesVerify(unittest.TestCase):
    def test_tiny_line_travel_matches_brute_force(self) -> None:
        m = build_tiny_line_two_jobs()
        self.assertEqual(brute_force_optimal_travel_single_vehicle(m), 4)

    def test_asymmetric_matrix_travel_matches_brute_force(self) -> None:
        m = build_asymmetric_matrix_two_jobs()
        self.assertEqual(brute_force_optimal_travel_single_vehicle(m), 52)

    def test_all_toys_validate(self) -> None:
        for toy in TOY_CASES:
            with self.subTest(toy=toy.name):
                m = toy.build()
                m.validate()

    def test_documented_travel_matches_brute_where_applicable(self) -> None:
        for toy in TOY_CASES:
            if toy.documented_optimal_travel is None:
                continue
            m = toy.build()
            bf = brute_force_optimal_travel_single_vehicle(m)
            if bf is not None:
                with self.subTest(toy=toy.name):
                    self.assertEqual(bf, toy.documented_optimal_travel)

    def test_prize_toy_golden_objective(self) -> None:
        from tests.toy_instances import build_prize_collecting

        m = build_prize_collecting()
        d = next(iter(m.depots))
        v = next(iter(m.vehicles))
        mandatory = next(j for j in m.jobs if j.label == "mandatory")
        route = Route(vehicle=v, start_depot=d, end_depot=d, jobs=[mandatory])
        m._solution = Solution(routes=[route])
        self.assertTrue(m.is_solution_feasible())
        self.assertEqual(m.solution_travel_distance(), 2.0)
        self.assertEqual(m.solution_cost(), 10002.0)


if __name__ == "__main__":
    unittest.main()
