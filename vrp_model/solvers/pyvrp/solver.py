"""PyVRP solver: canonical model ↔ PyVRP ``ProblemData`` in-process."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from vrp_model.core.errors import MappingError, SolverNotInstalledError
from vrp_model.core.kinds import NodeKind
from vrp_model.core.model import Feature, Model, SolveStatus
from vrp_model.core.solution import Route, Solution
from vrp_model.core.travel_edges import TRAVEL_COST_INF
from vrp_model.core.views import Depot, Job, Vehicle
from vrp_model.solvers._helpers import (
    depot_node_ids_ordered,
    empty_instance_solution_status,
    is_model_travel_inf,
    job_node_ids_ordered,
    max_capacity_dims,
    pad_vec,
    skill_violation_message,
    skill_violations,
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
    PYVRP_MAX_VALUE,
    TW_LATE_DEFAULT,
    PyVRPClient,
    PyVRPClientGroup,
    PyVRPDataLike,
    PyVRPDepot,
    PyVRPLocation,
    PyVRPMaxRuntime,
    PyVRPProblemData,
    PyVRPResultLike,
    PyVRPShipment,
    PyVRPSolve,
    PyVRPVehicleType,
    np,
)
from vrp_model.solvers.pyvrp.options import (
    SKILL_INCOMPATIBLE_COST,
    PyVRPSolverOptions,
    merge_pyvrp_solver_options,
)
from vrp_model.solvers.status import SolutionStatus, SolverStopReason

_PYVRP_PROGRESS_LOGGER = "pyvrp.ProgressPrinter"

Coords = tuple[float, float]

# A routing profile is identified by the job skill requirements its vehicles cannot meet.
ProfileKey = frozenset[frozenset[int]]


def _pad_capacity(cap: list[int], dims: int) -> list[int]:
    if len(cap) == 0:
        return []
    out = list(cap)
    while len(out) < dims:
        out.append(CAP_PAD)
    return out[:dims]


def _shipment_job_node_ids(model: Model) -> set[int]:
    """Job node ids that PyVRP models as shipment steps rather than standalone clients."""
    out: set[int] = set()
    for pd in model._pickup_deliveries:
        out.add(int(pd.pickup_job_node_id))
        out.add(int(pd.delivery_job_node_id))
    return out


def _pyvrp_shipment_unified_ids(model: Model) -> list[tuple[int, int]]:
    """Map PyVRP shipment index -> (pickup node id, delivery node id).

    Order matches PyVRP: pickup-delivery pairs in registration order.
    """
    return [
        (int(pd.pickup_job_node_id), int(pd.delivery_job_node_id))
        for pd in model._pickup_deliveries
    ]


def _pyvrp_client_unified_ids(model: Model) -> list[int]:
    """Map PyVRP client index -> unified node id.

    Order matches PyVRP: jobs (ascending node id) that are not part of a pickup-delivery
    pair, since paired jobs become shipments instead.
    """
    shipment_ids = _shipment_job_node_ids(model)
    return [i for i in job_node_ids_ordered(model) if i not in shipment_ids]


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


# ---------------------------------------------------------------------------------------
# Routing profiles for vehicle-job compatibility
# ---------------------------------------------------------------------------------------


def _distinct_job_requirements(model: Model) -> list[frozenset[int]]:
    """The distinct non-empty ``skills_required`` sets that jobs ask for."""
    seen = {
        row.as_job().skills_required
        for row in model._nodes
        if row.kind == NodeKind.JOB and row.as_job().skills_required
    }
    return sorted(seen, key=sorted)


def _assign_profiles(
    model: Model,
    requirements: list[frozenset[int]],
) -> tuple[list[ProfileKey], list[int]]:
    """Return the profile keys in matrix order, plus each vehicle's profile index.

    A profile is keyed by what its vehicles *cannot* serve rather than by their skill set,
    so vehicles whose skills differ only in ways no job asks about collapse onto one
    profile, and every vehicle able to serve the whole instance lands on the unrestricted
    profile -- which needs no blocked arcs and can share the base matrices outright. PyVRP
    carries two full ``n x n`` int64 matrices per profile, so this keying matters.
    """
    order: list[ProfileKey] = []
    index: dict[ProfileKey, int] = {}
    per_vehicle: list[int] = []
    for veh in model._vehicles:
        key: ProfileKey = frozenset(req for req in requirements if not req <= veh.skills)
        pos = index.get(key)
        if pos is None:
            pos = len(order)
            index[key] = pos
            order.append(key)
        per_vehicle.append(pos)
    return order, per_vehicle


def _blocked_location_indices(
    model: Model,
    blocked: ProfileKey,
    loc_of: list[int],
) -> list[int]:
    """Location indices of the jobs a profile's vehicles may not serve."""
    return [
        loc_of[i]
        for i, row in enumerate(model._nodes)
        if row.kind == NodeKind.JOB and row.as_job().skills_required in blocked
    ]


