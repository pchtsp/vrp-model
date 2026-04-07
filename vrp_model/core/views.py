"""Lightweight proxies over Model storage (no copied state)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vrp_model.core.errors import ValidationError
from vrp_model.core.kinds import NodeKind
from vrp_model.core.storage import normalize_load

if TYPE_CHECKING:
    from vrp_model.core.model import Model


class Depot:
    """Read/write view of a depot row in :class:`~vrp_model.core.model.Model` storage."""

    __slots__ = ("_model", "_node_id")

    def __init__(self, model: Model, node_id: int) -> None:
        self._model = model
        if node_id < 0 or node_id >= len(model._nodes):
            raise ValidationError("depot node_id is out of range for this model")
        if model._nodes[node_id].kind != NodeKind.DEPOT:
            raise ValidationError("node_id does not refer to a depot")
        self._node_id = node_id

    @property
    def node_id(self) -> int:
        return self._node_id

    @property
    def label(self) -> str | None:
        return self._model._nodes[self._node_id].label

    @label.setter
    def label(self, value: str | None) -> None:
        self._model._nodes[self._node_id].label = value

    @property
    def location(self) -> tuple[float, float] | None:
        loc = self._model._nodes[self._node_id].location
        if loc is None:
            return None
        return (float(loc[0]), float(loc[1]))

    @location.setter
    def location(self, value: tuple[float, float] | None) -> None:
        if value is None:
            self._model._nodes[self._node_id].location = None
        else:
            self._model._nodes[self._node_id].location = (
                float(value[0]),
                float(value[1]),
            )


class Vehicle:
    """Read/write view of one vehicle row (capacity, depots, skills, time window)."""

    __slots__ = ("_model", "_idx")

    def __init__(self, model: Model, idx: int) -> None:
        self._model = model
        self._idx = idx

    @property
    def label(self) -> str | None:
        return self._model._vehicles[self._idx].label

    @label.setter
    def label(self, value: str | None) -> None:
        self._model._vehicles[self._idx].label = value

    @property
    def capacity(self) -> list[int]:
        return self._model._vehicles[self._idx].capacity

    @capacity.setter
    def capacity(self, value: int | list[int]) -> None:
        self._model._vehicles[self._idx].capacity = normalize_load(value)

    @property
    def start_depot(self) -> Depot:
        nid = self._model._vehicles[self._idx].start_depot_node_id
        return Depot(self._model, nid)

    @start_depot.setter
    def start_depot(self, value: Depot) -> None:
        if value._model is not self._model:
            raise ValidationError("depot must belong to this model")
        self._model._vehicles[self._idx].start_depot_node_id = value.node_id

    @property
    def end_depot(self) -> Depot:
        rec = self._model._vehicles[self._idx]
        end_nid = rec.end_depot_node_id
        if end_nid is None:
            return Depot(self._model, rec.start_depot_node_id)
        return Depot(self._model, end_nid)

    @end_depot.setter
    def end_depot(self, value: Depot | None) -> None:
        if value is None:
            self._model._vehicles[self._idx].end_depot_node_id = None
        else:
            if value._model is not self._model:
                raise ValidationError("depot must belong to this model")
            self._model._vehicles[self._idx].end_depot_node_id = value.node_id

    @property
    def skills(self) -> frozenset[str]:
        return self._model._vehicles[self._idx].skills

    @skills.setter
    def skills(self, value: set[str] | frozenset[str]) -> None:
        self._model._vehicles[self._idx].skills = frozenset(value)

    @property
    def time_window(self) -> tuple[int, int] | None:
        return self._model._vehicles[self._idx].time_window

    @time_window.setter
    def time_window(self, value: tuple[int, int] | None) -> None:
        self._model._vehicles[self._idx].time_window = value


class Job:
    """Read/write view of a customer / stop row (demand, location, time window, skills, prize)."""

    __slots__ = ("_model", "_node_id")

    def __init__(self, model: Model, node_id: int) -> None:
        self._model = model
        if node_id < 0 or node_id >= len(model._nodes):
            raise ValidationError("job node_id is out of range for this model")
        if model._nodes[node_id].kind != NodeKind.JOB:
            raise ValidationError("node_id does not refer to a job")
        self._node_id = node_id

    @property
    def node_id(self) -> int:
        return self._node_id

    @property
    def label(self) -> str | None:
        return self._model._nodes[self._node_id].label

    @label.setter
    def label(self, value: str | None) -> None:
        self._model._nodes[self._node_id].label = value

    @property
    def location(self) -> tuple[float, float] | None:
        loc = self._model._nodes[self._node_id].location
        if loc is None:
            return None
        return (float(loc[0]), float(loc[1]))

    @location.setter
    def location(self, value: tuple[float, float] | None) -> None:
        if value is None:
            self._model._nodes[self._node_id].location = None
        else:
            self._model._nodes[self._node_id].location = (
                float(value[0]),
                float(value[1]),
            )

    @property
    def demand(self) -> list[int]:
        return self._model._nodes[self._node_id].demand

    @demand.setter
    def demand(self, value: int | list[int]) -> None:
        self._model._nodes[self._node_id].demand = normalize_load(value)

    @property
    def service_time(self) -> int:
        return self._model._nodes[self._node_id].service_time

    @service_time.setter
    def service_time(self, value: int) -> None:
        self._model._nodes[self._node_id].service_time = int(value)

    @property
    def time_window(self) -> tuple[int, int] | None:
        return self._model._nodes[self._node_id].time_window

    @time_window.setter
    def time_window(self, value: tuple[int, int] | None) -> None:
        self._model._nodes[self._node_id].time_window = value

    @property
    def skills_required(self) -> frozenset[str]:
        return self._model._nodes[self._node_id].skills_required

    @skills_required.setter
    def skills_required(self, value: set[str] | frozenset[str]) -> None:
        self._model._nodes[self._node_id].skills_required = frozenset(value)

    @property
    def prize(self) -> float | None:
        return self._model._nodes[self._node_id].prize

    @prize.setter
    def prize(self, value: float | None) -> None:
        self._model._nodes[self._node_id].prize = value
