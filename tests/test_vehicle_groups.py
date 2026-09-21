"""Vehicle groups (vehicles sharing one unit of availability)."""

from __future__ import annotations

import unittest

from tests._limits import ORTOOLS_TIME_LIMIT
from vrp_model import Feature, Model, ValidationError


def _two_vehicle_model(prize: float | None = None) -> Model:
    """Two jobs, each servable only by the vehicle carrying its skill."""
    m = Model()
    d = m.add_depot(location=(0.0, 0.0))
    m.add_vehicle([10], d, label="A", skills={1})
    m.add_vehicle([10], d, label="B", skills={2})
    m.add_job(1, location=(1.0, 0.0), skills_required={1}, prize=prize)
    m.add_job(1, location=(0.0, 1.0), skills_required={2}, prize=prize)
    return m


class TestVehicleGroupValidation(unittest.TestCase):
    def test_single_member_rejected(self) -> None:
        m = _two_vehicle_model()
        m.add_vehicle_group(list(m.vehicles)[:1])
        with self.assertRaisesRegex(ValidationError, "at least two vehicles"):
            m.validate()

    def test_duplicate_members_rejected(self) -> None:
        m = _two_vehicle_model()
        first = next(m.vehicles)
        with self.assertRaisesRegex(ValidationError, "distinct vehicles"):
            m.add_vehicle_group([first, first])

    def test_disjoint_groups(self) -> None:
        m = _two_vehicle_model()
        va, vb = list(m.vehicles)
        m.add_vehicle_group([va, vb])
        m.add_vehicle_group([vb, va])
        with self.assertRaisesRegex(ValidationError, "more than one vehicle group"):
            m.validate()

    def test_max_active_must_be_positive(self) -> None:
        m = _two_vehicle_model()
        m.add_vehicle_group(list(m.vehicles), max_active=0)
        with self.assertRaisesRegex(ValidationError, "at least one active vehicle"):
            m.validate()

    def test_vehicle_from_other_model_rejected(self) -> None:
        m = _two_vehicle_model()
        other = _two_vehicle_model()
        with self.assertRaisesRegex(ValidationError, "must belong to this model"):
            m.add_vehicle_group([next(m.vehicles), next(other.vehicles)])


class TestVehicleGroupModel(unittest.TestCase):
    def test_feature_detected(self) -> None:
        m = _two_vehicle_model()
        self.assertNotIn(Feature.VEHICLE_GROUPS, m.features)
        m.add_vehicle_group(list(m.vehicles))
        self.assertIn(Feature.VEHICLE_GROUPS, m.features)

    def test_view_reads_back_members(self) -> None:
        m = _two_vehicle_model()
        group = m.add_vehicle_group(list(m.vehicles), max_active=1)
        self.assertEqual(group.index, 0)
        self.assertEqual([v.label for v in group.member_vehicles], ["A", "B"])
        self.assertEqual(group.max_active, 1)
        self.assertEqual([g.index for g in m.vehicle_groups], [0])

    def test_solution_activating_both_members_is_infeasible(self) -> None:
        from vrp_model.core.solution import Route, Solution

        # Optional jobs, so that leaving one unvisited is not itself an infeasibility.
        m = _two_vehicle_model(prize=1000.0)
        m.add_vehicle_group(list(m.vehicles))
        m.validate()
        depot = next(m.depots)
        va, vb = list(m.vehicles)
        ja, jb = list(m.jobs)
        m._solution = Solution(
            routes=[
                Route(vehicle=va, start_depot=depot, end_depot=depot, jobs=[ja]),
                Route(vehicle=vb, start_depot=depot, end_depot=depot, jobs=[jb]),
            ],
        )
        self.assertFalse(m.is_solution_feasible())

        m._solution = Solution(
            routes=[Route(vehicle=va, start_depot=depot, end_depot=depot, jobs=[ja])],
        )
        self.assertTrue(m.is_solution_feasible())


try:
    import ortools  # noqa: F401

    from vrp_model.solvers.ortools import ORToolsSolver

    _ORTOOLS_INSTALLED = True
except ModuleNotFoundError:
    _ORTOOLS_INSTALLED = False

try:
    import pyvrp  # noqa: F401

    from vrp_model.solvers.pyvrp import PyVRPSolver

    _PYVRP_INSTALLED = True
except ModuleNotFoundError:
    _PYVRP_INSTALLED = False


@unittest.skipIf(not _ORTOOLS_INSTALLED, "ortools extra not installed")
class TestVehicleGroupORTools(unittest.TestCase):
    def test_grouped_vehicles_do_not_both_run(self) -> None:
        m = _two_vehicle_model(prize=1000.0)
        m.add_vehicle_group(list(m.vehicles))
        m.validate()
        ORToolsSolver({"time_limit": ORTOOLS_TIME_LIMIT, "msg": False}).solve(m)
        sol = m.solution
        assert sol is not None
        active = [rt for rt in sol.routes if rt.jobs]
        self.assertEqual(len(active), 1)
        self.assertTrue(m.is_solution_feasible())

    def test_without_the_group_both_run(self) -> None:
        m = _two_vehicle_model(prize=1000.0)
        m.validate()
        ORToolsSolver({"time_limit": ORTOOLS_TIME_LIMIT, "msg": False}).solve(m)
        sol = m.solution
        assert sol is not None
        self.assertEqual(len([rt for rt in sol.routes if rt.jobs]), 2)


@unittest.skipIf(not _PYVRP_INSTALLED, "pyvrp extra not installed")
class TestVehicleGroupPyVRP(unittest.TestCase):
    def test_pyvrp_rejects_vehicle_groups(self) -> None:
        from vrp_model import SolverCapabilityError

        m = _two_vehicle_model()
        m.add_vehicle_group(list(m.vehicles))
        with self.assertRaises(SolverCapabilityError):
            PyVRPSolver({"time_limit": 0.05, "msg": False}).solve(m)


if __name__ == "__main__":
    unittest.main()