# ---------------------------------------------------------------------------------------
# Travel matrices
# ---------------------------------------------------------------------------------------


def _edge_component(value: int | None, *, missing: int) -> int:
    if value is None or is_model_travel_inf(value):
        return missing
    return int(value)


def _edge_is_reachable(distance: int | None, duration: int | None) -> bool:
    """Mirror of ``should_add_explicit_edge`` for one stored travel edge."""
    if distance is None or is_model_travel_inf(distance):
        return False
    return duration is not None and not is_model_travel_inf(duration)


@dataclass(frozen=True)
class _ArcFill:
    """Values written into the distance / duration matrices for an arc PyVRP must avoid."""

    distance: int
    duration: int


def _arc_fill(opts: PyVRPSolverOptions, fallback: int) -> _ArcFill:
    """Per-matrix ``MISSING_ARC_*`` override when set, else ``fallback``; capped for PyVRP."""

    def pick(key: str) -> int:
        value = opts.get(key)
        return min(int(cast(int, value) if value is not None else fallback), PYVRP_MAX_VALUE)

    return _ArcFill(pick(MISSING_ARC_DISTANCE), pick(MISSING_ARC_DURATION))


def _euclidean_matrices(coords_by_loc: list[Coords]) -> tuple[Any, Any]:
    """Rounded Euclidean distance/duration matrices over location coordinates."""
    xy = np.asarray(coords_by_loc, dtype=np.float64)
    dx = xy[:, 0, None] - xy[None, :, 0]
    dy = xy[:, 1, None] - xy[None, :, 1]
    dist = np.rint(np.hypot(dx, dy)).astype(np.int64)
    np.fill_diagonal(dist, 0)
    return dist, dist.copy()


def _base_matrices(
    model: Model,
    loc_of: list[int],
    coords_by_loc: list[Coords],
    fill: _ArcFill,
    *,
    omit_unreachable: bool,
) -> tuple[Any, Any]:
    """Build the distance/duration matrices shared by every routing profile.

    Indices are PyVRP location indices: depots (ascending node id), then jobs. Arcs the
    model leaves unreachable get ``fill.distance`` / ``fill.duration``. With
    ``omit_unreachable``, an edge missing either component is dropped whole, so its finite
    half is filled too.
    """
    n = len(coords_by_loc)

    if not model._travel_edges:
        dist, dur = _euclidean_matrices(coords_by_loc)
        if omit_unreachable:
            unreachable = dist >= TRAVEL_COST_INF
            dist[unreachable] = fill.distance
            dur[unreachable] = fill.duration
        return dist, dur

    dist = np.full((n, n), fill.distance, np.int64)
    dur = np.full((n, n), fill.duration, np.int64)
    for (i, j), attrs in model._travel_edges.items():
        if omit_unreachable and not _edge_is_reachable(attrs.distance, attrs.duration):
            continue
        li = loc_of[i]
        lj = loc_of[j]
        dist[li, lj] = _edge_component(attrs.distance, missing=fill.distance)
        dur[li, lj] = _edge_component(attrs.duration, missing=fill.duration)
    np.fill_diagonal(dist, 0)
    np.fill_diagonal(dur, 0)
    return dist, dur


