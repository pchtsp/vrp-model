"""OR-Tools integration tests (optional dependency)."""

from __future__ import annotations

import contextlib
import os
import unittest

from tests._limits import ORTOOLS_TIME_LIMIT
from tests.tiny_line_solver import run_tiny_line_two_jobs
from vrp_model import Model, TimeWindowFlex, TravelEdgeAttrs, TravelEdgesMap
from vrp_model.core.errors import SolverNotInstalledError
from vrp_model.solvers.ortools import ORToolsSolver

try:
    import ortools  # noqa: F401
except ModuleNotFoundError:
    _ORTOOLS_INSTALLED = False
else:
    _ORTOOLS_INSTALLED = True


@contextlib.contextmanager
def _capture_fd(fd: int):
    """Capture OS-level output on ``fd``.

    OR-Tools' ``log_search`` writes through absl logging straight to the C++ file
    descriptor, so redirecting Python's ``sys.stdout``/``sys.stderr`` objects (e.g.
    ``contextlib.redirect_stdout``) does not see it. Only an fd-level ``dup2`` does.
    """
    read_fd, write_fd = os.pipe()
    saved_fd = os.dup(fd)
    os.dup2(write_fd, fd)
    os.close(write_fd)
    captured = bytearray()
    try:
        yield captured
    finally:
        os.dup2(saved_fd, fd)
        os.close(saved_fd)
        while True:
            chunk = os.read(read_fd, 65536)
            if not chunk:
                break
            captured.extend(chunk)
        os.close(read_fd)


