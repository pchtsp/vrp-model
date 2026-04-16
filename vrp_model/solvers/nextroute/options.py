"""Nextmv Nextroute solver options."""

from __future__ import annotations

from datetime import UTC, datetime

from vrp_model.solvers.options import TIME_LIMIT, default_solver_options

# Anchor for mapping model integer times (seconds offset) to Nextroute datetimes.
TIME_ANCHOR = "time_anchor"

_DEFAULT_ANCHOR = datetime(2020, 1, 1, tzinfo=UTC)

# Fallback speed (m/s) for Nextroute when travel is not matrix-only.
DEFAULT_SPEED_MPS = 30.0


def default_nextroute_solver_options() -> dict[str, object]:
    base = default_solver_options()
    base[TIME_ANCHOR] = _DEFAULT_ANCHOR
    base["speed_mps"] = DEFAULT_SPEED_MPS
    return base


def merge_nextroute_solver_options(*layers: dict | None) -> dict[str, object]:
    merged: dict[str, object] = dict(default_nextroute_solver_options())
    for layer in layers:
        if not layer:
            continue
        merged.update(layer)
    return merged


def build_nextroute_engine_options(
    merged: dict[str, object],
    nextroute_options_cls: type,
) -> object:
    tl = float(merged[TIME_LIMIT])
    dur = max(tl, 0.1)
    return nextroute_options_cls(SOLVE_DURATION=dur)
