"""Job group (mutually exclusive jobs) checks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vrp_model.core.errors import ValidationError
from vrp_model.core.kinds import NodeKind
from vrp_model.validation.tags import job_tag

if TYPE_CHECKING:
    from vrp_model.core.model import Model


def validate(model: Model) -> None:
    """Disjoint job groups, valid members, no per-job prize, no pickup–delivery endpoints (v1)."""
    n_nodes = len(model._nodes)
    seen: set[int] = set()
    pd_jobs: set[int] = set()
    for pd in model._pickup_deliveries:
        pd_jobs.add(pd.pickup_job_node_id)
        pd_jobs.add(pd.delivery_job_node_id)

    for gi, g in enumerate(model._job_groups):
        members = g.member_job_node_ids
        if len(members) < 2:
            raise ValidationError(f"job group {gi} must contain at least two job node ids")
        for mid in members:
            if mid < 0 or mid >= n_nodes or model._nodes[mid].kind != NodeKind.JOB:
                raise ValidationError(f"job group {gi} references invalid job node id {mid}")
            if mid in seen:
                raise ValidationError(
                    f"job {job_tag(model, mid)} appears in more than one job group",
                )
            seen.add(mid)
            jr = model._nodes[mid].as_job()
            if jr.prize is not None:
                raise ValidationError(
                    f"job {job_tag(model, mid)} has prize set but belongs to a job group; "
                    "use skip_penalty on the group for optional groups",
                )
            if mid in pd_jobs:
                raise ValidationError(
                    f"job {job_tag(model, mid)} is part of pickup_delivery and cannot be in a "
                    "job group",
                )
        if g.skip_penalty is not None and g.skip_penalty < 0:
            raise ValidationError(f"job group {gi} skip_penalty must be non-negative when set")
