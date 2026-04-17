"""Google OR-Tools routing: canonical :class:`~vrp_model.core.model.Model` adapter."""

from __future__ import annotations

import time
from typing import Any

from vrp_model.core.errors import SolverNotInstalledError
from vrp_model.core.kinds import NodeKind
from vrp_model.core.model import Feature, Model, SolveStatus
from vrp_model.core.solution import Route, Solution
from vrp_model.core.views import Depot, Job, Vehicle
from vrp_model.solvers._helpers import (
    depot_node_ids_ordered,
    empty_instance_solution_status,
    job_node_ids_ordered,
    max_capacity_dims,
)
from vrp_model.solvers.base import Solver
from vrp_model.solvers.options import TIME_LIMIT
from vrp_model.solvers.ortools.bindings import PyWrapCP
from vrp_model.solvers.ortools.options import (
    FIRST_SOLUTION_STRATEGY,
    LOCAL_SEARCH_METAHEURISTIC,
    FullORToolsSolverOptions,
    merge_ortools_solver_options,
)
from vrp_model.solvers.status import SolutionStatus, SolverStopReason

# OR-Tools transit values must stay within practical int32-friendly range.
ORTOOLS_TRANSIT_CAP = 2_000_000_000


def _clamp_arc(value: int) -> int:
    if value >= ORTOOLS_TRANSIT_CAP:
        return ORTOOLS_TRANSIT_CAP
    if value < 0:
        return 0
    return int(value)


def _build_distance_matrix(model: Model) -> list[list[int]]:
    n = len(model._nodes)
    mat = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            raw = model._directed_travel_distance(i, j)
            mat[i][j] = _clamp_arc(raw)
    return mat


def _build_duration_leg_matrix(model: Model) -> list[list[int]]:
    n = len(model._nodes)
    mat = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            raw = model._directed_travel_duration(i, j)
            mat[i][j] = _clamp_arc(raw)
    return mat


def _service_at_node(model: Model, node_id: int) -> int:
    row = model._nodes[node_id]
    if row.kind != NodeKind.JOB:
        return 0
    return int(row.as_job().service_time)


def _time_matrix_including_service(model: Model, leg: list[list[int]]) -> list[list[int]]:
    n = len(model._nodes)
    out = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            out[i][j] = leg[i][j] + _service_at_node(model, i)
    return out


def _single_depot_topology(model: Model) -> bool:
    return len(depot_node_ids_ordered(model)) <= 1


def _any_job_requires_skills(model: Model) -> bool:
    for row in model._nodes:
        if row.kind == NodeKind.JOB and bool(row.as_job().skills_required):
            return True
    return False


def _register_matrix_or_vehicle_transits(
    routing: Any,
    manager: Any,
    matrix: list[list[int]],
    model: Model,
    *,
    uniform: bool,
) -> list[int]:
    """Return list of transit callback indices (one per vehicle).

    Uses :meth:`RegisterTransitMatrix` only when a single shared matrix is valid (one depot
    and no job skills). Otherwise registers per-vehicle callbacks (multi-depot routing and/or
    skills via forbidden arcs — ``SetAllowedVehiclesForIndex`` is not reliably exposed for
    Python on all platforms).
    """
    pywrapcp = PyWrapCP
    assert pywrapcp is not None
    nveh = len(model._vehicles)
    depot_ids = frozenset(depot_node_ids_ordered(model))

    if uniform:
        mat_list = [[int(matrix[i][j]) for j in range(len(matrix))] for i in range(len(matrix))]
        shared = int(routing.RegisterTransitMatrix(mat_list))
        return [shared] * nveh

    indices: list[int] = []
    for vi in range(nveh):
        veh = model._vehicles[vi]
        end_n = veh.end_depot_node_id
        if end_n is None:
            end_n = veh.start_depot_node_id
        vskills = veh.skills

        def make_transit(end_depot: int, sk: frozenset[int]) -> object:
            def transit_cb(from_index: int, to_index: int) -> int:
                fn = manager.IndexToNode(from_index)
                tn = manager.IndexToNode(to_index)
                if tn in depot_ids and tn != end_depot:
                    return ORTOOLS_TRANSIT_CAP
                row_t = model._nodes[tn]
                if row_t.kind == NodeKind.JOB:
                    req = row_t.as_job().skills_required
                    if req and not req <= sk:
                        return ORTOOLS_TRANSIT_CAP
                return int(matrix[fn][tn])

            return transit_cb

        idx = int(routing.RegisterTransitCallback(make_transit(end_n, vskills)))
        indices.append(idx)
    return indices


