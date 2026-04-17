"""VROOM (pyvroom) solver: canonical model ↔ ``vroom.Input``."""

from __future__ import annotations

import time
from datetime import timedelta
from typing import Any

import numpy as np
import pandas

from vrp_model.core.errors import MappingError, SolverNotInstalledError
from vrp_model.core.kinds import NodeKind
from vrp_model.core.model import Feature, Model, SolveStatus
from vrp_model.core.solution import Route, Solution
from vrp_model.core.travel_edges import TRAVEL_COST_INF
from vrp_model.core.views import Depot, Job, Vehicle
from vrp_model.solvers._helpers import (
    empty_instance_solution_status,
    job_node_ids_ordered,
    max_capacity_dims,
    pad_vec,
)
from vrp_model.solvers.base import Solver
from vrp_model.solvers.options import TIME_LIMIT
from vrp_model.solvers.status import SolutionStatus, SolverStopReason
from vrp_model.solvers.vroom.bindings import VROOM_PROFILE, VROOM_UINT32_MAX, VroomInput
from vrp_model.solvers.vroom.options import (
    EXPLORATION_LEVEL,
    NB_THREADS,
    FullVroomSolverOptions,
    merge_vroom_solver_options,
)


def _clamp_mat(value: int) -> int:
    if value >= TRAVEL_COST_INF:
        return VROOM_UINT32_MAX
    if value < 0:
        return 0
    return min(int(value), VROOM_UINT32_MAX)


def _uint32_matrix_for_pyvroom(mat: np.ndarray) -> np.ndarray:
    """Return a C-contiguous, aligned ``uint32`` matrix for pyvroom's ``_vroom.Matrix``.

    On Linux/macOS, ``numpy.asarray(..., dtype=uint32)`` inside pyvroom can raise
    ``RuntimeError: Incompatible buffer format!`` if the buffer is not strictly
    compatible with NumPy 2 / the extension expectations.
    """
    a = np.ascontiguousarray(mat, dtype=np.uint32)
    return np.require(a, dtype=np.uint32, requirements=["C"])


def _build_duration_matrix(model: Model) -> np.ndarray:
    n = len(model._nodes)
    mat = np.zeros((n, n), dtype=np.uint32, order="C")
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            raw = model._directed_travel_duration(i, j)
            mat[i, j] = _clamp_mat(raw)
    return _uint32_matrix_for_pyvroom(mat)


def _build_distance_matrix(model: Model) -> np.ndarray:
    n = len(model._nodes)
    mat = np.zeros((n, n), dtype=np.uint32, order="C")
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            raw = model._directed_travel_distance(i, j)
            mat[i, j] = _clamp_mat(raw)
    return _uint32_matrix_for_pyvroom(mat)


def _pyvroom_input_solve(
    inp: Any,
    exploration_level: int,
    nb_threads: int,
    timeout: timedelta | None,
) -> Any:
    """Run pyvroom ``Input`` optimization.

    pyvroom 1.15.0's :meth:`vroom.Input.solve` validates ``timeout`` with
    ``isinstance(..., (None, timedelta))``, which raises :exc:`TypeError` on
    Python 3.12+. Replicate :meth:`~vroom.Input.solve` via :meth:`_solve`.
    """
    from vroom.solution.solution import Solution as PyvroomSolution

    sol = PyvroomSolution(
        inp._solve(
            exploration_level=int(exploration_level),
            nb_threads=int(nb_threads),
            timeout=timeout,
        ),
    )
    sol._geometry = inp._geometry
    sol._distances = inp._distances
    return sol


