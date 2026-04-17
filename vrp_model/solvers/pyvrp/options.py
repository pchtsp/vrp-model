"""PyVRP-specific solver options (extends shared keys)."""

from __future__ import annotations

from vrp_model.solvers.options import (
    FullSolverOptions,
    default_solver_options,
    merge_solver_options,
)


class PyVRPSolverOptions(FullSolverOptions):
    """Options for :class:`~vrp_model.solvers.pyvrp.solver.PyVRPSolver`."""


def default_pyvrp_solver_options() -> dict[str, object]:
    """Defaults: same as :func:`~vrp_model.solvers.options.default_solver_options`."""
    return default_solver_options()


def merge_pyvrp_solver_options(*layers: dict | None) -> PyVRPSolverOptions:
    """Merge option dicts on top of :func:`default_pyvrp_solver_options`."""
    # Structural alias of FullSolverOptions (distinct public name for PyVRP).
    return merge_solver_options(*layers, defaults=default_pyvrp_solver_options())
