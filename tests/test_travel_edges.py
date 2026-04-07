"""Unit tests for :mod:`vrp_model.core.travel_edges`."""

from __future__ import annotations

import unittest

from vrp_model import TravelEdgeAttrs, ValidationError
from vrp_model.core.travel_edges import TravelEdgesMap, validate_travel_edges


class TestValidateTravelEdges(unittest.TestCase):
    def test_self_loop(self) -> None:
        with self.assertRaises(ValidationError):
            validate_travel_edges(2, {(0, 0): TravelEdgeAttrs(distance=1)})

    def test_unknown_node(self) -> None:
        with self.assertRaises(ValidationError):
            validate_travel_edges(2, {(0, 9): TravelEdgeAttrs(distance=1)})

    def test_requires_distance_or_duration(self) -> None:
        with self.assertRaises(ValidationError):
            validate_travel_edges(2, {(0, 1): TravelEdgeAttrs()})

    def test_rejects_non_attrs_value(self) -> None:
        with self.assertRaises(TypeError):
            validate_travel_edges(2, {(0, 1): {"distance": 1}})  # type: ignore[arg-type]

    def test_valid_edges_pass(self) -> None:
        edges: TravelEdgesMap = {(0, 1): TravelEdgeAttrs(distance=3, duration=None)}
        validate_travel_edges(2, edges)
        self.assertEqual(edges[(0, 1)], TravelEdgeAttrs(distance=3, duration=None))


if __name__ == "__main__":
    unittest.main()
