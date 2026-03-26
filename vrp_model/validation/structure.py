"""Layer 1: required entities exist."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vrp_model.core.errors import ValidationError
from vrp_model.core.kinds import NodeKind

if TYPE_CHECKING:
    from vrp_model.core.model import Model


def validate(model: Model) -> None:
    n_depot = sum(1 for row in model._nodes if row["kind"] == NodeKind.DEPOT)
    if n_depot < 1:
        raise ValidationError("at least one depot is required")
    if len(model._vehicles) < 1:
        raise ValidationError("at least one vehicle is required")
