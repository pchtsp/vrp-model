"""Internal mutable records for :class:`~vrp_model.core.model.Model` storage."""

from __future__ import annotations

from dataclasses import dataclass

from vrp_model.core.kinds import NodeKind
from vrp_model.core.time_window_flex import TimeWindowFlex


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
    skills_required: frozenset[int]
    prize: float | None = None
    time_window_flex: TimeWindowFlex | None = None


@dataclass(slots=True)
class VehicleRecord:
    """One vehicle in the fleet."""

    label: str | None
    capacity: list[int]
    start_depot_node_id: int
    end_depot_node_id: int | None
    skills: frozenset[int]
    time_window: tuple[int, int] | None = None
    time_window_flex: TimeWindowFlex | None = None
    fixed_use_cost: int = 0
    max_route_distance: int | None = None
    max_route_time: int | None = None
    max_route_overtime: int | None = None
    route_overtime_unit_cost: int = 0
    max_slack_time: int | None = None


@dataclass(slots=True)
class PickupDeliveryRecord:
    """Pickup–delivery pair by unified job node ids."""

    pickup_job_node_id: int
    delivery_job_node_id: int


NodeRecord = DepotNodeRecord | JobNodeRecord
