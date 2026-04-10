"""Core model, solution, and feature types."""

from vrp_model.core.errors import (
    MappingError,
    SolutionUnavailableError,
    SolverCapabilityError,
    SolverNotInstalledError,
    ValidationError,
    VRPModelError,
)
from vrp_model.core.kinds import NodeKind
from vrp_model.core.model import Feature, Model, SolveStatus
from vrp_model.core.solution import Route, Solution
from vrp_model.core.time_window_flex import TimeWindowFlex
from vrp_model.core.travel_edges import TRAVEL_COST_INF, TravelEdgeAttrs, TravelEdgesMap
from vrp_model.core.views import Depot, Job, Vehicle

__all__ = [
    "Depot",
    "Feature",
    "Job",
    "MappingError",
    "Model",
    "NodeKind",
    "Route",
    "Solution",
    "SolveStatus",
    "TRAVEL_COST_INF",
    "TravelEdgeAttrs",
    "TravelEdgesMap",
    "TimeWindowFlex",
    "SolverCapabilityError",
    "SolverNotInstalledError",
    "SolutionUnavailableError",
    "ValidationError",
    "VRPModelError",
    "Vehicle",
]
