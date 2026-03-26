"""Canonical VRP model: internal dict storage and public API."""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum, auto
from typing import TYPE_CHECKING, TypeAlias

from vrp_model.core.errors import SolverCapabilityError, ValidationError
from vrp_model.core.kinds import NodeKind
from vrp_model.core.solution import Solution
from vrp_model.core.storage import normalize_load, skills_to_frozen
from vrp_model.core.travel_edges import TravelEdgeAttrs
from vrp_model.core.views import Depot, Job, Vehicle
from vrp_model.validation import consistency, feasibility, structure


if TYPE_CHECKING:
    from vrp_model.solvers.base import Solver


class SolveStatus(Enum):
    OPTIMAL = auto()
    FEASIBLE = auto()
    INFEASIBLE = auto()
    UNKNOWN = auto()
    TIME_LIMIT = auto()


class Feature(Enum):
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
        self._nodes: list[dict] = []
        self._vehicles: list[dict] = []
        self._pickup_deliveries: list[dict] = []
        self._solution: Solution | None = None
        self._travel_edges: dict[tuple[int, int], TravelEdgeAttrs] = {}

    def _depot_index(self, depot: Depot) -> int:
        if depot._model is not self:
            raise ValidationError("depot must belong to this model")
        nid = depot._node_id
        if nid < 0 or nid >= len(self._nodes):
            raise ValidationError("depot reference is out of range for this model")
        if self._nodes[nid]["kind"] != NodeKind.DEPOT:
            raise ValidationError("depot reference does not refer to a depot node")
        return nid

    def _job_index(self, job: Job) -> int:
        if job._model is not self:
            raise ValidationError("job must belong to this model")
        nid = job._node_id
        if nid < 0 or nid >= len(self._nodes):
            raise ValidationError("job reference is out of range for this model")
        if self._nodes[nid]["kind"] != NodeKind.JOB:
            raise ValidationError("job reference does not refer to a job node")
        return nid

    def _endpoint_node_id(self, endpoint: Depot | Job) -> int:
        if isinstance(endpoint, Depot):
            return self._depot_index(endpoint)
        if isinstance(endpoint, Job):
            return self._job_index(endpoint)
        msg = "origin and destination must be Depot or Job views from this model"
        raise TypeError(msg)

    @property
    def depots(self) -> tuple[Depot, ...]:
        return tuple(
            Depot(self, i) for i, row in enumerate(self._nodes) if row["kind"] == NodeKind.DEPOT
        )

    @property
    def vehicles(self) -> tuple[Vehicle, ...]:
        return tuple(Vehicle(self, i) for i in range(len(self._vehicles)))

    @property
    def jobs(self) -> tuple[Job, ...]:
        return tuple(
            Job(self, i) for i, row in enumerate(self._nodes) if row["kind"] == NodeKind.JOB
        )

    def set_travel_edges(self, edges: Mapping[tuple[int, int], TravelEdgeAttrs]) -> None:
        """Replace sparse travel overrides keyed by ``(from_id, to_id)``.

        Values are not fully checked here; :meth:`validate` normalizes and enforces rules
        (bounds, self-loops, non-negative costs, at least one of distance/duration per edge).
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

        Semantic checks run in :meth:`validate`. ``prev`` may be a mapping or
        :class:`TravelEdgeAttrs` until validation normalizes storage.
        """
        i = self._endpoint_node_id(origin)
        j = self._endpoint_node_id(destination)
        key = (i, j)
        prev_raw = self._travel_edges.get(key)
        prev_d: int | None
        prev_t: int | None
        if isinstance(prev_raw, TravelEdgeAttrs):
            prev_d, prev_t = prev_raw.distance, prev_raw.duration
        elif isinstance(prev_raw, Mapping):
            pd = prev_raw.get("distance")
            pt = prev_raw.get("duration")
            prev_d = int(pd) if pd is not None else None
            prev_t = int(pt) if pt is not None else None
        else:
            prev_d, prev_t = None, None
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
        loc: tuple[float, float] | None = None
        if location is not None:
            loc = (float(location[0]), float(location[1]))
        row = {
            "kind": NodeKind.DEPOT,
            "label": label,
            "location": loc,
        }
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
        sd = self._depot_index(start_depot)
        end_nid: int | None
        if end_depot is None:
            end_nid = None
        else:
            end_nid = self._depot_index(end_depot)
        row = {
            "label": label,
            "capacity": normalize_load(capacity),
            "start_depot_node_id": sd,
            "end_depot_node_id": end_nid,
            "skills": skills_to_frozen(skills or frozenset()),
            "time_window": time_window,
        }
        self._vehicles.append(row)
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
        loc: tuple[float, float] | None = None
        if location is not None:
            loc = (float(location[0]), float(location[1]))
        row = {
            "kind": NodeKind.JOB,
            "label": label,
            "location": loc,
            "demand": normalize_load(demand),
            "service_time": int(service_time),
            "time_window": time_window,
            "skills_required": skills_to_frozen(skills_required or frozenset()),
            "prize": prize,
        }
        self._nodes.append(row)
        return Job(self, len(self._nodes) - 1)

    def add_pickup_delivery(self, pickup: Job, delivery: Job) -> None:
        pu = self._job_index(pickup)
        dl = self._job_index(delivery)
        self._pickup_deliveries.append(
            {"pickup_job_node_id": pu, "delivery_job_node_id": dl},
        )

    def validate(self) -> None:
        structure.validate(self)
        consistency.validate(self)
        feasibility.validate(self)

    def check_solver_compatibility(self, solver: Solver) -> None:
        required = self._detect_features()
        missing = [f for f in required if f not in solver.supported_features]
        if missing:
            names = ", ".join(sorted(m.name for m in missing))
            raise SolverCapabilityError(
                f"solver {solver.name!r} does not support features: {names}",
            )

    def _detect_features(self) -> frozenset[Feature]:
        return _detect_features_impl(self)

    @property
    def features(self) -> frozenset[Feature]:
        return self._detect_features()

    def map_status(self, status: object) -> SolveStatus:
        if isinstance(status, SolveStatus):
            return status
        return SolveStatus.UNKNOWN

    @property
    def solution(self) -> Solution | None:
        return self._solution


