"""Shared tiny-line instance smoke check for solver integration tests."""

from __future__ import annotations

from tests.toy_instances import build_tiny_line_two_jobs
from vrp_model import Model
from vrp_model.solvers.base import Solver
from vrp_model.solvers.status import SolutionStatus


def run_tiny_line_two_jobs(solver: Solver) -> tuple[SolutionStatus, Model]:
    """Build the two-job line toy, solve, assert feasibility and both job labels; return status."""
    m = build_tiny_line_two_jobs()
    status = solver.solve(m)
    sol = m.solution
    assert sol is not None
    assert m.is_solution_feasible()
    covered = {j.label for r in sol.routes for j in r.jobs}
    assert covered == {"j0", "j1"}
    return status, m
