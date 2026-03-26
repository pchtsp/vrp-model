"""vrp_model: canonical VRP modeling API (solver-agnostic core)."""

from vrp_model.core.errors import (
    MappingError,
    SolverCapabilityError,
    SolverNotInstalledError,
    ValidationError,
    VRPModelError,
)
from vrp_model.core.kinds import NodeKind
from vrp_model.core.model import Feature, Model, SolveStatus, detect_features
from vrp_model.core.solution import Route, Solution
from vrp_model.core.travel_edges import TRAVEL_COST_INF, TravelEdgeAttrs
from vrp_model.core.views import Depot, Job, Vehicle
from vrp_model.solvers.base import Solver
from vrp_model.solvers.options import (
    GAP_ABS,
    GAP_REL,
    LOG_PATH,
    MAX_ITERATIONS,
    MSG,
    SEED,
    TIME_LIMIT,
    SolverOptions,
    default_solver_options,
    merge_solver_options,
)

__all__ = [
    "Depot",
    "Feature",
    "GAP_ABS",
    "GAP_REL",
    "Job",
    "LOG_PATH",
    "MappingError",
    "MSG",
    "Model",
    "NodeKind",
    "Route",
    "Solution",
    "SolveStatus",
    "TIME_LIMIT",
    "TRAVEL_COST_INF",
    "TravelEdgeAttrs",
    "MAX_ITERATIONS",
    "SEED",
    "Solver",
    "SolverOptions",
    "SolverCapabilityError",
    "SolverNotInstalledError",
    "ValidationError",
    "VRPModelError",
    "Vehicle",
    "default_solver_options",
    "detect_features",
    "merge_solver_options",
]