def _profile_matrices(
    model: Model,
    profile_keys: list[ProfileKey],
    loc_of: list[int],
    base_dist: Any,
    base_dur: Any,
    blocked: _ArcFill,
) -> tuple[list[Any], list[Any]]:
    """One distance/duration matrix pair per profile, with incompatible jobs priced out.

    Blocking a whole column prohibits every arc *into* a job the profile's vehicles cannot
    serve, which is enough to keep it out of their routes. The unrestricted profile reuses
    the base matrices rather than copying them.
    """
    if not profile_keys:
        return [base_dist], [base_dur]

    distances: list[Any] = []
    durations: list[Any] = []
    for key in profile_keys:
        if not key:
            distances.append(base_dist)
            durations.append(base_dur)
            continue
        cols = _blocked_location_indices(model, key, loc_of)
        prof_dist = base_dist.copy()
        prof_dur = base_dur.copy()
        prof_dist[:, cols] = blocked.distance
        prof_dur[:, cols] = blocked.duration
        # Column blocking also hits the diagonal, which PyVRP expects to stay zero.
        prof_dist[cols, cols] = 0
        prof_dur[cols, cols] = 0
        distances.append(prof_dist)
        durations.append(prof_dur)
    return distances, durations


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

    def build_solver_model(self, model: Model) -> PyVRPDataLike:
        """Build PyVRP ``ProblemData`` from canonical ``model``. Read-only on ``self``.

        PyVRP's ``Model`` builder is bypassed on purpose: it holds one Python ``Edge`` object
        per arc and per profile override before flattening them into the dense matrices that
        ``ProblemData`` actually wants. Writing those matrices directly keeps the build
        vectorised, which matters most for profile blocking.
        """
        if PyVRPProblemData is None:
            raise SolverNotInstalledError('install the "pyvrp" extra to use PyVRPSolver')

        dims = max_capacity_dims(model, min_dims=1)
        opts = self._options

        depot_ids = depot_node_ids_ordered(model)
        job_ids = job_node_ids_ordered(model)
        n_nodes = len(model._nodes)

        # PyVRP 0.14 separates locations from the depots/clients/shipments placed on them.
        # Locations are created depots-first, then jobs, matching
        # ``_pyvrp_location_unified_ids``; matrix indices are these location indices.
        loc_of: list[int] = [-1] * n_nodes
        coords_by_loc: list[Coords] = []
        locations: list[object] = []
        syn_i = 0

        for prefix, node_ids in (("depot", depot_ids), ("job", job_ids)):
            for i in node_ids:
                row = model._nodes[i]
                if row.location is not None:
                    xy: Coords = (float(row.location[0]), float(row.location[1]))
                else:
                    xy = (float(syn_i), 0.0)
                    syn_i += 1
                loc_of[i] = len(locations)
                coords_by_loc.append(xy)
                locations.append(
                    PyVRPLocation(xy[0], xy[1], name=_export_name(row.label, i, prefix)),
                )

        depots = [
            PyVRPDepot(loc_of[i], name=_export_name(model._nodes[i].label, i, "depot"))
            for i in depot_ids
        ]
        depot_pos = {nid: k for k, nid in enumerate(depot_ids)}

        group_of_job: dict[int, int] = {}
        for gi, grec in enumerate(model._job_groups):
            for nid in grec.member_job_node_ids:
                group_of_job[int(nid)] = gi
        group_members: list[list[int]] = [[] for _ in model._job_groups]

        shipment_ids = _shipment_job_node_ids(model)
        clients: list[object] = []
        for i in job_ids:
            if i in shipment_ids:
                continue
            job = model._nodes[i].as_job()
            tw = job.time_window
            group_idx = group_of_job.get(i)
            if group_idx is not None:
                # The group decides whether the job is served, so the client itself is
                # optional and carries no prize of its own.
                prize = 0
                required = False
                group_members[group_idx].append(len(clients))
            else:
                prize_raw = job.prize
                if prize_raw is not None:
                    prize = int(round(float(prize_raw)))
                    required = False
                else:
                    prize = 0
                    required = True

            clients.append(
                PyVRPClient(
                    loc_of[i],
                    delivery=pad_vec(job.demand, dims),
                    pickup=[0] * dims,
                    service_duration=int(job.service_time),
                    tw_early=int(tw[0]) if tw is not None else 0,
                    tw_late=int(tw[1]) if tw is not None else TW_LATE_DEFAULT,
                    prize=prize,
                    required=required,
                    group=group_idx,
                    name=_export_name(job.label, i, "job"),
                ),
            )

        groups = [
            PyVRPClientGroup(clients=members, required=grec.skip_penalty is None)
            for grec, members in zip(model._job_groups, group_members, strict=True)
        ]

        # Pickup-delivery pairs are shipments in PyVRP 0.14: one load moved between two
        # locations, which enforces precedence and same-vehicle service.
        shipments: list[object] = []
        for pu_id, dl_id in _pyvrp_shipment_unified_ids(model):
            pickup = model._nodes[pu_id].as_job()
            delivery = model._nodes[dl_id].as_job()
            amount = pad_vec(pickup.demand, dims)
            if not any(amount):
                amount = pad_vec(delivery.demand, dims)
            pu_tw = pickup.time_window
            dl_tw = delivery.time_window
            prizes = [j.prize for j in (pickup, delivery)]
            # A pair may only be skipped when both of its jobs are optional; see
            # ``Model._pickup_delivery_pairs_valid``.
            required = any(p is None for p in prizes)
            prize = 0 if required else sum(int(round(float(p))) for p in prizes if p is not None)
            pu_name = _export_name(pickup.label, pu_id, "job")
            dl_name = _export_name(delivery.label, dl_id, "job")
            shipments.append(
                PyVRPShipment(
                    loc_of[pu_id],
                    loc_of[dl_id],
                    pickup_tw_early=int(pu_tw[0]) if pu_tw is not None else 0,
                    pickup_tw_late=int(pu_tw[1]) if pu_tw is not None else TW_LATE_DEFAULT,
                    pickup_service_duration=int(pickup.service_time),
                    delivery_tw_early=int(dl_tw[0]) if dl_tw is not None else 0,
                    delivery_tw_late=int(dl_tw[1]) if dl_tw is not None else TW_LATE_DEFAULT,
                    delivery_service_duration=int(delivery.service_time),
                    amount=amount,
                    prize=prize,
                    required=required,
                    name=f"{pu_name}->{dl_name}",
                ),
            )

        # Unreachable and skill-blocked arcs share the per-matrix overrides; only their
        # fallback differs.
        missing = _arc_fill(opts, TRAVEL_COST_INF)
        blocked = _arc_fill(opts, int(opts[SKILL_INCOMPATIBLE_COST]))
        base_dist, base_dur = _base_matrices(
            model,
            loc_of,
            coords_by_loc,
            missing,
            omit_unreachable=bool(opts[OMIT_UNREACHABLE_ARCS]),
        )

        requirements = _distinct_job_requirements(model)
        profile_keys, profile_of_vehicle = _assign_profiles(model, requirements)
        distances, durations = _profile_matrices(
            model,
            profile_keys,
            loc_of,
            base_dist,
            base_dur,
            blocked,
        )

        vehicle_types: list[object] = []
        for vi, vehicle in enumerate(model._vehicles):
            sd_nid = vehicle.start_depot_node_id
            end_nid_raw = vehicle.end_depot_node_id
            ed_nid = end_nid_raw if end_nid_raw is not None else sd_nid
            if sd_nid not in depot_pos or ed_nid not in depot_pos:
                msg = "internal error: vehicle depot node missing PyVRP object"
                raise RuntimeError(msg)
            vtw = vehicle.time_window
            vt_kwargs: dict[str, object] = {
                "num_available": 1,
                "capacity": _pad_capacity(vehicle.capacity, dims),
                "start_depot": depot_pos[sd_nid],
                "end_depot": depot_pos[ed_nid],
                "fixed_cost": int(vehicle.fixed_use_cost),
                "tw_early": int(vtw[0]) if vtw is not None else 0,
                "tw_late": int(vtw[1]) if vtw is not None else TW_LATE_DEFAULT,
                "profile": profile_of_vehicle[vi],
                "name": _export_name(vehicle.label, vi, "vehicle"),
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
            vehicle_types.append(PyVRPVehicleType(**vt_kwargs))

        return cast(
            PyVRPDataLike,
            PyVRPProblemData(
                locations,
                clients,
                depots,
                vehicle_types,
                distances,
                durations,
                groups,
                shipments,
            ),
        )

    def call_solver(self, data: PyVRPDataLike) -> PyVRPResultLike:
        """Run PyVRP search using ``self._options`` (set in ``__init__``)."""
        if PyVRPMaxRuntime is None or PyVRPSolve is None:
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

        try:
            raw = PyVRPSolve(data, stop, seed=seed, display=pyvrp_display)
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
        client_ids = _pyvrp_client_unified_ids(model)
        shipment_ids = _pyvrp_shipment_unified_ids(model)
        n_depot_py = len(depot_ids)

        def lookup(seq: list[int] | list[tuple[int, int]], idx: int, what: str) -> object:
            if idx < 0 or idx >= len(seq):
                raise MappingError(f"{what} index {idx!r} out of range in PyVRP solution")
            return seq[idx]

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

            # PyVRP 0.14 reports routes as activity schedules: depot stops plus client and
            # shipment pickup/delivery steps, each indexing its own model collection.
            job_seq: list[Job] = []
            for act in rt.schedule():
                if act.is_client():
                    uid = cast(int, lookup(client_ids, act.idx, "client"))
                elif act.is_pickup():
                    uid = cast(tuple[int, int], lookup(shipment_ids, act.idx, "shipment"))[0]
                elif act.is_delivery():
                    uid = cast(tuple[int, int], lookup(shipment_ids, act.idx, "shipment"))[1]
                else:
                    continue
                job_seq.append(Job(model, uid))

            routes_out.append(
                Route(
                    vehicle=Vehicle(model, vidx),
                    start_depot=Depot(model, depot_ids[sdi]),
                    end_depot=Depot(model, depot_ids[edi]),
                    jobs=job_seq,
                ),
            )

        return Solution(routes=routes_out)

    def _run(self, model: Model) -> SolutionStatus:
        job_ids = job_node_ids_ordered(model)
        if not job_ids:
            model._solution = Solution(routes=[])
            return empty_instance_solution_status(self.name, iterations=0)

        if PyVRPProblemData is None or PyVRPMaxRuntime is None:
            raise SolverNotInstalledError('install the "pyvrp" extra to use PyVRPSolver')

        data = self.build_solver_model(model)
        result = self.call_solver(data)
        best = result.best
        solution = self.find_solution_values(model, result)
        model._solution = solution

        # Profile blocking prices incompatible arcs out of the objective but does not forbid
        # them, so PyVRP can report a "feasible" route that still serves a job its vehicle
        # lacks the skills for. Check explicitly rather than pass that off as feasible.
        violations = skill_violations(model, solution)
        feasible = best.is_feasible() and not violations
        raw_status = SolveStatus.FEASIBLE if feasible else SolveStatus.INFEASIBLE

        tl = float(self._options[TIME_LIMIT])
        elapsed = float(result.runtime)
        if violations:
            stop_reason = SolverStopReason.INFEASIBLE
        elif elapsed + 1e-6 >= tl:
            stop_reason = SolverStopReason.TIME_LIMIT
        elif feasible:
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
            error_message=skill_violation_message(model, violations) if violations else None,
            solver_status=result.summary(),
        )
