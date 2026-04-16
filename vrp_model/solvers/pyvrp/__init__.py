"""PyVRP backend."""

from vrp_model.solvers.pyvrp.options import (
    PyVRPSolverOptions,
    default_pyvrp_solver_options,
    merge_pyvrp_solver_options,
)
from vrp_model.solvers.pyvrp.solver import PyVRPSolver
from vrp_model.solvers.registry import register

register("pyvrp", PyVRPSolver)

__all__ = [
    "PyVRPSolver",
    "PyVRPSolverOptions",
    "default_pyvrp_solver_options",
    "merge_pyvrp_solver_options",
]
