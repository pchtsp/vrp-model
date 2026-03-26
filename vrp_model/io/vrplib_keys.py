"""Canonical read keys for ``vrplib.read_instance`` and derived keys for ``vrplib.write_instance``.

``vrplib`` parses file specifications with ``key.lower()`` and section headers
``FOO_BAR_SECTION`` as read key ``foo_bar``. Writing uses the inverse: UPPER spec
keys and ``{READ_KEY.upper()}_SECTION`` for array sections.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from enum import StrEnum
from typing import Any, Final


class VRPLibReadKey(StrEnum):
    """Snake_case dict keys as returned by ``vrplib.read_instance``.

    ``CAPACITY`` vs ``CAPACITY_SECTION`` are different VRPLIB constructs (not aliases):
    the former is the scalar ``CAPACITY`` specification (one limit for every vehicle);
    the latter is the ``CAPACITY_SECTION`` data block (one value per vehicle).
    """

    NAME = "name"
    TYPE = "type"
    DIMENSION = "dimension"
    VEHICLES = "vehicles"
    CAPACITY = "capacity"  # file spec ``CAPACITY`` (homogeneous fleet)
    CAPACITY_SECTION = "capacity_section"  # file section ``CAPACITY_SECTION`` (per vehicle)
    NODE_COORD = "node_coord"
    DEMAND = "demand"
    DEPOT = "depot"
    SERVICE_TIME = "service_time"
    TIME_WINDOW = "time_window"
    PRIZE = "prize"
    LINEHAUL = "linehaul"
    BACKHAUL = "backhaul"
    EDGE_WEIGHT = "edge_weight"
    EDGE_WEIGHT_TYPE = "edge_weight_type"
    EDGE_WEIGHT_FORMAT = "edge_weight_format"
    VEHICLES_DEPOT = "vehicles_depot"
    VEHICLES_DEPOTS = "vehicles_depots"
    EDGE_DURATION = "edge_duration"
    EDGE_TIME = "edge_time"
    DURATION_MATRIX = "duration_matrix"
    TIME_MATRIX = "time_matrix"
    EDGE_WEIGHT_DURATION = "edge_weight_duration"
    EDGE_WEIGHT_TIME = "edge_weight_time"


def write_spec_key(read_key: str) -> str:
    """Write dict key for a scalar specification (inverse of parse_specification)."""
    return read_key.upper()


def write_section_key(read_key: str) -> str:
    """Write dict key for a data section (inverse of parse_section header parsing)."""
    return f"{read_key.upper()}_SECTION"


def read_key_from_write_spec(key: str) -> str:
    """Read-side spec key from a write dict key."""
    return key.lower()


def read_key_from_write_section(header: str) -> str:
    """Read-side key from a write section header string."""
    return header.removesuffix("_SECTION").lower()


def get_first_present(data: Mapping[str, Any], keys: Iterable[str]) -> Any | None:
    """Return ``data[k]`` for the first ``k`` in ``keys`` that is present."""
    for key in keys:
        if key in data:
            return data[key]
    return None


VEHICLES_DEPOT_READ_KEYS: Final[tuple[VRPLibReadKey, ...]] = (
    VRPLibReadKey.VEHICLES_DEPOT,
    VRPLibReadKey.VEHICLES_DEPOTS,
)

DURATION_MATRIX_READ_KEYS: Final[tuple[VRPLibReadKey, ...]] = (
    VRPLibReadKey.EDGE_DURATION,
    VRPLibReadKey.EDGE_TIME,
    VRPLibReadKey.DURATION_MATRIX,
    VRPLibReadKey.TIME_MATRIX,
    VRPLibReadKey.EDGE_WEIGHT_DURATION,
    VRPLibReadKey.EDGE_WEIGHT_TIME,
)
