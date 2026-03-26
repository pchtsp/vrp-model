"""Validation and normalization for sparse travel cost storage."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from vrp_model.core.errors import ValidationError

_ALLOWED_KEYS = frozenset({"distance", "duration"})

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


def _validate_travel_edge_attrs(attrs: TravelEdgeAttrs, key: tuple[int, int]) -> None:
    if attrs.distance is None and attrs.duration is None:
        raise ValidationError(f"travel edge {key} must set distance and/or duration")
    if attrs.distance is not None and attrs.distance < 0:
        raise ValidationError(f"travel edge ({key[0]}, {key[1]}) distance must be non-negative")
    if attrs.duration is not None and attrs.duration < 0:
        raise ValidationError(f"travel edge ({key[0]}, {key[1]}) duration must be non-negative")


def _coerce_edge_value(
    value: TravelEdgeAttrs | Mapping[str, int],
) -> TravelEdgeAttrs:
    if isinstance(value, TravelEdgeAttrs):
        return TravelEdgeAttrs(distance=value.distance, duration=value.duration)
    if not isinstance(value, Mapping):
        msg = f"travel edge value must be TravelEdgeAttrs or mapping, got {type(value).__name__}"
        raise TypeError(msg)
    unknown = set(value) - _ALLOWED_KEYS
    if unknown:
        names = ", ".join(sorted(repr(k) for k in unknown))
        raise ValidationError(f"travel edge has unknown keys: {names}")
    dist = value.get("distance")
    dur = value.get("duration")
    if dist is not None and not isinstance(dist, int):
        msg = f"distance must be int or omitted, got {type(dist).__name__}"
        raise TypeError(msg)
    if dur is not None and not isinstance(dur, int):
        msg = f"duration must be int or omitted, got {type(dur).__name__}"
        raise TypeError(msg)
    return TravelEdgeAttrs(distance=dist, duration=dur)


def parse_travel_edges(
    n_nodes: int,
    edges: dict[tuple[int, int], TravelEdgeAttrs | Mapping[str, int]],
) -> dict[tuple[int, int], TravelEdgeAttrs]:
    """Validate ``edges`` against ``n_nodes`` and return a normalized copy."""
    out: dict[tuple[int, int], TravelEdgeAttrs] = {}
    for (i, j), raw in edges.items():
        if not isinstance(i, int) or not isinstance(j, int):
            msg = f"travel edge keys must be int node ids, got {(i, j)!r}"
            raise TypeError(msg)
        if i < 0 or i >= n_nodes or j < 0 or j >= n_nodes:
            raise ValidationError(f"travel edge ({i}, {j}) references unknown node id")
        if i == j:
            raise ValidationError(f"travel edge ({i}, {j}) must not be a self-loop")
        attrs = _coerce_edge_value(raw)
        _validate_travel_edge_attrs(attrs, (i, j))
        out[(i, j)] = attrs
    return out
