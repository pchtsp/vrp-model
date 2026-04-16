"""Run shared toy instances against each installed solver (feature-gated)."""

from __future__ import annotations

import unittest

from tests.toy_instances import TOY_CASES, ToyCase
from vrp_model import Model
from vrp_model.solvers.base import Solver

try:
    import ortools  # noqa: F401

    from vrp_model.solvers.ortools import ORToolsSolver
except ModuleNotFoundError:
    ORToolsSolver = None  # type: ignore[misc, assignment]

try:
    import pyvrp  # noqa: F401

    from vrp_model.solvers.pyvrp import PyVRPSolver
except ModuleNotFoundError:
    PyVRPSolver = None  # type: ignore[misc, assignment]

try:
    import numpy as np
    import vroom  # noqa: F401

    from vrp_model.solvers.vroom import VroomSolver
except ModuleNotFoundError:
    VroomSolver = None  # type: ignore[misc, assignment]
    _VROOM_MATRIX_OK = False
else:

    def _vroom_matrix_probe() -> bool:
        try:
            inp = vroom.Input()
            m = np.ascontiguousarray([[0, 1], [1, 0]], dtype=np.uint32)
            inp.set_durations_matrix("car", m)
        except RuntimeError:
            return False
        return True

    _VROOM_MATRIX_OK = _vroom_matrix_probe()

try:
    import nextroute  # noqa: F401

    from vrp_model.solvers.nextroute import NextrouteSolver
except ModuleNotFoundError:
    NextrouteSolver = None  # type: ignore[misc, assignment]


def _solver_factories() -> list[tuple[str, type[Solver], dict]]:
    out: list[tuple[str, type[Solver], dict]] = []
    if ORToolsSolver is not None:
        out.append(("ortools", ORToolsSolver, {"time_limit": 15.0}))
    if PyVRPSolver is not None:
        out.append(("pyvrp", PyVRPSolver, {"time_limit": 5.0, "msg": False}))
    if VroomSolver is not None and _VROOM_MATRIX_OK:
        out.append(("vroom", VroomSolver, {"time_limit": 10.0}))
    if NextrouteSolver is not None:
        out.append(("nextroute", NextrouteSolver, {"time_limit": 15.0}))
    return out


def _assert_cost(toy: ToyCase, m: Model, tc: unittest.TestCase) -> None:
    if toy.cost_assertion == "none":
        return
    cost = m.solution_cost()
    if toy.cost_assertion == "exact":
        target = toy.documented_optimal_objective
        if target is None:
            target = float(toy.documented_optimal_travel or 0.0)
        tc.assertIsNotNone(target)
        tc.assertAlmostEqual(cost, float(target), places=4, msg=f"{toy.name} cost={cost}")
    elif toy.cost_assertion == "bounded":
        target = toy.documented_optimal_objective
        if target is None:
            target = float(toy.documented_optimal_travel or 0.0)
        tc.assertIsNotNone(target)
        tc.assertLessEqual(
            cost,
            float(target) + toy.cost_tolerance + 1e-6,
            msg=f"{toy.name} cost={cost} target={target}",
        )


def _structural(toy: ToyCase, m: Model, tc: unittest.TestCase) -> None:
    sol = m.solution
    assert sol is not None
    if toy.name == "vehicle_fixed_cost":
        for r in sol.routes:
            if r.jobs:
                tc.assertEqual(r.vehicle.label, "cheap_fixed")
    elif toy.name == "skills":
        for r in sol.routes:
            for j in r.jobs:
                if j.label == "needs_1":
                    tc.assertTrue(j.skills_required <= frozenset(r.vehicle.skills))
    elif toy.name == "multi_depot":
        for r in sol.routes:
            if not r.jobs:
                continue
            tc.assertEqual(r.end_depot.node_id, r.vehicle.end_depot.node_id)
    elif toy.name == "heterogeneous_fleet":
        for r in sol.routes:
            for j in r.jobs:
                if j.label == "heavy":
                    tc.assertGreaterEqual(r.vehicle.capacity[0], 5)
    elif toy.name == "prize_collecting":
        # Canonical optimum skips optional (see tests.test_toy_instances_verify); heuristics
        # may still visit it to reduce travel-only surrogate objectives.
        pass


class TestToyInstancesSolvers(unittest.TestCase):
    def test_toys_against_gated_solvers(self) -> None:
        for toy in TOY_CASES:
            for solver_name, solver_cls, opts in _solver_factories():
                solver = solver_cls(opts)
                if not toy.required_features <= solver.supported_features:
                    continue
                if solver_name in toy.skip_for_solvers:
                    continue
                with self.subTest(toy=toy.name, solver=solver_name):
                    m = toy.build()
                    status = solver.solve(m)
                    self.assertTrue(status.solution_found)
                    self.assertIsNotNone(m.solution)
                    self.assertTrue(m.is_solution_feasible(), msg=f"{toy.name} {solver_name}")
                    mandatory = {j.node_id for j in m.jobs if j.prize is None}
                    visited = {j.node_id for r in m.solution.routes for j in r.jobs}
                    self.assertEqual(mandatory, mandatory & visited)
                    self.assertEqual(len(visited & mandatory), len(mandatory))
                    _assert_cost(toy, m, self)
                    _structural(toy, m, self)


if __name__ == "__main__":
    unittest.main()
