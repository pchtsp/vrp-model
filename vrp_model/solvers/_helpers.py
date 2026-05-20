"""Shared helpers for solver adapters (internal)."""

from __future__ import annotations

from vrp_model.core.kinds import NodeKind
from vrp_model.core.model import Model, SolveStatus
from vrp_model.core.travel_edges import TRAVEL_COST_INF
from vrp_model.solvers.status import SolutionStatus, SolverStopReason


def is_model_travel_inf(value: int) -> bool:
    """True when ``value`` is the canonical model unreachable-arc sentinel."""
    return value >= TRAVEL_COST_INF


def solver_travel_int(
    raw: int,
    *,
    override: int | None,
    backend_default: int,
) -> int:
    """Map a model leg cost to an int the backend matrix accepts.

    When ``raw`` is unreachable in the model, use ``override`` if set, else
    ``backend_default`` (each solver's previous hard-coded cap).
    """
    if is_model_travel_inf(raw):
        return int(override) if override is not None else int(backend_default)
    return int(raw)


def solver_travel_float(
    raw: int,
    *,
    override: int | None,
    backend_default: float,
) -> float:
    """Same as :func:`solver_travel_int` but for float matrix backends."""
    if is_model_travel_inf(raw):
        return float(override) if override is not None else float(backend_default)
    return float(raw)


def should_add_explicit_edge(
    model: Model,
    u: int,
    v: int,
    *,
    omit_unreachable: bool,
) -> bool:
    """Whether explicit-edge backends (e.g. PyVRP ``add_edge``) should create ``(u, v)``.

    When ``omit_unreachable`` is false, every directed pair is added. When true, skip arcs
    without usable distance, or without usable duration when time windows are not active.
    """
    if not omit_unreachable:
        return True
    if is_model_travel_inf(model._directed_travel_distance(u, v)):
        return False
    return not is_model_travel_inf(model._directed_travel_duration(u, v))


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
