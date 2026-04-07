"""Internal schema helpers: normalize loads and clone-friendly set handling."""

from __future__ import annotations

from typing import TypeAlias

LoadVec: TypeAlias = list[int]


def normalize_load(value: int | list[int]) -> LoadVec:
    """Normalize capacity or demand to a non-empty list of int dimensions."""
    if isinstance(value, int):
        return [value]
    if not value:
        return []
    return [int(x) for x in value]


def skills_to_frozen(skills: set[str] | frozenset[str]) -> frozenset[str]:
    """Copy skill names to an immutable set for model storage."""
    return frozenset(skills)
