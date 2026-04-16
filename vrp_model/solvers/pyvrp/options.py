"""PyVRP-specific solver options (extends shared keys)."""

from __future__ import annotations

from vrp_model.solvers.options import SolverOptions, default_solver_options


class PyVRPSolverOptions(SolverOptions, total=False):
    """Options for :class:`~vrp_model.solvers.pyvrp.solver.PyVRPSolver`.

    Currently the same keys as :class:`~vrp_model.solvers.options.SolverOptions`
    (``time_limit``, ``seed``, ``msg``, ``log_path``, etc.). Add PyVRP-only fields here
    when the adapter exposes them.
    """


def default_pyvrp_solver_options() -> dict[str, object]:
    """Defaults: same as :func:`~vrp_model.solvers.options.default_solver_options`."""
    return default_solver_options()


def merge_pyvrp_solver_options(*layers: dict | None) -> dict[str, object]:
    """Merge option dicts on top of :func:`default_pyvrp_solver_options`."""
    merged: dict[str, object] = dict(default_pyvrp_solver_options())
    for layer in layers:
        if not layer:
            continue
        merged.update(layer)
    return merged
