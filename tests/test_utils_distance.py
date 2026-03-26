"""Tests for distance utilities."""

import unittest

from vrp_model.utils.distance import euclidean_int


class TestEuclideanInt(unittest.TestCase):
    def test_axis_aligned(self) -> None:
        self.assertEqual(euclidean_int((0.0, 0.0), (3.0, 4.0)), 5)

    def test_rounding(self) -> None:
        self.assertEqual(euclidean_int((0.0, 0.0), (1.0, 1.0)), 1)


if __name__ == "__main__":
    unittest.main()
