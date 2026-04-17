"""Shared helpers for solver adapters (internal)."""

from __future__ import annotations

from vrp_model.core.kinds import NodeKind
from vrp_model.core.model import Model, SolveStatus
from vrp_model.solvers.status import SolutionStatus, SolverStopReason


def depot_node_ids_ordered(model: Model) -> list[int]:
    return [i for i, row in enumerate(model._nodes) if row.kind == NodeKind.DEPOT]


def job_node_ids_ordered(model: Model) -> list[int]:
    return [i for i, row in enumerate(model._nodes) if row.kind == NodeKind.JOB]


def max_capacity_dims(model: Model, *, min_dims: int = 1) -> int:
    d = min_dims
    for v in model._vehicles:
        d = max(d, len(v.capacity))
    for row in model._nodes:
        if row.kind == NodeKind.JOB:
            d = max(d, len(row.as_job().demand))
    return d


def pad_vec(vec: list[int], dims: int) -> list[int]:
    out = list(vec)
    while len(out) < dims:
        out.append(0)
    return out[:dims]


def empty_instance_solution_status(
    solver_name: str,
    *,
    iterations: int | None = None,
) -> SolutionStatus:
    """Return status for a model with no jobs (trivial feasible empty solution)."""
    return SolutionStatus(
        mapped_status=SolveStatus.FEASIBLE,
        solver_name=solver_name,
        wall_time_seconds=0.0,
        optimality_gap=None,
        solver_reported_cost=0.0,
        stop_reason=SolverStopReason.COMPLETED,
        solution_found=True,
        iterations=iterations,
        error_message=None,
        solver_status="",
    )
