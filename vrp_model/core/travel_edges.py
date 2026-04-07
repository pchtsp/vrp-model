"""Validation for sparse travel cost storage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from vrp_model.core.errors import ValidationError

# Align with ``pyvrp.constants.MAX_VALUE`` (large, but within solver limits).
TRAVEL_COST_INF = 1 << 44


@dataclass(frozen=True, slots=True)
class TravelEdgeAttrs:
    """Directed travel override for one pair of node ids.

    ``None`` means the field was not specified for this stored edge. In PyVRP, that field is
    set to infinite cost. When ``travel_edges`` is non-empty, arcs not in the map are also
    infinite; Euclidean is used only when the map is empty (and every job has a location).
    """

    distance: int | None = None
    duration: int | None = None


TravelEdgesMap: TypeAlias = dict[tuple[int, int], TravelEdgeAttrs]


def validate_travel_edges(
    n_nodes: int,
    edges: TravelEdgesMap,
) -> None:
    """Validate ``edges`` against ``n_nodes``.

    Keys must be ``(int, int)`` node ids; values must be :class:`TravelEdgeAttrs` instances.
    """
    for (i, j), attrs in edges.items():
        if not isinstance(i, int) or not isinstance(j, int):
            msg = f"travel edge keys must be int node ids, got {(i, j)!r}"
            raise TypeError(msg)
        if not isinstance(attrs, TravelEdgeAttrs):
            msg = f"travel edge values must be TravelEdgeAttrs, got {type(attrs).__name__}"
            raise TypeError(msg)
        if i < 0 or i >= n_nodes or j < 0 or j >= n_nodes:
            raise ValidationError(f"travel edge ({i}, {j}) references unknown node id")
        if i == j:
            raise ValidationError(f"travel edge ({i}, {j}) must not be a self-loop")
        if attrs.distance is None and attrs.duration is None:
            raise ValidationError(
                f"travel edge ({i}, {j}) must set distance and/or duration"
            )
        if attrs.distance is not None and attrs.distance < 0:
            raise ValidationError(
                f"travel edge ({i}, {j}) distance must be non-negative"
            )
        if attrs.duration is not None and attrs.duration < 0:
            raise ValidationError(
                f"travel edge ({i}, {j}) duration must be non-negative"
            )
