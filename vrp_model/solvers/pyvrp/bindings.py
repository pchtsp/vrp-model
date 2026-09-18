"""Lazy PyVRP imports and typing protocols (no vrp_model.core imports)."""

from __future__ import annotations

from typing import Any, Protocol

PyVRPClient: Any = None
PyVRPClientGroup: Any = None
PyVRPDepot: Any = None
PyVRPLocation: Any = None
PyVRPMaxRuntime: Any = None
PyVRPProblemData: Any = None
PyVRPShipment: Any = None
PyVRPSolve: Any = None
PyVRPVehicleType: Any = None
np: Any = None

try:
    import numpy as _np
    from pyvrp import Client as _Client
    from pyvrp import ClientGroup as _ClientGroup
    from pyvrp import Depot as _Depot
    from pyvrp import Location as _Location
    from pyvrp import ProblemData as _ProblemData
    from pyvrp import Shipment as _Shipment
    from pyvrp import VehicleType as _VehicleType
    from pyvrp import solve as _solve
    from pyvrp.stop import MaxRuntime as _PyVRPMaxRuntime

    PyVRPClient = _Client
    PyVRPClientGroup = _ClientGroup
    PyVRPDepot = _Depot
    PyVRPLocation = _Location
    PyVRPMaxRuntime = _PyVRPMaxRuntime
    PyVRPProblemData = _ProblemData
    PyVRPShipment = _Shipment
    PyVRPSolve = _solve
    PyVRPVehicleType = _VehicleType
    np = _np

except ModuleNotFoundError:  # pragma: no cover - exercised when extra not installed
    pass

TW_LATE_DEFAULT = 9223372036854775807
CAP_PAD = 10**9

# Mirrors ``pyvrp.constants.MAX_VALUE``: the largest value PyVRP accepts in a distance or
# duration matrix before it warns about overflow from internal scaling.
PYVRP_MAX_VALUE = 1 << 44


class PyVRPDataLike(Protocol):
    """Minimal view of ``pyvrp.ProblemData`` that the adapter builds and hands to the solver."""

    @property
    def num_clients(self) -> int: ...

    @property
    def num_vehicle_types(self) -> int: ...

    @property
    def num_profiles(self) -> int: ...

    def vehicle_type(self, idx: int) -> Any: ...

    def distance_matrix(self, profile: int) -> Any: ...

    def duration_matrix(self, profile: int) -> Any: ...


class PyVRPActivityLike(Protocol):
    """One stop on a route: a depot, a client, or a shipment pickup/delivery.

    ``idx`` indexes into the model's depots, clients, or shipments, depending on the
    activity kind.
    """

    @property
    def idx(self) -> int: ...

    def is_depot(self) -> bool: ...
    def is_client(self) -> bool: ...
    def is_pickup(self) -> bool: ...
    def is_delivery(self) -> bool: ...


class PyVRPRouteLike(Protocol):
    def vehicle_type(self) -> int: ...
    def start_depot(self) -> int: ...
    def end_depot(self) -> int: ...
    def schedule(self) -> list[PyVRPActivityLike]: ...


class PyVRPBestLike(Protocol):
    def is_feasible(self) -> bool: ...
    def routes(self) -> list[PyVRPRouteLike]: ...
    def distance(self) -> int: ...


class PyVRPResultLike(Protocol):
    @property
    def best(self) -> PyVRPBestLike: ...

    @property
    def num_iterations(self) -> int: ...

    @property
    def runtime(self) -> float: ...

    def cost(self) -> int: ...

    def summary(self) -> str: ...
