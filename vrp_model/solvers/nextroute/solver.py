"""Nextmv Nextroute solver (``nextroute`` Python package)."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from vrp_model.core.errors import SolverNotInstalledError
from vrp_model.core.kinds import NodeKind
from vrp_model.core.model import Feature, Model, SolveStatus
from vrp_model.core.records import JobNodeRecord
from vrp_model.core.solution import Route, Solution
from vrp_model.core.travel_edges import TRAVEL_COST_INF
from vrp_model.core.views import Depot, Job, Vehicle
from vrp_model.solvers.base import Solver
from vrp_model.solvers.nextroute.bindings import (
    NextrouteInput,
    nextroute_solve,
)
from vrp_model.solvers.nextroute.options import (
    DEFAULT_SPEED_MPS,
    TIME_ANCHOR,
    build_nextroute_engine_options,
    merge_nextroute_solver_options,
)
from vrp_model.solvers.options import TIME_LIMIT
from vrp_model.solvers.status import SolutionStatus, SolverStopReason

_STOP_PREFIX = "j"
_MATRIX_INF = 1e12


def _job_node_ids_ordered(model: Model) -> list[int]:
    return [i for i, row in enumerate(model._nodes) if row.kind == NodeKind.JOB]


def _max_capacity_dims(model: Model) -> int:
    d = 0
    for v in model._vehicles:
        d = max(d, len(v.capacity))
    for row in model._nodes:
        if row.kind == NodeKind.JOB:
            d = max(d, len(cast(JobNodeRecord, row).demand))
    return max(d, 1)


def _pad_vec(vec: list[int], dims: int) -> list[int]:
    out = list(vec)
    while len(out) < dims:
        out.append(0)
    return out[:dims]


def _resource_key(i: int) -> str:
    return f"d{i}"


def _lon_lat_for_node(model: Model, node_id: int) -> tuple[float, float]:
    loc = model._nodes[node_id].location
    if loc is not None:
        return (float(loc[0]), float(loc[1]))
    step = float(node_id) * 1e-4 + 1e-3
    return (step, step)


def _sec_to_dt(anchor: datetime, sec: int) -> datetime:
    return anchor + timedelta(seconds=int(sec))


def _tw_to_iso_pair(anchor: datetime, tw: tuple[int, int]) -> list[str]:
    a, b = tw
    return [_sec_to_dt(anchor, a).isoformat(), _sec_to_dt(anchor, b).isoformat()]


def _decode_stop_id(stop_id: str) -> int | None:
    if not stop_id.startswith(_STOP_PREFIX):
        return None
    tail = stop_id[len(_STOP_PREFIX) :]
    if not tail.isdigit():
        return None
    return int(tail)


def _leg_seconds(model: Model, u: int, v: int) -> float:
    if u == v:
        return 0.0
    raw = model._directed_travel_duration(u, v)
    if raw >= TRAVEL_COST_INF:
        return _MATRIX_INF
    return float(raw)


def _leg_meters(model: Model, u: int, v: int) -> float:
    if u == v:
        return 0.0
    raw = model._directed_travel_distance(u, v)
    if raw >= TRAVEL_COST_INF:
        return _MATRIX_INF
    return float(raw)


class NextrouteSolver(Solver):
    name = "nextroute"
    supported_features = frozenset(
        {
            Feature.CAPACITY,
            Feature.TIME_WINDOWS,
            Feature.PICKUP_DELIVERY,
            Feature.MULTI_DEPOT,
            Feature.HETEROGENEOUS_FLEET,
            Feature.SKILLS,
            Feature.VEHICLE_FIXED_COST,
            Feature.MAX_ROUTE_DISTANCE,
            Feature.MAX_ROUTE_TIME,
        },
    )

    def __init__(self, options: dict | None = None) -> None:
        self._options = merge_nextroute_solver_options(options)

    def _run(self, model: Model) -> SolutionStatus:
        if NextrouteInput is None or nextroute_solve is None:
            raise SolverNotInstalledError('install the "nextroute" extra to use NextrouteSolver')

        from nextroute import Options as NextrouteOptions

        job_ids = _job_node_ids_ordered(model)
        if not job_ids:
            model._solution = Solution(routes=[])
            return SolutionStatus(
                mapped_status=SolveStatus.FEASIBLE,
                solver_name=self.name,
                wall_time_seconds=0.0,
                optimality_gap=None,
                solver_reported_cost=0.0,
                stop_reason=SolverStopReason.COMPLETED,
                solution_found=True,
                iterations=None,
                error_message=None,
                solver_status="",
            )

        opts = self._options
        anchor_raw = opts[TIME_ANCHOR]
        if isinstance(anchor_raw, datetime):
            anchor = anchor_raw if anchor_raw.tzinfo else anchor_raw.replace(tzinfo=UTC)
        else:
            anchor = datetime.fromisoformat(str(anchor_raw).replace("Z", "+00:00"))
        speed = float(opts.get("speed_mps", DEFAULT_SPEED_MPS))

        dims = _max_capacity_dims(model)
        n = len(job_ids)
        m = len(model._vehicles)
        dim_m = n + 2 * m

        def entity_node(matrix_idx: int) -> int:
            if matrix_idx < n:
                return job_ids[matrix_idx]
            pair = matrix_idx - n
            vi = pair // 2
            if pair % 2 == 0:
                return model._vehicles[vi].start_depot_node_id
            end = model._vehicles[vi].end_depot_node_id
            return end if end is not None else model._vehicles[vi].start_depot_node_id

        dur_mat: list[list[float]] = [[0.0] * dim_m for _ in range(dim_m)]
        dist_mat: list[list[float]] = [[0.0] * dim_m for _ in range(dim_m)]
        for i in range(dim_m):
            for j in range(dim_m):
                if i == j:
                    continue
                u = entity_node(i)
                v = entity_node(j)
                dur_mat[i][j] = _leg_seconds(model, u, v)
                dist_mat[i][j] = _leg_meters(model, u, v)

        pd_pickups = {p.pickup_job_node_id for p in model._pickup_deliveries}
        precedes_map: dict[int, list[str]] = {}
        for pd in model._pickup_deliveries:
            pu = pd.pickup_job_node_id
            dl = pd.delivery_job_node_id
            precedes_map.setdefault(pu, []).append(f"{_STOP_PREFIX}{dl}")

        stops_payload: list[dict[str, Any]] = []
        for jid in job_ids:
            row = cast(JobNodeRecord, model._nodes[jid])
            dem = _pad_vec(row.demand, dims)
            q: dict[str, int] = {}
            for i, qv in enumerate(dem):
                key = _resource_key(i)
                if jid in pd_pickups:
                    q[key] = 0
                else:
                    q[key] = int(qv)
            lon, lat = _lon_lat_for_node(model, jid)
            stop: dict[str, Any] = {
                "id": f"{_STOP_PREFIX}{jid}",
                "location": {"lon": lon, "lat": lat},
                "duration": int(row.service_time),
                "quantity": q,
            }
            tw = row.time_window
            if tw is not None:
                stop["start_time_window"] = _tw_to_iso_pair(anchor, tw)
            skills = [str(s) for s in sorted(row.skills_required)]
            if skills:
                stop["compatibility_attributes"] = skills
            if jid in precedes_map:
                stop["precedes"] = precedes_map[jid]
            stops_payload.append(stop)

        vehicles_payload: list[dict[str, Any]] = []
        for vi, veh in enumerate(model._vehicles):
            cap = _pad_vec(list(veh.capacity), dims)
            cap_d = {_resource_key(i): int(c) for i, c in enumerate(cap)}
            start_lvl = {_resource_key(i): int(c) for i, c in enumerate(cap)}
            slon, slat = _lon_lat_for_node(model, veh.start_depot_node_id)
            end_nid = veh.end_depot_node_id
            if end_nid is None:
                end_nid = veh.start_depot_node_id
            elon, elat = _lon_lat_for_node(model, end_nid)
            vdict: dict[str, Any] = {
                "id": str(vi),
                "start_location": {"lon": slon, "lat": slat},
                "end_location": {"lon": elon, "lat": elat},
                "capacity": cap_d,
                "start_level": start_lvl,
                "speed": speed,
            }
            vtw = veh.time_window
            if vtw is not None:
                vdict["start_time"] = _sec_to_dt(anchor, vtw[0]).isoformat()
                vdict["end_time"] = _sec_to_dt(anchor, vtw[1]).isoformat()
            if veh.fixed_use_cost > 0:
                vdict["activation_penalty"] = int(veh.fixed_use_cost)
            if veh.max_route_time is not None:
                vdict["max_duration"] = int(veh.max_route_time)
            if veh.max_route_distance is not None:
                vdict["max_distance"] = int(veh.max_route_distance)
            vskills = [str(s) for s in sorted(veh.skills)]
            if vskills:
                vdict["compatibility_attributes"] = vskills
            vehicles_payload.append(vdict)

        inp_dict: dict[str, Any] = {
            "stops": stops_payload,
            "vehicles": vehicles_payload,
            "duration_matrix": dur_mat,
            "distance_matrix": dist_mat,
        }

        inp = NextrouteInput.model_validate(inp_dict)
        engine_opts = build_nextroute_engine_options(opts, NextrouteOptions)

        t0 = time.perf_counter()
        try:
            out = nextroute_solve(inp, engine_opts)
        except Exception as exc:  # pragma: no cover - subprocess errors
            return SolutionStatus(
                mapped_status=SolveStatus.UNKNOWN,
                solver_name=self.name,
                wall_time_seconds=time.perf_counter() - t0,
                optimality_gap=None,
                solver_reported_cost=None,
                stop_reason=SolverStopReason.ERROR,
                solution_found=False,
                iterations=None,
                error_message=str(exc),
                solver_status="",
            )

        elapsed = time.perf_counter() - t0
        solutions = out.solutions or []
        if not solutions:
            model._solution = Solution(routes=[])
            return SolutionStatus(
                mapped_status=SolveStatus.UNKNOWN,
                solver_name=self.name,
                wall_time_seconds=elapsed,
                optimality_gap=None,
                solver_reported_cost=None,
                stop_reason=SolverStopReason.UNKNOWN,
                solution_found=False,
                iterations=None,
                error_message="no solution returned",
                solver_status="",
            )

        sol0 = solutions[0]
        veh_out = sol0.vehicles or []
        routes_out: list[Route] = []
        by_id = {v.id: v for v in veh_out}
        for vi in range(len(model._vehicles)):
            vo = by_id.get(str(vi))
            veh_rec = model._vehicles[vi]
            sd = veh_rec.start_depot_node_id
            ed = veh_rec.end_depot_node_id if veh_rec.end_depot_node_id is not None else sd
            jobs_seq: list[Job] = []
            if vo is not None and vo.route:
                for step in vo.route:
                    sid = step.stop.id
                    jid = _decode_stop_id(sid)
                    if jid is None:
                        continue
                    if model._nodes[jid].kind != NodeKind.JOB:
                        continue
                    jobs_seq.append(Job(model, jid))
            routes_out.append(
                Route(
                    vehicle=Vehicle(model, vi),
                    start_depot=Depot(model, sd),
                    end_depot=Depot(model, ed),
                    jobs=jobs_seq,
                ),
            )

        model._solution = Solution(routes=routes_out)
        obj_val = None
        if sol0.objective is not None and sol0.objective.value is not None:
            obj_val = float(sol0.objective.value)
        feasible = bool(model.is_solution_feasible())
        mapped = SolveStatus.FEASIBLE if feasible else SolveStatus.INFEASIBLE
        tl = float(opts[TIME_LIMIT])
        if elapsed + 1e-6 >= tl and tl > 0:
            stop = SolverStopReason.TIME_LIMIT
        elif feasible:
            stop = SolverStopReason.COMPLETED
        else:
            stop = SolverStopReason.INFEASIBLE

        return SolutionStatus(
            mapped_status=mapped,
            solver_name=self.name,
            wall_time_seconds=elapsed,
            optimality_gap=None,
            solver_reported_cost=obj_val,
            stop_reason=stop,
            solution_found=True,
            iterations=None,
            error_message=None,
            solver_status="",
        )
