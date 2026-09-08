"""PyVRP solver: canonical model ↔ PyVRP ``Model`` in-process."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import cast

from vrp_model.core.errors import MappingError, SolverNotInstalledError
from vrp_model.core.kinds import NodeKind
from vrp_model.core.model import Feature, Model, SolveStatus
from vrp_model.core.solution import Route, Solution
from vrp_model.core.travel_edges import TRAVEL_COST_INF, TravelEdgesMap
from vrp_model.core.views import Depot, Job, Vehicle
from vrp_model.solvers._helpers import (
    depot_node_ids_ordered,
    empty_instance_solution_status,
    is_model_travel_inf,
    job_node_ids_ordered,
    max_capacity_dims,
    pad_vec,
    should_add_explicit_edge,
)
from vrp_model.solvers.base import Solver
from vrp_model.solvers.options import (
    LOG_PATH,
    MISSING_ARC_DISTANCE,
    MISSING_ARC_DURATION,
    MSG,
    OMIT_UNREACHABLE_ARCS,
    SEED,
    TIME_LIMIT,
)
from vrp_model.solvers.pyvrp.bindings import (
    CAP_PAD,
    TW_LATE_DEFAULT,
    HasXY,
    PyVRPMaxRuntime,
    PyVRPModel,
    PyVRPModelLike,
    PyVRPResultLike,
)
from vrp_model.solvers.pyvrp.options import (
    SKILL_INCOMPATIBLE_COST,
    PyVRPSolverOptions,
    merge_pyvrp_solver_options,
)
from vrp_model.solvers.status import SolutionStatus, SolverStopReason
from vrp_model.utils.distance import euclidean_int

_PYVRP_PROGRESS_LOGGER = "pyvrp.ProgressPrinter"


def _pad_capacity(cap: list[int], dims: int) -> list[int]:
    if len(cap) == 0:
        return []
    out = list(cap)
    while len(out) < dims:
        out.append(CAP_PAD)
    return out[:dims]


def _pyvrp_location_unified_ids(model: Model) -> list[int]:
    """Map PyVRP location index -> unified node id.

    Order matches PyVRP: depots (ascending node id), then jobs (ascending node id).
    """
    dep = depot_node_ids_ordered(model)
    jobs = job_node_ids_ordered(model)
    return dep + jobs


def _export_name(label: str | None, idx: int, prefix: str) -> str:
    if label is not None:
        return label
    return f"{prefix}_{idx}"


def _coords(node: object) -> tuple[float, float]:
    n = cast(HasXY, node)
    return (float(n.x), float(n.y))


def _euclidean_leg(solver_node_for_id: list[object], i: int, j: int) -> tuple[int, int]:
    dist = euclidean_int(_coords(solver_node_for_id[i]), _coords(solver_node_for_id[j]))
    return dist, dist


def _any_job_requires_skills(model: Model) -> bool:
    for row in model._nodes:
        if row.kind == NodeKind.JOB and bool(row.as_job().skills_required):
            return True
    return False


def _profile_name_for_skills(skills: frozenset[int]) -> str:
    if not skills:
        return "skills_none"
    return "skills_" + "_".join(str(s) for s in sorted(skills))


def _build_skill_profiles(
    pm: PyVRPModelLike,
    model: Model,
) -> dict[frozenset[int], object]:
    """One PyVRP routing profile per unique vehicle skill set."""
    profiles: dict[frozenset[int], object] = {}
    for veh in model._vehicles:
        sk = veh.skills
        if sk not in profiles:
            profiles[sk] = pm.add_profile(name=_profile_name_for_skills(sk))
    return profiles


def _edge_component(
    value: int | None,
    *,
    missing: int,
) -> int:
    if value is None or is_model_travel_inf(value):
        return missing
    return int(value)


def _pyvrp_missing_value(opts: PyVRPSolverOptions) -> int:
    """PyVRP ``missing_value`` for omitted edges.

    Uses distance override when set, else duration, else the canonical sentinel.
    """
    dist = opts.get(MISSING_ARC_DISTANCE)
    if dist is not None:
        return dist
    dur = opts.get(MISSING_ARC_DURATION)
    if dur is not None:
        return dur
    return TRAVEL_COST_INF


def _add_resolved_edges(
    pm: PyVRPModelLike,
    model: Model,
    solver_node_for_id: list[object],
    travel_edges: TravelEdgesMap,
    n: int,
    *,
    use_euclidean: bool,
    missing_distance: int,
    missing_duration: int,
    omit_unreachable: bool,
) -> None:
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if not should_add_explicit_edge(model, i, j, omit_unreachable=omit_unreachable):
                continue
            entry = travel_edges.get((i, j))
            if entry is not None:
                d = _edge_component(entry.distance, missing=missing_distance)
                t = _edge_component(entry.duration, missing=missing_duration)
            elif use_euclidean:
                d, t = _euclidean_leg(solver_node_for_id, i, j)
            else:
                d, t = missing_distance, missing_duration
            pm.add_edge(solver_node_for_id[i], solver_node_for_id[j], d, t)


def _add_skill_profile_edges(
    pm: PyVRPModelLike,
    solver_node_for_id: list[object],
    model: Model,
    profiles_by_skills: dict[frozenset[int], object],
    *,
    blocked_cost: int,
) -> None:
    """Profile-specific overrides: prohibit arcs into jobs a profile's vehicles cannot serve."""
    n_nodes = len(model._nodes)
    location_nodes: list[object] = []
    for i in range(n_nodes):
        sn = solver_node_for_id[i]
        if sn is not None:
            location_nodes.append(sn)

    for vskills, profile in profiles_by_skills.items():
        for j in range(n_nodes):
            row = model._nodes[j]
            if row.kind != NodeKind.JOB:
                continue
            req = row.as_job().skills_required
            if not req or req <= vskills:
                continue
            to_obj = solver_node_for_id[j]
            if to_obj is None:
                msg = "internal error: job node missing PyVRP object for skill edges"
                raise RuntimeError(msg)
            for frm in location_nodes:
                if frm is to_obj:
                    continue
                pm.add_edge(
                    frm,
                    to_obj,
                    blocked_cost,
                    blocked_cost,
                    profile=profile,
                )


