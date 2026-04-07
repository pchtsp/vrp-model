"""Solver run outcome: mapped status plus solver-reported statistics."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from vrp_model.core.model import Model, SolveStatus


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
    iterations: int | None
    error_message: str | None

    @classmethod
    def from_mapped(
        cls,
        model: Model,
        raw_status: object,
        *,
        solver_name: str,
        wall_time_seconds: float | None = None,
        optimality_gap: float | None = None,
        solver_reported_cost: float | None = None,
        stop_reason: SolverStopReason = SolverStopReason.UNKNOWN,
        solution_found: bool = False,
        iterations: int | None = None,
        error_message: str | None = None,
    ) -> SolutionStatus:
        """Build status with ``mapped_status = model.map_status(raw_status)``."""
        return cls(
            mapped_status=model.map_status(raw_status),
            solver_name=solver_name,
            wall_time_seconds=wall_time_seconds,
            optimality_gap=optimality_gap,
            solver_reported_cost=solver_reported_cost,
            stop_reason=stop_reason,
            solution_found=solution_found,
            iterations=iterations,
            error_message=error_message,
        )
