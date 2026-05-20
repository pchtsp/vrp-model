"""Tests for standard solver option merging."""

import unittest

from vrp_model.core.travel_edges import TRAVEL_COST_INF
from vrp_model import Model, TravelEdgeAttrs
from vrp_model.solvers._helpers import is_model_travel_inf, should_add_explicit_edge, solver_travel_int
from vrp_model.solvers.options import (
    GAP_ABS,
    GAP_REL,
    LOG_PATH,
    MAX_ITERATIONS,
    MISSING_ARC_DISTANCE,
    MISSING_ARC_DURATION,
    MSG,
    OMIT_UNREACHABLE_ARCS,
    SEED,
    TIME_LIMIT,
    default_solver_options,
    merge_solver_options,
)


class TestSolverOptions(unittest.TestCase):
    def test_default_has_all_standard_keys(self) -> None:
        d = default_solver_options()
        self.assertIn(TIME_LIMIT, d)
        self.assertIn(SEED, d)
        self.assertIn(MAX_ITERATIONS, d)
        self.assertIn(GAP_REL, d)
        self.assertIn(GAP_ABS, d)
        self.assertIn(MSG, d)
        self.assertIn(LOG_PATH, d)
        self.assertIn(MISSING_ARC_DISTANCE, d)
        self.assertIn(MISSING_ARC_DURATION, d)
        self.assertIn(OMIT_UNREACHABLE_ARCS, d)
        self.assertIsNone(d[MISSING_ARC_DISTANCE])
        self.assertIsNone(d[MISSING_ARC_DURATION])
        self.assertFalse(d[OMIT_UNREACHABLE_ARCS])

    def test_merge_omit_unreachable_arcs(self) -> None:
        out = merge_solver_options({OMIT_UNREACHABLE_ARCS: True})
        self.assertTrue(out[OMIT_UNREACHABLE_ARCS])

    def test_should_add_explicit_edge(self) -> None:
        m = Model()
        d = m.add_depot()
        m.add_vehicle([], d)
        j = m.add_job(0, location=(1.0, 0.0))
        m.update_travel_edge(d, j, distance=5)
        m.validate()
        self.assertTrue(should_add_explicit_edge(m, 0, j.node_id, omit_unreachable=False))
        self.assertFalse(should_add_explicit_edge(m, 0, j.node_id, omit_unreachable=True))
        m.update_travel_edge(d, j, duration=10)
        m.validate()
        self.assertTrue(should_add_explicit_edge(m, 0, j.node_id, omit_unreachable=True))

    def test_merge_missing_arc_overrides(self) -> None:
        out = merge_solver_options({MISSING_ARC_DISTANCE: 9_999, MISSING_ARC_DURATION: 8_888})
        self.assertEqual(out[MISSING_ARC_DISTANCE], 9_999)
        self.assertEqual(out[MISSING_ARC_DURATION], 8_888)

    def test_solver_travel_int_override(self) -> None:
        self.assertTrue(is_model_travel_inf(TRAVEL_COST_INF))
        self.assertEqual(
            solver_travel_int(TRAVEL_COST_INF, override=100, backend_default=999),
            100,
        )
        self.assertEqual(
            solver_travel_int(TRAVEL_COST_INF, override=None, backend_default=999),
            999,
        )
        self.assertEqual(solver_travel_int(12, override=100, backend_default=999), 12)

    def test_merge_overrides_and_preserves_extra(self) -> None:
        base = merge_solver_options(None, {TIME_LIMIT: 10.0, MSG: True, LOG_PATH: "/tmp/x.log"})
        self.assertEqual(base[TIME_LIMIT], 10.0)
        self.assertEqual(base[MSG], True)
        self.assertEqual(base[LOG_PATH], "/tmp/x.log")
        self.assertEqual(base[SEED], 0)

    def test_later_layer_wins(self) -> None:
        out = merge_solver_options({SEED: 1}, {SEED: 42})
        self.assertEqual(out[SEED], 42)


if __name__ == "__main__":
    unittest.main()
