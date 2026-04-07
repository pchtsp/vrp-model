"""Layer 1: required entities exist."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vrp_model.core.errors import ValidationError

if TYPE_CHECKING:
    from vrp_model.core.model import Model


def validate(model: Model) -> None:
    """Require at least one depot and one vehicle."""
    if next(model.depots, None) is None:
        raise ValidationError("at least one depot is required")
    if next(model.vehicles, None) is None:
        raise ValidationError("at least one vehicle is required")
