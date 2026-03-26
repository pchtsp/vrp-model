"""Tests for time helpers."""

import unittest

from vrp_model.utils.time import tw_duration


class TestTwDuration(unittest.TestCase):
    def test_sum(self) -> None:
        self.assertEqual(tw_duration(10, 5), 15)


if __name__ == "__main__":
    unittest.main()
