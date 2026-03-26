"""Distance helpers for coordinate-based edges."""

from __future__ import annotations

import math


def euclidean_int(a: tuple[float, float], b: tuple[float, float]) -> int:
    """Euclidean distance rounded to nearest integer (non-negative)."""
    dx = float(a[0]) - float(b[0])
    dy = float(a[1]) - float(b[1])
    return int(round(math.hypot(dx, dy)))
