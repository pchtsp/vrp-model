"""Tests for importing VRPLIB / Solomon instances via PyPI ``vrplib``."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import vrplib

from vrp_model import Feature, Model, Route, Solution, SolutionUnavailableError
from vrp_model.io.vrplib_io import (
    read_model,
    vrplib_dict_to_model,
    write_vrplib_instance,
    write_vrplib_solution,
)

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "vrplib"


class TestVRPLIBIO(unittest.TestCase):
    def test_read_cvrp_en13_k4(self) -> None:
        path = _FIXTURES / "E-n13-k4.vrp"
        raw = vrplib.read_instance(str(path), instance_format="vrplib")

        model = read_model(path, instance_format="vrplib")
        self.assertEqual(len(list(model.depots)), 1)
        self.assertEqual(len(list(model.jobs)), 12)
        self.assertEqual(len(list(model.vehicles)), 4)

        cap = int(raw["capacity"])
        for v in model.vehicles:
            self.assertEqual(v.capacity, [cap])

        dem = np.asarray(raw["demand"], dtype=int)
        self.assertEqual(sum(sum(j.demand) for j in model.jobs), int(dem[1:].sum()))

        n_nodes = len(model._nodes)
        self.assertEqual(len(model._travel_edges), n_nodes * (n_nodes - 1))

        self.assertIn(Feature.CAPACITY, model.features)

    def test_read_solomon_c1_2_1(self) -> None:
        path = _FIXTURES / "C1_2_1.txt"
        raw = vrplib.read_instance(str(path), instance_format="solomon")

        model = read_model(path, instance_format="solomon")
        self.assertEqual(len(list(model.depots)), 1)
        n_locs = int(np.asarray(raw["node_coord"]).shape[0])
        self.assertEqual(len(list(model.jobs)), n_locs - 1)
        self.assertEqual(len(list(model.vehicles)), int(raw["vehicles"]))

        self.assertTrue(any(j.time_window is not None for j in model.jobs))
        self.assertIn(Feature.TIME_WINDOWS, model.features)
        self.assertIn(Feature.CAPACITY, model.features)

        n_nodes = len(model._nodes)
        self.assertEqual(len(model._travel_edges), n_nodes * (n_nodes - 1))
        self.assertTrue(all(a.duration is None for a in model._travel_edges.values()))

    def test_multi_depot_vehicles_depot_mapping(self) -> None:
        # Minimal synthetic dict shaped like vrplib output (0-based depot indices).
        data = {
            "name": "synthetic-mdvrp",
            "demand": np.array([0, 10, 10], dtype=int),
            "depot": np.array([0, 1], dtype=int),
            "vehicles": 2,
            "capacity": 50,
            "node_coord": np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]], dtype=float),
            "vehicles_depot": np.array([0, 1], dtype=int),
            "edge_weight": np.array(
                [
                    [0, 1, 2],
                    [1, 0, 1],
                    [2, 1, 0],
                ],
                dtype=float,
            ),
        }

        model = vrplib_dict_to_model(data)
        self.assertEqual(len(list(model.depots)), 2)
        self.assertEqual(len(list(model.jobs)), 1)

        starts = [v.start_depot.node_id for v in model.vehicles]
        self.assertEqual(starts, [0, 1])

        self.assertIn(Feature.MULTI_DEPOT, model.features)

    def test_write_read_round_trip_file_hub(self) -> None:
        path = _FIXTURES / "E-n13-k4.vrp"
        m1 = read_model(path, instance_format="vrplib")
        m1.validate()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "round.vrp"
            write_vrplib_instance(out, m1)
            m2 = read_model(out, instance_format="vrplib")
        m2.validate()
        self.assertEqual(len(list(m1.depots)), len(list(m2.depots)))
        self.assertEqual(len(list(m1.jobs)), len(list(m2.jobs)))
        self.assertEqual(len(list(m1.vehicles)), len(list(m2.vehicles)))

    def test_write_solution_requires_attached_solution(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([], d)
        m.add_job(0, location=(1.0, 0.0))
        m.validate()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "sol.sol"
            with self.assertRaises(SolutionUnavailableError):
                write_vrplib_solution(out, m)

    def test_write_solution_creates_file(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        v = m.add_vehicle([], d)
        j = m.add_job(0, location=(1.0, 0.0))
        m.validate()
        m._solution = Solution(routes=[Route(vehicle=v, start_depot=d, end_depot=d, jobs=[j])])
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "sol.sol"
            write_vrplib_solution(out, m)
            self.assertTrue(out.is_file())


if __name__ == "__main__":
    unittest.main()
