"""Vehicle group (shared availability) checks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vrp_model.core.errors import ValidationError
from vrp_model.validation.tags import vehicle_tag

if TYPE_CHECKING:
    from vrp_model.core.model import Model


def validate(model: Model) -> None:
    """Disjoint vehicle groups, valid members, at least two members, sane ``max_active``."""
    n_vehicles = len(model._vehicles)
    seen: set[int] = set()

    for gi, g in enumerate(model._vehicle_groups):
        members = g.member_vehicle_indices
        if len(members) < 2:
            raise ValidationError(f"vehicle group {gi} must contain at least two vehicles")
        if g.max_active < 1:
            raise ValidationError(f"vehicle group {gi} must allow at least one active vehicle")
        for vi in members:
            if vi < 0 or vi >= n_vehicles:
                raise ValidationError(f"vehicle group {gi} references invalid vehicle index {vi}")
            if vi in seen:
                raise ValidationError(
                    f"vehicle {vehicle_tag(model, vi)} appears in more than one vehicle group",
                )
            seen.add(vi)
