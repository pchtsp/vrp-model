"""Human-readable labels for validation error messages."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vrp_model.core.model import Model


def vehicle_tag(model: Model, vi: int) -> str:
    """Return vehicle label or a default ``vehicle_{vi}`` string."""
    lab = model._vehicles[vi].label
    return lab if lab is not None else f"vehicle_{vi}"


def job_tag(model: Model, node_id: int) -> str:
    """Return job label or a default ``job_{node_id}`` string."""
    lab = model._nodes[node_id].label
    return lab if lab is not None else f"job_{node_id}"
