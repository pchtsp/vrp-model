"""Canonical VRP model: internal record storage and public API."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator, Sequence
from enum import Enum, auto
from typing import TYPE_CHECKING

from vrp_model.core.errors import (
    SolutionUnavailableError,
    SolverCapabilityError,
    ValidationError,
)
from vrp_model.core.kinds import NodeKind
from vrp_model.core.records import (
    DepotNodeRecord,
    JobNodeRecord,
    NodeRecord,
    PickupDeliveryRecord,
    VehicleRecord,
)
from vrp_model.core.solution import Route, Solution
from vrp_model.core.storage import normalize_load, skills_to_frozen
from vrp_model.core.time_window_flex import TimeWindowFlex
from vrp_model.core.travel_edges import TRAVEL_COST_INF, TravelEdgeAttrs, TravelEdgesMap
from vrp_model.core.views import Depot, Job, Vehicle
from vrp_model.utils.distance import euclidean_int
from vrp_model.validation import consistency, feasibility, structure

if TYPE_CHECKING:
    from vrp_model.solvers.base import Solver


class SolveStatus(Enum):
    """Coarse solve outcome used after mapping a solver-specific status."""

    OPTIMAL = auto()
    FEASIBLE = auto()
    INFEASIBLE = auto()
    UNKNOWN = auto()
    TIME_LIMIT = auto()


class TravelAttr(Enum):
    """Which travel cost to read from :class:`~vrp_model.core.travel_edges.TravelEdgeAttrs`."""

    DISTANCE = auto()
    DURATION = auto()


class Feature(Enum):
    """Modeling features inferred from nodes, vehicles, and constraints."""

    CAPACITY = auto()
    TIME_WINDOWS = auto()
    PICKUP_DELIVERY = auto()
    MULTI_DEPOT = auto()
    HETEROGENEOUS_FLEET = auto()
    SKILLS = auto()
    PRIZE_COLLECTING = auto()
    FLEXIBLE_TIME_WINDOWS = auto()
    VEHICLE_FIXED_COST = auto()
    MAX_ROUTE_DISTANCE = auto()
    MAX_ROUTE_TIME = auto()
    ROUTE_OVERTIME = auto()
    MAX_NODE_SLACK = auto()


class Model:
    """Owns unified nodes (depots and jobs), vehicles, pickup-delivery, optional solution."""

    __slots__ = (
        "_nodes",
        "_vehicles",
        "_pickup_deliveries",
        "_solution",
        "_travel_edges",
    )

    def __init__(self) -> None:
        self._nodes: list[NodeRecord] = []
        self._vehicles: list[VehicleRecord] = []
        self._pickup_deliveries: list[PickupDeliveryRecord] = []
        self._solution: Solution | None = None
        self._travel_edges: TravelEdgesMap = {}

    def _require_view_on_model(self, view: Depot | Job) -> None:
        if view._model is not self:
            raise ValidationError("depot or job view must belong to this model")

    @property
    def depots(self) -> Iterator[Depot]:
        """Yield depot views in unified node-id order."""
        for i, row in enumerate(self._nodes):
            if row.kind == NodeKind.DEPOT:
                yield Depot(self, i)

    @property
    def vehicles(self) -> Iterator[Vehicle]:
        """Yield vehicle views in creation order."""
        for i in range(len(self._vehicles)):
            yield Vehicle(self, i)

    @property
    def jobs(self) -> Iterator[Job]:
        """Yield job views in unified node-id order."""
        for i, row in enumerate(self._nodes):
            if row.kind == NodeKind.JOB:
                yield Job(self, i)

    def set_travel_edges(self, edges: TravelEdgesMap) -> None:
        """Replace sparse travel overrides; values must be :class:`TravelEdgeAttrs` instances.

        Full validation runs in :meth:`validate`.
        """
        self._travel_edges = dict(edges)

    def update_travel_edge(
        self,
        origin: Depot | Job,
        destination: Depot | Job,
        *,
        distance: int | None = None,
        duration: int | None = None,
    ) -> None:
        """Merge travel costs for ``origin → destination`` (unified node ids).

        Semantic checks run in :meth:`validate`.
        """
        self._require_view_on_model(origin)
        self._require_view_on_model(destination)
        i = origin.node_id
        j = destination.node_id
        key = (i, j)
        prev = self._travel_edges.get(key)
        prev_d = prev.distance if prev is not None else None
        prev_t = prev.duration if prev is not None else None
        next_d = int(distance) if distance is not None else prev_d
        next_t = int(duration) if duration is not None else prev_t
        self._travel_edges[key] = TravelEdgeAttrs(distance=next_d, duration=next_t)

    def clear_travel_edges(self) -> None:
        """Remove all sparse travel overrides.

        After clearing, solvers use Euclidean legs only if ``validate()`` passes, which
        requires every job to have a ``location`` when ``travel_edges`` is empty.
        """
        self._travel_edges = {}

    def add_depot(
        self,
        *,
        location: tuple[float, float] | None = None,
        label: str | None = None,
    ) -> Depot:
        """Append a depot node and return its view."""
        loc: tuple[float, float] | None = None
        if location is not None:
            loc = (float(location[0]), float(location[1]))
        row = DepotNodeRecord(kind=NodeKind.DEPOT, label=label, location=loc)
        self._nodes.append(row)
        return Depot(self, len(self._nodes) - 1)

    def add_vehicle(
        self,
        capacity: int | list[int],
        start_depot: Depot,
        end_depot: Depot | None = None,
        *,
        label: str | None = None,
        skills: set[int] | frozenset[int] | None = None,
        time_window: tuple[int, int] | None = None,
        time_window_flex: TimeWindowFlex | None = None,
        fixed_use_cost: int = 0,
        max_route_distance: int | None = None,
        max_route_time: int | None = None,
        max_route_overtime: int | None = None,
        route_overtime_unit_cost: int = 0,
        max_slack_time: int | None = None,
    ) -> Vehicle:
        """Append a vehicle referencing start (and optional end) depots by view.

        ``skills`` are non-negative integer skill ids; a job is served only if
        ``job.skills_required`` is a subset of the vehicle's skills.
        """
        self._require_view_on_model(start_depot)
        sd = start_depot.node_id
        end_nid: int | None
        if end_depot is None:
            end_nid = None
        else:
            self._require_view_on_model(end_depot)
            end_nid = end_depot.node_id
        rec = VehicleRecord(
            label=label,
            capacity=normalize_load(capacity),
            start_depot_node_id=sd,
            end_depot_node_id=end_nid,
            skills=skills_to_frozen(skills or frozenset()),
            time_window=time_window,
            time_window_flex=time_window_flex,
            fixed_use_cost=int(fixed_use_cost),
            max_route_distance=max_route_distance,
            max_route_time=max_route_time,
            max_route_overtime=max_route_overtime,
            route_overtime_unit_cost=int(route_overtime_unit_cost),
            max_slack_time=max_slack_time,
        )
        self._vehicles.append(rec)
        return Vehicle(self, len(self._vehicles) - 1)

    def add_job(
        self,
        demand: int | list[int] = 0,
        *,
        location: tuple[float, float] | None = None,
        label: str | None = None,
        service_time: int = 0,
        time_window: tuple[int, int] | None = None,
        time_window_flex: TimeWindowFlex | None = None,
        skills_required: set[int] | frozenset[int] | None = None,
        prize: float | None = None,
    ) -> Job:
        """Append a job node and return its view.

        ``skills_required`` are non-negative integer ids; at least one vehicle must
        include every required id in its ``skills`` set.

        ``prize``: when ``None`` the job is **mandatory** (must appear in any feasible
        solution). When set, the job is **optional** for hard feasibility; skipping it
        incurs a **skip penalty** of ``round(float(prize))`` in :meth:`solution_cost`
        (aligned with OR-Tools disjunction semantics). Visiting an optional job pays no
        skip penalty for that job.
        """
        loc: tuple[float, float] | None = None
        if location is not None:
            loc = (float(location[0]), float(location[1]))
        row = JobNodeRecord(
            kind=NodeKind.JOB,
            label=label,
            location=loc,
            demand=normalize_load(demand),
            service_time=int(service_time),
            time_window=time_window,
            skills_required=skills_to_frozen(skills_required or frozenset()),
            prize=prize,
            time_window_flex=time_window_flex,
        )
        self._nodes.append(row)
        return Job(self, len(self._nodes) - 1)

    def add_pickup_delivery(self, pickup: Job, delivery: Job) -> None:
        """Register a pickup-delivery pair (both must be job views on this model)."""
        self._require_view_on_model(pickup)
        self._require_view_on_model(delivery)
        self._pickup_deliveries.append(
            PickupDeliveryRecord(
                pickup_job_node_id=pickup.node_id,
                delivery_job_node_id=delivery.node_id,
            ),
        )

    def validate(self) -> None:
        """Run structure, consistency, and feasibility checks (may normalize travel edges)."""
        structure.validate(self)
        consistency.validate(self)
        feasibility.validate(self)

    def check_solver_compatibility(self, solver: Solver) -> None:
        """Raise :class:`SolverCapabilityError` if ``solver`` lacks a required :class:`Feature`."""
        required = self.detect_features()
        missing = [f for f in required if f not in solver.supported_features]
        if missing:
            names = ", ".join(sorted(m.name for m in missing))
            raise SolverCapabilityError(
                f"solver {solver.name!r} does not support features: {names}",
            )

    def detect_features(self) -> frozenset[Feature]:
        """Infer which modeling features are present."""
        features: set[Feature] = set()

        for row in self._nodes:
            if row.kind != NodeKind.JOB:
                continue
            job_row = row.as_job()
            demand = job_row.demand
            if any(d > 0 for d in demand):
                features.add(Feature.CAPACITY)
            if job_row.time_window is not None:
                features.add(Feature.TIME_WINDOWS)
            flex_j = job_row.time_window_flex
            if flex_j is not None and flex_j.has_soft_penalties():
                features.add(Feature.FLEXIBLE_TIME_WINDOWS)
            if job_row.skills_required:
                features.add(Feature.SKILLS)
            if job_row.prize is not None:
                features.add(Feature.PRIZE_COLLECTING)

        for vehicle in self._vehicles:
            if vehicle.time_window is not None:
                features.add(Feature.TIME_WINDOWS)
            flex_v = vehicle.time_window_flex
            if flex_v is not None and flex_v.has_soft_penalties():
                features.add(Feature.FLEXIBLE_TIME_WINDOWS)
            if vehicle.fixed_use_cost > 0:
                features.add(Feature.VEHICLE_FIXED_COST)
            if vehicle.max_route_distance is not None:
                features.add(Feature.MAX_ROUTE_DISTANCE)
            if vehicle.max_route_time is not None:
                features.add(Feature.MAX_ROUTE_TIME)
            ot = vehicle.max_route_overtime
            if (ot is not None and ot > 0) or vehicle.route_overtime_unit_cost != 0:
                features.add(Feature.ROUTE_OVERTIME)
            if vehicle.max_slack_time is not None:
                features.add(Feature.MAX_NODE_SLACK)
            cap = vehicle.capacity
            if len(cap) > 0:
                features.add(Feature.CAPACITY)

        if self._pickup_deliveries:
            features.add(Feature.PICKUP_DELIVERY)

        if self._uses_multi_depot():
            features.add(Feature.MULTI_DEPOT)

        if self._fleet_is_heterogeneous():
            features.add(Feature.HETEROGENEOUS_FLEET)

        return frozenset(features)

    @property
    def features(self) -> frozenset[Feature]:
        """Same as :meth:`detect_features`."""
        return self.detect_features()

    @property
    def solution(self) -> Solution | None:
        """Last solution attached by a solver, if any."""
        return self._solution

    def _require_solution(self) -> Solution:
        if self._solution is None:
            raise SolutionUnavailableError("no solution is attached to this model")
        return self._solution

    def unassigned_jobs(self) -> list[Job]:
        """Jobs not visited on any route in :attr:`solution` (requires attached solution)."""
        sol = self._require_solution()
        on_route: set[int] = set()
        for route in sol.routes:
            for j in route.jobs:
                on_route.add(j.node_id)
        return [j for j in self.jobs if j.node_id not in on_route]

    def mandatory_unassigned_jobs(self) -> list[Job]:
        """Mandatory jobs (``prize is None``) that are not on any route."""
        return [j for j in self.unassigned_jobs() if self._job_record(j.node_id).prize is None]

    def solution_travel_distance(self) -> float:
        """Sum of leg distances over all routes only (no prizes, fixed costs, or soft penalties)."""
        return float(self._solution_travel_distance_sum(self._require_solution()))

    def solution_cost(self) -> float:
        """Canonical objective value to **minimize** for the attached solution.

        Includes, when applicable:

        * total **travel distance** (same rules as :meth:`_directed_travel_distance`);
        * **fixed_use_cost** for each route that serves at least one job;
        * **skip penalties** for **optional** jobs (``prize is not None``) that are not visited
          — each adds ``round(float(prize))``;
        * **linear soft time-window** penalties from
          :class:`~vrp_model.core.time_window_flex.TimeWindowFlex` on jobs and vehicles
          (evaluated at service start / route start/end times);
        * **route overtime charge** when ``route_overtime_unit_cost`` is positive: units of
          time beyond ``max_route_time`` up to ``max_route_overtime`` multiplied by the unit cost.

        Does **not** yet model ``max_slack_time`` penalties (reserved for a later revision).

        Mandatory jobs are those with ``prize is None``; optional jobs use a non-``None`` prize
        as the skip penalty coefficient.
        """
        sol = self._require_solution()
        visited = self._visited_job_node_ids(sol)
        total = float(self._solution_travel_distance_sum(sol))
        for route in sol.routes:
            if len(route.jobs) == 0:
                continue
            vrec = self._vehicles[route.vehicle._idx]
            total += float(vrec.fixed_use_cost)

        for node_id, row in enumerate(self._nodes):
            if row.kind != NodeKind.JOB:
                continue
            jr = row.as_job()
            if jr.prize is None:
                continue
            if node_id not in visited:
                total += float(round(float(jr.prize)))

        for route in sol.routes:
            soft, overtime = self._route_soft_and_overtime_costs(route)
            total += float(soft + overtime)

        return total

    def _routes_depots_match_vehicles(self, sol: Solution) -> bool:
        for route in sol.routes:
            v = route.vehicle
            if route.start_depot.node_id != v.start_depot.node_id:
                return False
            if route.end_depot.node_id != v.end_depot.node_id:
                return False
        return True

    def _job_node_ids_in_visit_order(self, sol: Solution) -> list[int]:
        visited: list[int] = []
        for route in sol.routes:
            for j in route.jobs:
                visited.append(j.node_id)
        return visited

    def _visit_counts_by_node_id(self, visited: Sequence[int]) -> dict[int, int]:
        return dict(Counter(visited))

    def _job_visits_are_unique(self, visited: Sequence[int]) -> bool:
        return len(set(visited)) == len(visited)

    def _mandatory_jobs_each_visited_once(self, visit_by_node: dict[int, int]) -> bool:
        for node_id, row in enumerate(self._nodes):
            if row.kind != NodeKind.JOB:
                continue
            jr = row.as_job()
            if jr.prize is not None:
                continue
            if visit_by_node.get(node_id, 0) != 1:
                return False
        return True

    def _visit_count_keys_are_job_nodes(self, visit_by_node: dict[int, int]) -> bool:
        for node_id in visit_by_node:
            if self._nodes[node_id].kind != NodeKind.JOB:
                return False
        return True

    def _capacity_dimension_count(self) -> int:
        dims = 0
        for row in self._nodes:
            if row.kind == NodeKind.JOB:
                dims = max(dims, len(row.as_job().demand))
        for v in self._vehicles:
            dims = max(dims, len(v.capacity))
        return dims

    def _route_within_capacity(self, route: Route, dims: int) -> bool:
        cap = route.vehicle.capacity
        if not cap:
            return True
        load = [0] * dims
        cap_padded = (list(cap) + [0] * (dims - len(cap)))[:dims]
        for j in route.jobs:
            job_row = self._nodes[j.node_id].as_job()
            dem = job_row.demand
            dvec = (list(dem) + [0] * (dims - len(dem)))[:dims]
            load = [load[i] + dvec[i] for i in range(dims)]
            if any(load[i] > cap_padded[i] for i in range(dims)):
                return False
        return True

    def _route_skills_satisfied(self, route: Route) -> bool:
        vskills = frozenset(route.vehicle.skills)
        for j in route.jobs:
            req = self._nodes[j.node_id].as_job().skills_required
            if req and not req <= vskills:
                return False
        return True

    def _all_routes_within_capacity_and_skills(self, sol: Solution, dims: int) -> bool:
        for route in sol.routes:
            if not self._route_within_capacity(route, dims):
                return False
            if not self._route_skills_satisfied(route):
                return False
        return True

    def _all_routes_pass_hard_timeline(self, sol: Solution) -> bool:
        for route in sol.routes:
            ok, _dist, _time = self._route_hard_feasibility(route)
            if not ok:
                return False
        return True

    def is_solution_feasible(self) -> bool:
        """Hard feasibility only (mandatory coverage, depots, capacity, PD, skills, caps, TW).

        Optional jobs (``prize is not None``) need not be visited. Soft time-window
        violations and priced overtime within allowed caps are **not** failures here.
        """
        sol = self._require_solution()
        if not self._routes_depots_match_vehicles(sol):
            return False
        visited = self._job_node_ids_in_visit_order(sol)
        if not self._job_visits_are_unique(visited):
            return False
        visit_by_node = self._visit_counts_by_node_id(visited)
        if not self._mandatory_jobs_each_visited_once(visit_by_node):
            return False
        if not self._visit_count_keys_are_job_nodes(visit_by_node):
            return False
        if not self._pickup_delivery_pairs_valid(sol, visited):
            return False
        dims = self._capacity_dimension_count()
        if not self._all_routes_within_capacity_and_skills(sol, dims):
            return False
        if not self._all_routes_pass_hard_timeline(sol):
            return False
        return True

    def _job_record(self, node_id: int) -> JobNodeRecord:
        """Return the job record at ``node_id`` or raise :class:`ValidationError`."""
        row = self._nodes[node_id]
        if row.kind != NodeKind.JOB:
            raise ValidationError(f"node {node_id} is not a job")
        return row.as_job()

    def _visited_job_node_ids(self, sol: Solution) -> set[int]:
        out: set[int] = set()
        for route in sol.routes:
            for j in route.jobs:
                out.add(j.node_id)
        return out

    def _solution_travel_distance_sum(self, sol: Solution) -> int:
        total = 0
        for route in sol.routes:
            seq = [route.start_depot.node_id]
            seq.extend(j.node_id for j in route.jobs)
            seq.append(route.end_depot.node_id)
            for k in range(len(seq) - 1):
                d = self._directed_travel_distance(seq[k], seq[k + 1])
                if d >= TRAVEL_COST_INF:
                    return TRAVEL_COST_INF
                total += d
        return total

    def _pickup_delivery_pairs_valid(self, sol: Solution, visited: list[int]) -> bool:
        job_pos: dict[int, tuple[int, int]] = {}
        for ri, route in enumerate(sol.routes):
            for pos, j in enumerate(route.jobs):
                job_pos[j.node_id] = (ri, pos)

        for pd in self._pickup_deliveries:
            pu = pd.pickup_job_node_id
            dl = pd.delivery_job_node_id
            pu_opt = self._job_record(pu).prize is not None
            dl_opt = self._job_record(dl).prize is not None
            pu_in = pu in job_pos
            dl_in = dl in job_pos
            if not pu_in and not dl_in:
                if pu_opt and dl_opt:
                    continue
                return False
            if pu_in != dl_in:
                return False
            ri, pi = job_pos[pu]
            rj, dj = job_pos[dl]
            if ri != rj or pi >= dj:
                return False
        return True

    def _flex_penalty(self, flex: TimeWindowFlex | None, service_start: int) -> int:
        if flex is None:
            return 0
        pen = 0
        se = flex.soft_earliest
        pe = flex.penalty_per_unit_before_soft_earliest
        if se is not None and pe is not None and pe > 0 and service_start < se:
            pen += (se - service_start) * pe
        sl = flex.soft_latest
        pl = flex.penalty_per_unit_after_soft_latest
        if sl is not None and pl is not None and pl > 0 and service_start > sl:
            pen += (service_start - sl) * pl
        return pen

    def _route_timeline(
        self,
        route: Route,
        *,
        include_soft_penalties: bool,
    ) -> tuple[bool, int, int, int]:
        """Simulate one route: return (ok, total_distance, time_at_end, soft_penalty).

        When ``include_soft_penalties`` is False, soft_penalty is always 0 (hard-feasibility
        walk only). When True, ``ok`` is still hard-feasibility; soft_penalty accumulates.
        """
        vrec = self._vehicles[route.vehicle._idx]
        t = 0
        if vrec.time_window is not None:
            twv = vrec.time_window
            if t < int(twv[0]):
                t = int(twv[0])
            if t > int(twv[1]):
                return False, 0, 0, 0
        soft = 0
        if include_soft_penalties:
            soft += self._flex_penalty(vrec.time_window_flex, t)

        total_dist = 0
        prev = route.start_depot.node_id
        for j in route.jobs:
            nid = j.node_id
            du = self._directed_travel_distance(prev, nid)
            if du >= TRAVEL_COST_INF:
                return False, 0, 0, 0
            total_dist += du
            dur = self._directed_travel_duration(prev, nid)
            if dur >= TRAVEL_COST_INF:
                return False, 0, 0, 0
            t += dur
            jr = self._nodes[nid].as_job()
            tw = jr.time_window
            if tw is not None:
                if t > int(tw[1]):
                    return False, 0, 0, 0
                if t < int(tw[0]):
                    t = int(tw[0])
            if include_soft_penalties:
                soft += self._flex_penalty(jr.time_window_flex, t)
            t += int(jr.service_time)
            prev = nid

        end_id = route.end_depot.node_id
        du = self._directed_travel_distance(prev, end_id)
        if du >= TRAVEL_COST_INF:
            return False, 0, 0, 0
        total_dist += du
        dur = self._directed_travel_duration(prev, end_id)
        if dur >= TRAVEL_COST_INF:
            return False, 0, 0, 0
        t += dur

        if vrec.time_window is not None and t > int(vrec.time_window[1]):
            return False, 0, 0, 0
        if include_soft_penalties:
            soft += self._flex_penalty(vrec.time_window_flex, t)

        if vrec.max_route_distance is not None and total_dist > int(vrec.max_route_distance):
            return False, 0, 0, 0

        mrt = vrec.max_route_time
        if mrt is not None:
            hard_time_limit = int(mrt)
            mot = vrec.max_route_overtime
            if mot is not None and int(mot) > 0:
                hard_time_limit += int(mot)
            if t > hard_time_limit:
                return False, 0, 0, 0

        return True, total_dist, t, soft

    def _route_soft_and_overtime_costs(self, route: Route) -> tuple[int, int]:
        """Return (soft_tw_penalty, overtime_charge) for one route (hard-feasible assumed)."""
        vrec = self._vehicles[route.vehicle._idx]
        ok, _dist, t, soft = self._route_timeline(route, include_soft_penalties=True)
        if not ok:
            return 0, 0
        overtime_charge = 0
        mrt = vrec.max_route_time
        if mrt is not None and vrec.route_overtime_unit_cost > 0:
            over = max(0, t - int(mrt))
            overtime_charge = over * int(vrec.route_overtime_unit_cost)
        return soft, overtime_charge

    def _route_hard_feasibility(self, route: Route) -> tuple[bool, int, int]:
        """Return (ok, total_distance, total_time_at_end) for hard checks on one route."""
        ok, dist, t_end, _s = self._route_timeline(route, include_soft_penalties=False)
        return ok, dist, t_end

    def _uses_multi_depot(self) -> bool:
        depot_ids = [i for i, row in enumerate(self._nodes) if row.kind == NodeKind.DEPOT]
        if len(depot_ids) > 1:
            return True
        starts = {v.start_depot_node_id for v in self._vehicles}
        if len(starts) > 1:
            return True
        ends: set[int] = set()
        for v in self._vehicles:
            e = v.end_depot_node_id
            if e is not None:
                ends.add(e)
        return len(ends) > 1

    def _fleet_is_heterogeneous(self) -> bool:
        if len(self._vehicles) <= 1:
            return False
        first = self._vehicles[0]
        return any(v != first for v in self._vehicles[1:])

    def _planar_coord_for_node(self, node_id: int) -> tuple[float, float]:
        """Planar coordinates matching PyVRP adapter (synthetic axis for missing locations)."""
        syn_i = 0
        for phase in (NodeKind.DEPOT, NodeKind.JOB):
            for i, row in enumerate(self._nodes):
                if row.kind != phase:
                    continue
                loc = row.location
                if loc is not None:
                    xy = (float(loc[0]), float(loc[1]))
                else:
                    xy = (float(syn_i), 0.0)
                    syn_i += 1
                if i == node_id:
                    return xy
        msg = f"node_id {node_id} is not a depot or job"
        raise ValueError(msg)

    def _directed_travel(self, u: int, v: int, attr: TravelAttr) -> int:
        if u == v:
            return 0
        if self._travel_edges:
            e = self._travel_edges.get((u, v))
            if e is None:
                return TRAVEL_COST_INF
            if attr is TravelAttr.DISTANCE:
                val = e.distance
            else:
                val = e.duration
            if val is None:
                return TRAVEL_COST_INF
            return int(val)
        return euclidean_int(self._planar_coord_for_node(u), self._planar_coord_for_node(v))

    def _directed_travel_distance(self, u: int, v: int) -> int:
        return self._directed_travel(u, v, TravelAttr.DISTANCE)

    def _directed_travel_duration(self, u: int, v: int) -> int:
        return self._directed_travel(u, v, TravelAttr.DURATION)
