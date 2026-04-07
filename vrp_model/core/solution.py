"""Standard solution format shared by all solvers."""

from __future__ import annotations

from dataclasses import dataclass, field

from vrp_model.core.views import Depot, Job, Vehicle


@dataclass
class Route:
    """One vehicle path: depots and ordered job visits."""

    vehicle: Vehicle
    start_depot: Depot
    end_depot: Depot
    jobs: list[Job]


@dataclass
class Solution:
    """Feasible or infeasible incumbent: routes only.

    Objective value and feasibility are queried on :class:`~vrp_model.core.model.Model`
    (e.g. :meth:`~vrp_model.core.model.Model.solution_cost`,
    :meth:`~vrp_model.core.model.Model.is_solution_feasible`). Solver-reported cost lives on
    :class:`~vrp_model.solvers.status.SolutionStatus`.
    """

    routes: list[Route] = field(default_factory=list)
