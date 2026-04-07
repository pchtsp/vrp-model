"""Canonical VRP model: internal record storage and public API."""

from __future__ import annotations

from collections.abc import Iterator
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
from vrp_model.core.solution import Solution
from vrp_model.core.storage import normalize_load, skills_to_frozen
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


class Feature(Enum):
    """Modeling features inferred from nodes, vehicles, and constraints."""

    CAPACITY = auto()
    TIME_WINDOWS = auto()
    PICKUP_DELIVERY = auto()
    MULTI_DEPOT = auto()
    HETEROGENEOUS_FLEET = auto()
    SKILLS = auto()
    PRIZE_COLLECTING = auto()


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
        skills: set[str] | frozenset[str] | None = None,
        time_window: tuple[int, int] | None = None,
    ) -> Vehicle:
        """Append a vehicle referencing start (and optional end) depots by view."""
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
        skills_required: set[str] | frozenset[str] | None = None,
        prize: float | None = None,
    ) -> Job:
        """Append a job node and return its view."""
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
            job_row = row
            demand = job_row.demand
            if any(d > 0 for d in demand):
                features.add(Feature.CAPACITY)
            if job_row.time_window is not None:
                features.add(Feature.TIME_WINDOWS)
            if job_row.skills_required:
                features.add(Feature.SKILLS)
            if job_row.prize is not None:
                features.add(Feature.PRIZE_COLLECTING)

        for vehicle in self._vehicles:
            if vehicle.time_window is not None:
                features.add(Feature.TIME_WINDOWS)
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

    def solution_cost(self) -> float:
        """Sum leg distances for all routes (sparse matrix or Euclidean, same rules as solvers)."""
        sol = self._require_solution()
        total = 0
        for route in sol.routes:
            seq: list[int] = [route.start_depot.node_id]
            seq.extend(j.node_id for j in route.jobs)
            seq.append(route.end_depot.node_id)
            for k in range(len(seq) - 1):
                total += self._directed_travel_distance(seq[k], seq[k + 1])
        return float(total)

    def is_solution_feasible(self) -> bool:
        """Necessary checks on routes (coverage, depots, capacity, pickup-before-delivery).

        Does not fully replicate time-window propagation along routes unless durations are
        modeled consistently; tighten in a later revision if needed.
        """
        sol = self._require_solution()
        job_ids = {j.node_id for j in self.jobs}
        visited: list[int] = []
        for route in sol.routes:
            v = route.vehicle
            if route.start_depot.node_id != v.start_depot.node_id:
                return False
            if route.end_depot.node_id != v.end_depot.node_id:
                return False
            for j in route.jobs:
                visited.append(j.node_id)

        if sorted(visited) != sorted(job_ids):
            return False
        if len(set(visited)) != len(visited):
            return False

        dims = 0
        for row in self._nodes:
            if row.kind == NodeKind.JOB:
                dims = max(dims, len(row.demand))
        for v in self._vehicles:
            dims = max(dims, len(v.capacity))

        for route in sol.routes:
            cap = route.vehicle.capacity
            if not cap:
                continue
            load = [0] * dims
            cap_padded = list(cap) + [0] * (dims - len(cap))
            cap_padded = cap_padded[:dims]
            for j in route.jobs:
                node_row = self._nodes[j.node_id]
                dem = node_row.demand
                dvec = list(dem) + [0] * (dims - len(dem))
                dvec = dvec[:dims]
                load = [load[i] + dvec[i] for i in range(dims)]
                if any(load[i] > cap_padded[i] for i in range(dims)):
                    return False

        for route in sol.routes:
            order = [j.node_id for j in route.jobs]
            pos = {nid: i for i, nid in enumerate(order)}
            for pd in self._pickup_deliveries:
                pu = pd.pickup_job_node_id
                dl = pd.delivery_job_node_id
                if pu not in pos or dl not in pos:
                    return False
                if pos[pu] >= pos[dl]:
                    return False

        for route in sol.routes:
            vskills = frozenset(route.vehicle.skills)
            for j in route.jobs:
                req = self._nodes[j.node_id].skills_required
                if req and not req <= vskills:
                    return False

        return True

    def _uses_multi_depot(self) -> bool:
        depot_ids = [
            i for i, row in enumerate(self._nodes) if row.kind == NodeKind.DEPOT
        ]
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
        for v in self._vehicles[1:]:
            if (
                v.capacity != first.capacity
                or v.time_window != first.time_window
                or v.skills != first.skills
                or v.start_depot_node_id != first.start_depot_node_id
                or v.end_depot_node_id != first.end_depot_node_id
            ):
                return True
        return False

    def _planar_coord_for_node(self, node_id: int) -> tuple[float, float]:
        """Planar coordinates matching PyVRP adapter (synthetic axis for missing locations)."""
        syn_i = 0
        for i in range(len(self._nodes)):
            row = self._nodes[i]
            if row.kind != NodeKind.DEPOT:
                continue
            loc = row.location
            if loc is not None:
                xy = (float(loc[0]), float(loc[1]))
            else:
                xy = (float(syn_i), 0.0)
                syn_i += 1
            if i == node_id:
                return xy
        for i in range(len(self._nodes)):
            row = self._nodes[i]
            if row.kind != NodeKind.JOB:
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

    def _directed_travel_distance(self, u: int, v: int) -> int:
        if u == v:
            return 0
        if self._travel_edges:
            e = self._travel_edges.get((u, v))
            if e is None or e.distance is None:
                return TRAVEL_COST_INF
            return int(e.distance)
        return euclidean_int(
            self._planar_coord_for_node(u), self._planar_coord_for_node(v)
        )
