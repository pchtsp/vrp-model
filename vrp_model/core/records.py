"""Internal mutable records for :class:`~vrp_model.core.model.Model` storage."""

from __future__ import annotations

from dataclasses import dataclass

from vrp_model.core.kinds import NodeKind


@dataclass(slots=True)
class DepotNodeRecord:
    """Unified-node row for a depot."""

    kind: NodeKind
    label: str | None
    location: tuple[float, float] | None


@dataclass(slots=True)
class JobNodeRecord(DepotNodeRecord):
    """Unified-node row for a job / customer stop."""

    demand: list[int]
    service_time: int
    time_window: tuple[int, int] | None
    skills_required: frozenset[str]
    prize: float | None


@dataclass(slots=True)
class VehicleRecord:
    """One vehicle in the fleet."""

    label: str | None
    capacity: list[int]
    start_depot_node_id: int
    end_depot_node_id: int | None
    skills: frozenset[str]
    time_window: tuple[int, int] | None


@dataclass(slots=True)
class PickupDeliveryRecord:
    """Pickup–delivery pair by unified job node ids."""

    pickup_job_node_id: int
    delivery_job_node_id: int


NodeRecord = DepotNodeRecord | JobNodeRecord
