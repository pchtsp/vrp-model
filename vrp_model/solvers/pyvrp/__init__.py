"""PyVRP backend."""

from vrp_model.solvers.pyvrp.solver import PyVRPSolver
from vrp_model.solvers.registry import register

register("pyvrp", PyVRPSolver)

__all__ = ["PyVRPSolver"]
