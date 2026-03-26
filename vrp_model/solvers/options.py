"""Standard solver option keys and default merge behavior for all backends."""

from __future__ import annotations

from typing import TypedDict

# Canonical option keys (use these when building option dicts).
TIME_LIMIT = "time_limit"
SEED = "seed"
MAX_ITERATIONS = "max_iterations"
GAP_REL = "gap_rel"
GAP_ABS = "gap_abs"
MSG = "msg"
LOG_PATH = "log_path"


class SolverOptions(TypedDict, total=False):
    """Typed view of the standard solver options (all keys optional in user input)."""

    time_limit: float | None
    seed: int | None
    max_iterations: int | None
    gap_rel: float | None
    gap_abs: float | None
    msg: bool | None
    log_path: str | None


def default_solver_options() -> dict[str, object]:
    """Return the full standard option set with package defaults.

    ``None`` means “leave to the solver” where applicable (gaps / iteration cap).
    ``time_limit`` is in seconds (wall-clock budget for the search loop).
    ``msg`` enables progress messages; ``log_path`` (if set) receives PyVRP progress logs.
    """
    return {
        TIME_LIMIT: 3.0,
        SEED: 0,
        MAX_ITERATIONS: None,
        GAP_REL: None,
        GAP_ABS: None,
        MSG: False,
        LOG_PATH: None,
    }


def merge_solver_options(*layers: dict | None) -> dict[str, object]:
    """Merge option dicts: later layers override earlier ones. Skips empty ``None`` layers.

    Extra keys (e.g. backend-specific flags) are preserved.
    """
    merged: dict[str, object] = dict(default_solver_options())
    for layer in layers:
        if not layer:
            continue
        merged.update(layer)
    return merged
