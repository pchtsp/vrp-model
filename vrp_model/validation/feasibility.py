"""Layer 3: simple necessary conditions for feasibility."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vrp_model.core.errors import ValidationError
from vrp_model.core.kinds import NodeKind
from vrp_model.validation.tags import job_tag, vehicle_tag

if TYPE_CHECKING:
    from vrp_model.core.model import Model


def validate(model: Model) -> None:
    """Run travel, time window, capacity, and skills sanity checks."""
    _travel_coordinates_or_edges(model)
    _time_windows(model)
    _capacity(model)
    _skills(model)


def _travel_coordinates_or_edges(model: Model) -> None:
    """Euclidean travel is only allowed with an empty travel map if every job has coordinates."""
    if model._travel_edges:
        return
    for node_id, row in enumerate(model._nodes):
        if row.kind != NodeKind.JOB:
            continue
        if row.location is None:
            tag = job_tag(model, node_id)
            raise ValidationError(
                f"job {tag} has no location; add coordinates for all jobs when travel_edges is "
                "empty, or define travel_edges (any edge enables matrix-only travel)",
            )


def _time_windows(model: Model) -> None:
    """Reject time windows with start after end on vehicles and jobs."""
    for vi, v in enumerate(model._vehicles):
        tw = v.time_window
        if tw is not None:
            a, b = tw
            if a > b:
                tag = vehicle_tag(model, vi)
                raise ValidationError(f"vehicle {tag} has impossible time window")

    for node_id, row in enumerate(model._nodes):
        if row.kind != NodeKind.JOB:
            continue
        tw = row.time_window
        if tw is not None:
            a, b = tw
            if a > b:
                raise ValidationError(
                    f"job {job_tag(model, node_id)} has impossible time window"
                )


def _capacity(model: Model) -> None:
    """Ensure no job demand exceeds the best fleet capacity per dimension (when capacities set)."""
    if any(len(v.capacity) == 0 for v in model._vehicles):
        return

    job_dims = 0
    for row in model._nodes:
        if row.kind != NodeKind.JOB:
            continue
        job_dims = max(job_dims, len(row.demand))

    max_cap: list[float] = []
    for v in model._vehicles:
        cap = v.capacity
        while len(max_cap) < len(cap):
            max_cap.append(0.0)
        for i, c in enumerate(cap):
            max_cap[i] = max(max_cap[i], float(c))

    while len(max_cap) < job_dims:
        max_cap.append(0.0)

    for node_id, row in enumerate(model._nodes):
        if row.kind != NodeKind.JOB:
            continue
        dem = row.demand
        for i, q in enumerate(dem):
            limit = max_cap[i] if i < len(max_cap) else 0.0
            if float(q) > limit:
                jt = job_tag(model, node_id)
                raise ValidationError(
                    f"job {jt} demand dim {i} exceeds max fleet capacity on that dimension",
                )


def _skills(model: Model) -> None:
    """Ensure each job with required skills has at least one compatible vehicle."""
    vehicles = model._vehicles
    if not vehicles:
        return
    for node_id, row in enumerate(model._nodes):
        if row.kind != NodeKind.JOB:
            continue
        req = row.skills_required
        if not req:
            continue
        if not any(req <= v.skills for v in vehicles):
            raise ValidationError(
                f"no vehicle covers skills required by job {job_tag(model, node_id)}",
            )
