"""OR-Tools–specific solver options (extends shared keys)."""

from __future__ import annotations

from typing import TypedDict

from vrp_model.solvers.options import default_solver_options

FIRST_SOLUTION_STRATEGY = "first_solution_strategy"
LOCAL_SEARCH_METAHEURISTIC = "local_search_metaheuristic"


class ORToolsSolverOptions(TypedDict, total=False):
    """Options for :class:`~vrp_model.solvers.ortools.solver.ORToolsSolver`.

    Includes shared keys from :mod:`vrp_model.solvers.options` plus OR-Tools search enums
    (integer values matching ``ortools.constraint_solver.routing_enums_pb2``).
    """

    time_limit: float | None
    seed: int | None
    max_iterations: int | None
    gap_rel: float | None
    gap_abs: float | None
    msg: bool | None
    log_path: str | None
    first_solution_strategy: int | None
    local_search_metaheuristic: int | None


def default_ortools_solver_options() -> dict[str, object]:
    """Defaults: shared solver defaults plus OR-Tools search fields (``None`` = library default)."""
    out = default_solver_options()
    out[FIRST_SOLUTION_STRATEGY] = None
    out[LOCAL_SEARCH_METAHEURISTIC] = None
    return out


def merge_ortools_solver_options(*layers: dict | None) -> dict[str, object]:
    """Merge option dicts on top of :func:`default_ortools_solver_options`."""
    merged: dict[str, object] = default_ortools_solver_options()
    for layer in layers:
        if not layer:
            continue
        merged.update(layer)
    return merged
