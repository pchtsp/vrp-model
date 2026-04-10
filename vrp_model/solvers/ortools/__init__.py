"""Google OR-Tools routing."""

from vrp_model.solvers.ortools.options import (
    FIRST_SOLUTION_STRATEGY,
    LOCAL_SEARCH_METAHEURISTIC,
    ORToolsSolverOptions,
    default_ortools_solver_options,
    merge_ortools_solver_options,
)
from vrp_model.solvers.ortools.solver import ORToolsSolver
from vrp_model.solvers.registry import register

register("ortools", ORToolsSolver)

__all__ = [
    "FIRST_SOLUTION_STRATEGY",
    "LOCAL_SEARCH_METAHEURISTIC",
    "ORToolsSolver",
    "ORToolsSolverOptions",
    "default_ortools_solver_options",
    "merge_ortools_solver_options",
]