def _uses_multi_depot(model: Model) -> bool:
    depot_ids = [i for i, row in enumerate(model._nodes) if row["kind"] == NodeKind.DEPOT]
    if len(depot_ids) > 1:
        return True
    starts = {v["start_depot_node_id"] for v in model._vehicles}
    if len(starts) > 1:
        return True
    ends: set[int] = set()
    for v in model._vehicles:
        e = v["end_depot_node_id"]
        if e is not None:
            ends.add(e)
    return len(ends) > 1


def _fleet_is_heterogeneous(model: Model) -> bool:
    if len(model._vehicles) <= 1:
        return False
    first = model._vehicles[0]
    for v in model._vehicles[1:]:
        if (
            v["capacity"] != first["capacity"]
            or v["time_window"] != first["time_window"]
            or v["skills"] != first["skills"]
            or v["start_depot_node_id"] != first["start_depot_node_id"]
            or v["end_depot_node_id"] != first["end_depot_node_id"]
        ):
            return True
    return False


def _detect_features_impl(model: Model) -> frozenset[Feature]:
    features: set[Feature] = set()

    for row in model._nodes:
        if row["kind"] != NodeKind.JOB:
            continue
        demand = row["demand"]
        if any(d > 0 for d in demand):
            features.add(Feature.CAPACITY)
        if row["time_window"] is not None:
            features.add(Feature.TIME_WINDOWS)
        if row["skills_required"]:
            features.add(Feature.SKILLS)
        if row["prize"] is not None:
            features.add(Feature.PRIZE_COLLECTING)

    for vehicle in model._vehicles:
        if vehicle["time_window"] is not None:
            features.add(Feature.TIME_WINDOWS)
        cap = vehicle["capacity"]
        if len(cap) > 0:
            features.add(Feature.CAPACITY)

    if model._pickup_deliveries:
        features.add(Feature.PICKUP_DELIVERY)

    if _uses_multi_depot(model):
        features.add(Feature.MULTI_DEPOT)

    if _fleet_is_heterogeneous(model):
        features.add(Feature.HETEROGENEOUS_FLEET)

    return frozenset(features)


def detect_features(model: object) -> frozenset[Feature]:
    """Infer which modeling features are present on ``model``."""
    if not isinstance(model, Model):
        msg = "detect_features expects a Model instance"
        raise TypeError(msg)
    return _detect_features_impl(model)
