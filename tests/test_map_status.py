"""Tests for ``Model.map_status``."""

import unittest

from vrp_model import Model, SolveStatus


class TestMapStatus(unittest.TestCase):
    def test_known_status_passthrough(self) -> None:
        m = Model()
        self.assertEqual(m.map_status(SolveStatus.FEASIBLE), SolveStatus.FEASIBLE)

    def test_unknown_for_arbitrary_object(self) -> None:
        m = Model()
        self.assertEqual(m.map_status("weird"), SolveStatus.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
