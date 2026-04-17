"""VROOM-specific solver options."""

from __future__ import annotations

from typing import TypedDict, cast

from vrp_model.solvers.options import (
    FullSolverOptions,
    default_solver_options,
    full_solver_options_from_dict,
    merge_option_layers,
)

EXPLORATION_LEVEL = "exploration_level"
NB_THREADS = "nb_threads"


class VroomSolverOptions(TypedDict, total=False):
    """Options for :class:`~vrp_model.solvers.vroom.solver.VroomSolver`.

    Extra keys:
        exploration_level: VROOM search depth, 1--5 (default 5).
        nb_threads: thread count for :meth:`vroom.Input.solve` (default 4).
    """

    exploration_level: int
    nb_threads: int


class FullVroomSolverOptions(FullSolverOptions):
    exploration_level: int
    nb_threads: int


def default_vroom_solver_options() -> dict[str, object]:
    base = default_solver_options()
    base[EXPLORATION_LEVEL] = 5
    base[NB_THREADS] = 4
    return base


def merge_vroom_solver_options(*layers: dict | None) -> FullVroomSolverOptions:
    merged = merge_option_layers(default_vroom_solver_options(), *layers)
    std = full_solver_options_from_dict(merged)
    combined: dict[str, object] = {**std}
    combined[EXPLORATION_LEVEL] = int(cast(int, merged[EXPLORATION_LEVEL]))
    combined[NB_THREADS] = int(cast(int, merged[NB_THREADS]))
    return cast(FullVroomSolverOptions, combined)
