"""Parse VRPLIB dicts into a normalized, list-based intermediate representation."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from vrp_model.io.vrplib_keys import (
    DURATION_MATRIX_READ_KEYS,
    VEHICLES_DEPOT_READ_KEYS,
    VRPLibReadKey,
    get_first_present,
)
from vrp_model.io.vrplib_types import VRPLibReadDict


@dataclass(frozen=True, slots=True)
class NormalizedInstance:
    """Normalized VRPLIB row data (lists + int matrices) before building a :class:`Model`."""

    n_locations: int
    demand: tuple[int, ...]
    depot_orig_indices: tuple[int, ...]
    coordinates: tuple[tuple[float, float] | None, ...]
    linehaul: tuple[int, ...] | None
    backhaul: tuple[int, ...] | None
    service_times: tuple[int, ...]
    time_windows: tuple[tuple[int, int] | None, ...]
    prizes: tuple[float | None, ...]
    vehicle_count: int
    vehicle_start_depot_orig: tuple[int, ...]
    capacities: tuple[tuple[int, ...], ...]
    distance_rounded: tuple[tuple[int, ...], ...]
    duration_rounded: tuple[tuple[int, ...], ...] | None


def normalize_vrplib_read_dict(data: VRPLibReadDict) -> NormalizedInstance:
    """Convert a :func:`vrplib.read_instance` dict to lists and int matrices (no :class:`Model`)."""
    node_coord = data.get(VRPLibReadKey.NODE_COORD)
    demand_list = _delivery_demand_list(data)
    n_locs = len(demand_list)

    depot_raw = data.get(VRPLibReadKey.DEPOT)
    if depot_raw is None:
        depot_idxs_list = [0]
    else:
        depot_idxs_list = [
            int(x) for x in np.asarray(depot_raw, dtype=int).reshape(-1).tolist()
        ]
    depot_idxs = tuple(sorted(set(depot_idxs_list)))

    coords = _coordinates_list(node_coord, n_locs)
    linehaul = _optional_int_list(data, VRPLibReadKey.LINEHAUL, n_locs)
    backhaul = _optional_int_list(data, VRPLibReadKey.BACKHAUL, n_locs)

    service_times = _service_times_list(data, n_locs)
    time_windows = _time_windows_list(data, n_locs)
    prizes = _prizes_list(data, n_locs)

    n_veh = _resolve_vehicle_count(data, n_clients=max(n_locs - len(depot_idxs), 0))
    veh_depot = _vehicle_start_depot_orig_list(data, n_veh, depot_idxs)
    cap_tuples = tuple(tuple(row) for row in _vehicle_capacities(data, n_veh=n_veh))

    edge_weight_raw = data.get(VRPLibReadKey.EDGE_WEIGHT)
    if edge_weight_raw is None:
        raise KeyError(VRPLibReadKey.EDGE_WEIGHT)
    dist = _square_matrix_int_rounded(edge_weight_raw, n_locs)
    dur = _optional_duration_matrix_int(data, n_locs)

    return NormalizedInstance(
        n_locations=n_locs,
        demand=tuple(demand_list),
        depot_orig_indices=depot_idxs,
        coordinates=tuple(coords),
        linehaul=tuple(linehaul) if linehaul is not None else None,
        backhaul=tuple(backhaul) if backhaul is not None else None,
        service_times=tuple(service_times),
        time_windows=tuple(time_windows),
        prizes=tuple(prizes),
        vehicle_count=n_veh,
        vehicle_start_depot_orig=tuple(veh_depot),
        capacities=cap_tuples,
        distance_rounded=tuple(tuple(row) for row in dist),
        duration_rounded=tuple(tuple(row) for row in dur) if dur is not None else None,
    )


def _delivery_demand_list(data: Mapping[str, Any]) -> list[int]:
    if VRPLibReadKey.LINEHAUL in data and VRPLibReadKey.BACKHAUL in data:
        linehaul = np.asarray(data[VRPLibReadKey.LINEHAUL], dtype=int).reshape(-1)
        return [max(int(x), 0) for x in linehaul.tolist()]
    dem = np.asarray(data[VRPLibReadKey.DEMAND], dtype=int).reshape(-1)
    return [int(x) for x in dem.tolist()]


def _optional_int_list(
    data: Mapping[str, Any],
    key: str | VRPLibReadKey,
    n: int,
) -> list[int] | None:
    if key not in data:
        return None
    arr = np.asarray(data[key], dtype=int).reshape(-1)
    if arr.size != n:
        msg = f"{key!r} length {arr.size} != n_locations {n}"
        raise ValueError(msg)
    return [int(x) for x in arr.tolist()]


def _coordinates_list(
    node_coord: object | None, n_locs: int
) -> list[tuple[float, float] | None]:
    if node_coord is None:
        return [None] * n_locs
    coords = np.asarray(node_coord, dtype=float)
    out: list[tuple[float, float] | None] = []
    for idx in range(n_locs):
        out.append((float(coords[idx, 0]), float(coords[idx, 1])))
    return out


def _service_times_list(data: Mapping[str, Any], n_locs: int) -> list[int]:
    if VRPLibReadKey.SERVICE_TIME not in data:
        return [0] * n_locs
    st = np.asarray(data[str(VRPLibReadKey.SERVICE_TIME)], dtype=int).reshape(-1)
    return [int(st[i]) for i in range(n_locs)]


def _time_windows_list(
    data: Mapping[str, Any], n_locs: int
) -> list[tuple[int, int] | None]:
    if VRPLibReadKey.TIME_WINDOW not in data:
        return [None] * n_locs
    tw_arr = np.asarray(data[str(VRPLibReadKey.TIME_WINDOW)])
    out: list[tuple[int, int] | None] = []
    for orig_idx in range(n_locs):
        out.append((int(tw_arr[orig_idx, 0]), int(tw_arr[orig_idx, 1])))
    return out


def _prizes_list(data: Mapping[str, Any], n_locs: int) -> list[float | None]:
    if VRPLibReadKey.PRIZE not in data:
        return [None] * n_locs
    pr = np.asarray(data[str(VRPLibReadKey.PRIZE)]).reshape(-1)
    out: list[float | None] = []
    for orig_idx in range(n_locs):
        prize_val = float(pr[orig_idx])
        out.append(None if prize_val == 0.0 else prize_val)
    return out


def _vehicle_start_depot_orig_list(
    data: Mapping[str, Any],
    n_veh: int,
    depot_idxs: tuple[int, ...],
) -> list[int]:
    default_depot_orig = min(depot_idxs)
    raw = get_first_present(data, VEHICLES_DEPOT_READ_KEYS)
    if raw is None:
        return [default_depot_orig] * n_veh
    arr = np.asarray(raw, dtype=int).reshape(-1)
    if arr.size != n_veh:
        msg = f"vehicles depot list length {arr.size} != vehicle count {n_veh}"
        raise ValueError(msg)
    return [int(x) for x in arr.tolist()]


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


def _square_matrix_int_rounded(value: object, n: int) -> list[list[int]]:
    mat = np.asarray(value, dtype=float)
    if mat.shape != (n, n):
        msg = f"expected ({n}, {n}) matrix, got {mat.shape}"
        raise ValueError(msg)
    return [[int(np.rint(float(mat[i, j]))) for j in range(n)] for i in range(n)]


def _optional_duration_matrix_int(
    data: Mapping[str, Any], n: int
) -> list[list[int]] | None:
    for cand in DURATION_MATRIX_READ_KEYS:
        if cand not in data:
            continue
        mat = np.asarray(data[cand], dtype=float)
        if mat.shape != (n, n):
            raise ValueError(f"matrix {cand!r} must be ({n}, {n})")
        return [[int(np.rint(float(mat[i, j]))) for j in range(n)] for i in range(n)]
    return None
