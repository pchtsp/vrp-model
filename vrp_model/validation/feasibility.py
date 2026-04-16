"""Layer 3: simple necessary conditions for feasibility."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vrp_model.core.errors import ValidationError
from vrp_model.core.kinds import NodeKind
from vrp_model.core.time_window_flex import TimeWindowFlex
from vrp_model.validation.tags import job_tag, vehicle_tag

if TYPE_CHECKING:
    from vrp_model.core.model import Model


def validate(model: Model) -> None:
    """Run travel, time window, capacity, and skills sanity checks."""
    _travel_coordinates_or_edges(model)
    _time_windows(model)
    _time_window_flex(model)
    _vehicle_routing_limits(model)
    _capacity(model)
    _skill_ids_non_negative(model)
    _skills(model)
    _pickup_delivery_pair_skills(model)


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
                raise ValidationError(f"job {job_tag(model, node_id)} has impossible time window")


def _time_window_flex(model: Model) -> None:
    """Validate soft time window fields vs hard windows and penalty signs."""
    for vi, v in enumerate(model._vehicles):
        _check_one_time_window_flex(
            v.time_window,
            v.time_window_flex,
            vehicle_tag(model, vi),
        )

    for node_id, row in enumerate(model._nodes):
        if row.kind != NodeKind.JOB:
            continue
        _check_one_time_window_flex(
            row.time_window,
            row.time_window_flex,
            job_tag(model, node_id),
        )


def _check_one_time_window_flex(
    hard: tuple[int, int] | None,
    flex: TimeWindowFlex | None,
    tag: str,
) -> None:
    if flex is None:
        return
    if not isinstance(flex, TimeWindowFlex):
        msg = f"internal error: expected TimeWindowFlex for {tag}"
        raise TypeError(msg)

    se = flex.soft_earliest
    pe = flex.penalty_per_unit_before_soft_earliest
    sl = flex.soft_latest
    pl = flex.penalty_per_unit_after_soft_latest

    if se is not None and pe is not None and pe < 0:
        raise ValidationError(f"{tag} has negative soft early penalty")
    if sl is not None and pl is not None and pl < 0:
        raise ValidationError(f"{tag} has negative soft late penalty")

    if hard is not None:
        a, b = hard
        if se is not None and se < a:
            raise ValidationError(
                f"{tag} soft_earliest is before hard time window start",
            )
        if sl is not None and sl > b:
            raise ValidationError(
                f"{tag} soft_latest is after hard time window end",
            )


def _vehicle_routing_limits(model: Model) -> None:
    """Non-negative fixed cost; strictly positive route caps when set."""
    for vi, v in enumerate(model._vehicles):
        tag = vehicle_tag(model, vi)
        if v.fixed_use_cost < 0:
            raise ValidationError(f"{tag} has negative fixed_use_cost")
        if v.max_route_distance is not None and v.max_route_distance <= 0:
            raise ValidationError(f"{tag} max_route_distance must be positive when set")
        if v.max_route_time is not None and v.max_route_time <= 0:
            raise ValidationError(f"{tag} max_route_time must be positive when set")
        mot = v.max_route_overtime
        if mot is not None and mot < 0:
            raise ValidationError(f"{tag} max_route_overtime must be non-negative when set")
        if mot is not None and mot > 0 and v.max_route_time is None:
            raise ValidationError(
                f"{tag} max_route_time must be set when max_route_overtime is positive",
            )
        uoc = v.route_overtime_unit_cost
        if uoc < 0:
            raise ValidationError(f"{tag} route_overtime_unit_cost must be non-negative")
        if uoc > 0 and (mot is None or mot <= 0):
            raise ValidationError(
                f"{tag} max_route_overtime must be positive when route_overtime_unit_cost is "
                "positive",
            )
        if v.max_slack_time is not None and v.max_slack_time < 0:
            raise ValidationError(f"{tag} max_slack_time must be non-negative when set")


def _pickup_delivery_pair_skills(model: Model) -> None:
    """Same physical vehicle must satisfy pickup and delivery skill requirements."""
    vehicles = model._vehicles
    if not vehicles:
        return
    for pd in model._pickup_deliveries:
        pu = model._nodes[pd.pickup_job_node_id]
        dl = model._nodes[pd.delivery_job_node_id]
        if pu.kind != NodeKind.JOB or dl.kind != NodeKind.JOB:
            continue
        req_pu = pu.skills_required
        req_dl = dl.skills_required
        if not req_pu and not req_dl:
            continue
        if not any(req_pu <= v.skills and req_dl <= v.skills for v in vehicles):
            raise ValidationError(
                "no vehicle covers combined skills for a pickup–delivery pair",
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


def _skill_ids_non_negative(model: Model) -> None:
    """Skill ids must be non-negative on vehicles and jobs."""
    for vi, v in enumerate(model._vehicles):
        for s in v.skills:
            if s < 0:
                raise ValidationError(f"{vehicle_tag(model, vi)} has negative skill id {s}")
    for node_id, row in enumerate(model._nodes):
        if row.kind != NodeKind.JOB:
            continue
        for s in row.skills_required:
            if s < 0:
                raise ValidationError(
                    f"job {job_tag(model, node_id)} has negative skill id {s}",
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
