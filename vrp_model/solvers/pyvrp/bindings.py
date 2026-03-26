"""Lazy PyVRP imports and typing protocols (no vrp_model.core imports)."""

from __future__ import annotations

from typing import Any, Protocol

PyVRPModel: Any = None
PyVRPMaxRuntime: Any = None

try:
    from pyvrp import Model as _PyVRPModel
    from pyvrp.stop import MaxRuntime as _PyVRPMaxRuntime

    PyVRPModel = _PyVRPModel
    PyVRPMaxRuntime = _PyVRPMaxRuntime

except ModuleNotFoundError:  # pragma: no cover - exercised when extra not installed
    pass

TW_LATE_DEFAULT = 9223372036854775807
CAP_PAD = 10**9


class HasXY(Protocol):
    x: float
    y: float


class PyVRPModelLike(Protocol):
    def add_depot(self, x: float, y: float, *args: object, **kwargs: object) -> object: ...

    def add_client(self, x: float, y: float, *args: object, **kwargs: object) -> object: ...

    def add_edge(self, frm: object, to: object, distance: int, duration: int = 0) -> object: ...

    def add_vehicle_type(self, *args: object, **kwargs: object) -> object: ...

    def solve(self, stop: object, *args: object, **kwargs: object) -> object: ...


class PyVRPRouteLike(Protocol):
    def vehicle_type(self) -> int: ...
    def start_depot(self) -> int: ...
    def end_depot(self) -> int: ...
    def visits(self) -> list[int]: ...


class PyVRPBestLike(Protocol):
    def is_feasible(self) -> bool: ...
    def routes(self) -> list[PyVRPRouteLike]: ...
    def distance(self) -> int: ...


class PyVRPResultLike(Protocol):
    @property
    def best(self) -> PyVRPBestLike: ...
