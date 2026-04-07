"""TypedDict shapes for ``vrplib.read_instance`` / ``vrplib.write_instance`` payloads."""

from __future__ import annotations

from typing import TypedDict

import numpy as np
from numpy.typing import NDArray


class VRPLibReadDict(TypedDict, total=False):
    """Shape of instance dicts from ``vrplib.read_instance`` (snake_case keys)."""

    name: str
    type: str
    dimension: int
    vehicles: int
    capacity: int | float
    node_coord: NDArray[np.float64]
    demand: NDArray[np.int_]
    depot: NDArray[np.int_]
    service_time: NDArray[np.int_]
    time_window: NDArray[np.int_]
    prize: NDArray[np.float64]
    linehaul: NDArray[np.int_]
    backhaul: NDArray[np.int_]
    edge_weight: NDArray[np.float64]
    edge_weight_type: str
    edge_weight_format: str
    capacity_section: NDArray[np.int_] | int
    vehicles_depot: NDArray[np.int_]
    vehicles_depots: NDArray[np.int_]
    edge_duration: NDArray[np.float64]
    edge_time: NDArray[np.float64]
    duration_matrix: NDArray[np.float64]
    time_matrix: NDArray[np.float64]
    edge_weight_duration: NDArray[np.float64]
    edge_weight_time: NDArray[np.float64]


class VRPLibWriteDict(TypedDict, total=False):
    """Payload for ``vrplib.write_instance`` (file-style UPPER keys)."""

    NAME: str
    DIMENSION: int
    TYPE: str
    VEHICLES: int
    CAPACITY: int
    NODE_COORD_SECTION: NDArray[np.float64]
    DEMAND_SECTION: NDArray[np.int32]
    TIME_WINDOW_SECTION: NDArray[np.int32]
    SERVICE_TIME_SECTION: NDArray[np.int32]
    VEHICLES_DEPOT_SECTION: NDArray[np.int32]
    CAPACITY_SECTION: NDArray[np.int32]
    DEPOT_SECTION: NDArray[np.int32]
    EDGE_WEIGHT_SECTION: NDArray[np.float64]
    EDGE_WEIGHT_TYPE: str
    EDGE_WEIGHT_FORMAT: str
