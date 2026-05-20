"""Tests that solver options override unreachable-arc costs in backend matrices."""

from __future__ import annotations

import unittest
from typing import Any

from vrp_model import MISSING_ARC_DISTANCE, MISSING_ARC_DURATION, Model, TravelEdgeAttrs
from vrp_model.core.travel_edges import TRAVEL_COST_INF
from vrp_model.solvers.nextroute.solver import (
    _MATRIX_INF,
    NextrouteSolver,
    _leg_meters,
    _leg_seconds,
)
from vrp_model.solvers.ortools.solver import (
    ORTOOLS_TRANSIT_CAP,
    ORToolsSolver,
    _build_distance_matrix,
    _build_duration_leg_matrix,
)
from vrp_model.solvers.pyvrp.solver import PyVRPSolver, _add_resolved_edges, _pyvrp_missing_value

try:
    import numpy  # noqa: F401

    from vrp_model.solvers.vroom.bindings import VROOM_UINT32_MAX
    from vrp_model.solvers.vroom.solver import (
        VroomSolver,
    )
    from vrp_model.solvers.vroom.solver import (
        _build_distance_matrix as vroom_build_distance_matrix,
    )
    from vrp_model.solvers.vroom.solver import (
        _build_duration_matrix as vroom_build_duration_matrix,
    )

    _VROOM_AVAILABLE = True
except ModuleNotFoundError:
    VroomSolver = None  # type: ignore[misc, assignment]
    VROOM_UINT32_MAX = 0
    _VROOM_AVAILABLE = False

_CUSTOM_DISTANCE = 4_242_424
_CUSTOM_DURATION = 5_252_525
_FORBIDDEN_FROM = 0
_FORBIDDEN_TO = 2


def _sparse_model_missing_arc() -> Model:
    """Depot + two jobs; only 0→1 and 1→2 arcs — (0, 2) is unreachable in the model."""
    m = Model()
    d = m.add_depot(location=(0.0, 0.0))
    m.add_vehicle([10], d)
    m.add_job(1, location=(1.0, 0.0))
    m.add_job(1, location=(2.0, 0.0))
    m.set_travel_edges(
        {
            (0, 1): TravelEdgeAttrs(distance=10, duration=100),
            (1, 2): TravelEdgeAttrs(distance=10, duration=100),
        },
    )
    m.validate()
    return m


class _EdgeCapture:
    """Record PyVRP ``add_edge`` distance/duration for selected node index pairs."""

    def __init__(self) -> None:
        self.by_pair: dict[tuple[int, int], tuple[int, int]] = {}
        self._nodes: list[object] = []

    def register_nodes(self, n: int) -> list[object]:
        self._nodes = [object() for _ in range(n)]
        return self._nodes

    def add_edge(
        self,
        frm: object,
        to: object,
        distance: int,
        duration: int = 0,
        *_args: object,
        **_kwargs: object,
    ) -> None:
        i = self._nodes.index(frm)
        j = self._nodes.index(to)
        self.by_pair[(i, j)] = (int(distance), int(duration))


