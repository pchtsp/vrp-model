"""Solver run outcome: mapped status plus solver-reported statistics."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from vrp_model.core.model import SolveStatus


class SolverStopReason(Enum):
    """Why the solver stopped (best-effort mapping from backend semantics)."""

    TIME_LIMIT = auto()
    MAX_ITERATIONS = auto()
    OPTIMAL = auto()
    FEASIBLE = auto()
    INFEASIBLE = auto()
    NO_SOLUTION = auto()
    ERROR = auto()
    UNKNOWN = auto()


@dataclass(frozen=True, slots=True)
class SolutionStatus:
    """Summary of one solver run; returned from :meth:`Solver.solve`."""

    mapped_status: SolveStatus
    solver_name: str
    wall_time_seconds: float | None
    optimality_gap: float | None
    solver_reported_cost: float | None
    stop_reason: SolverStopReason
    solution_found: bool
    iterations: int | None = None
    error_message: str | None = None
    solver_status: str = ""
