"""VRPLIB / Solomon interchange: ``vrplib`` dict hub + thin file I/O.

Read dict keys match ``vrplib.read_instance`` (snake_case). Write dict keys match
``vrplib.write_instance`` (UPPER specs and ``*_SECTION`` headers). See
``vrplib_keys.write_spec_key`` / ``write_section_key`` and module
``vrplib.parse.parse_vrplib`` for the exact mapping.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal, TypedDict, cast

import numpy as np
import vrplib
from numpy.typing import NDArray

from vrp_model.core.kinds import NodeKind
from vrp_model.core.model import Model
from vrp_model.core.solution import Solution
from vrp_model.core.travel_edges import TRAVEL_COST_INF, TravelEdgeAttrs
from vrp_model.core.views import Depot, Job
from vrp_model.io.vrplib_keys import (
    DURATION_MATRIX_READ_KEYS,
    VEHICLES_DEPOT_READ_KEYS,
    VRPLibReadKey,
    get_first_present,
    write_section_key,
    write_spec_key,
)


class VRPLibReadDict(TypedDict, total=False):
    """Shape of instance dicts from ``vrplib.read_instance`` (snake_case keys)."""

    name: str
    type: str
    dimension: int
    vehicles: int
    capacity: int | float
    node_coord: NDArray[np.float64]
    demand: NDArray[np.int_]
    depot: NDArray[np.int_]
    service_time: NDArray[np.int_]
    time_window: NDArray[np.int_]
    prize: NDArray[np.float64]
    linehaul: NDArray[np.int_]
    backhaul: NDArray[np.int_]
    edge_weight: NDArray[np.float64]
    edge_weight_type: str
    edge_weight_format: str
    capacity_section: NDArray[np.int_] | int
    vehicles_depot: NDArray[np.int_]
    vehicles_depots: NDArray[np.int_]
    edge_duration: NDArray[np.float64]
    edge_time: NDArray[np.float64]
    duration_matrix: NDArray[np.float64]
    time_matrix: NDArray[np.float64]
    edge_weight_duration: NDArray[np.float64]
    edge_weight_time: NDArray[np.float64]


class VRPLibWriteDict(TypedDict, total=False):
    """Payload for ``vrplib.write_instance`` (file-style UPPER keys)."""

    NAME: str
    DIMENSION: int
    TYPE: str
    VEHICLES: int
    CAPACITY: int
    NODE_COORD_SECTION: NDArray[np.float64]
    DEMAND_SECTION: NDArray[np.int32]
    TIME_WINDOW_SECTION: NDArray[np.int32]
    SERVICE_TIME_SECTION: NDArray[np.int32]
    VEHICLES_DEPOT_SECTION: NDArray[np.int32]
    CAPACITY_SECTION: NDArray[np.int32]
    DEPOT_SECTION: NDArray[np.int32]
    EDGE_WEIGHT_SECTION: NDArray[np.float64]
    EDGE_WEIGHT_TYPE: str
    EDGE_WEIGHT_FORMAT: str


def read_model(
    path: str | Path,
    *,
    instance_format: Literal["vrplib", "solomon"] = "vrplib",
) -> Model:
    """Parse a file with :func:`vrplib.read_instance` and build a :class:`Model`."""
    data = vrplib.read_instance(str(path), instance_format=instance_format)
    return vrplib_dict_to_model(cast(VRPLibReadDict, data))


def write_vrplib_instance(path: str | Path, model: Model) -> None:
    """Write a ``.vrp``-style instance using :func:`vrplib.write_instance`."""
    payload: dict[str, Any] = cast(dict[str, Any], model_to_vrplib_dict(model))
    vrplib.write_instance(str(path), payload)


def write_vrplib_solution(path: str | Path, solution: Solution) -> None:
    """Write a solution file using :func:`vrplib.write_solution`."""
    routes = solution_to_vrplib_routes(solution)
    extra = {"Cost": int(round(float(solution.cost)))}
    vrplib.write_solution(str(path), routes, extra)


def solution_to_vrplib_routes(solution: Solution) -> list[list[int]]:
    """VRPLIB routes use 1-based location indices (matching written ``DIMENSION`` rows)."""
    out: list[list[int]] = []
    for route in solution.routes:
        seq = [j.node_id + 1 for j in route.jobs]
        if seq:
            out.append(seq)
    return out


def vrplib_dict_to_model(data: VRPLibReadDict) -> Model:
    """Build a :class:`Model` from a dict returned by :func:`vrplib.read_instance`."""
    # TypedDict keys must be string literals for the type checker; ``StrEnum`` members
    # are str at runtime but not ``Literal[...]``, so use a plain mapping for lookups.
    inst: Mapping[str, Any] = cast(Mapping[str, Any], data)
    model = Model()

    node_coord = inst.get(VRPLibReadKey.NODE_COORD)
    demand = _delivery_demand_vector(inst)
    n_locs = int(demand.shape[0])

    depot_raw = inst.get(VRPLibReadKey.DEPOT)
    if depot_raw is None:
        depot_idxs = np.array([0], dtype=int)
    else:
        depot_idxs = np.asarray(depot_raw, dtype=int).reshape(-1)
    depot_set = {int(x) for x in depot_idxs.tolist()}

    depot_by_orig: dict[int, Depot] = {}
    unified_by_orig: dict[int, int] = {}
    for orig_idx in sorted(depot_set):
        loc = _node_location(node_coord, orig_idx)
        depot_by_orig[orig_idx] = model.add_depot(location=loc)
        unified_by_orig[orig_idx] = depot_by_orig[orig_idx].node_id

    linehaul = _optional_array(inst, VRPLibReadKey.LINEHAUL)
    backhaul = _optional_array(inst, VRPLibReadKey.BACKHAUL)

    job_by_orig: dict[int, Job] = {}
    for orig_idx in range(n_locs):
        if orig_idx in depot_set:
            continue
        dem = int(demand[orig_idx])
        loc = _node_location(node_coord, orig_idx)
        service_time = 0
        if VRPLibReadKey.SERVICE_TIME in inst:
            st = np.asarray(inst[VRPLibReadKey.SERVICE_TIME], dtype=int).reshape(-1)
            service_time = int(st[orig_idx])

        tw: tuple[int, int] | None = None
        if VRPLibReadKey.TIME_WINDOW in inst:
            tw_arr = np.asarray(inst[VRPLibReadKey.TIME_WINDOW])
            tw = (int(tw_arr[orig_idx, 0]), int(tw_arr[orig_idx, 1]))

        prize: float | None = None
        if VRPLibReadKey.PRIZE in inst:
            pr = np.asarray(inst[VRPLibReadKey.PRIZE]).reshape(-1)
            prize_val = float(pr[orig_idx])
            prize = None if prize_val == 0.0 else prize_val

        if linehaul is not None or backhaul is not None:
            if linehaul is None or backhaul is None:
                raise KeyError("linehaul and backhaul must both be present")
            lh = int(linehaul[orig_idx])
            bh = int(backhaul[orig_idx])
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

    vehicles_depot = _vehicles_depot_array(inst)
    n_veh = _resolve_vehicle_count(inst, n_clients=max(n_locs - len(depot_set), 0))

    cap_each = _vehicle_capacities(inst, n_veh=n_veh)

    default_depot_orig = int(depot_idxs.min())
    for veh in range(n_veh):
        start_orig = default_depot_orig
        if vehicles_depot is not None:
            start_orig = int(vehicles_depot[veh])
        start = depot_by_orig[start_orig]
        model.add_vehicle(cap_each[veh], start, end_depot=start)

    edge_weight_raw = inst.get(VRPLibReadKey.EDGE_WEIGHT)
    if edge_weight_raw is None:
        raise KeyError(VRPLibReadKey.EDGE_WEIGHT)
    dist = _square_matrix(edge_weight_raw, n_locs)
    dur = _optional_square_matrix(inst, n_locs)

    edges: dict[tuple[int, int], TravelEdgeAttrs] = {}
    for u_orig in range(n_locs):
        uid = unified_by_orig[u_orig]
        for v_orig in range(n_locs):
            if u_orig == v_orig:
                continue
            vid = unified_by_orig[v_orig]
            d_uv = int(np.rint(float(dist[u_orig, v_orig])))
            t_uv: int | None = None if dur is None else int(np.rint(float(dur[u_orig, v_orig])))
            edges[(uid, vid)] = TravelEdgeAttrs(distance=d_uv, duration=t_uv)

    model.set_travel_edges(edges)
    return model


def model_to_vrplib_dict(model: Model) -> VRPLibWriteDict:
    """Build a dict for :func:`vrplib.write_instance` from a :class:`Model`."""
    n = len(model._nodes)
    if n == 0:
        return cast(
            VRPLibWriteDict,
            {
                write_spec_key(VRPLibReadKey.NAME): "empty",
                write_spec_key(VRPLibReadKey.DIMENSION): 0,
                write_spec_key(VRPLibReadKey.TYPE): "CVRP",
            },
        )

    demands: list[int] = []
    coords: list[list[float]] = []
    depot_1based: list[int] = []
    has_coord = True
    for i in range(n):
        row = model._nodes[i]
        dem = row.get("demand")
        demands.append(int(dem[0]) if dem else 0)
        loc = row["location"]
        if loc is None:
            has_coord = False
            coords.append([0.0, 0.0])
        else:
            coords.append([float(loc[0]), float(loc[1])])
        if row["kind"] == NodeKind.DEPOT:
            depot_1based.append(i + 1)

    edge_mat = np.zeros((n, n), dtype=float)
    use_edges = bool(model._travel_edges)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if use_edges:
                e = model._travel_edges.get((i, j))
                if e is None:
                    d = TRAVEL_COST_INF
                else:
                    d = e.distance if e.distance is not None else TRAVEL_COST_INF
                edge_mat[i, j] = float(d)
            else:
                if not has_coord:
                    edge_mat[i, j] = 0.0
                else:
                    dx = coords[i][0] - coords[j][0]
                    dy = coords[i][1] - coords[j][1]
                    edge_mat[i, j] = float(np.hypot(dx, dy))

    n_veh = len(model._vehicles)
    caps = [v["capacity"][0] if v["capacity"] else 0 for v in model._vehicles]
    cap0 = caps[0] if caps else 0

    tw_rows: list[list[int]] = []
    st_rows: list[int] = []
    has_tw = False
    has_st = False
    for i in range(n):
        row = model._nodes[i]
        tw = row.get("time_window")
        if tw is not None:
            has_tw = True
            tw_rows.append([int(tw[0]), int(tw[1])])
        else:
            tw_rows.append([0, 0])
        st = int(row.get("service_time", 0))
        if st != 0:
            has_st = True
        st_rows.append(st)

    # ``vrplib.write_instance`` emits items in dict order; specifications (scalars)
    # must precede all array sections or ``read_instance`` raises.
    out: dict[str, Any] = {
        write_spec_key(VRPLibReadKey.NAME): "model",
        write_spec_key(VRPLibReadKey.TYPE): "CVRP",
        write_spec_key(VRPLibReadKey.DIMENSION): n,
        write_spec_key(VRPLibReadKey.VEHICLES): n_veh,
        write_spec_key(VRPLibReadKey.CAPACITY): cap0,
    }
    if use_edges or not has_coord:
        out[write_spec_key(VRPLibReadKey.EDGE_WEIGHT_TYPE)] = "EXPLICIT"
        out[write_spec_key(VRPLibReadKey.EDGE_WEIGHT_FORMAT)] = "FULL_MATRIX"
    else:
        out[write_spec_key(VRPLibReadKey.EDGE_WEIGHT_TYPE)] = "EUC_2D"

    out[write_section_key(VRPLibReadKey.NODE_COORD)] = np.array(coords, dtype=float)
    out[write_section_key(VRPLibReadKey.DEMAND)] = np.array(demands, dtype=int)
    if has_tw:
        out[write_section_key(VRPLibReadKey.TIME_WINDOW)] = np.array(tw_rows, dtype=int)
    if has_st:
        out[write_section_key(VRPLibReadKey.SERVICE_TIME)] = np.array(st_rows, dtype=int)
    if len(depot_1based) > 1:
        vdep = [model._vehicles[v]["start_depot_node_id"] + 1 for v in range(n_veh)]
        out[write_section_key(VRPLibReadKey.VEHICLES_DEPOT)] = np.array(vdep, dtype=int)
    if len(set(caps)) > 1 and n_veh > 0:
        out[write_section_key(VRPLibReadKey.CAPACITY_SECTION)] = np.array(caps, dtype=int)
    out[write_section_key(VRPLibReadKey.DEPOT)] = np.array(depot_1based, dtype=int)
    if use_edges or not has_coord:
        out[write_section_key(VRPLibReadKey.EDGE_WEIGHT)] = edge_mat

    return cast(VRPLibWriteDict, out)


def _delivery_demand_vector(data: Mapping[str, Any]) -> NDArray[np.int_]:
    if VRPLibReadKey.LINEHAUL in data and VRPLibReadKey.BACKHAUL in data:
        linehaul = np.asarray(data[VRPLibReadKey.LINEHAUL], dtype=int).reshape(-1)
        return np.maximum(linehaul, 0)
    return np.asarray(data[VRPLibReadKey.DEMAND], dtype=int).reshape(-1)


def _optional_array(data: Mapping[str, Any], key: str) -> NDArray[np.int_] | None:
    if key not in data:
        return None
    return np.asarray(data[key], dtype=int).reshape(-1)


def _node_location(node_coord: object | None, idx: int) -> tuple[float, float] | None:
    if node_coord is None:
        return None
    coords = np.asarray(node_coord, dtype=float)
    return (float(coords[idx, 0]), float(coords[idx, 1]))


def _vehicles_depot_array(data: Mapping[str, Any]) -> NDArray[np.int_] | None:
    raw = get_first_present(data, VEHICLES_DEPOT_READ_KEYS)
    if raw is None:
        return None
    return np.asarray(raw, dtype=int).reshape(-1)


def _resolve_vehicle_count(data: Mapping[str, Any], *, n_clients: int) -> int:
    v_raw = data.get(VRPLibReadKey.VEHICLES)
    if v_raw is not None:
        return int(v_raw)

    name = data.get(VRPLibReadKey.NAME)
    if isinstance(name, str):
        m = re.search(r"(?i)[-_]k(\d+)(?:[-_]|$)", name)
        if m:
            k = int(m.group(1))
            if k > 0:
                return k

    if n_clients > 0:
        return n_clients

    raise ValueError("cannot infer vehicle count from vrplib dict")


def _vehicle_capacities(data: Mapping[str, Any], *, n_veh: int) -> list[list[int]]:
    cap_section = data.get(
        VRPLibReadKey.CAPACITY_SECTION,
        data.get(VRPLibReadKey.CAPACITY),
    )
    if cap_section is None:
        raise KeyError("capacity")
    cap_arr = np.asarray(cap_section, dtype=int)
    if cap_arr.shape == ():
        cap = int(cap_arr)
        return [[cap] for _ in range(n_veh)]

    cap_flat = cap_arr.reshape(-1)
    if cap_flat.size == 1:
        cap = int(cap_flat[0])
        return [[cap] for _ in range(n_veh)]

    if cap_flat.size == n_veh:
        return [[int(x)] for x in cap_flat.tolist()]

    if cap_flat.size % n_veh != 0:
        raise ValueError("capacity data size does not divide vehicle count")

    per = cap_flat.size // n_veh
    out: list[list[int]] = []
    for i in range(n_veh):
        chunk = cap_flat[i * per : (i + 1) * per].astype(int).tolist()
        out.append([chunk[0]] if per == 1 else chunk)
    return out


def _square_matrix(value: object, n: int) -> NDArray[np.float64]:
    mat = np.asarray(value, dtype=float)
    if mat.shape != (n, n):
        msg = f"expected ({n}, {n}) matrix, got {mat.shape}"
        raise ValueError(msg)
    return mat


def _optional_square_matrix(data: Mapping[str, Any], n: int) -> NDArray[np.float64] | None:
    for cand in DURATION_MATRIX_READ_KEYS:
        if cand not in data:
            continue
        mat = np.asarray(data[cand], dtype=float)
        if mat.shape == (n, n):
            return mat
        raise ValueError(f"matrix {cand!r} must be ({n}, {n})")
    return None
