"""Layer 2: indices and references are internally consistent."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, cast

from vrp_model.core.errors import ValidationError
from vrp_model.core.kinds import NodeKind
from vrp_model.core.travel_edges import TravelEdgeAttrs, parse_travel_edges

if TYPE_CHECKING:
    from vrp_model.core.model import Model


def validate(model: Model) -> None:
    n_nodes = len(model._nodes)

    for vi, v in enumerate(model._vehicles):
        tag = _vehicle_tag(model, vi)
        sd = v["start_depot_node_id"]
        if sd < 0 or sd >= n_nodes or model._nodes[sd]["kind"] != NodeKind.DEPOT:
            raise ValidationError(f"vehicle {tag} has invalid start_depot node id")
        end_nid = v["end_depot_node_id"]
        if end_nid is not None and (
            end_nid < 0 or end_nid >= n_nodes or model._nodes[end_nid]["kind"] != NodeKind.DEPOT
        ):
            raise ValidationError(f"vehicle {tag} has invalid end_depot node id")

    pickup_ids = {pd["pickup_job_node_id"] for pd in model._pickup_deliveries}
    delivery_ids = {pd["delivery_job_node_id"] for pd in model._pickup_deliveries}
    overlap = pickup_ids & delivery_ids
    if overlap:
        bad = next(iter(overlap))
        raise ValidationError(
            f"job node id {bad} cannot be both pickup and delivery in pickup_delivery pairs",
        )

    seen_pairs: set[tuple[int, int]] = set()
    for pd in model._pickup_deliveries:
        pickup = pd["pickup_job_node_id"]
        delivery = pd["delivery_job_node_id"]
        if pickup < 0 or pickup >= n_nodes or model._nodes[pickup]["kind"] != NodeKind.JOB:
            raise ValidationError(f"pickup_delivery references invalid pickup job node id {pickup}")
        if delivery < 0 or delivery >= n_nodes or model._nodes[delivery]["kind"] != NodeKind.JOB:
            raise ValidationError(
                f"pickup_delivery references invalid delivery job node id {delivery}",
            )
        if pickup == delivery:
            raise ValidationError("pickup and delivery jobs must differ")
        key = (pickup, delivery)
        if key in seen_pairs:
            raise ValidationError(f"duplicate pickup_delivery pair {pickup} -> {delivery}")
        seen_pairs.add(key)

    if model._travel_edges:
        normalized = parse_travel_edges(len(model._nodes), model._travel_edges)
        model._travel_edges = cast(
            dict[tuple[int, int], TravelEdgeAttrs | Mapping[str, int]],
            normalized,
        )


def _vehicle_tag(model: Model, vi: int) -> str:
    lab = model._vehicles[vi]["label"]
    return lab if lab is not None else f"vehicle_{vi}"
