"""Job type incompatibility checks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vrp_model.core.errors import ValidationError
from vrp_model.core.kinds import NodeKind
from vrp_model.validation.tags import job_tag

if TYPE_CHECKING:
    from vrp_model.core.model import Model


def validate(model: Model) -> None:
    """Non-negative job types, distinct type pairs, no incompatible pickup–delivery pair."""
    for node_id, row in enumerate(model._nodes):
        if row.kind != NodeKind.JOB:
            continue
        t = row.as_job().job_type
        if t is not None and t < 0:
            raise ValidationError(f"job {job_tag(model, node_id)} job_type must be non-negative")

    incompatible: set[frozenset[int]] = set()
    for a, b in model._job_type_incompatibilities:
        if a < 0 or b < 0:
            raise ValidationError(f"job type incompatibility ({a}, {b}) has a negative type")
        if a == b:
            raise ValidationError(
                f"job type incompatibility ({a}, {b}) must reference two distinct types",
            )
        incompatible.add(frozenset((a, b)))

    for pd in model._pickup_deliveries:
        pu = pd.pickup_job_node_id
        dl = pd.delivery_job_node_id
        ta = model._nodes[pu].as_job().job_type
        tb = model._nodes[dl].as_job().job_type
        if ta is not None and tb is not None and frozenset((ta, tb)) in incompatible:
            raise ValidationError(
                f"pickup {job_tag(model, pu)} and delivery {job_tag(model, dl)} have "
                f"incompatible job types ({ta}, {tb})",
            )
