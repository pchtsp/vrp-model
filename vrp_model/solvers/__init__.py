"""Pluggable VRP solvers."""

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
from vrp_model.solvers.registry import get, register
from vrp_model.solvers.status import SolutionStatus, SolverStopReason

__all__ = [
    "SolutionStatus",
    "SolverStopReason",
    "GAP_ABS",
    "GAP_REL",
    "LOG_PATH",
    "MAX_ITERATIONS",
    "MSG",
    "SEED",
    "TIME_LIMIT",
    "Solver",
    "SolverOptions",
    "default_solver_options",
    "get",
    "merge_solver_options",
    "register",
]
