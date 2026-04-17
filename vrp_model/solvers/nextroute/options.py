"""Nextmv Nextroute solver options."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from vrp_model.solvers.options import (
    TIME_LIMIT,
    FullSolverOptions,
    default_solver_options,
    full_solver_options_from_dict,
    merge_option_layers,
)

# Anchor for mapping model integer times (seconds offset) to Nextroute datetimes.
TIME_ANCHOR = "time_anchor"

_DEFAULT_ANCHOR = datetime(2020, 1, 1, tzinfo=UTC)

# Fallback speed (m/s) for Nextroute when travel is not matrix-only.
DEFAULT_SPEED_MPS = 30.0
SPEED_MPS = "speed_mps"


class FullNextrouteSolverOptions(FullSolverOptions):
    time_anchor: datetime
    speed_mps: float


def default_nextroute_solver_options() -> dict[str, object]:
    base = default_solver_options()
    base[TIME_ANCHOR] = _DEFAULT_ANCHOR
    base[SPEED_MPS] = DEFAULT_SPEED_MPS
    return base


def merge_nextroute_solver_options(*layers: dict | None) -> FullNextrouteSolverOptions:
    merged = merge_option_layers(default_nextroute_solver_options(), *layers)
    std = full_solver_options_from_dict(merged)
    combined: dict[str, object] = {**std}
    anchor_raw = merged[TIME_ANCHOR]
    if isinstance(anchor_raw, datetime):
        anchor = anchor_raw if anchor_raw.tzinfo else anchor_raw.replace(tzinfo=UTC)
    else:
        anchor = datetime.fromisoformat(str(anchor_raw).replace("Z", "+00:00"))
    combined[TIME_ANCHOR] = anchor
    combined[SPEED_MPS] = float(cast(float | int, merged.get(SPEED_MPS, DEFAULT_SPEED_MPS)))
    return cast(FullNextrouteSolverOptions, combined)


def build_nextroute_engine_options(
    merged: FullNextrouteSolverOptions,
    nextroute_options_cls: type,
) -> object:
    tl = float(merged[TIME_LIMIT])
    dur = max(tl, 0.1)
    return nextroute_options_cls(SOLVE_DURATION=dur)
