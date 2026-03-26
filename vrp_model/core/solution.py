"""Standard solution format shared by all solvers."""

from __future__ import annotations

from dataclasses import dataclass, field

from vrp_model.core.views import Depot, Job, Vehicle


@dataclass
class Route:
    vehicle: Vehicle
    start_depot: Depot
    end_depot: Depot
    jobs: list[Job]


@dataclass
class Solution:
    routes: list[Route] = field(default_factory=list)
    cost: float = 0.0
    feasible: bool = True
    unassigned: list[Job] = field(default_factory=list)