class VroomSolver(Solver):
    name = "vroom"
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
        self._options: FullVroomSolverOptions = merge_vroom_solver_options(options)

    def _run(self, model: Model) -> SolutionStatus:
        if VroomInput is None:
            raise SolverNotInstalledError('install the "vroom" extra to use VroomSolver')

        job_ids = job_node_ids_ordered(model)
        if not job_ids:
            model._solution = Solution(routes=[])
            return empty_instance_solution_status(self.name)

        t0 = time.perf_counter()
        try:
            inp = VroomInput()
            dur = _build_duration_matrix(model)
            dist = _build_distance_matrix(model)
            inp.set_durations_matrix(VROOM_PROFILE, dur)
            inp.set_distances_matrix(VROOM_PROFILE, dist)
        except RuntimeError as exc:
            raise SolverNotInstalledError(
                "pyvroom failed to load travel matrices "
                "(try NumPy<2 with pyvroom on some platforms)",
            ) from exc

        import vroom
        from vroom.time_window import TimeWindow as VroomTimeWindow

        dims = max_capacity_dims(model, min_dims=1)
        pd_pickups = {p.pickup_job_node_id for p in model._pickup_deliveries}
        pd_deliveries = {p.delivery_job_node_id for p in model._pickup_deliveries}
        in_pd = pd_pickups | pd_deliveries

        jobs_payload: list[object] = []
        for pair in model._pickup_deliveries:
            pu_id = pair.pickup_job_node_id
            dl_id = pair.delivery_job_node_id
            pu_row = model._nodes[pu_id].as_job()
            dl_row = model._nodes[dl_id].as_job()
            amt = pad_vec(pu_row.demand, dims)
            skills = set(pu_row.skills_required) | set(dl_row.skills_required)
            pickup_step = vroom.ShipmentStep(
                pu_id,
                pu_id,
                default_service=int(pu_row.service_time),
                time_windows=_vroom_tws(pu_row.time_window),
            )
            delivery_step = vroom.ShipmentStep(
                dl_id,
                dl_id,
                default_service=int(dl_row.service_time),
                time_windows=_vroom_tws(dl_row.time_window),
            )
            jobs_payload.append(
                vroom.Shipment(
                    pickup_step,
                    delivery_step,
                    amount=vroom.Amount(amt),
                    skills=skills,
                ),
            )

        for nid in job_ids:
            if nid in in_pd:
                continue
            row = model._nodes[nid].as_job()
            dem = pad_vec(row.demand, dims)
            tws = _vroom_tws(row.time_window)
            jobs_payload.append(
                vroom.Job(
                    nid,
                    nid,
                    default_service=int(row.service_time),
                    delivery=vroom.Amount(dem),
                    pickup=vroom.Amount([0] * dims),
                    skills=set(row.skills_required),
                    time_windows=tws,
                ),
            )

        inp.add_job(jobs_payload)

        for vi, veh in enumerate(model._vehicles):
            sd = veh.start_depot_node_id
            ed = veh.end_depot_node_id if veh.end_depot_node_id is not None else sd
            cap = pad_vec(list(veh.capacity), dims)
            if not cap:
                cap = [0] * dims
            vtw = veh.time_window
            tw = None if vtw is None else VroomTimeWindow(int(vtw[0]), int(vtw[1]))
            max_travel_time = int(veh.max_route_time) if veh.max_route_time is not None else None
            max_distance = (
                int(veh.max_route_distance) if veh.max_route_distance is not None else None
            )
            inp.add_vehicle(
                vroom.Vehicle(
                    id=vi,
                    start=sd,
                    end=ed,
                    capacity=vroom.Amount(cap),
                    skills=set(veh.skills),
                    time_window=tw,
                    costs=vroom.VehicleCosts(fixed=int(veh.fixed_use_cost)),
                    max_travel_time=max_travel_time,
                    max_distance=max_distance,
                ),
            )

        opts = self._options
        exploration = int(opts[EXPLORATION_LEVEL])
        nb_threads = int(opts[NB_THREADS])
        tl = float(opts[TIME_LIMIT])
        timeout = timedelta(seconds=tl) if tl > 0 else None

        try:
            sol = _pyvroom_input_solve(
                inp,
                exploration_level=exploration,
                nb_threads=nb_threads,
                timeout=timeout,
            )
        except KeyboardInterrupt:
            raise
        except Exception as exc:  # pragma: no cover - backend-specific
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
        routes_df = sol.routes
        # Coerce vehicle ids: pyvroom's DataFrame may use uint32/float/string per OS;
        # strict ``== vi`` can yield empty slices on Linux/macOS so routes look empty.
        vehicle_ids = pandas.to_numeric(routes_df["vehicle_id"], errors="coerce")
        routes_out: list[Route] = []
        for vi in range(len(model._vehicles)):
            sub = routes_df.loc[vehicle_ids == vi].reset_index(drop=True)
            if sub.empty:
                veh = model._vehicles[vi]
                sd = veh.start_depot_node_id
                ed = veh.end_depot_node_id if veh.end_depot_node_id is not None else sd
                routes_out.append(
                    Route(
                        vehicle=Vehicle(model, vi),
                        start_depot=Depot(model, sd),
                        end_depot=Depot(model, ed),
                        jobs=[],
                    ),
                )
                continue
            step_kind = sub["type"].astype(str)
            start_unified = int(sub.loc[step_kind == "start", "location_index"].iloc[0])
            end_unified = int(sub.loc[step_kind == "end", "location_index"].iloc[0])
            steps = sub.loc[step_kind.isin(["job", "pickup", "delivery"])]
            job_seq: list[Job] = []
            for raw_id in steps["id"]:
                if raw_id is None or pandas.isna(raw_id):
                    continue
                jid = int(raw_id)
                row = model._nodes[jid]
                if row.kind != NodeKind.JOB:
                    raise MappingError(f"VROOM step id {jid} is not a job node")
                job_seq.append(Job(model, jid))
            routes_out.append(
                Route(
                    vehicle=Vehicle(model, vi),
                    start_depot=Depot(model, start_unified),
                    end_depot=Depot(model, end_unified),
                    jobs=job_seq,
                ),
            )

        model._solution = Solution(routes=routes_out)
        sol_dict: dict[str, Any] = sol.to_dict()
        summary = sol_dict.get("summary") or {}
        code = int(sol_dict.get("code", 0))
        cost_raw = summary.get("cost")
        cost = float(cost_raw) if cost_raw is not None else None
        mandatory_unassigned = len(model.mandatory_unassigned_jobs())
        feasible = code == 0 and mandatory_unassigned == 0 and bool(model.is_solution_feasible())
        mapped = SolveStatus.FEASIBLE if feasible else SolveStatus.INFEASIBLE
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
            solver_reported_cost=cost,
            stop_reason=stop,
            solution_found=True,
            iterations=None,
            error_message=None,
            solver_status=str(summary),
        )


def _vroom_tws(tw: tuple[int, int] | None) -> list:
    from vroom.time_window import TimeWindow as VroomTimeWindow

    if tw is None:
        return []
    return [VroomTimeWindow(int(tw[0]), int(tw[1]))]
