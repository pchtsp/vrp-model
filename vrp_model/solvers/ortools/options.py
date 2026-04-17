"""OR-Tools–specific solver options (extends shared keys)."""

from __future__ import annotations

from typing import TypedDict, cast

from vrp_model.solvers.options import (
    FullSolverOptions,
    default_solver_options,
    full_solver_options_from_dict,
    merge_option_layers,
)

FIRST_SOLUTION_STRATEGY = "first_solution_strategy"
LOCAL_SEARCH_METAHEURISTIC = "local_search_metaheuristic"


class ORToolsSolverOptions(TypedDict, total=False):
    """Options for :class:`~vrp_model.solvers.ortools.solver.ORToolsSolver`.

    Includes shared keys from :mod:`vrp_model.solvers.options` plus OR-Tools search enums
    (integer values matching ``ortools.constraint_solver.routing_enums_pb2``).
    """

    first_solution_strategy: int | None
    local_search_metaheuristic: int | None


class FullORToolsSolverOptions(FullSolverOptions):
    """Merged OR-Tools options including normalized standard keys."""

    first_solution_strategy: int | None
    local_search_metaheuristic: int | None


def default_ortools_solver_options() -> dict[str, object]:
    """Defaults: shared solver defaults plus OR-Tools search fields (``None`` = library default)."""
    out = default_solver_options()
    out[FIRST_SOLUTION_STRATEGY] = None
    out[LOCAL_SEARCH_METAHEURISTIC] = None
    return out


def merge_ortools_solver_options(*layers: dict | None) -> FullORToolsSolverOptions:
    """Merge option dicts on top of :func:`default_ortools_solver_options`."""
    merged = merge_option_layers(default_ortools_solver_options(), *layers)
    std = full_solver_options_from_dict(merged)
    combined: dict[str, object] = {**std}
    combined[FIRST_SOLUTION_STRATEGY] = cast(int | None, merged.get(FIRST_SOLUTION_STRATEGY))
    combined[LOCAL_SEARCH_METAHEURISTIC] = cast(
        int | None,
        merged.get(LOCAL_SEARCH_METAHEURISTIC),
    )
    return cast(FullORToolsSolverOptions, combined)
