"""Tests for validation layers."""

import unittest

from vrp_model import Model, TravelEdgeAttrs, ValidationError


class TestStructure(unittest.TestCase):
    def test_requires_depot_and_vehicle(self) -> None:
        m = Model()
        with self.assertRaises(ValidationError):
            m.validate()
        d = m.add_depot()
        with self.assertRaises(ValidationError):
            m.validate()
        m.add_vehicle([], d)
        m.validate()


class TestConsistency(unittest.TestCase):
    def test_duplicate_labels_allowed(self) -> None:
        m = Model()
        d = m.add_depot(label="x")
        m.add_vehicle([], d, label="same")
        m.add_vehicle([], d, label="same")
        m.add_job(0, label="same", location=(0.0, 0.0))
        m.add_job(0, label="same", location=(1.0, 0.0))
        m.validate()

    def test_vehicle_bad_depot_index_corrupt(self) -> None:
        m = Model()
        d = m.add_depot()
        m.add_vehicle([], d)
        m._vehicles[0].start_depot_node_id = 99
        with self.assertRaises(ValidationError):
            m.validate()

    def test_pickup_delivery_overlap(self) -> None:
        m = Model()
        d = m.add_depot()
        m.add_vehicle([], d)
        a = m.add_job(0, location=(0.0, 0.0))
        b = m.add_job(0, location=(1.0, 0.0))
        m.add_pickup_delivery(a, b)
        m.add_pickup_delivery(b, a)
        with self.assertRaises(ValidationError):
            m.validate()


class TestTravelEdges(unittest.TestCase):
    def test_empty_travel_requires_job_locations(self) -> None:
        m = Model()
        d = m.add_depot()
        m.add_vehicle([], d)
        m.add_job(0)
        with self.assertRaises(ValidationError) as ctx:
            m.validate()
        self.assertIn("no location", str(ctx.exception))

    def test_travel_edge_invalid_node_id(self) -> None:
        m = Model()
        d = m.add_depot()
        m.add_vehicle([], d)
        m.add_job(0, location=(0.0, 0.0))
        m._travel_edges = {(0, 99): TravelEdgeAttrs(distance=1)}
        with self.assertRaises(ValidationError):
            m.validate()

    def test_self_loop_rejected(self) -> None:
        m = Model()
        d = m.add_depot()
        m.add_vehicle([], d)
        m.set_travel_edges({(0, 0): TravelEdgeAttrs(distance=1)})
        with self.assertRaises(ValidationError):
            m.validate()

    def test_sparse_only_distance_ok(self) -> None:
        m = Model()
        d = m.add_depot()
        m.add_vehicle([], d)
        j = m.add_job(0, location=(0.0, 0.0))
        m.update_travel_edge(d, j, distance=5)
        m.validate()
        self.assertEqual(m._travel_edges[(0, j.node_id)], TravelEdgeAttrs(distance=5))

    def test_partial_override_then_validate_after_new_node(self) -> None:
        m = Model()
        d = m.add_depot()
        m.add_vehicle([], d)
        j = m.add_job(0, location=(0.0, 0.0))
        m.update_travel_edge(d, j, duration=10)
        m.validate()
        m.add_job(0, location=(1.0, 0.0))
        m.validate()

    def test_set_travel_edges_rejects_negative(self) -> None:
        m = Model()
        d = m.add_depot()
        m.add_vehicle([], d)
        m.add_job(0, location=(0.0, 0.0))
        m.set_travel_edges({(0, 1): TravelEdgeAttrs(distance=-1)})
        with self.assertRaises(ValidationError):
            m.validate()

    def test_clear_travel_edges(self) -> None:
        m = Model()
        d = m.add_depot()
        m.add_vehicle([], d)
        m.add_job(0, location=(0.0, 0.0))
        m.update_travel_edge(d, next(iter(m.jobs)), distance=1)
        m.clear_travel_edges()
        self.assertEqual(m._travel_edges, {})
        m.validate()

    def test_update_travel_edge_requires_metric(self) -> None:
        m = Model()
        d = m.add_depot()
        m.add_vehicle([], d)
        j = m.add_job(0, location=(0.0, 0.0))
        m.update_travel_edge(d, j)
        with self.assertRaises(ValidationError):
            m.validate()

    def test_set_travel_edges_rejects_plain_dict_value(self) -> None:
        m = Model()
        d = m.add_depot()
        m.add_vehicle([], d)
        m.add_job(0, location=(0.0, 0.0))
        bad: dict[str, int] = {"distance": 1}
        bad["detour"] = 2
        m.set_travel_edges({(0, 1): bad})  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            m.validate()


class TestFeasibility(unittest.TestCase):
    def test_demand_exceeds_capacity(self) -> None:
        m = Model()
        d = m.add_depot()
        m.add_vehicle([5], d)
        m.add_job(10, location=(0.0, 0.0))
        with self.assertRaises(ValidationError):
            m.validate()

    def test_impossible_time_window(self) -> None:
        m = Model()
        d = m.add_depot()
        m.add_vehicle([], d)
        m.add_job(0, time_window=(5, 1), location=(0.0, 0.0))
        with self.assertRaises(ValidationError):
            m.validate()

    def test_skills_no_covering_vehicle(self) -> None:
        m = Model()
        d = m.add_depot()
        m.add_vehicle([], d, skills={"x"})
        m.add_job(0, skills_required={"y"}, location=(0.0, 0.0))
        with self.assertRaises(ValidationError):
            m.validate()


if __name__ == "__main__":
    unittest.main()
