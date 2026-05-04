"""Internal mutable records for :class:`~vrp_model.core.model.Model` storage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from vrp_model.core.errors import ValidationError
from vrp_model.core.kinds import NodeKind
from vrp_model.core.time_window_flex import TimeWindowFlex


@dataclass(slots=True)
class NodeBase:
    """Shared fields for depot and job rows in unified node storage."""

    kind: NodeKind
    label: str | None
    location: tuple[float, float] | None

    def as_job(self) -> JobNodeRecord:
        """Return this row as a job record, or raise if it is a depot."""
        if self.kind != NodeKind.JOB:
            raise ValidationError("node is a depot, not a job")
        return cast(JobNodeRecord, self)


@dataclass(slots=True)
class DepotNodeRecord(NodeBase):
    """Unified-node row for a depot."""


@dataclass(slots=True)
class JobNodeRecord(NodeBase):
    """Unified-node row for a job / customer stop."""

    demand: list[int]
    service_time: int
    time_window: tuple[int, int] | None
    skills_required: frozenset[int]
    prize: float | None = None
    time_window_flex: TimeWindowFlex | None = None

    def as_job(self) -> JobNodeRecord:
        return self


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

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, VehicleRecord):
            return NotImplemented
        return (
            self.capacity == other.capacity
            and self.start_depot_node_id == other.start_depot_node_id
            and self.end_depot_node_id == other.end_depot_node_id
            and self.skills == other.skills
            and self.time_window == other.time_window
            and self.time_window_flex == other.time_window_flex
            and self.fixed_use_cost == other.fixed_use_cost
            and self.max_route_distance == other.max_route_distance
            and self.max_route_time == other.max_route_time
            and self.max_route_overtime == other.max_route_overtime
            and self.route_overtime_unit_cost == other.route_overtime_unit_cost
            and self.max_slack_time == other.max_slack_time
        )

    def __ne__(self, other: object) -> bool:
        eq = self.__eq__(other)
        if eq is NotImplemented:
            return NotImplemented
        return not eq


@dataclass(slots=True)
class PickupDeliveryRecord:
    """Pickup–delivery pair by unified job node ids."""

    pickup_job_node_id: int
    delivery_job_node_id: int


@dataclass(frozen=True, slots=True)
class JobGroupRecord:
    """Mutually exclusive jobs: at most one visit among members (see ``skip_penalty``)."""

    member_job_node_ids: tuple[int, ...]
    skip_penalty: int | None = None


NodeRecord = DepotNodeRecord | JobNodeRecord