@unittest.skipIf(not _ORTOOLS_INSTALLED, "ortools extra not installed")
class TestORToolsSolverMsgOption(unittest.TestCase):
    """Regression test: ``msg=True`` must make OR-Tools print its search log.

    ``ORToolsSolver`` used to ignore the ``msg`` option entirely (unlike the PyVRP
    backend), so ``--quiet``/``msg`` toggles had no effect and OR-Tools solves ran
    completely silent. The fix sets ``RoutingSearchParameters.log_search``.
    """

    def test_msg_true_emits_search_log(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([10], d)
        m.add_job(1, location=(1.0, 0.0), label="a")
        m.validate()

        with _capture_fd(2) as captured:
            ORToolsSolver({"time_limit": ORTOOLS_TIME_LIMIT, "msg": True}).solve(m)

        output = bytes(captured).decode(errors="replace")
        self.assertIn("search.cc", output)

    def test_msg_false_is_silent(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([10], d)
        m.add_job(1, location=(1.0, 0.0), label="a")
        m.validate()

        with _capture_fd(2) as captured:
            ORToolsSolver({"time_limit": ORTOOLS_TIME_LIMIT, "msg": False}).solve(m)

        output = bytes(captured).decode(errors="replace")
        self.assertNotIn("search.cc", output)


@unittest.skipIf(not _ORTOOLS_INSTALLED, "ortools extra not installed")
class TestORToolsSolver(unittest.TestCase):
    def test_tiny_instance_feasible(self) -> None:
        result, _m = run_tiny_line_two_jobs(ORToolsSolver({"time_limit": ORTOOLS_TIME_LIMIT}))
        self.assertIn(result.mapped_status.name, ("FEASIBLE", "OPTIMAL"))
        self.assertEqual(result.solver_name, "ortools")
        self.assertTrue(result.solution_found)

    def test_without_locations_uses_full_travel_edges(self) -> None:
        m = Model()
        d = m.add_depot()
        m.add_vehicle([10], d)
        m.add_job(3, label="j0")
        m.add_job(4, label="j1")
        edges: TravelEdgesMap = {}
        for i in range(3):
            for j in range(3):
                if i == j:
                    continue
                edges[(i, j)] = TravelEdgeAttrs(distance=1, duration=1)
        m.set_travel_edges(edges)
        m.validate()

        solver = ORToolsSolver({"time_limit": ORTOOLS_TIME_LIMIT})
        result = solver.solve(m)
        sol = m.solution
        assert sol is not None
        self.assertIn(result.mapped_status.name, ("FEASIBLE", "OPTIMAL"))
        self.assertTrue(m.is_solution_feasible())
        covered = {j.label for r in sol.routes for j in r.jobs}
        self.assertEqual(covered, {"j0", "j1"})

    def test_time_windows(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([10], d, time_window=(0, 10_000))
        m.add_job(1, location=(1.0, 0.0), time_window=(0, 5000), service_time=1)
        m.validate()
        result = ORToolsSolver({"time_limit": ORTOOLS_TIME_LIMIT}).solve(m)
        self.assertTrue(m.is_solution_feasible())
        self.assertIn(result.mapped_status.name, ("FEASIBLE", "OPTIMAL"))

    def test_skills_routes_compatible_vehicle(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([10], d, skills={1})
        m.add_vehicle([10], d, skills={2})
        m.add_job(1, location=(1.0, 0.0), skills_required={1})
        m.add_job(1, location=(2.0, 0.0), skills_required={2})
        m.validate()
        ORToolsSolver({"time_limit": ORTOOLS_TIME_LIMIT}).solve(m)
        self.assertTrue(m.is_solution_feasible())
        for r in m.solution.routes:
            if not r.jobs:
                continue
            vs = r.vehicle.skills
            for j in r.jobs:
                req = j.skills_required
                if req:
                    self.assertTrue(req <= vs)

    def test_fixed_use_cost_and_route_caps_do_not_crash(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle(
            [10],
            d,
            fixed_use_cost=100,
            max_route_distance=1_000_000,
            max_route_time=1_000_000,
            max_slack_time=500_000,
            time_window=(0, 10_000_000),
        )
        m.add_job(1, location=(1.0, 0.0), service_time=0, time_window=(0, 10_000_000))
        m.validate()
        r = ORToolsSolver({"time_limit": ORTOOLS_TIME_LIMIT}).solve(m)
        self.assertIn(r.mapped_status.name, ("FEASIBLE", "OPTIMAL"))

    def test_route_time_overtime_makes_tight_span_feasible(self) -> None:
        """Nominal span too small; extra overtime window allows a feasible route."""
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle(
            [10],
            d,
            time_window=(0, 10_000),
            max_route_time=3,
            max_route_overtime=10,
            route_overtime_unit_cost=0,
        )
        m.add_job(1, location=(1.0, 0.0), label="a", time_window=(0, 10_000))
        m.add_job(1, location=(2.0, 0.0), label="b", time_window=(0, 10_000))
        m.validate()
        r = ORToolsSolver({"time_limit": ORTOOLS_TIME_LIMIT}).solve(m)
        self.assertIn(r.mapped_status.name, ("FEASIBLE", "OPTIMAL"))
        self.assertTrue(m.is_solution_feasible())

    def test_flexible_time_window_soft_latest(self) -> None:
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([10], d, time_window=(0, 10_000))
        flex = TimeWindowFlex(soft_latest=100, penalty_per_unit_after_soft_latest=1)
        m.add_job(
            1,
            location=(1.0, 0.0),
            time_window=(0, 500),
            time_window_flex=flex,
            service_time=1,
        )
        m.validate()
        r = ORToolsSolver({"time_limit": ORTOOLS_TIME_LIMIT}).solve(m)
        self.assertIn(r.mapped_status.name, ("FEASIBLE", "OPTIMAL"))

    def test_interleaved_nodes_ortools(self) -> None:
        m = Model()
        d0 = m.add_depot(location=(0.0, 0.0))
        m.add_job(2, location=(1.0, 0.0), label="mid")
        d1 = m.add_depot(location=(3.0, 0.0))
        m.add_vehicle([10], d0, end_depot=d1)
        m.add_job(1, location=(2.0, 0.0), label="last")
        m.validate()
        result = ORToolsSolver({"time_limit": ORTOOLS_TIME_LIMIT}).solve(m)
        sol = m.solution
        assert sol is not None
        self.assertIn(result.mapped_status.name, ("FEASIBLE", "OPTIMAL"))
        labels = {j.label for r in sol.routes for j in r.jobs}
        self.assertEqual(labels, {"mid", "last"})


HOUR = 3600
"""Seconds per hour: late-shift tests use an absolute clock whose origin is midnight."""
DAY = 24 * HOUR


def _uniform_edges(n_nodes: int, *, duration: int, distance: int) -> TravelEdgesMap:
    """Complete edge map with identical travel cost on every directed arc."""
    edges: TravelEdgesMap = {}
    for i in range(n_nodes):
        for j in range(n_nodes):
            if i == j:
                continue
            edges[(i, j)] = TravelEdgeAttrs(distance=distance, duration=duration)
    return edges


@unittest.skipIf(not _ORTOOLS_INSTALLED, "ortools extra not installed")
class TestORToolsLateShiftStart(unittest.TestCase):
    """Time cumuls are absolute clock values, so route starts must float above zero.

    Each case here breaks if the ``Time`` dimension is ever built with
    ``fix_start_cumul_to_zero=True``: pinning the start cumul to 0 forces every vehicle
    to leave the depot at midnight.
    """

    def test_shift_starting_at_five_am(self) -> None:
        """Vehicle works 05:00-22:00; a zero-pinned start contradicts its time window."""
        m = Model()
        d = m.add_depot(label="depot")
        m.add_vehicle([10], d, time_window=(5 * HOUR, 22 * HOUR))
        m.add_job(1, label="morning", service_time=600, time_window=(6 * HOUR, 7 * HOUR))
        m.add_job(1, label="noon", service_time=600, time_window=(12 * HOUR, 13 * HOUR))
        m.set_travel_edges(_uniform_edges(3, duration=1800, distance=1000))
        m.validate()

        r = ORToolsSolver({"time_limit": ORTOOLS_TIME_LIMIT}).solve(m)
        sol = m.solution
        assert sol is not None
        self.assertIn(r.mapped_status.name, ("FEASIBLE", "OPTIMAL"))
        self.assertTrue(m.is_solution_feasible())
        covered = {j.label for route in sol.routes for j in route.jobs}
        self.assertEqual(covered, {"morning", "noon"})

    def test_two_disjoint_shifts_start_at_their_own_hours(self) -> None:
        """Morning and evening shifts cannot both depart at time 0."""
        m = Model()
        d = m.add_depot(label="depot")
        m.add_vehicle([10], d, label="morning-shift", time_window=(5 * HOUR, 9 * HOUR))
        m.add_vehicle([10], d, label="evening-shift", time_window=(18 * HOUR, 22 * HOUR))
        m.add_job(1, label="early", service_time=600, time_window=(6 * HOUR, 7 * HOUR))
        m.add_job(1, label="late", service_time=600, time_window=(19 * HOUR, 20 * HOUR))
        m.set_travel_edges(_uniform_edges(3, duration=1800, distance=1000))
        m.validate()

        r = ORToolsSolver({"time_limit": ORTOOLS_TIME_LIMIT}).solve(m)
        sol = m.solution
        assert sol is not None
        self.assertIn(r.mapped_status.name, ("FEASIBLE", "OPTIMAL"))
        self.assertTrue(m.is_solution_feasible())
        by_vehicle = {route.vehicle.label: [j.label for j in route.jobs] for route in sol.routes}
        self.assertEqual(by_vehicle, {"morning-shift": ["early"], "evening-shift": ["late"]})

    def test_no_slack_vehicle_must_depart_late(self) -> None:
        """Waiting is banned (``max_slack_time=0``), so only a late start reaches a 05:00 job.

        The vehicle window covers the whole day, so time 0 is a legal start here; what
        rules it out is that a route leaving at midnight arrives 04:30 too early and
        cannot wait.
        """
        m = Model()
        d = m.add_depot(label="depot")
        m.add_vehicle([10], d, time_window=(0, DAY), max_slack_time=0)
        m.add_job(
            1,
            label="five-am",
            service_time=0,
            time_window=(5 * HOUR, 5 * HOUR + 60),
        )
        m.set_travel_edges(_uniform_edges(2, duration=1800, distance=1000))
        m.validate()

        r = ORToolsSolver({"time_limit": ORTOOLS_TIME_LIMIT}).solve(m)
        sol = m.solution
        assert sol is not None
        self.assertIn(r.mapped_status.name, ("FEASIBLE", "OPTIMAL"))
        self.assertTrue(m.is_solution_feasible())
        covered = {j.label for route in sol.routes for j in route.jobs}
        self.assertEqual(covered, {"five-am"})

    def test_optional_job_at_five_am_is_not_silently_skipped(self) -> None:
        """A zero-pinned start drops this job instead of failing, so assert it is served."""
        m = Model()
        d = m.add_depot(label="depot")
        m.add_vehicle([10], d, time_window=(0, DAY), max_slack_time=0)
        m.add_job(
            1,
            label="five-am",
            service_time=0,
            time_window=(5 * HOUR, 5 * HOUR + 60),
            prize=10_000,
        )
        m.set_travel_edges(_uniform_edges(2, duration=1800, distance=1000))
        m.validate()

        r = ORToolsSolver({"time_limit": ORTOOLS_TIME_LIMIT}).solve(m)
        sol = m.solution
        assert sol is not None
        self.assertIn(r.mapped_status.name, ("FEASIBLE", "OPTIMAL"))
        covered = {j.label for route in sol.routes for j in route.jobs}
        self.assertEqual(covered, {"five-am"})

    def test_route_time_cap_measures_span_not_wall_clock(self) -> None:
        """A 2h span cap holds for an 06:00 visit only because the span excludes the offset."""
        m = Model()
        d = m.add_depot(label="depot")
        m.add_vehicle([10], d, time_window=(5 * HOUR, 22 * HOUR), max_route_time=2 * HOUR)
        m.add_job(1, label="morning", service_time=600, time_window=(6 * HOUR, 7 * HOUR))
        m.set_travel_edges(_uniform_edges(2, duration=1800, distance=1000))
        m.validate()

        r = ORToolsSolver({"time_limit": ORTOOLS_TIME_LIMIT}).solve(m)
        sol = m.solution
        assert sol is not None
        self.assertIn(r.mapped_status.name, ("FEASIBLE", "OPTIMAL"))
        covered = {j.label for route in sol.routes for j in route.jobs}
        self.assertEqual(covered, {"morning"})

    def test_fix_start_cumul_to_zero_pins_the_start_cumul(self) -> None:
        """The OR-Tools semantics the cases above rely on, on a bare routing model."""
        from vrp_model.solvers.ortools.bindings import PyWrapCP

        assert PyWrapCP is not None

        def start_cumul_bounds(fix_start_cumul_to_zero: bool) -> tuple[int, int]:
            manager = PyWrapCP.RoutingIndexManager(2, 1, [0], [0])
            routing = PyWrapCP.RoutingModel(manager)
            cb = routing.RegisterTransitCallback(lambda _i, _j: 1800)
            routing.AddDimension(cb, DAY, DAY, fix_start_cumul_to_zero, "Time")
            cumul = routing.GetDimensionOrDie("Time").CumulVar(routing.Start(0))
            return cumul.Min(), cumul.Max()

        self.assertEqual(start_cumul_bounds(True), (0, 0))
        self.assertEqual(start_cumul_bounds(False), (0, DAY))


class TestORToolsSolverNotInstalled(unittest.TestCase):
    def test_raises_without_dependency(self) -> None:
        if _ORTOOLS_INSTALLED:
            self.skipTest("ortools is installed")

        from vrp_model.solvers.ortools import solver as ortools_solver_module

        self.assertIsNone(ortools_solver_module.PyWrapCP)
        m = Model()
        d = m.add_depot(location=(0.0, 0.0))
        m.add_vehicle([10], d)
        m.add_job(1, location=(1.0, 0.0))
        m.validate()
        with self.assertRaises(SolverNotInstalledError):
            fake = ortools_solver_module.ORToolsSolver({"time_limit": 1.0})
            fake._run(m)


if __name__ == "__main__":
    unittest.main()
