"""Lazy OR-Tools imports (no heavy :mod:`vrp_model.core` import cycle)."""

from __future__ import annotations

from typing import Any

PyWrapCP: Any = None
RoutingEnums: Any = None

try:
    from ortools.constraint_solver import pywrapcp as _PyWrapCP
    from ortools.constraint_solver import routing_enums_pb2 as _RoutingEnums

    PyWrapCP = _PyWrapCP
    RoutingEnums = _RoutingEnums
except ModuleNotFoundError:
    PyWrapCP = None
    RoutingEnums = None
