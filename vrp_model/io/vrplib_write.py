"""Serialize :class:`~vrp_model.core.model.Model` to VRPLIB dicts or files."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import vrplib

from vrp_model.core.errors import SolutionUnavailableError
from vrp_model.core.kinds import NodeKind
from vrp_model.core.model import Model
from vrp_model.core.solution import Solution
from vrp_model.core.travel_edges import TRAVEL_COST_INF
from vrp_model.io.vrplib_keys import VRPLibReadKey, write_section_key, write_spec_key


def write_vrplib_instance(path: str | Path, model: Model) -> None:
    """Write a ``.vrp``-style instance using :func:`vrplib.write_instance`."""
    vrplib.write_instance(str(path), model_to_vrplib_dict(model))


def write_vrplib_solution(path: str | Path, model: Model) -> None:
    """Write a solution file using :func:`vrplib.write_solution`.

    Requires ``model.solution`` and writes **travel distance** as ``Cost`` (VRPLIB-style
    distance), not the full :meth:`~vrp_model.core.model.Model.solution_cost` objective.
    """
    sol = model.solution
    if sol is None:
        raise SolutionUnavailableError("no solution is attached to this model")
    routes = solution_to_vrplib_routes(sol)
    extra = {"Cost": int(round(float(model.solution_travel_distance())))}
    vrplib.write_solution(str(path), routes, extra)


def solution_to_vrplib_routes(solution: Solution) -> list[list[int]]:
    """VRPLIB routes use 1-based location indices (matching written ``DIMENSION`` rows)."""
    out: list[list[int]] = []
    for route in solution.routes:
        seq = [j.node_id + 1 for j in route.jobs]
        if seq:
            out.append(seq)
    return out


def model_to_vrplib_dict(model: Model) -> dict[str, str | int | float | np.ndarray]:
    """Build a dict for :func:`vrplib.write_instance` from a :class:`Model`.

    Keys and value kinds match :class:`~vrp_model.io.vrplib_types.VRPLibWriteDict`; the return
    type is the concrete ``dict`` accepted by ``vrplib.write_instance``.
    """
    n = len(model._nodes)
    if n == 0:
        return {
            write_spec_key(VRPLibReadKey.NAME): "empty",
            write_spec_key(VRPLibReadKey.DIMENSION): 0,
            write_spec_key(VRPLibReadKey.TYPE): "CVRP",
        }

    demands: list[int] = []
    coords: list[list[float]] = []
    depot_1based: list[int] = []
    has_coord = True
    for i in range(n):
        row = model._nodes[i]
        if row.kind == NodeKind.JOB:
            dem = row.demand
            demands.append(int(dem[0]) if dem else 0)
        else:
            demands.append(0)
        loc = row.location
        if loc is None:
            has_coord = False
            coords.append([0.0, 0.0])
        else:
            coords.append([float(loc[0]), float(loc[1])])
        if row.kind == NodeKind.DEPOT:
            depot_1based.append(i + 1)

    edge_mat: list[list[float]] = [[0.0] * n for _ in range(n)]
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
                edge_mat[i][j] = float(d)
            elif not has_coord:
                edge_mat[i][j] = 0.0
            else:
                dx = coords[i][0] - coords[j][0]
                dy = coords[i][1] - coords[j][1]
                edge_mat[i][j] = float(math.hypot(dx, dy))

    n_veh = len(model._vehicles)
    caps = [v.capacity[0] if v.capacity else 0 for v in model._vehicles]
    cap0 = caps[0] if caps else 0

    tw_rows: list[list[int]] = []
    st_rows: list[int] = []
    has_tw = False
    has_st = False
    for i in range(n):
        row = model._nodes[i]
        if row.kind == NodeKind.JOB:
            tw = row.time_window
            st = row.service_time
        else:
            tw = None
            st = 0
        if tw is not None:
            has_tw = True
            tw_rows.append([int(tw[0]), int(tw[1])])
        else:
            tw_rows.append([0, 0])
        if st != 0:
            has_st = True
        st_rows.append(st)

    # ``vrplib.write_instance`` emits items in dict order; specifications (scalars)
    # must precede all array sections or ``read_instance`` raises.
    out: dict[str, str | int | float | np.ndarray] = {
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
        out[write_section_key(VRPLibReadKey.SERVICE_TIME)] = np.array(
            st_rows, dtype=int
        )
    if len(depot_1based) > 1:
        vdep = [model._vehicles[v].start_depot_node_id + 1 for v in range(n_veh)]
        out[write_section_key(VRPLibReadKey.VEHICLES_DEPOT)] = np.array(vdep, dtype=int)
    if len(set(caps)) > 1 and n_veh > 0:
        out[write_section_key(VRPLibReadKey.CAPACITY_SECTION)] = np.array(
            caps, dtype=int
        )
    out[write_section_key(VRPLibReadKey.DEPOT)] = np.array(depot_1based, dtype=int)
    if use_edges or not has_coord:
        out[write_section_key(VRPLibReadKey.EDGE_WEIGHT)] = np.array(
            edge_mat, dtype=float
        )

    return out
