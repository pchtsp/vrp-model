"""Tests for ``vrp_model.core.storage``."""

import unittest

from vrp_model.core.storage import normalize_load, skills_to_frozen


class TestNormalizeLoad(unittest.TestCase):
    def test_int_becomes_single_dimension(self) -> None:
        self.assertEqual(normalize_load(3), [3])
        self.assertEqual(normalize_load(0), [0])

    def test_list_passthrough(self) -> None:
        self.assertEqual(normalize_load([1, 2, 3]), [1, 2, 3])

    def test_empty_list(self) -> None:
        self.assertEqual(normalize_load([]), [])


class TestSkills(unittest.TestCase):
    def test_frozenset_from_set(self) -> None:
        self.assertEqual(skills_to_frozen({"a", "b"}), frozenset({"a", "b"}))


if __name__ == "__main__":
    unittest.main()
