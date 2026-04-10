"""vrp_model: canonical VRP modeling API (solver-agnostic core)."""

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
from vrp_model.solvers.status import SolutionStatus, SolverStopReason

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
    "TimeWindowFlex",
    "TRAVEL_COST_INF",
    "TravelEdgeAttrs",
    "TravelEdgesMap",
    "MAX_ITERATIONS",
    "SEED",
    "Solver",
    "SolverOptions",
    "SolverCapabilityError",
    "SolutionStatus",
    "SolutionUnavailableError",
    "SolverNotInstalledError",
    "SolverStopReason",
    "ValidationError",
    "VRPModelError",
    "Vehicle",
    "default_solver_options",
    "merge_solver_options",
]
