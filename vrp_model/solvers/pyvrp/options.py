"""PyVRP-specific solver options (extends shared keys)."""

from __future__ import annotations

from typing import cast

from vrp_model.core.travel_edges import TRAVEL_COST_INF
from vrp_model.solvers.options import (
    FullSolverOptions,
    default_solver_options,
    full_solver_options_from_dict,
    merge_option_layers,
)

# PyVRP-only: cost for profile-specific edges into jobs a vehicle cannot serve.
SKILL_INCOMPATIBLE_COST = "skill_incompatible_cost"


class PyVRPSolverOptions(FullSolverOptions, total=False):
    """Options for :class:`~vrp_model.solvers.pyvrp.solver.PyVRPSolver`."""

    skill_incompatible_cost: int


def default_pyvrp_solver_options() -> dict[str, object]:
    """Defaults: shared solver keys plus PyVRP-specific options."""
    out = default_solver_options()
    out[SKILL_INCOMPATIBLE_COST] = TRAVEL_COST_INF
    return out


def merge_pyvrp_solver_options(*layers: dict | None) -> PyVRPSolverOptions:
    """Merge option dicts on top of :func:`default_pyvrp_solver_options`."""
    merged = merge_option_layers(default_pyvrp_solver_options(), *layers)
    base = full_solver_options_from_dict(merged)
    return PyVRPSolverOptions(
        **base,
        skill_incompatible_cost=int(cast(int, merged[SKILL_INCOMPATIBLE_COST])),
    )
