"""Build :class:`~vrp_model.core.model.Model` from VRPLIB / Solomon dicts or files."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, cast

import vrplib

from vrp_model.core.model import Model
from vrp_model.core.travel_edges import TravelEdgeAttrs, TravelEdgesMap
from vrp_model.core.views import Depot, Job
from vrp_model.io.vrplib_normalize import NormalizedInstance, normalize_vrplib_read_dict
from vrp_model.io.vrplib_types import VRPLibReadDict


def read_model(
    path: str | Path,
    *,
    instance_format: Literal["vrplib", "solomon"] = "vrplib",
) -> Model:
    """Parse a file with :func:`vrplib.read_instance` and build a :class:`Model`."""
    data = vrplib.read_instance(str(path), instance_format=instance_format)
    return vrplib_dict_to_model(cast(VRPLibReadDict, data))


def vrplib_dict_to_model(data: VRPLibReadDict) -> Model:
    """Build a :class:`Model` from a dict returned by :func:`vrplib.read_instance`.

    Expected shape: :class:`VRPLibReadDict` (and any extra keys ``vrplib`` preserves).
    """
    return build_model_from_normalized(normalize_vrplib_read_dict(data))


def build_model_from_normalized(inst: NormalizedInstance) -> Model:
    """Materialize a :class:`Model` from :class:`NormalizedInstance`."""
    model = Model()
    depot_set = set(inst.depot_orig_indices)

    depot_by_orig: dict[int, Depot] = {}
    unified_by_orig: dict[int, int] = {}
    for orig_idx in sorted(depot_set):
        loc = inst.coordinates[orig_idx]
        depot_by_orig[orig_idx] = model.add_depot(location=loc)
        unified_by_orig[orig_idx] = depot_by_orig[orig_idx].node_id

    _add_jobs_for_normalized(model, inst, depot_set, unified_by_orig)

    for veh in range(inst.vehicle_count):
        start_orig = inst.vehicle_start_depot_orig[veh]
        if start_orig not in depot_by_orig:
            msg = f"vehicle {veh} start depot orig index {start_orig} is not a depot"
            raise ValueError(msg)
        start = depot_by_orig[start_orig]
        cap = list(inst.capacities[veh])
        model.add_vehicle(cap, start, end_depot=start)

    edges: TravelEdgesMap = {}
    dur = inst.duration_rounded
    for u_orig in range(inst.n_locations):
        uid = unified_by_orig[u_orig]
        for v_orig in range(inst.n_locations):
            if u_orig == v_orig:
                continue
            vid = unified_by_orig[v_orig]
            d_uv = inst.distance_rounded[u_orig][v_orig]
            t_uv: int | None = None if dur is None else dur[u_orig][v_orig]
            edges[(uid, vid)] = TravelEdgeAttrs(distance=d_uv, duration=t_uv)

    model.set_travel_edges(edges)
    return model


def _add_jobs_for_normalized(
    model: Model,
    inst: NormalizedInstance,
    depot_set: set[int],
    unified_by_orig: dict[int, int],
) -> dict[int, Job]:
    """Add job nodes and P/D links for clients; fill ``unified_by_orig`` for edge build."""
    job_by_orig: dict[int, Job] = {}
    linehaul = inst.linehaul
    backhaul = inst.backhaul

    for orig_idx in range(inst.n_locations):
        if orig_idx in depot_set:
            continue
        dem = inst.demand[orig_idx]
        loc = inst.coordinates[orig_idx]
        service_time = inst.service_times[orig_idx]
        tw = inst.time_windows[orig_idx]
        prize = inst.prizes[orig_idx]

        if linehaul is not None or backhaul is not None:
            if linehaul is None or backhaul is None:
                raise KeyError("linehaul and backhaul must both be present")
            lh = linehaul[orig_idx]
            bh = backhaul[orig_idx]
            if lh <= 0 and bh <= 0:
                job = model.add_job(
                    0,
                    location=loc,
                    service_time=service_time,
                    time_window=tw,
                    prize=prize,
                )
                job_by_orig[orig_idx] = job
            elif lh > 0:
                pickup = model.add_job(
                    0,
                    location=loc,
                    service_time=service_time,
                    time_window=tw,
                    prize=prize,
                )
                delivery = model.add_job(
                    lh,
                    location=loc,
                    service_time=0,
                    time_window=tw,
                    prize=None,
                )
                model.add_pickup_delivery(pickup, delivery)
                job_by_orig[orig_idx] = delivery
            else:
                pickup = model.add_job(
                    bh,
                    location=loc,
                    service_time=0,
                    time_window=tw,
                    prize=None,
                )
                delivery = model.add_job(
                    0,
                    location=loc,
                    service_time=service_time,
                    time_window=tw,
                    prize=prize,
                )
                model.add_pickup_delivery(pickup, delivery)
                job_by_orig[orig_idx] = pickup
        else:
            job = model.add_job(
                dem,
                location=loc,
                service_time=service_time,
                time_window=tw,
                prize=prize,
            )
            job_by_orig[orig_idx] = job

        unified_by_orig[orig_idx] = job_by_orig[orig_idx].node_id

    return job_by_orig
