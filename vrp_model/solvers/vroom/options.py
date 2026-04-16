"""VROOM-specific solver options."""

from __future__ import annotations

from vrp_model.solvers.options import SolverOptions, default_solver_options


class VroomSolverOptions(SolverOptions, total=False):
    """Options for :class:`~vrp_model.solvers.vroom.solver.VroomSolver`.

    Extra keys:
        exploration_level: VROOM search depth, 1--5 (default 5).
        nb_threads: thread count for :meth:`vroom.Input.solve` (default 4).
    """

    exploration_level: int
    nb_threads: int


def default_vroom_solver_options() -> dict[str, object]:
    base = default_solver_options()
    base["exploration_level"] = 5
    base["nb_threads"] = 4
    return base


def merge_vroom_solver_options(*layers: dict | None) -> dict[str, object]:
    merged: dict[str, object] = dict(default_vroom_solver_options())
    for layer in layers:
        if not layer:
            continue
        merged.update(layer)
    return merged
