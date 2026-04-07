"""Tests for ``Model`` and view proxies."""

import unittest

from vrp_model import Depot, Job, Model, NodeKind, ValidationError
from vrp_model.core.records import PickupDeliveryRecord


class TestModelViews(unittest.TestCase):
    def test_add_entities_return_views_and_mutate_storage(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0), label="hub")
        self.assertEqual(d.label, "hub")
        self.assertEqual(d.node_id, 0)
        self.assertEqual(m._nodes[0].kind, NodeKind.DEPOT)
        d.location = (1.0, 2.0)
        self.assertEqual(m._nodes[0].location, (1.0, 2.0))

        v = m.add_vehicle(10, d)
        self.assertEqual(v.capacity, [10])
        self.assertEqual(v.start_depot.node_id, d.node_id)
        self.assertEqual(v.end_depot.node_id, v.start_depot.node_id)
        self.assertEqual(len(list(m.depots)), 1)
        self.assertEqual(len(list(m.vehicles)), 1)
        v.capacity = [5, 5]
        self.assertEqual(m._vehicles[0].capacity, [5, 5])

        j = m.add_job(2, location=(3.0, 4.0))
        self.assertEqual(j.node_id, 1)
        self.assertEqual(len(list(m.jobs)), 1)
        self.assertEqual(j.demand, [2])
        j.service_time = 7
        self.assertEqual(m._nodes[1].service_time, 7)

    def test_pickup_delivery_list(self) -> None:
        m = Model()
        d = m.add_depot()
        m.add_vehicle([], d)
        p1 = m.add_job(1)
        p2 = m.add_job(1)
        m.add_pickup_delivery(p1, p2)
        self.assertEqual(
            m._pickup_deliveries,
            [PickupDeliveryRecord(pickup_job_node_id=1, delivery_job_node_id=2)],
        )

    def test_depot_from_other_model_rejected(self) -> None:
        m1 = Model()
        m2 = Model()
        d1 = m1.add_depot()
        with self.assertRaises(ValidationError):
            m2.add_vehicle(1, d1)

    def test_interleaved_nodes_unique_ids(self) -> None:
        m = Model()
        d0 = m.add_depot(label="d0")
        j0 = m.add_job(0, label="j0")
        d1 = m.add_depot(label="d1")
        self.assertEqual(d0.node_id, 0)
        self.assertEqual(j0.node_id, 1)
        self.assertEqual(d1.node_id, 2)
        self.assertEqual([d.label for d in m.depots], ["d0", "d1"])
        self.assertEqual([j.label for j in m.jobs], ["j0"])

    def test_job_view_rejects_depot_node_id(self) -> None:
        m = Model()
        m.add_depot()
        with self.assertRaises(ValidationError):
            Job(m, 0)

    def test_depot_view_rejects_job_node_id(self) -> None:
        m = Model()
        m.add_depot()
        m.add_job(0)
        with self.assertRaises(ValidationError):
            Depot(m, 1)


if __name__ == "__main__":
    unittest.main()
