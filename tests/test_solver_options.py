"""Tests for standard solver option merging."""

import unittest

from vrp_model.solvers.options import (
    GAP_ABS,
    GAP_REL,
    LOG_PATH,
    MAX_ITERATIONS,
    MSG,
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
