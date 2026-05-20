"""Standard solver option keys and default merge behavior for all backends."""

from __future__ import annotations

from typing import TypedDict, cast

# Canonical option keys (use these when building option dicts).
TIME_LIMIT = "time_limit"
SEED = "seed"
MAX_ITERATIONS = "max_iterations"
GAP_REL = "gap_rel"
GAP_ABS = "gap_abs"
MSG = "msg"
LOG_PATH = "log_path"
# When the canonical model marks an arc as unreachable (``TRAVEL_COST_INF``), solvers map it
# to a backend-specific large cost. Set these to override that sentinel per solver run.
MISSING_ARC_DISTANCE = "missing_arc_distance"
MISSING_ARC_DURATION = "missing_arc_duration"
# PyVRP: skip ``add_edge`` for arcs failing :func:`~vrp_model.solvers._helpers.should_add_explicit_edge`.
OMIT_UNREACHABLE_ARCS = "omit_unreachable_arcs"


class SolverOptions(TypedDict, total=False):
    """Typed view of the standard solver options (all keys optional in user input)."""

    time_limit: float | None
    seed: int | None
    max_iterations: int | None
    gap_rel: float | None
    gap_abs: float | None
    msg: bool | None
    log_path: str | None
    missing_arc_distance: int | None
    missing_arc_duration: int | None
    omit_unreachable_arcs: bool | None


class FullSolverOptions(TypedDict):
    """Merged standard options with concrete defaults (post-merge)."""

    time_limit: float
    seed: int
    max_iterations: int | None
    gap_rel: float | None
    gap_abs: float | None
    msg: bool
    log_path: str | None
    missing_arc_distance: int | None
    missing_arc_duration: int | None
    omit_unreachable_arcs: bool


def default_solver_options() -> dict[str, object]:
    """Return the full standard option set with package defaults.

    ``None`` means “leave to the solver” where applicable (gaps / iteration cap).
    ``time_limit`` is in seconds (wall-clock budget for the search loop).
    ``msg`` enables progress messages; ``log_path`` (if set) receives PyVRP progress logs.
    ``missing_arc_distance`` / ``missing_arc_duration`` override the backend cost used when the
    canonical model marks an arc unreachable (``TRAVEL_COST_INF``); ``None`` keeps each solver's
    built-in default (e.g. PyVRP ``MAX_VALUE`` scale, OR-Tools transit cap, VROOM uint32 max).
    ``omit_unreachable_arcs`` (PyVRP) skips ``add_edge`` for forbidden legs; omitted pairs use
    PyVRP's ``missing_value`` (from ``missing_arc_*`` when set).
    """
    return {
        TIME_LIMIT: 3.0,
        SEED: 0,
        MAX_ITERATIONS: None,
        GAP_REL: None,
        GAP_ABS: None,
        MSG: False,
        LOG_PATH: None,
        MISSING_ARC_DISTANCE: None,
        MISSING_ARC_DURATION: None,
        OMIT_UNREACHABLE_ARCS: False,
    }


def merge_option_layers(
    defaults: dict[str, object],
    *layers: dict | None,
) -> dict[str, object]:
    """Merge flat option dicts: later layers override earlier ones; skip empty ``None`` layers."""
    merged = dict(defaults)
    for layer in layers:
        if not layer:
            continue
        merged.update(layer)
    return merged


def full_solver_options_from_dict(merged: dict[str, object]) -> FullSolverOptions:
    """Normalize a merged flat dict to :class:`FullSolverOptions` (standard keys only)."""
    return FullSolverOptions(
        time_limit=float(cast(float | int, merged[TIME_LIMIT])),
        seed=int(cast(int, merged[SEED])),
        max_iterations=cast(int | None, merged.get(MAX_ITERATIONS)),
        gap_rel=cast(float | None, merged.get(GAP_REL)),
        gap_abs=cast(float | None, merged.get(GAP_ABS)),
        msg=bool(merged[MSG]),
        log_path=cast(str | None, merged.get(LOG_PATH)),
        missing_arc_distance=_optional_int(merged.get(MISSING_ARC_DISTANCE)),
        missing_arc_duration=_optional_int(merged.get(MISSING_ARC_DURATION)),
        omit_unreachable_arcs=bool(merged.get(OMIT_UNREACHABLE_ARCS, False)),
    )


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return int(cast(int, value))


def merge_solver_options(
    *layers: dict | None,
    defaults: dict[str, object] | None = None,
) -> FullSolverOptions:
    """Merge option dicts: later layers override earlier ones. Skips empty ``None`` layers."""
    base = defaults if defaults is not None else default_solver_options()
    merged = merge_option_layers(base, *layers)
    return full_solver_options_from_dict(merged)


def opt_float(merged: dict[str, object], key: str) -> float:
    """Read a float option from a merged dict (fallback when not in a TypedDict)."""
    return float(cast(float | int, merged[key]))


def opt_int(merged: dict[str, object], key: str, default: int = 0) -> int:
    """Read an int option from a merged dict."""
    return int(cast(int, merged.get(key, default)))