class PyVRPSolver(Solver):
    name = "pyvrp"
    supported_features = frozenset(
        {
            Feature.CAPACITY,
            Feature.TIME_WINDOWS,
            Feature.PICKUP_DELIVERY,
            Feature.MULTI_DEPOT,
            Feature.HETEROGENEOUS_FLEET,
            Feature.PRIZE_COLLECTING,
            Feature.VEHICLE_FIXED_COST,
            Feature.MAX_ROUTE_DISTANCE,
            Feature.MAX_ROUTE_TIME,
            Feature.ROUTE_OVERTIME,
            Feature.JOB_GROUPS,
            Feature.SKILLS,
        },
    )

    def __init__(self, options: dict | None = None) -> None:
        self._options: PyVRPSolverOptions = merge_pyvrp_solver_options(options)

    def build_solver_model(self, model: Model) -> PyVRPModelLike:
        """Build PyVRP model from canonical ``model``. Read-only on ``self``."""
        pmc = PyVRPModel
        if pmc is None:
            raise SolverNotInstalledError('install the "pyvrp" extra to use PyVRPSolver')

        dims = max_capacity_dims(model, min_dims=1)
        pickup_ids = {pd.pickup_job_node_id for pd in model._pickup_deliveries}
        delivery_ids = {pd.delivery_job_node_id for pd in model._pickup_deliveries}

        pm = cast(PyVRPModelLike, pmc())
        syn_i = 0

        def xy_for_row(loc: tuple[float, float] | None) -> tuple[float, float]:
            nonlocal syn_i
            if loc is not None:
                return (float(loc[0]), float(loc[1]))
            p = (float(syn_i), 0.0)
            syn_i += 1
            return p

        n_nodes = len(model._nodes)
        solver_node_for_id: list[object | None] = [None] * n_nodes

        pyvrp_group_for_job: dict[int, object] = {}
        for grec in model._job_groups:
            cg = pm.add_client_group(required=grec.skip_penalty is None)
            for nid in grec.member_job_node_ids:
                pyvrp_group_for_job[int(nid)] = cg

        for i in range(n_nodes):
            row = model._nodes[i]
            if row.kind != NodeKind.DEPOT:
                continue
            x, y = xy_for_row(row.location)
            name = _export_name(row.label, i, "depot")
            d_obj = pm.add_depot(x, y, name=name)
            solver_node_for_id[i] = d_obj

        for i in range(n_nodes):
            row = model._nodes[i]
            if row.kind != NodeKind.JOB:
                continue
            job = row.as_job()
            dem = pad_vec(job.demand, dims)
            if i in pickup_ids:
                delivery: list[int] = [0] * dims
                pickup = dem
            elif i in delivery_ids:
                delivery = dem
                pickup = [0] * dims
            else:
                delivery = dem
                pickup = [0] * dims

            x, y = xy_for_row(job.location)
            tw = job.time_window
            tw_early = int(tw[0]) if tw is not None else 0
            tw_late = int(tw[1]) if tw is not None else TW_LATE_DEFAULT
            grp = pyvrp_group_for_job.get(i)
            if grp is not None:
                prize = 0
                required = False
                client_kw: dict[str, object] = {"group": grp}
            else:
                prize_raw = job.prize
                if prize_raw is not None:
                    prize = int(round(float(prize_raw)))
                    required = False
                else:
                    prize = 0
                    required = True
                client_kw = {}

            name = _export_name(job.label, i, "job")
            c_obj = pm.add_client(
                x,
                y,
                delivery=delivery,
                pickup=pickup,
                service_duration=int(job.service_time),
                tw_early=tw_early,
                tw_late=tw_late,
                prize=prize,
                required=required,
                name=name,
                **client_kw,
            )
            solver_node_for_id[i] = c_obj

        nodes_for_edges: list[object] = [sn for sn in solver_node_for_id if sn is not None]
        if len(nodes_for_edges) != n_nodes:
            msg = "internal error: missing PyVRP node for some model node"
            raise RuntimeError(msg)

        use_euclidean = len(model._travel_edges) == 0
        nodes_resolved = cast(list[object], solver_node_for_id)
        use_skill_profiles = _any_job_requires_skills(model)
        profiles_by_skills: dict[frozenset[int], object] = {}
        if use_skill_profiles:
            profiles_by_skills = _build_skill_profiles(pm, model)

        opts = self._options
        missing_d = int(opts.get(MISSING_ARC_DISTANCE) or TRAVEL_COST_INF)
        missing_t = int(opts.get(MISSING_ARC_DURATION) or TRAVEL_COST_INF)
        omit_unreachable = bool(opts.get(OMIT_UNREACHABLE_ARCS, False))
        _add_resolved_edges(
            pm,
            model,
            nodes_resolved,
            model._travel_edges,
            n_nodes,
            use_euclidean=use_euclidean,
            missing_distance=missing_d,
            missing_duration=missing_t,
            omit_unreachable=omit_unreachable,
        )
        if use_skill_profiles:
            blocked = int(self._options[SKILL_INCOMPATIBLE_COST])
            _add_skill_profile_edges(
                pm,
                nodes_resolved,
                model,
                profiles_by_skills,
                blocked_cost=blocked,
            )

        for vi, vehicle in enumerate(model._vehicles):
            sd_nid = vehicle.start_depot_node_id
            end_nid_raw = vehicle.end_depot_node_id
            ed_nid = end_nid_raw if end_nid_raw is not None else sd_nid
            sd_obj = solver_node_for_id[sd_nid]
            ed_obj = solver_node_for_id[ed_nid]
            if sd_obj is None or ed_obj is None:
                msg = "internal error: vehicle depot node missing PyVRP object"
                raise RuntimeError(msg)
            cap = _pad_capacity(vehicle.capacity, dims)
            vtw = vehicle.time_window
            tw_early = int(vtw[0]) if vtw is not None else 0
            tw_late = int(vtw[1]) if vtw is not None else TW_LATE_DEFAULT
            vname = _export_name(vehicle.label, vi, "vehicle")
            vt_kwargs: dict[str, object] = {
                "num_available": 1,
                "capacity": cap,
                "start_depot": sd_obj,
                "end_depot": ed_obj,
                "fixed_cost": int(vehicle.fixed_use_cost),
                "tw_early": tw_early,
                "tw_late": tw_late,
                "name": vname,
            }
            mrd = vehicle.max_route_distance
            if mrd is not None:
                vt_kwargs["max_distance"] = int(mrd)
            mrt = vehicle.max_route_time
            if mrt is not None:
                vt_kwargs["shift_duration"] = int(mrt)
                extra = vehicle.max_route_overtime
                vt_kwargs["max_overtime"] = int(extra) if extra is not None else 0
                vt_kwargs["unit_overtime_cost"] = int(vehicle.route_overtime_unit_cost)
            if use_skill_profiles:
                vt_kwargs["profile"] = profiles_by_skills[vehicle.skills]
            pm.add_vehicle_type(**vt_kwargs)

        return pm

    def call_solver(self, pm: PyVRPModelLike) -> PyVRPResultLike:
        """Run PyVRP search using ``self._options`` (set in ``__init__``)."""
        if PyVRPMaxRuntime is None:
            raise SolverNotInstalledError('install the "pyvrp" extra to use PyVRPSolver')

        opts = self._options
        max_rt = float(opts[TIME_LIMIT])
        seed = int(opts[SEED])
        msg = bool(opts[MSG])
        log_path_raw = opts.get(LOG_PATH)
        pyvrp_display = msg or log_path_raw is not None

        stop = PyVRPMaxRuntime(max_rt)
        handler: logging.Handler | None = None
        progress_log = logging.getLogger(_PYVRP_PROGRESS_LOGGER)
        if log_path_raw is not None:
            path = Path(str(log_path_raw))
            path.parent.mkdir(parents=True, exist_ok=True)
            handler = logging.FileHandler(path, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(message)s"))
            progress_log.addHandler(handler)
            progress_log.setLevel(logging.INFO)

        missing_value: int | None = None
        if bool(opts.get(OMIT_UNREACHABLE_ARCS, False)):
            missing_value = _pyvrp_missing_value(opts)

        try:
            if missing_value is None:
                raw = pm.solve(stop, seed=seed, display=pyvrp_display)
            else:
                raw = pm.solve(
                    stop,
                    seed=seed,
                    display=pyvrp_display,
                    missing_value=missing_value,
                )
        finally:
            if handler is not None:
                progress_log.removeHandler(handler)
                handler.close()

        return cast(PyVRPResultLike, raw)

    def find_solution_values(self, model: Model, result: PyVRPResultLike) -> Solution:
        """Map PyVRP result to canonical solution. Read-only on ``self``."""
        best = result.best
        routes_out: list[Route] = []

        depot_ids = depot_node_ids_ordered(model)
        loc_order = _pyvrp_location_unified_ids(model)
        n_depot_py = len(depot_ids)
        n_locs = len(loc_order)

        for rt in best.routes():
            vidx = rt.vehicle_type()
            if vidx < 0 or vidx >= len(model._vehicles):
                raise MappingError("vehicle_type index out of range in PyVRP solution")

            sdi = rt.start_depot()
            edi = rt.end_depot()
            if sdi < 0 or sdi >= n_depot_py:
                raise MappingError("start_depot index out of range in PyVRP solution")
            if edi < 0 or edi >= n_depot_py:
                raise MappingError("end_depot index out of range in PyVRP solution")

            start_unified = depot_ids[sdi]
            end_unified = depot_ids[edi]

            job_seq: list[Job] = []
            for visit in rt.visits():
                if visit < 0 or visit >= n_locs:
                    raise MappingError(f"visit location index {visit!r} out of range")
                uid = loc_order[visit]
                row = model._nodes[uid]
                if row.kind != NodeKind.JOB:
                    continue
                job_seq.append(Job(model, uid))

            routes_out.append(
                Route(
                    vehicle=Vehicle(model, vidx),
                    start_depot=Depot(model, start_unified),
                    end_depot=Depot(model, end_unified),
                    jobs=job_seq,
                ),
            )

        return Solution(routes=routes_out)

    def _run(self, model: Model) -> SolutionStatus:
        job_ids = job_node_ids_ordered(model)
        if not job_ids:
            model._solution = Solution(routes=[])
            return empty_instance_solution_status(self.name, iterations=0)

        if PyVRPModel is None or PyVRPMaxRuntime is None:
            raise SolverNotInstalledError('install the "pyvrp" extra to use PyVRPSolver')

        pm = self.build_solver_model(model)
        result = self.call_solver(pm)
        best = result.best
        raw_status = SolveStatus.FEASIBLE if best.is_feasible() else SolveStatus.INFEASIBLE
        model._solution = self.find_solution_values(model, result)

        tl = float(self._options[TIME_LIMIT])
        elapsed = float(result.runtime)
        if elapsed + 1e-6 >= tl:
            stop_reason = SolverStopReason.TIME_LIMIT
        elif best.is_feasible():
            stop_reason = SolverStopReason.COMPLETED
        else:
            stop_reason = SolverStopReason.INFEASIBLE

        return SolutionStatus(
            mapped_status=raw_status,
            solver_name=self.name,
            wall_time_seconds=elapsed,
            optimality_gap=None,
            solver_reported_cost=float(result.cost()),
            stop_reason=stop_reason,
            solution_found=True,
            iterations=int(result.num_iterations),
            error_message=None,
            solver_status=result.summary(),
        )