def _needs_time_dimension(model: Model) -> bool:
    for row in model._nodes:
        if row.kind != NodeKind.JOB:
            continue
        jr = row.as_job()
        if jr.service_time > 0:
            return True
        if jr.time_window is not None:
            return True
        flex_j = jr.time_window_flex
        if flex_j is not None and flex_j.has_soft_penalties():
            return True
    if any(v.time_window is not None for v in model._vehicles):
        return True
    if any(v.max_route_time is not None for v in model._vehicles):
        return True
    if any(
        (v.max_route_overtime or 0) > 0 or v.route_overtime_unit_cost != 0 for v in model._vehicles
    ):
        return True
    if any(v.max_slack_time is not None for v in model._vehicles):
        return True
    for v in model._vehicles:
        flex = v.time_window_flex
        if flex is not None and flex.has_soft_penalties():
            return True
    return False


def _needs_distance_span_dimension(model: Model) -> bool:
    return any(v.max_route_distance is not None for v in model._vehicles)


def _route_horizon(model: Model, dist: list[list[int]], time_m: list[list[int]]) -> int:
    h = 1
    for row in model._nodes:
        if row.kind == NodeKind.JOB:
            tw = row.as_job().time_window
            if tw is not None:
                h = max(h, int(tw[1]))
    for v in model._vehicles:
        if v.time_window is not None:
            h = max(h, int(v.time_window[1]))
    for r in dist:
        if r:
            h = max(h, max(r))
    for r in time_m:
        if r:
            h = max(h, max(r))
    for row in model._nodes:
        if row.kind == NodeKind.JOB:
            h += int(row.as_job().service_time)
    return min(max(h, 10_000), ORTOOLS_TRANSIT_CAP)


def _time_slack_max(model: Model, horizon: int) -> int:
    specified = [v.max_slack_time for v in model._vehicles if v.max_slack_time is not None]
    if not specified:
        return min(horizon, ORTOOLS_TRANSIT_CAP)
    return min(max(specified), ORTOOLS_TRANSIT_CAP)