class TestMissingArcOptions(unittest.TestCase):
    def setUp(self) -> None:
        self.model = _sparse_model_missing_arc()
        self.assertGreaterEqual(
            self.model._directed_travel_distance(_FORBIDDEN_FROM, _FORBIDDEN_TO),
            TRAVEL_COST_INF,
        )
        self.assertGreaterEqual(
            self.model._directed_travel_duration(_FORBIDDEN_FROM, _FORBIDDEN_TO),
            TRAVEL_COST_INF,
        )

    def test_ortools_distance_from_options_only(self) -> None:
        solver = ORToolsSolver({MISSING_ARC_DISTANCE: _CUSTOM_DISTANCE})
        opts: dict[str, Any] = dict(solver._options)
        mat = _build_distance_matrix(
            self.model,
            missing_arc_distance=opts[MISSING_ARC_DISTANCE],
        )
        self.assertEqual(mat[_FORBIDDEN_FROM][_FORBIDDEN_TO], _CUSTOM_DISTANCE)
        mat_default = _build_distance_matrix(self.model, missing_arc_distance=None)
        self.assertEqual(mat_default[_FORBIDDEN_FROM][_FORBIDDEN_TO], ORTOOLS_TRANSIT_CAP)

    def test_ortools_duration_from_options_only(self) -> None:
        solver = ORToolsSolver({MISSING_ARC_DURATION: _CUSTOM_DURATION})
        opts: dict[str, Any] = dict(solver._options)
        mat = _build_duration_leg_matrix(
            self.model,
            missing_arc_duration=opts[MISSING_ARC_DURATION],
        )
        self.assertEqual(mat[_FORBIDDEN_FROM][_FORBIDDEN_TO], _CUSTOM_DURATION)
        mat_default = _build_duration_leg_matrix(self.model, missing_arc_duration=None)
        self.assertEqual(mat_default[_FORBIDDEN_FROM][_FORBIDDEN_TO], ORTOOLS_TRANSIT_CAP)

    @unittest.skipUnless(_VROOM_AVAILABLE, "vroom extra not installed")
    def test_vroom_distance_from_options_only(self) -> None:
        solver = VroomSolver({MISSING_ARC_DISTANCE: _CUSTOM_DISTANCE})
        opts: dict[str, Any] = dict(solver._options)
        mat = vroom_build_distance_matrix(
            self.model,
            missing_arc_distance=opts[MISSING_ARC_DISTANCE],
        )
        self.assertEqual(int(mat[_FORBIDDEN_FROM, _FORBIDDEN_TO]), _CUSTOM_DISTANCE)
        mat_default = vroom_build_distance_matrix(self.model, missing_arc_distance=None)
        self.assertEqual(int(mat_default[_FORBIDDEN_FROM, _FORBIDDEN_TO]), VROOM_UINT32_MAX)

    @unittest.skipUnless(_VROOM_AVAILABLE, "vroom extra not installed")
    def test_vroom_duration_from_options_only(self) -> None:
        solver = VroomSolver({MISSING_ARC_DURATION: _CUSTOM_DURATION})
        opts: dict[str, Any] = dict(solver._options)
        mat = vroom_build_duration_matrix(
            self.model,
            missing_arc_duration=opts[MISSING_ARC_DURATION],
        )
        self.assertEqual(int(mat[_FORBIDDEN_FROM, _FORBIDDEN_TO]), _CUSTOM_DURATION)
        mat_default = vroom_build_duration_matrix(self.model, missing_arc_duration=None)
        self.assertEqual(int(mat_default[_FORBIDDEN_FROM, _FORBIDDEN_TO]), VROOM_UINT32_MAX)

    def test_nextroute_distance_from_options_only(self) -> None:
        solver = NextrouteSolver({MISSING_ARC_DISTANCE: _CUSTOM_DISTANCE})
        opts: dict[str, Any] = dict(solver._options)
        val = _leg_meters(
            self.model,
            _FORBIDDEN_FROM,
            _FORBIDDEN_TO,
            missing_arc_distance=opts[MISSING_ARC_DISTANCE],
        )
        self.assertEqual(val, float(_CUSTOM_DISTANCE))
        default = _leg_meters(
            self.model,
            _FORBIDDEN_FROM,
            _FORBIDDEN_TO,
            missing_arc_distance=None,
        )
        self.assertEqual(default, _MATRIX_INF)

    def test_nextroute_duration_from_options_only(self) -> None:
        solver = NextrouteSolver({MISSING_ARC_DURATION: _CUSTOM_DURATION})
        opts: dict[str, Any] = dict(solver._options)
        val = _leg_seconds(
            self.model,
            _FORBIDDEN_FROM,
            _FORBIDDEN_TO,
            missing_arc_duration=opts[MISSING_ARC_DURATION],
        )
        self.assertEqual(val, float(_CUSTOM_DURATION))
        default = _leg_seconds(
            self.model,
            _FORBIDDEN_FROM,
            _FORBIDDEN_TO,
            missing_arc_duration=None,
        )
        self.assertEqual(default, _MATRIX_INF)

    def test_pyvrp_edges_from_options_only(self) -> None:
        solver = PyVRPSolver(
            {
                MISSING_ARC_DISTANCE: _CUSTOM_DISTANCE,
                MISSING_ARC_DURATION: _CUSTOM_DURATION,
            },
        )
        opts: dict[str, Any] = dict(solver._options)
        missing_d = int(opts[MISSING_ARC_DISTANCE] or TRAVEL_COST_INF)
        missing_t = int(opts[MISSING_ARC_DURATION] or TRAVEL_COST_INF)
        capture = _EdgeCapture()
        nodes = capture.register_nodes(3)
        _add_resolved_edges(
            capture,
            self.model,
            nodes,
            self.model._travel_edges,
            3,
            use_euclidean=False,
            missing_distance=missing_d,
            missing_duration=missing_t,
            omit_unreachable=False,
        )
        d, t = capture.by_pair[(_FORBIDDEN_FROM, _FORBIDDEN_TO)]
        self.assertEqual(d, _CUSTOM_DISTANCE)
        self.assertEqual(t, _CUSTOM_DURATION)
        capture_default = _EdgeCapture()
        nodes_def = capture_default.register_nodes(3)
        _add_resolved_edges(
            capture_default,
            self.model,
            nodes_def,
            self.model._travel_edges,
            3,
            use_euclidean=False,
            missing_distance=TRAVEL_COST_INF,
            missing_duration=TRAVEL_COST_INF,
            omit_unreachable=False,
        )
        d_def, t_def = capture_default.by_pair[(_FORBIDDEN_FROM, _FORBIDDEN_TO)]
        self.assertEqual(d_def, TRAVEL_COST_INF)
        self.assertEqual(t_def, TRAVEL_COST_INF)

    def test_pyvrp_omit_unreachable_skips_forbidden_pair(self) -> None:
        capture = _EdgeCapture()
        nodes = capture.register_nodes(3)
        _add_resolved_edges(
            capture,
            self.model,
            nodes,
            self.model._travel_edges,
            3,
            use_euclidean=False,
            missing_distance=TRAVEL_COST_INF,
            missing_duration=TRAVEL_COST_INF,
            omit_unreachable=True,
        )
        self.assertNotIn((_FORBIDDEN_FROM, _FORBIDDEN_TO), capture.by_pair)
        self.assertIn((0, 1), capture.by_pair)
        self.assertIn((1, 2), capture.by_pair)

    def test_pyvrp_missing_value_prefers_distance_override(self) -> None:
        opts: dict[str, object] = {
            MISSING_ARC_DISTANCE: _CUSTOM_DISTANCE,
            MISSING_ARC_DURATION: _CUSTOM_DURATION,
        }
        self.assertEqual(_pyvrp_missing_value(opts), _CUSTOM_DISTANCE)


if __name__ == "__main__":
    unittest.main()