class ORToolsSolver(Solver):
    name = "ortools"
    supported_features = frozenset(
        {
            Feature.CAPACITY,
            Feature.TIME_WINDOWS,
            Feature.PICKUP_DELIVERY,
            Feature.MULTI_DEPOT,
            Feature.HETEROGENEOUS_FLEET,
            Feature.PRIZE_COLLECTING,
            Feature.FLEXIBLE_TIME_WINDOWS,
            Feature.SKILLS,
            Feature.VEHICLE_FIXED_COST,
            Feature.MAX_ROUTE_DISTANCE,
            Feature.MAX_ROUTE_TIME,
            Feature.ROUTE_OVERTIME,
            Feature.MAX_NODE_SLACK,
        },
    )

    def __init__(self, options: dict | None = None) -> None:
        self._options: FullORToolsSolverOptions = merge_ortools_solver_options(options)

    def _run(self, model: Model) -> SolutionStatus:
        if PyWrapCP is None:
            raise SolverNotInstalledError(
                'install the "ortools" extra to use ORToolsSolver',
            )

        job_ids = job_node_ids_ordered(model)
        if not job_ids:
            model._solution = Solution(routes=[])
            st = empty_instance_solution_status(self.name, iterations=0)
            return st

        t0 = time.perf_counter()
        pywrapcp = PyWrapCP

        n = len(model._nodes)
        nveh = len(model._vehicles)
        starts = [int(v.start_depot_node_id) for v in model._vehicles]
        ends: list[int] = []
        for v in model._vehicles:
            e = v.end_depot_node_id
            ends.append(int(e if e is not None else v.start_depot_node_id))

        manager = pywrapcp.RoutingIndexManager(n, nveh, starts, ends)
        routing = pywrapcp.RoutingModel(manager)

        dist_mat = _build_distance_matrix(model)
        leg_dur = _build_duration_leg_matrix(model)
        time_mat = _time_matrix_including_service(model, leg_dur)
        uniform = _single_depot_topology(model) and not _any_job_requires_skills(model)

        dist_cb_indices = _register_matrix_or_vehicle_transits(
            routing,
            manager,
            dist_mat,
            model,
            uniform=uniform,
        )
        for v in range(nveh):
            routing.SetArcCostEvaluatorOfVehicle(dist_cb_indices[v], v)

        for v in range(nveh):
            routing.SetFixedCostOfVehicle(int(model._vehicles[v].fixed_use_cost), v)

        horizon = _route_horizon(model, dist_mat, time_mat)
        need_time = _needs_time_dimension(model)
        need_dist_span = _needs_distance_span_dimension(model)

        if need_dist_span:
            dist_dim_cbs = _register_matrix_or_vehicle_transits(
                routing,
                manager,
                dist_mat,
                model,
                uniform=uniform,
            )
            routing.AddDimensionWithVehicleTransits(
                dist_dim_cbs,
                0,
                horizon,
                True,
                "Distance",
            )
            dist_dim = routing.GetDimensionOrDie("Distance")
            for vi, veh in enumerate(model._vehicles):
                cap_d = veh.max_route_distance
                if cap_d is not None:
                    dist_dim.SetSpanUpperBoundForVehicle(int(cap_d), vi)

        if need_time:
            time_cb_indices = _register_matrix_or_vehicle_transits(
                routing,
                manager,
                time_mat,
                model,
                uniform=uniform,
            )
            slack_max = _time_slack_max(model, horizon)
            routing.AddDimensionWithVehicleTransits(
                time_cb_indices,
                slack_max,
                horizon,
                True,
                "Time",
            )
            time_dim = routing.GetDimensionOrDie("Time")
            for vi, veh in enumerate(model._vehicles):
                cap_t = veh.max_route_time
                if cap_t is None:
                    continue
                extra = int(veh.max_route_overtime) if veh.max_route_overtime is not None else 0
                hard_span = int(cap_t) + max(0, extra)
                hard_span = min(hard_span, ORTOOLS_TRANSIT_CAP)
                time_dim.SetSpanUpperBoundForVehicle(hard_span, vi)

            for vi, veh in enumerate(model._vehicles):
                cap_t = veh.max_route_time
                if cap_t is None:
                    continue
                uc = int(veh.route_overtime_unit_cost)
                if uc > 0:
                    bc = pywrapcp.BoundCost(int(cap_t), uc)
                    time_dim.SetSoftSpanUpperBoundForVehicle(bc, vi)

            for vi, veh in enumerate(model._vehicles):
                tw = veh.time_window
                if tw is not None:
                    a, b = int(tw[0]), int(tw[1])
                    st = routing.Start(vi)
                    en = routing.End(vi)
                    time_dim.CumulVar(st).SetRange(a, b)
                    time_dim.CumulVar(en).SetRange(a, b)

            for node_id, row in enumerate(model._nodes):
                if row.kind != NodeKind.JOB:
                    continue
                jr = row.as_job()
                idx = manager.NodeToIndex(node_id)
                tw = jr.time_window
                if tw is not None:
                    a, b = int(tw[0]), int(tw[1])
                    time_dim.CumulVar(idx).SetRange(a, b)
                else:
                    time_dim.CumulVar(idx).SetRange(0, horizon)

                flex = jr.time_window_flex
                if flex is not None:
                    se = flex.soft_earliest
                    pe = flex.penalty_per_unit_before_soft_earliest
                    if se is not None and (pe or 0) > 0 and pe is not None:
                        time_dim.SetCumulVarSoftLowerBound(idx, int(se), int(pe))
                    sl = flex.soft_latest
                    pl = flex.penalty_per_unit_after_soft_latest
                    if sl is not None and (pl or 0) > 0 and pl is not None:
                        time_dim.SetCumulVarSoftUpperBound(idx, int(sl), int(pl))

            for vi, veh in enumerate(model._vehicles):
                flex = veh.time_window_flex
                if flex is None:
                    continue
                st = routing.Start(vi)
                en = routing.End(vi)
                se = flex.soft_earliest
                pe = flex.penalty_per_unit_before_soft_earliest
                if se is not None and (pe or 0) > 0 and pe is not None:
                    c = int(pe)
                    sb = int(se)
                    time_dim.SetCumulVarSoftLowerBound(st, sb, c)
                    time_dim.SetCumulVarSoftLowerBound(en, sb, c)
                sl = flex.soft_latest
                pl = flex.penalty_per_unit_after_soft_latest
                if sl is not None and (pl or 0) > 0 and pl is not None:
                    c = int(pl)
                    ub = int(sl)
                    time_dim.SetCumulVarSoftUpperBound(st, ub, c)
                    time_dim.SetCumulVarSoftUpperBound(en, ub, c)

        dims = max_capacity_dims(model, min_dims=0)
        if dims > 0 and any(len(v.capacity) > 0 for v in model._vehicles):

            def demand_cb_factory(dim_idx: int) -> object:
                def unary(from_index: int) -> int:
                    node = manager.IndexToNode(from_index)
                    row = model._nodes[node]
                    if row.kind != NodeKind.JOB:
                        return 0
                    dem = row.as_job().demand
                    if dim_idx < len(dem):
                        return int(dem[dim_idx])
                    return 0

                return unary

            for dim_idx in range(dims):
                cb = routing.RegisterUnaryTransitCallback(demand_cb_factory(dim_idx))
                caps = []
                for v in model._vehicles:
                    cap = v.capacity
                    if dim_idx < len(cap):
                        caps.append(int(cap[dim_idx]))
                    else:
                        caps.append(0)
                name = f"Capacity_{dim_idx}"
                routing.AddDimensionWithVehicleCapacity(
                    cb,
                    0,
                    caps,
                    True,
                    name,
                )

        for node_id, row in enumerate(model._nodes):
            if row.kind != NodeKind.JOB:
                continue
            jr = row.as_job()
            if jr.prize is None:
                continue
            idx = manager.NodeToIndex(node_id)
            penalty = int(round(float(jr.prize)))
            routing.AddDisjunction([idx], penalty)

        for pd in model._pickup_deliveries:
            pu = manager.NodeToIndex(pd.pickup_job_node_id)
            dl = manager.NodeToIndex(pd.delivery_job_node_id)
            routing.AddPickupAndDelivery(pu, dl)

        params = pywrapcp.DefaultRoutingSearchParameters()
        opts = self._options
        tl = float(opts[TIME_LIMIT])
        params.time_limit.FromSeconds(int(max(1, round(tl))))

        fss = opts[FIRST_SOLUTION_STRATEGY]
        if isinstance(fss, int):
            params.first_solution_strategy = fss

        ls = opts[LOCAL_SEARCH_METAHEURISTIC]
        if isinstance(ls, int):
            params.local_search_metaheuristic = ls

        assignment = routing.SolveWithParameters(params)
        elapsed = time.perf_counter() - t0

        if assignment is None:
            model._solution = Solution(routes=[])
            return SolutionStatus(
                mapped_status=SolveStatus.INFEASIBLE,
                solver_name=self.name,
                wall_time_seconds=float(elapsed),
                optimality_gap=None,
                solver_reported_cost=0.0,
                stop_reason=SolverStopReason.INFEASIBLE,
                solution_found=False,
                iterations=0,
                error_message=None,
                solver_status="no assignment",
            )

        sol = self._extract_solution(model, manager, routing, assignment)
        model._solution = sol

        objective = float(assignment.ObjectiveValue())
        raw_status = SolveStatus.FEASIBLE
        if routing.status() == 1:  # ROUTING_SUCCESS (optimal)
            raw_status = SolveStatus.OPTIMAL

        stop_reason = SolverStopReason.COMPLETED
        if raw_status == SolveStatus.OPTIMAL:
            stop_reason = SolverStopReason.OPTIMAL
        if elapsed + 1e-6 >= tl:
            stop_reason = SolverStopReason.TIME_LIMIT

        return SolutionStatus(
            mapped_status=raw_status,
            solver_name=self.name,
            wall_time_seconds=float(elapsed),
            optimality_gap=None,
            solver_reported_cost=objective,
            stop_reason=stop_reason,
            solution_found=True,
            iterations=0,
            error_message=None,
            solver_status="optimal" if raw_status == SolveStatus.OPTIMAL else "feasible",
        )

    def _extract_solution(
        self,
        model: Model,
        manager: Any,
        routing: Any,
        assignment: Any,
    ) -> Solution:
        nveh = len(model._vehicles)
        routes_out: list[Route] = []
        for v in range(nveh):
            veh_rec = model._vehicles[v]
            vehicle = Vehicle(model, v)
            start_unified = veh_rec.start_depot_node_id
            end_unified = (
                veh_rec.end_depot_node_id
                if veh_rec.end_depot_node_id is not None
                else veh_rec.start_depot_node_id
            )
            start_depot = Depot(model, start_unified)
            end_depot = Depot(model, end_unified)

            index = routing.Start(v)
            jobs: list[Job] = []
            while not routing.IsEnd(index):
                node = manager.IndexToNode(index)
                row = model._nodes[node]
                if row.kind == NodeKind.JOB:
                    jobs.append(Job(model, node))
                index = assignment.Value(routing.NextVar(index))

            routes_out.append(
                Route(
                    vehicle=vehicle,
                    start_depot=start_depot,
                    end_depot=end_depot,
                    jobs=jobs,
                ),
            )
        return Solution(routes=routes_out)
